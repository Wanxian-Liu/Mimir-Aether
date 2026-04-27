# 深度自研改造方案 - Hermes残留依赖替换

> 分析日期: 2026-04-27
> QA Lead: 琬弦 (subagent)
> 项目: MimirAether深度自研改造

---

## 一、现状总览

### Hermes特定依赖分布（grep结果统计）

| 依赖 | 出现次数 | 主要文件 |
|------|----------|----------|
| `hermes_cli.auth` | ~30处 | web_server.py, models.py, runtime_provider.py, doctor.py, setup.py, model_switch.py |
| `hermes_state.SessionDB` | 6处 | web_server.py, session.py(注释) |
| `hermes_cli.config` | ~10处 | claw.py, webhook.py, profiles.py |
| `hermes_constants` | ~8处 | claw.py, webhook.py, profiles.py, runtime_provider.py |
| `hermes_cli.gateway` | ~5处 | cron.py, profiles.py |
| `hermes_cli.models` | ~4处 | runtime_provider.py, model_normalize.py |
| `hermes-logging` | 1处 | gateway/run.py |

---

## 二、可替换依赖清单

### | 当前依赖 | 替换为 | 难度 | 涉及文件 | 备注 |
|---------|--------|------|----------|------|
| `hermes_cli.auth.clear_provider_auth` | `agent/credential_pool.py` 或 env直接读取 | P1 | web_server.py | auth.py已是stub，直接用env更简单 |
| `hermes_cli.auth._request_device_code` | 移除（OAuth未实现） | P2 | web_server.py | OAuth flow未在MimirAether实现 |
| `hermes_cli.auth._poll_for_token` | 移除（OAuth未实现） | P2 | web_server.py | 同上 |
| `hermes_cli.auth.refresh_nous_oauth_from_state` | 移除 | P2 | web_server.py | OAuth not implemented |
| `hermes_cli.auth.get_active_provider` | `agent/credential_pool.get_active_provider()` | P1 | setup.py | 需要先实现credential_pool |
| `hermes_cli.auth.get_anthropic_key` | `os.getenv("ANTHROPIC_API_KEY")` | P0 | doctor.py | 简单替换 |
| `hermes_cli.auth.get_nous_auth_status` | `bool(os.getenv("NOUS_API_KEY"))` | P0 | doctor.py | 简单替换 |
| `hermes_cli.auth.get_codex_auth_status` | `bool(os.getenv("OPENAI_API_KEY"))` | P0 | doctor.py | 简单替换 |
| `hermes_cli.auth.resolve_nous_runtime_credentials` | `{"access_token": os.getenv("NOUS_API_KEY")}` | P0 | models.py, runtime_provider.py | 已在auth.py有stub实现 |
| `hermes_cli.auth.get_provider_auth_state` | `os.getenv(f"{provider.upper()}_API_KEY")` | P0 | models.py | auth.py已有此实现 |
| `hermes_cli.auth.has_usable_secret` | 直接内联key检查逻辑 | P0 | models.py | auth.py已有实现 |
| `hermes_cli.auth.PROVIDER_REGISTRY` | `mimicore/config/provider_registry.py` | P1 | models.py, model_switch.py | 需要新建或使用现有config |
| `hermes_cli.auth._load_auth_store` | `agent/credential_pool.py` | P1 | model_switch.py | 需要先实现credential_pool |
| `hermes_state.SessionDB` | `hermes_state.py`(自研SQLite) 或 `mimicore/memory_layer/rl_access.py` | P1 | web_server.py, session.py | hermes_state.py已是MimirAether自研 |
| `hermes_cli.config.get_hermes_home` | `mimiraether_constants.get_mimiraether_home()` | P0 | claw.py, webhook.py, profiles.py | mimiraether_constants.py已存在 |
| `hermes_cli.config.load_config/save_config` | `mimicore/config/` 模块 | P1 | claw.py, webhook.py | OpenClaw已有config系统 |
| `hermes_constants.get_hermes_home` | `mimiraether_constants.get_mimiraether_home()` | P0 | claw.py, profiles.py, logs.py | 已有替代 |
| `hermes_constants.display_hermes_home` | `mimiraether_constants.display_mimiraether_home()` | P1 | logs.py, webhook.py | 需要在constants中添加 |
| `hermes_constants.get_optional_skills_dir` | `AGENTS.md` 或 skill系统 | P1 | profiles.py | OpenClaw skills在 `~/.openclaw/skills/` |
| `hermes_cli.gateway.find_gateway_pids` | `openclaw gateway status` | P1 | cron.py | OpenClaw CLI |
| `hermes_cli.gateway.get_service_name` | OpenClaw service name | P1 | profiles.py | OpenClaw launcher |
| `hermes_cli.models.normalize_provider` | `mimicore/normalizer/` | P1 | runtime_provider.py | 检查mimicore是否有对应 |
| `hermes_cli.models.copilot_model_api_mode` | `mimicore/models.py` | P2 | runtime_provider.py | 需要检查 |
| `hermes_cli.models.opencode_model_api_mode` | `mimicore/models.py` | P2 | runtime_provider.py | 需要检查 |
| `hermes-logging.setup_logging` | `mimiraether_logging.py` | P0 | gateway/run.py | mimiraether_logging.py已存在 |
| `HermesAIAgent` | `mimicore/agent/` 或 OpenClaw agent | P2 | gateway/session.py(注释) | 已是注释状态 |

---

## 三、优先级定义

### P0 - 必须立即（阻断性问题）

**定义**: 系统无法启动或核心功能完全不可用

1. **`hermes-logging.setup_logging`** → `mimiraether_logging.py`
   - 文件: `gateway/run.py:115`
   - 方案: 直接import `mimiraether_logging` 替换

2. **`hermes_constants.get_hermes_home`** → `mimiraether_constants`
   - 文件: `gateway/run.py`, `claw.py`, `profiles.py`
   - 方案: 使用已有 `mimiraether_constants.get_mimiraether_home()`

3. **`hermes_cli.auth.get_anthropic_key`** → `os.getenv()`
   - 文件: `hermes_cli/doctor.py:689`
   - 方案: 直接读取 `ANTHROPIC_API_KEY` 环境变量

4. **`hermes_cli.auth.get_nous_auth_status`** → `os.getenv()`
   - 文件: `hermes_cli/doctor.py:374`
   - 方案: `bool(os.getenv("NOUS_API_KEY"))`

5. **`hermes_cli.auth.get_codex_auth_status`** → `os.getenv()`
   - 文件: `hermes_cli/doctor.py:374`
   - 方案: `bool(os.getenv("OPENAI_API_KEY"))`

6. **`hermes_cli.auth.resolve_nous_runtime_credentials`** → 直接env读取
   - 文件: `hermes_cli/models.py:471,828,1239`
   - 方案: auth.py已有stub实现，env读取即可工作

### P1 - 高优先级（功能受损）

**定义**: 功能可用但不稳定，或有明确替代方案

1. **`hermes_cli.auth` (30处整体)** → OpenClaw credential pool
   - 方案: 建立 `agent/credential_pool.py` 统一credential管理
   - 覆盖: web_server.py, models.py, runtime_provider.py, setup.py, model_switch.py
   - 建议: 渐进替换，先建立pool再用

2. **`hermes_state.SessionDB`** → `hermes_state.py` (已是自研)
   - 文件: `gateway/web_server.py`, `gateway/session.py`
   - 方案: hermes_state.py已是MimirAether自研实现，可直接使用
   - 状态: session.py已注释掉引用，只需在web_server.py中解除

3. **`hermes_cli.config`** → `mimicore/config/`
   - 文件: `claw.py`, `webhook.py`
   - 方案: 检查mimicore/config是否已有完整实现

4. **`hermes_constants.display_hermes_home`** → `mimiraether_constants`
   - 文件: `logs.py`, `webhook.py`, `plugins_cmd.py`
   - 方案: 在mimiraether_constants中添加display函数

5. **`hermes_cli.gateway.find_gateway_pids`** → OpenClaw CLI
   - 文件: `cron.py`
   - 方案: 调用 `openclaw gateway status` 解析PID

### P2 - 中优先级（可延后）

**定义**: 有替代但需要开发工作，不阻断当前功能

1. **`hermes_cli.models`** → `mimicore/normalizer/`
   - 文件: `runtime_provider.py`
   - 方案: 检查mimicore是否已有model normalization

2. **`hermes_cli.auth._request_device_code/_poll_for_token`** → 移除
   - OAuth flow在MimirAether未实现，可以直接移除相关代码路径

3. **`hermes_cli.gateway.get_service_name/get_launchd_plist_path`**
   - macOS launchd特定功能，检查OpenClaw是否需要支持

4. **`HermesAIAgent`**
   - 已是注释状态，确认无引用后可彻底删除

---

## 四、改造执行计划

### Phase 1: P0清理（预计2小时）
```bash
# 1. gateway/run.py - logging替换
grep -n "hermes-logging\|hermes_logging" gateway/run.py

# 2. hermes_cli/doctor.py - auth替换
grep -n "from hermes_cli.auth import" hermes_cli/doctor.py

# 3. 全局hermes_constants替换
grep -rn "from hermes_constants import\|import hermes_constants" hermes_cli/ gateway/
```

### Phase 2: P1清理（预计4小时）
```bash
# 1. 建立credential_pool.py
cat > agent/credential_pool.py << 'EOF'
"""OpenClaw-native credential management."""
import os
from typing import Optional, Dict

def get_active_provider() -> Optional[str]:
    for p in ["openai", "anthropic", "nous", "qwen", "gemini"]:
        if os.getenv(f"{p.upper()}_API_KEY"):
            return p
    return os.getenv("ACTIVE_PROVIDER")

def get_provider_key(provider: str) -> Optional[str]:
    return os.getenv(f"{provider.upper()}_API_KEY") or os.getenv("API_KEY")
EOF

# 2. 替换hermes_cli.auth引用
```

### Phase 3: P2清理（预计持续）
- 模型规范化迁移到mimicore
- OAuth代码路径清理

---

## 五、风险评估

| 风险 | 影响 | 缓解 |
|------|------|------|
| credential pool不完善 | auth失败 | 先用env直读，P1后期再pool |
| SessionDB接口不兼容 | 会话持久化丢失 | hermes_state.py已是自研，接口兼容 |
| model normalization差异 | 模型路由错误 | 先保留hermes_cli.models作为fallback |

---

## 六、验证清单

改造完成后验证：
- [ ] `grep -rn "from hermes_cli\|import hermes" hermes_cli/ gateway/` 返回空
- [ ] `grep -rn "hermes_state\|HermesAIAgent" gateway/` 返回空（注释除外）
- [ ] Gateway能正常启动: `cd gateway && python run.py --help`
- [ ] CLI能正常显示doctor: `python -m hermes_cli.doctor`
- [ ] 会话持久化正常: 创建会话 → 重启 → 查询会话存在

---

*QA Lead: 琬弦 | 2026-04-27*
