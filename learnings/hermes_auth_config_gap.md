# Hermes vs MimirAether — Auth/Config 架构对比

> 学习日期: 2026-04-29  
> 学习小节: 第5小节 — Auth和Config架构对比  
> 状态: 完成

---

## 1. Hermes设计亮点

### 亮点1: 多Provider统一注册表（22个Provider）

Hermes使用 `ProviderConfig` dataclass 统一描述所有推理提供商，支持4种认证类型：

```python
@dataclass
class ProviderConfig:
    id: str              # "nous", "gemini", "anthropic"...
    name: str            # 人类可读名称
    auth_type: str       # "oauth_device_code" | "oauth_external" | "api_key" | "external_process"
    portal_base_url: str
    inference_base_url: str
    client_id: str
    scope: str
    api_key_env_vars: tuple  # 优先级排序的环境变量列表
    base_url_env_var: str
```

**22个已注册Provider**: nous, openai-codex, qwen-oauth, copilot, copilot-acp, gemini, zai, kimi-coding, kimi-coding-cn, arcee, minimax, anthropic, alibaba, minimax-cn, deepseek, xai, ai-gateway, opencode-zen, opencode-go, kilocode, huggingface, xiaomi

每个Provider自动解析凭证来源（env vars优先级链），无需手动指定。

### 亮点2: 智能Endpoint自动探测

**Z.AI 4端点自动探测**: 在API Key首次使用时，自动向4个候选端点（global/cn/coding-global/coding-cn）发送测试请求，选择第一个返回200的端点，并将结果按key hash缓存到auth.json，后续启动直接使用缓存。

```python
def detect_zai_endpoint(api_key: str, timeout: float = 8.0) -> Optional[Dict[str, str]]:
    for ep_id, base_url, model, label in ZAI_ENDPOINTS:
        # 探测4个端点，选择可用的
```

**Kimi Key前缀自动路由**: 检测 `sk-kimi-` 前缀的Key，自动路由到 `api.kimi.com/coding/v1`（Kimi Code API），传统key保持 `api.moonshot.ai/v1`。

### 亮点3: 完整OAuth 2.0/2.1设备码流程

实现了工业级的多OAuth Provider支持：
- **Nous Portal**: 标准设备码流程 (device_code → polling → access_token → mint_agent_key)
- **OpenAI Codex**: 外部OAuth流程 (读取~/.codex/auth.json，自动同步refresh token旋转)
- **Qwen OAuth**: 读取~/.qwen/oauth_creds.json，免API Key
- 跨进程token同步：当Codex CLI或其他Hermes实例刷新token时，自动检测并同步新token

### 亮点4: 凭证池（CredentialPool）与多策略Failover

```python
class CredentialPool:
    """Same-provider multi-credential failover."""
    strategies = ["fill_first", "round_robin", "random", "least_used"]
    
    # 核心功能
    - replace_entry()      # 原地替换凭证（刷新token后保持顺序）
    - _mark_exhausted()    # 标记耗尽 + 冷却计时
    - _sync_anthropic_entry_from_credentials_file()  # 外部token变更同步
    - _sync_codex_entry_from_cli()                   # Codex CLI token同步
    - 租约管理（_active_leases）防止单凭证过载
```

支持：
- 4种选择策略
- 凭证耗尽检测（区分429/402错误码）
- 自动冷却恢复（解析Retry-After / quotaResetDelay）
- 跨进程凭证状态同步

### 亮点5: 配置版本管理与自动迁移

```python
DEFAULT_CONFIG["_config_version"] = 17  # 当前版本

def check_config_version() -> Tuple[int, int]:  # → (current, latest)
def migrate_config(interactive=True) -> Dict[str, Any]:  # 无需用户干预升级
def validate_config_structure(config) -> List[ConfigIssue]:  # 结构化验证
```

config.yaml 内置版本号，Hermes启动时自动检测版本差异，执行迁移脚本将旧格式转为新格式，用户零感知。

---

## 2. MimirAether差距列表

### P0 — 阻断级（必须立即修复）

| 差距 | 描述 | Hermes代码量 | MimirAether代码量 |
|------|------|-------------|-------------------|
| **P0-1: Auth模块仅为存根** | PROVIDER_REGISTRY为空，无任何真实provider实现。22个provider全部缺失。 | 3270行 | 184行（94%缺失） |
| **P0-2: 无OAuth流程** | 缺少设备码流程、token轮询、刷新、mint_agent_key等全部OAuth逻辑 | 完整实现 | 0行 |
| **P0-3: 凭证池无同步机制** | CredentialPool缺少与外部CLI（Codex/Qwen/Anthropic）的token同步 | 3个同步函数 | 0个 |

**修复建议**:
1. P0-1: 从Hermes移植 `PROVIDER_REGISTRY` 和 `ProviderConfig`，至少包含 nous/openai-codex/gemini/anthropic/deepseek 5个provider
2. P0-2: 实现 `_request_device_code()` + `_poll_for_token()` + `_refresh_access_token()` 三个核心函数
3. P0-3: 在CredentialPool中添加 `_sync_codex_entry_from_cli()` 和对应的Anthropic同步

### P1 — 高优先级（影响用户体验）

| 差距 | 描述 |
|------|------|
| **P1-1: 无Endpoint自动探测** | Z.AI 4端点探测和Kimi前缀路由全缺失。用户必须手动指定base_url |
| **P1-2: 无跨进程文件锁** | auth.json读写无 `fcntl.LOCK_EX` 保护，多进程并发可能损坏认证状态 |
| **P1-3: 无配置版本迁移** | config.py有迁移框架但未激活（copy自Hermes），用户升级后配置不兼容 |
| **P1-4: 无Copilot Auth** | `copilot_auth.py` 已就绪，但 `PROVIDER_REGISTRY` 中未注册 copilot provider |

**修复建议**:
1. P1-1: 移植 `detect_zai_endpoint()` 和 `_resolve_kimi_base_url()`
2. P1-2: 在 `_save_auth_store()` 中添加 `fcntl.LOCK_EX` + 超时
3. P1-3: 在启动流程中调用 `check_config_version()` + `migrate_config()`
4. P1-4: 在PROVIDER_REGISTRY中添加copilot条目，连接已有的copilot_auth

### P2 — 中优先级（功能完善）

| 差距 | 描述 |
|------|------|
| **P2-1: 无占位符检测** | Hermes在加载凭证时检查 `_PLACEHOLDER_SECRET_VALUES`（"changeme", "your_api_key"等），MimirAether无此保护 |
| **P2-2: 无Auxiliary Model配置** | Hermes为vision/web_extract/compression等任务独立配置模型，MimirAether所有任务共享一个模型 |
| **P2-3: llm_config.yaml硬编码API Key** | `mimicore/config/llm_config.yaml` 中硬编码了MiniMax的API Key（安全隐患） |
| **P2-4: 无凭证耗尽冷却** | CredentialPool有mark_exhausted但缺TTL解析逻辑（Retry-After header / quotaResetDelay） |

**修复建议**:
1. P2-1: 在 `has_usable_secret()` 中添加占位符检测列表
2. P2-2: 在DEFAULT_CONFIG中添加 `auxiliary` 节（参考Hermes config.py L703-793）
3. P2-3: 从 `llm_config.yaml` 移除API Key，改为从 `.env` 读取
4. P2-4: 移植 `_parse_absolute_timestamp()` 和 `_extract_retry_delay_seconds()`

### P3 — 低优先级（锦上添花）

| 差距 | 描述 |
|------|------|
| **P3-1: 无NixOS Managed Mode** | Hermes支持NixOS声明式配置管理（`HERMES_MANAGED` env var），MimirAether虽有代码但未适配OpenClaw |
| **P3-2: 无Container-aware CLI** | Hermes检测 `.container-mode` 文件并自动exec进入容器（NixOS容器化部署） |
| **P3-3: 未适配Gateway多平台** | MimirAether gateway配置中platform支持较Hermes少（缺少DingTalk/Feishu/WeCom等10+平台） |
| **P3-4: 无配密钥脱敏显示** | Hermes的 `redact_key()` 和 `display.redact_secrets` 配置，在MimirAether中未激活 |

---

## 3. 修复优先级路线图

```
Phase 1 (本周): P0修复
  ├── P0-1: 移植PROVIDER_REGISTRY (5个核心provider)
  ├── P0-2: 实现OAuth设备码流程基础版
  └── P0-3: CredentialPool外部同步

Phase 2 (下周): P1修复
  ├── P1-1: Endpoint自动探测
  ├── P1-2: 跨进程文件锁
  ├── P1-3: 配置版本迁移激活
  └── P1-4: Copilot Provider注册

Phase 3 (2周内): P2修复
  ├── P2-1: 占位符检测
  ├── P2-2: Auxiliary Model配置
  ├── P2-3: 移除硬编码API Key
  └── P2-4: 凭证耗尽TTL解析

Phase 4 (后续): P3修复
  └── P3-1~P3-4: 按需实现
```

---

## 4. 代码量统计

| 模块 | Hermes | MimirAether | 差距 |
|------|--------|-------------|------|
| auth.py | 3,270行 | 184行 | -94.4% |
| config.py | 3,306行 | 3,309行 | ≈等同(copy) |
| gateway/config.py | 1,125行 | 1,139行 | ≈等同(adapted) |
| tools/credential_files.py | 407行 | 428行 | ≈等同 |
| tools/mcp_oauth.py | 338行 | ~338行 | ≈等同 |
| agent/credential_pool.py | 1,363行 | 2,202行 | +61.6% (自研增强) |
| **合计** | **9,809行** | **7,600行** | **-22.5%** |

> 注意：MimirAether credential_pool.py 虽然行数更多，但是自研简化版，缺少外部同步等关键功能。真正的差距在 auth.py，这是一个"空心化"问题——MimirAether有完整的config/copy框架，但核心auth逻辑全部缺失。
