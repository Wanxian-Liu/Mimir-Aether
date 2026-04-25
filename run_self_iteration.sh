#!/bin/bash
cd ~/.openclaw/projects/MimirAether
python3 cli.py -q "分析MimirAether当前代码状态，识别一个可以改进的地方（如代码重复、注释缺失、错误处理不足），完成一个小迭代改进并git commit" --max-iterations 10 2>&1
