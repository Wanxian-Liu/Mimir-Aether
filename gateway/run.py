#!/usr/bin/env python3
"""
MimirAether Gateway Runner

Gateway运行入口，负责：
- 启动所有配置的平台的适配器
- 管理Gateway生命周期
- 处理信号和优雅关闭

Usage:
    python gateway/run.py              # 启动Gateway
    python gateway/run.py --help     # 显示帮助
"""

import asyncio
import logging
import os
import signal
import sys
import threading
from pathlib import Path
from typing import Dict, Optional

# 添加项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =============================================================================
# SSL证书自动检测
# =============================================================================

def _ensure_ssl_certs() -> None:
    """Set SSL_CERT_FILE if the system doesn't expose CA certs to Python."""
    if "SSL_CERT_FILE" in os.environ:
        return

    import ssl
    paths = ssl.get_default_verify_paths()
    for candidate in (paths.cafile, paths.openssl_cafile):
        if candidate and os.path.exists(candidate):
            os.environ["SSL_CERT_FILE"] = candidate
            return

    try:
        import certifi
        os.environ["SSL_CERT_FILE"] = certifi.where()
        return
    except ImportError:
        pass

    # Common locations
    for candidate in [
        "/etc/ssl/certs/ca-certificates.crt",
        "/etc/pki/tls/certs/ca-bundle.crt",
        "/etc/ssl/ca-bundle.pem",
        "/etc/ssl/cert.pem",
    ]:
        if os.path.exists(candidate):
            os.environ["SSL_CERT_FILE"] = candidate
            return

_ensure_ssl_certs()

# =============================================================================
# GatewayRunner
# =============================================================================

class GatewayRunner:
    """
    MimirAether Gateway运行器
    
    负责：
    - 加载和配置平台适配器
    - 管理适配器生命周期
    - 处理信号和优雅关闭
    """
    
    def __init__(self):
        self._adapters: Dict[str, any] = {}
        self._running = False
        self._lock = threading.Lock()
        
    async def load_adapter(self, name: str, config: Dict) -> bool:
        """
        加载平台适配器
        
        Args:
            name: 适配器名称 (telegram, discord, feishu)
            config: 适配器配置
            
        Returns:
            是否加载成功
        """
        try:
            if name == "telegram":
                from gateway.telegram_adapter import TelegramAdapter
                adapter = TelegramAdapter(config)
            elif name == "discord":
                from gateway.discord_adapter import DiscordAdapter
                adapter = DiscordAdapter(config)
            elif name == "feishu":
                from gateway.feishu_adapter import FeishuAdapter
                adapter = FeishuAdapter(config)
            else:
                logger.warning(f"未知适配器类型: {name}")
                return False
            
            self._adapters[name] = adapter
            logger.info(f"加载适配器: {name}")
            return True
            
        except Exception as e:
            logger.error(f"加载适配器失败 {name}: {e}")
            return False
    
    async def start(self):
        """启动所有适配器"""
        if self._running:
            logger.warning("Gateway已经在运行")
            return
        
        self._running = True
        
        logger.info("启动MimirAether Gateway...")
        
        # 加载配置的适配器
        enabled_adapters = os.environ.get("MIMIR_ADAPTERS", "telegram,feishu,discord").split(",")
        
        for adapter_name in enabled_adapters:
            adapter_name = adapter_name.strip()
            if not adapter_name:
                continue
            
            # 尝试从环境变量获取配置
            config = self._load_adapter_config(adapter_name)
            
            if config is None:
                logger.warning(f"适配器 {adapter_name} 未配置，跳过")
                continue
            
            success = await self.load_adapter(adapter_name, config)
            if not success:
                continue
            
            # 启动适配器
            adapter = self._adapters[adapter_name]
            try:
                await adapter.start()
                logger.info(f"适配器已启动: {adapter_name}")
            except Exception as e:
                logger.error(f"启动适配器失败 {adapter_name}: {e}")
        
        if not self._adapters:
            logger.warning("没有加载任何适配器")
        
        logger.info(f"Gateway已启动，适配器数: {len(self._adapters)}")
    
    async def stop(self):
        """停止所有适配器"""
        if not self._running:
            return
        
        logger.info("停止MimirAether Gateway...")
        self._running = False
        
        for name, adapter in list(self._adapters.items()):
            try:
                await adapter.stop()
                logger.info(f"适配器已停止: {name}")
            except Exception as e:
                logger.error(f"停止适配器失败 {name}: {e}")
        
        self._adapters.clear()
        logger.info("Gateway已停止")
    
    def _load_adapter_config(self, name: str) -> Optional[Dict]:
        """从环境变量加载适配器配置"""
        prefix = f"MIMIR_{name.upper()}_"
        
        config = {}
        for key, value in os.environ.items():
            if key.startswith(prefix):
                config_key = key[len(prefix):].lower()
                config[config_key] = value
        
        # 检查必需的配置
        if name == "telegram":
            if "bot_token" not in config:
                return None
        elif name == "discord":
            if "bot_token" not in config:
                return None
        elif name == "feishu":
            if "app_id" not in config or "app_secret" not in config:
                return None
        
        return config if config else None
    
    @property
    def is_running(self) -> bool:
        return self._running
    
    @property
    def adapters(self) -> Dict[str, any]:
        return dict(self._adapters)


# =============================================================================
# 全局实例
# =============================================================================

_gateway_runner: Optional[GatewayRunner] = None
_main_loop: Optional[asyncio.AbstractEventLoop] = None


def _signal_handler(signum, frame):
    """处理系统信号"""
    logger.info(f"收到信号 {signum}")
    if _gateway_runner and _gateway_runner.is_running:
        asyncio.create_task(_gateway_runner.stop())


# =============================================================================
# CLI入口
# =============================================================================

def main():
    """主入口"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="MimirAether Gateway - 多平台消息集成",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python gateway/run.py                    # 启动Gateway
    python gateway/run.py --list-adapters  # 列出可用适配器
    python gateway/run.py --verbose        # 详细输出

环境变量:
    MIMIR_ADAPTERS     - 启用的适配器列表 (默认: telegram,feishu,discord)
    MIMIR_TELEGRAM_BOT_TOKEN - Telegram Bot Token
    MIMIR_DISCORD_BOT_TOKEN    - Discord Bot Token  
    MIMIR_FEISHU_APP_ID      - Feishu App ID
    MIMIR_FEISHU_APP_SECRET  - Feishu App Secret
        """
    )
    
    parser.add_argument(
        "--list-adapters",
        action="store_true",
        help="列出可用的平台适配器"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="详细输出"
    )
    parser.add_argument(
        "--adapters",
        type=str,
        default=None,
        help="指定启用的适配器 (逗号分隔)"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    if args.list_adapters:
        print("可用的平台适配器:")
        print("  - telegram  : Telegram Bot API")
        print("  - discord   : Discord Bot API")
        print("  - feishu    : 飞书开放平台")
        return
    
    # 设置适配器列表
    if args.adapters:
        os.environ["MIMIR_ADAPTERS"] = args.adapters
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)
    
    # 运行
    asyncio.run(_run_gateway())


async def _run_gateway():
    """运行Gateway"""
    global _gateway_runner, _main_loop
    
    _gateway_runner = GatewayRunner()
    _main_loop = asyncio.get_event_loop()
    
    try:
        await _gateway_runner.start()
        
        # 保持运行直到收到停止信号
        while _gateway_runner.is_running:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("收到中断信号")
    except Exception as e:
        logger.error(f"Gateway运行错误: {e}")
    finally:
        await _gateway_runner.stop()


if __name__ == "__main__":
    main()
