"""
MimirAether CLI - Unified command-line interface for MimirAether.

Adapted from Hermes hermes_cli for MimirAether project.
MimirAether is 刘哥's personal AI assistant project.

Provides subcommands for:
- mimir chat          - Interactive chat (same as ./mimir)
- mimir gateway       - Run gateway in foreground
- mimir gateway start - Start gateway service
- mimir gateway stop  - Stop gateway service
- mimir setup         - Interactive setup wizard
- mimir status        - Show status of all components
- mimir doctor        - Health check
"""

# TODO-自研: 版本号应与MimirAether项目同步
__version__ = "0.1.0"
__release_date__ = "2026.4.27"
