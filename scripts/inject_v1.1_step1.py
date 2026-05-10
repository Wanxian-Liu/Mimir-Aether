"""V1.1 Step 1: 注入推理方法到 capsule_generator.py"""
import subprocess

methods = '''
    SYMPTOM_TO_CAUSE = [
        (["未启用", "未集成", "未接入", "未加载", "未初始化"],
         "相关模块未被集成到系统生命周期，缺少启动/结束时调用对应接口"),
        (["为空", "无数据", "空白", "空文件", "空内容"],
         "缺少数据持久化逻辑，数据未被正确写入存储介质"),
        (["丢失", "消失", "找不到", "缺失", "缺少"],
         "缺少持久化或备份恢复机制"),
        (["崩溃", "异常退出", "OOM", "段错误"],
         "缺少资源限制或异常恢复机制"),
        (["慢", "延迟", "性能", "卡顿", "响应慢"],
         "缺少缓存或批量处理优化"),
        (["超时", "卡住", "无响应", "挂起", "死锁"],
         "缺少超时保护机制或异步等待处理"),
    ]

    CAUSE_TO_SOLUTION = [
        (["未集成", "未接入", "生命周期"],
         "在系统启动/结束点集成对应模块，确保在合适的生命周期阶段调用"),
        (["持久化", "写入", "存储"],
         "添加数据持久化逻辑，在关键节点执行读写操作"),
        (["未初始化", "初始化"],
         "添加初始化步骤，确保系统启动时正确加载并初始化数据"),
        (["异常", "错误", "恢复"],
         "添加异常捕获和降级策略，确保单点故障不影响整体"),
        (["备份", "恢复"],
         "添加定时备份和版本回退机制"),
    ]

    def _infer_root_cause(self, diagnosis: str, symptoms: str) -> str:
        """基于症状推断根因，绝不返回占位符"""
        combined = (diagnosis + " " + symptoms).lower()
        matches = []
        for keywords, cause in self.SYMPTOM_TO_CAUSE:
            if any(kw in combined for kw in keywords):
                matches.append(cause)
        if matches:
            return "根据症状分析，根因如下：\\n" + "\\n".join(f"- {m}" for m in matches[:3])
        return f"基于问题分析，根本原因与对应模块的实现逻辑或集成方式直接相关，需要检查是否存在遗漏或错误配置。"

    def _infer_solution(self, diagnosis: str, symptoms: str, root_cause: str) -> str:
        """基于根因推断解决方案，绝不返回占位符"""
        combined = root_cause.lower()
        matches = []
        for keywords, solution in self.CAUSE_TO_SOLUTION:
            if any(kw in combined for kw in keywords):
                matches.append(solution)
        if matches:
            return "根据根因分析，修复方案如下：\\n" + "\\n".join(f"- {m}" for m in matches[:3])
        return "根据根因分析制定修复方案：定位根因对应代码→应用修复→验证生效→确认无副作用"
'''

import os
os.chdir('/home/rayliu/.openclaw/projects/MimirAether')

with open('mimicore/capsule_generator.py') as f:
    content = f.read()

marker = '    def _generate_repair_capsule'
if marker in content:
    content = content.replace(marker, methods + '\n' + marker)
    result = subprocess.run(['cat'], input=content, capture_output=True, text=True)
    with open('mimicore/capsule_generator.py', 'w') as f:
        f.write(result.stdout)
    import py_compile
    py_compile.compile('mimicore/capsule_generator.py', doraise=True)
    print('✅ 推理方法注入完成')
else:
    print('❌ 找不到插入点')
