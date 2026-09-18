"""游离测试停放区（2026-09-18 批2.3）。

这些脚本原在仓根、不被 `pytest tests` 收集；停放后默认仍**不收集**：
它们多为一次性脚本（个别会真跑 agent / 写运行时状态），收集会污染 CI 判定。
需要时显式运行：`.venv/bin/python3 tests/legacy/<file>`。
"""

collect_ignore_glob = ["*.py"]
