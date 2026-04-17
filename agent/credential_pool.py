"""
MimirAether Credential Pool

简化版凭证池管理，支持多凭证Failover。

学习自Hermes credential_pool设计思路：
- 凭证池管理
- 多策略选择
- 状态追踪（ok/exhausted）
- 租约管理

核心原则：
- 不复制Hermes特定模块依赖
- 简化实现，专注核心功能
- 支持多provider
"""

import json
import logging
import os
import random
import threading
import time
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# ============================================================================
# 常量
# ============================================================================

STATUS_OK = "ok"
STATUS_EXHAUSTED = "exhausted"

AUTH_TYPE_API_KEY = "api_key"
AUTH_TYPE_OAUTH = "oauth"

SOURCE_MANUAL = "manual"

# 选择策略
STRATEGY_FILL_FIRST = "fill_first"
STRATEGY_ROUND_ROBIN = "round_robin"
STRATEGY_RANDOM = "random"
STRATEGY_LEAST_USED = "least_used"

SUPPORTED_STRATEGIES = {
    STRATEGY_FILL_FIRST,
    STRATEGY_ROUND_ROBIN,
    STRATEGY_RANDOM,
    STRATEGY_LEAST_USED,
}

# 耗尽冷却时间（秒）
EXHAUSTED_TTL_429 = 3600  # 1小时
EXHAUSTED_TTL_DEFAULT = 3600  # 1小时

# 凭证文件路径
DEFAULT_CREDENTIALS_DIR = Path.home() / ".openclaw" / "credentials"
CREDENTIAL_POOL_FILE = "credential_pool.json"

# ============================================================================
# 数据类
# ============================================================================

@dataclass
class PooledCredential:
    """池化凭证"""
    provider: str
    id: str
    label: str
    auth_type: str = AUTH_TYPE_API_KEY
    priority: int = 0
    source: str = SOURCE_MANUAL
    access_token: str = ""
    refresh_token: Optional[str] = None
    last_status: Optional[str] = STATUS_OK
    last_status_at: Optional[float] = None
    last_error_code: Optional[int] = None
    last_error_reason: Optional[str] = None
    last_error_message: Optional[str] = None
    last_error_reset_at: Optional[float] = None
    base_url: Optional[str] = None
    expires_at: Optional[str] = None
    expires_at_ms: Optional[int] = None
    request_count: int = 0
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, provider: str, payload: Dict[str, Any]) -> "PooledCredential":
        """从字典创建凭证"""
        known_fields = {
            "id", "label", "auth_type", "priority", "source",
            "access_token", "refresh_token", "last_status", "last_status_at",
            "last_error_code", "last_error_reason", "last_error_message",
            "last_error_reset_at", "base_url", "expires_at", "expires_at_ms",
            "request_count",
        }
        data = {k: payload.get(k) for k in known_fields if k in payload}
        data.setdefault("id", uuid.uuid4().hex[:6])
        data.setdefault("label", payload.get("source", provider))
        data.setdefault("auth_type", AUTH_TYPE_API_KEY)
        data.setdefault("priority", 0)
        data.setdefault("source", SOURCE_MANUAL)
        data.setdefault("access_token", "")
        data.setdefault("request_count", 0)
        data["extra"] = {k: v for k, v in payload.items() if k not in known_fields and v is not None}
        return cls(provider=provider, **data)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        always_emit = {
            "last_status", "last_status_at", "last_error_code",
            "last_error_reason", "last_error_message", "last_error_reset_at",
        }
        result = {}
        for key in ("provider", "id", "label", "auth_type", "priority", "source",
                    "access_token", "refresh_token", "last_status", "last_status_at",
                    "last_error_code", "last_error_reason", "last_error_message",
                    "last_error_reset_at", "base_url", "expires_at", "expires_at_ms",
                    "request_count"):
            value = getattr(self, key, None)
            if value is not None or key in always_emit:
                result[key] = value
        if self.extra:
            result.update(self.extra)
        return result

    @property
    def runtime_api_key(self) -> str:
        """运行时API Key"""
        return str(self.access_token or "")

    def is_expired(self) -> bool:
        """检查是否过期"""
        if self.expires_at_ms is None:
            return False
        return int(time.time() * 1000) >= self.expires_at_ms

    def needs_refresh(self) -> bool:
        """检查是否需要刷新"""
        if self.auth_type != AUTH_TYPE_OAUTH:
            return False
        if not self.refresh_token:
            return False
        # 提前2分钟刷新
        if self.expires_at_ms:
            return int(time.time() * 1000) >= (self.expires_at_ms - 120_000)
        return False


# ============================================================================
# 工具函数
# ============================================================================

def _exhausted_ttl(error_code: Optional[int]) -> int:
    """根据错误码返回冷却时间"""
    if error_code == 429:
        return EXHAUSTED_TTL_429
    return EXHAUSTED_TTL_DEFAULT


def _parse_timestamp(value: Any) -> Optional[float]:
    """解析时间戳（支持秒、毫秒、ISO-8601）"""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        numeric = float(value)
        if numeric <= 0:
            return None
        # 毫秒检测
        return numeric / 1000.0 if numeric > 1_000_000_000_000 else numeric
    if isinstance(value, str):
        try:
            numeric = float(value.strip())
            return numeric / 1000.0 if numeric > 1_000_000_000_000 else numeric
        except ValueError:
            pass
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None
    return None


def _exhausted_until(entry: PooledCredential) -> Optional[float]:
    """获取耗尽截止时间"""
    if entry.last_status != STATUS_EXHAUSTED:
        return None
    reset_at = _parse_timestamp(getattr(entry, "last_error_reset_at", None))
    if reset_at is not None:
        return reset_at
    if entry.last_status_at:
        return entry.last_status_at + _exhausted_ttl(entry.last_error_code)
    return None


def _next_priority(entries: List[PooledCredential]) -> int:
    """生成下一个优先级"""
    return max((entry.priority for entry in entries), default=-1) + 1


# ============================================================================
# 凭证池
# ============================================================================

class CredentialPool:
    """
    凭证池管理器
    
    支持：
    - 多凭证存储
    - 多种选择策略
    - 状态追踪（ok/exhausted）
    - 租约管理
    - 持久化
    """
    
    def __init__(
        self,
        provider: str,
        entries: Optional[List[PooledCredential]] = None,
        strategy: str = STRATEGY_FILL_FIRST,
    ):
        self.provider = provider
        self._entries = sorted(entries or [], key=lambda e: e.priority)
        self._strategy = strategy if strategy in SUPPORTED_STRATEGIES else STRATEGY_FILL_FIRST
        self._current_id: Optional[str] = None
        self._lock = threading.Lock()
        self._active_leases: Dict[str, int] = {}
        self._max_concurrent = 1  # 默认每个凭证同时只能有一个租约
        self._round_robin_index = 0
    
    @property
    def strategy(self) -> str:
        return self._strategy
    
    @property
    def entries(self) -> List[PooledCredential]:
        return list(self._entries)
    
    def has_credentials(self) -> bool:
        """是否有凭证"""
        return bool(self._entries)
    
    def has_available(self) -> bool:
        """是否有可用凭证（不在冷却中）"""
        return bool(self._available_entries())
    
    def current(self) -> Optional[PooledCredential]:
        """获取当前选中的凭证"""
        if not self._current_id:
            return None
        return next((e for e in self._entries if e.id == self._current_id), None)
    
    def _persist(self) -> None:
        """持久化到磁盘"""
        try:
            DEFAULT_CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
            # 每个provider一个子目录
            provider_dir = DEFAULT_CREDENTIALS_DIR / self.provider
            provider_dir.mkdir(parents=True, exist_ok=True)
            filepath = provider_dir / CREDENTIAL_POOL_FILE
            data = [entry.to_dict() for entry in self._entries]
            filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False))
            logger.debug(f"Credential pool persisted: {self.provider}")
        except Exception as e:
            logger.warning(f"Failed to persist credential pool: {e}")
    
    def _replace_entry(self, old: PooledCredential, new: PooledCredential) -> None:
        """替换凭证"""
        for idx, entry in enumerate(self._entries):
            if entry.id == old.id:
                self._entries[idx] = new
                return
    
    def _available_entries(self, *, clear_expired: bool = False) -> List[PooledCredential]:
        """获取可用凭证列表"""
        now = time.time()
        available = []
        cleared_any = False
        
        for entry in self._entries:
            # 检查耗尽状态
            if entry.last_status == STATUS_EXHAUSTED:
                exhausted_until = _exhausted_until(entry)
                if exhausted_until is not None and now < exhausted_until:
                    continue
                # 冷却期已过，清除耗尽状态
                if clear_expired:
                    cleared = replace(
                        entry,
                        last_status=STATUS_OK,
                        last_status_at=None,
                        last_error_code=None,
                        last_error_reason=None,
                        last_error_message=None,
                        last_error_reset_at=None,
                    )
                    self._replace_entry(entry, cleared)
                    entry = cleared
                    cleared_any = True
            available.append(entry)
        
        if cleared_any:
            self._persist()
        
        return available
    
    def _select_unlocked(self) -> Optional[PooledCredential]:
        """非线程安全的选择逻辑"""
        available = self._available_entries(clear_expired=True)
        if not available:
            self._current_id = None
            logger.info(f"Credential pool [{self.provider}]: no available entries")
            return None
        
        # 根据策略选择
        if self._strategy == STRATEGY_RANDOM:
            entry = random.choice(available)
            self._current_id = entry.id
            return entry
        
        if self._strategy == STRATEGY_LEAST_USED and len(available) > 1:
            entry = min(available, key=lambda e: e.request_count)
            self._current_id = entry.id
            return entry
        
        if self._strategy == STRATEGY_ROUND_ROBIN and len(available) > 1:
            self._round_robin_index = (self._round_robin_index + 1) % len(available)
            entry = available[self._round_robin_index]
            self._current_id = entry.id
            return entry
        
        # 默认fill_first
        entry = available[0]
        self._current_id = entry.id
        return entry
    
    def select(self) -> Optional[PooledCredential]:
        """选择凭证"""
        with self._lock:
            return self._select_unlocked()
    
    def peek(self) -> Optional[PooledCredential]:
        """查看可用凭证（不选中）"""
        with self._lock:
            current = self.current()
            if current is not None:
                return current
            available = self._available_entries()
            return available[0] if available else None
    
    def mark_exhausted(
        self,
        entry: Optional[PooledCredential] = None,
        status_code: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """标记凭证为耗尽状态"""
        with self._lock:
            target = entry or self.current()
            if target is None:
                return
            
            updated = replace(
                target,
                last_status=STATUS_EXHAUSTED,
                last_status_at=time.time(),
                last_error_code=status_code,
                last_error_message=error_message,
            )
            self._replace_entry(target, updated)
            self._persist()
            
            if self._current_id == target.id:
                self._current_id = None
                # 自动轮换到下一个
                self._select_unlocked()
            
            logger.info(f"Credential [{target.label}] marked exhausted: {error_message}")
    
    def try_refresh_current(self) -> Optional[PooledCredential]:
        """"尝试刷新当前凭证（Hermes 1:1学习）"""
        with self._lock:
            return self._try_refresh_current_unlocked()
    
    def _try_refresh_current_unlocked(self) -> Optional[PooledCredential]:
        """刷新当前凭证（内部版本，需要调用者持有锁）"""
        entry = self.current()
        if entry is None:
            return None
        refreshed = self._refresh_entry(entry, force=True)
        if refreshed is not None:
            self._current_id = refreshed.id
        return refreshed
    
    def _refresh_entry(self, entry: PooledCredential, force: bool = False) -> Optional[PooledCredential]:
        """刷新单个凭证（Hermes 1:1学习）"""
        # 如果凭证支持refresh_token，尝试刷新
        if entry.refresh_token and (force or self._entry_needs_refresh(entry)):
            try:
                logger.info(f"Refreshing credential {entry.id}")
                
                # 根据provider类型调用不同的刷新逻辑
                if entry.provider == "anthropic":
                    # 使用anthropic_adapter的OAuth刷新
                    from anthropic_adapter import refresh_anthropic_oauth
                    result = refresh_anthropic_oauth(entry.refresh_token)
                    if result and "access_token" in result:
                        # 创建新的PooledCredential
                        refreshed = PooledCredential(
                            provider=entry.provider,
                            id=entry.id,
                            label=entry.label,
                            auth_type=entry.auth_type,
                            access_token=result["access_token"],
                            refresh_token=result.get("refresh_token", entry.refresh_token),
                            expires_at=result.get("expires_at"),
                        )
                        return refreshed
                else:
                    # 其他Provider暂不支持刷新
                    logger.debug(f"Refresh not implemented for provider: {entry.provider}")
                
                return None
            except Exception as e:
                logger.warning(f"Failed to refresh credential {entry.id}: {e}")
                return None
        return None
    
    def _entry_needs_refresh(self, entry: PooledCredential) -> bool:
        """检查凭证是否需要刷新（Hermes 1:1学习）"""
        if not entry.refresh_token:
            return False
        # 检查是否过期（基于expires_at或last_refresh）
        if entry.expires_at:
            try:
                from datetime import datetime
                expires = datetime.fromisoformat(entry.expires_at.replace('Z', '+00:00'))
                return datetime.now() >= expires
            except:
                pass
        return False
    
    def _load_config_safe(self) -> Optional[dict]:
        """安全加载配置文件（Hermes 1:1学习）"""
        try:
            # 尝试加载MimirAether配置
            config_path = Path.home() / ".openclaw" / "config.json"
            if config_path.exists():
                import json
                with open(config_path) as f:
                    return json.load(f)
        except Exception:
            pass
        return None
    
    def _seed_from_env(self) -> None:
        """从环境变量加载凭证（Hermes 1:1学习）"""
        # 支持的环境变量
        env_keys = [
            "DEEPSEEK_API_KEY",
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "MOONSHOT_API_KEY",
        ]
        for key in env_keys:
            value = os.environ.get(key)
            if value:
                provider = key.replace("_API_KEY", "").lower()
                entry = PooledCredential(
                    provider=provider,
                    id=f"env_{key.lower()}",
                    label=f"{provider} from env",
                    auth_type="api_key",
                    priority=50,
                    source="env",
                    access_token=value,
                )
                self._entries.append(entry)
                logger.info(f"Loaded {provider} credential from environment")
    
    def mark_exhausted_and_rotate(self, status_code: int = None, error_context: dict = None) -> Optional[PooledCredential]:
        """标记当前凭证耗尽并轮换到下一个（Hermes 1:1学习）"""
        with self._lock:
            entry = self.current()
            if entry:
                self._mark_exhausted(entry, status_code, error_context)
            # 选择下一个可用凭证
            return self._select_unlocked()
    
    def _mark_exhausted(self, entry: PooledCredential, status_code: int = None, error_context: dict = None) -> None:
        """内部方法：标记凭证为耗尽（Hermes 1:1学习）"""
        from dataclasses import replace
        updated = replace(
            entry,
            last_status=STATUS_EXHAUSTED,
            last_status_at=time.time(),
            last_error_code=status_code,
            last_error_message=error_context.get("message") if error_context else None,
        )
        # 替换entries中的凭证
        for i, e in enumerate(self._entries):
            if e.id == entry.id:
                self._entries[i] = updated
                break
        if self._current_id == entry.id:
            self._current_id = None
    
    def _upsert_entry(self, source: str, payload: dict) -> bool:
        """插入或更新凭证（Hermes 1:1学习）"""
        # 查找是否存在
        for i, entry in enumerate(self._entries):
            if entry.source == source:
                # 更新
                from dataclasses import replace
                self._entries[i] = replace(self._entries[i], **payload)
                return True
        # 插入新凭证
        entry = PooledCredential(
            provider=self.provider,
            id=payload.get("id", uuid.uuid4().hex[:6]),
            label=payload.get("label", source),
            auth_type=payload.get("auth_type", "api_key"),
            priority=payload.get("priority", 50),
            source=source,
            access_token=payload.get("access_token", ""),
        )
        self._entries.append(entry)
        return True
    
    def mark_ok(self, entry: Optional[PooledCredential] = None) -> None:
        """标记凭证为正常状态"""
        with self._lock:
            target = entry or self.current()
            if target is None:
                return
            
            updated = replace(
                target,
                last_status=STATUS_OK,
                last_status_at=None,
                last_error_code=None,
                last_error_reason=None,
                last_error_message=None,
                last_error_reset_at=None,
            )
            self._replace_entry(target, updated)
            self._persist()
    
    def increment_request_count(self, entry: Optional[PooledCredential] = None) -> None:
        """增加请求计数"""
        with self._lock:
            target = entry or self.current()
            if target is None:
                return
            updated = replace(target, request_count=target.request_count + 1)
            self._replace_entry(target, updated)
            # 不立即持久化，避免频繁写入
    
    def acquire_lease(self, credential_id: Optional[str] = None) -> Optional[str]:
        """
        获取凭证租约
        
        Args:
            credential_id: 指定凭证ID，或None自动选择
            
        Returns:
            租约ID或None
        """
        with self._lock:
            if credential_id:
                # 指定的凭证
                for entry in self._entries:
                    if entry.id == credential_id:
                        self._active_leases[credential_id] = self._active_leases.get(credential_id, 0) + 1
                        self._current_id = credential_id
                        return credential_id
                return None
            
            # 自动选择最少使用的
            available = self._available_entries(clear_expired=True)
            if not available:
                return None
            
            # 找未达上限的
            below_cap = [
                e for e in available
                if self._active_leases.get(e.id, 0) < self._max_concurrent
            ]
            candidates = below_cap if below_cap else available
            
            # 选择请求数最少的
            chosen = min(candidates, key=lambda e: (self._active_leases.get(e.id, 0), e.priority))
            self._active_leases[chosen.id] = self._active_leases.get(chosen.id, 0) + 1
            self._current_id = chosen.id
            return chosen.id
    
    def release_lease(self, credential_id: str) -> None:
        """释放租约"""
        with self._lock:
            count = self._active_leases.get(credential_id, 0)
            if count <= 1:
                self._active_leases.pop(credential_id, None)
            else:
                self._active_leases[credential_id] = count - 1
    
    def add_entry(self, entry: PooledCredential) -> PooledCredential:
        """添加凭证到池"""
        with self._lock:
            # 生成新优先级
            new_priority = _next_priority(self._entries)
            new_entry = replace(entry, priority=new_priority)
            self._entries.append(new_entry)
            self._entries.sort(key=lambda e: e.priority)
            self._persist()
            return new_entry
    
    def remove_entry(self, entry_id: str) -> bool:
        """从池中移除凭证"""
        with self._lock:
            for idx, entry in enumerate(self._entries):
                if entry.id == entry_id:
                    self._entries.pop(idx)
                    if self._current_id == entry_id:
                        self._current_id = None
                    self._persist()
                    return True
            return False
    
    def reset_all_statuses(self) -> int:
        """重置所有凭证状态"""
        with self._lock:
            count = 0
            new_entries = []
            for entry in self._entries:
                if entry.last_status or entry.last_error_code:
                    new_entries.append(replace(
                        entry,
                        last_status=STATUS_OK,
                        last_status_at=None,
                        last_error_code=None,
                        last_error_reason=None,
                        last_error_message=None,
                        last_error_reset_at=None,
                    ))
                    count += 1
                else:
                    new_entries.append(entry)
            if count:
                self._entries = new_entries
                self._persist()
            return count
    
    def set_strategy(self, strategy: str) -> bool:
        """设置选择策略"""
        if strategy not in SUPPORTED_STRATEGIES:
            return False
        with self._lock:
            self._strategy = strategy
        return True


# ============================================================================
# 池注册表
# ============================================================================

class CredentialPoolRegistry:
    """
    凭证池注册表
    
    管理所有provider的凭证池
    """
    
    _instance: Optional["CredentialPoolRegistry"] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._pools: Dict[str, CredentialPool] = {}
                    cls._instance._pools_lock = threading.Lock()
        return cls._instance
    
    def get_pool(self, provider: str) -> Optional[CredentialPool]:
        """获取provider的凭证池"""
        with self._pools_lock:
            return self._pools.get(provider)
    
    def create_pool(
        self,
        provider: str,
        entries: Optional[List[PooledCredential]] = None,
        strategy: str = STRATEGY_FILL_FIRST,
    ) -> CredentialPool:
        """创建或获取凭证池"""
        with self._pools_lock:
            if provider in self._pools:
                return self._pools[provider]
            pool = CredentialPool(provider, entries, strategy)
            self._pools[provider] = pool
            return pool
    
    def remove_pool(self, provider: str) -> bool:
        """移除凭证池"""
        with self._pools_lock:
            if provider in self._pools:
                del self._pools[provider]
                return True
            return False
    
    def list_providers(self) -> List[str]:
        """列出所有provider"""
        with self._pools_lock:
            return list(self._pools.keys())


# ============================================================================
# 便捷函数
# ============================================================================

def get_default_registry() -> CredentialPoolRegistry:
    """获取默认注册表实例"""
    return CredentialPoolRegistry()


def create_credential(
    provider: str,
    api_key: str,
    label: Optional[str] = None,
    base_url: Optional[str] = None,
) -> PooledCredential:
    """创建新凭证"""
    return PooledCredential(
        provider=provider,
        id=uuid.uuid4().hex[:6],
        label=label or f"{provider} credential",
        auth_type=AUTH_TYPE_API_KEY,
        source=SOURCE_MANUAL,
        access_token=api_key,
        base_url=base_url,
    )


def load_pool_from_config(provider: str) -> Optional[CredentialPool]:
    """从环境变量加载凭证池"""
    api_key = os.environ.get(f"{provider.upper()}_API_KEY", "").strip()
    if not api_key:
        # 尝试通用key
        api_key = os.environ.get("API_KEY", "").strip()
    if not api_key:
        return None
    
    entry = create_credential(provider, api_key)
    pool = CredentialPool(provider, [entry])
    return pool


# ============================================================================
# 便捷函数
# ============================================================================

def load_pool(provider: str) -> Optional[CredentialPool]:
    """
    加载指定provider的凭证池。
    
    简化版：直接从环境变量加载单个凭证。
    """
    return load_pool_from_config(provider)


# ============================================================================
# 测试
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    
    print("=" * 60)
    print("MimirAether Credential Pool 测试")
    print("=" * 60)
    
    # 测试1: 创建凭证
    print("\n[测试1] 创建凭证")
    cred1 = create_credential("openai", "sk-key-1", "OpenAI Primary")
    cred2 = create_credential("openai", "sk-key-2", "OpenAI Backup")
    cred3 = create_credential("anthropic", "sk-ant-key-1", "Anthropic Primary")
    print(f"  凭证1: {cred1.id} - {cred1.label}")
    print(f"  凭证2: {cred2.id} - {cred2.label}")
    print(f"  凭证3: {cred3.id} - {cred3.label}")
    
    # 测试2: 创建池
    print("\n[测试2] 创建凭证池")
    pool = CredentialPool("openai", [cred1, cred2], strategy=STRATEGY_FILL_FIRST)
    print(f"  Provider: {pool.provider}")
    print(f"  凭证数: {len(pool.entries)}")
    print(f"  策略: {pool.strategy}")
    
    # 测试3: 选择凭证
    print("\n[测试3] 选择凭证")
    selected = pool.select()
    print(f"  选中: {selected.label if selected else 'None'}")
    
    # 测试4: 标记耗尽
    print("\n[测试4] 标记耗尽")
    pool.mark_exhausted(selected, status_code=429, error_message="Rate limited")
    print(f"  has_available: {pool.has_available()}")
    
    # 测试5: 自动轮换
    print("\n[测试5] 自动轮换")
    selected2 = pool.select()
    print(f"  新选中: {selected2.label if selected2 else 'None'}")
    
    # 测试6: 租约管理
    print("\n[测试6] 租约管理")
    lease_id = pool.acquire_lease()
    print(f"  获取租约: {lease_id}")
    pool.release_lease(lease_id)
    print(f"  释放租约: OK")
    
    # 测试7: 多种策略
    print("\n[测试7] 策略测试")
    strategies = [STRATEGY_FILL_FIRST, STRATEGY_ROUND_ROBIN, STRATEGY_LEAST_USED, STRATEGY_RANDOM]
    for strategy in strategies:
        test_pool = CredentialPool("test", [
            create_credential("test", f"key-{i}", f"Key-{i}") for i in range(3)
        ], strategy=strategy)
        selected = test_pool.select()
        print(f"  {strategy}: 选中 {selected.label if selected else 'None'}")
    
    # 测试8: 凭证池注册表
    print("\n[测试8] 凭证池注册表")
    registry = get_default_registry()
    registry.create_pool("openai", [cred1])
    registry.create_pool("anthropic", [cred3])
    providers = registry.list_providers()
    print(f"  Providers: {providers}")
    
    # 测试9: 凭证状态
    print("\n[测试9] 凭证状态管理")
    test_cred = create_credential("test", "key", "Test")
    print(f"  初始状态: {test_cred.last_status}")
    
    # 模拟请求计数
    for i in range(5):
        test_pool = CredentialPool("test", [test_cred])
        test_pool.select()
        test_pool.increment_request_count()
        test_cred = test_pool.current()
        print(f"  请求后计数: {test_cred.request_count if test_cred else 'N/A'}")
    
    # 测试10: 序列化
    print("\n[测试10] 序列化")
    cred = create_credential("test", "secret-key", "Test Cred", base_url="https://api.test.com")
    serialized = cred.to_dict()
    print(f"  Serialized keys: {list(serialized.keys())}")
    restored = PooledCredential.from_dict("test", serialized)
    print(f"  Restored: {restored.label} - {restored.runtime_api_key}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)