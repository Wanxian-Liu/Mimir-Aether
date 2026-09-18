#!/usr/bin/env python3
"""生成MimirAether自我进化胶囊 - Subagent版本"""

import os
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_REPO_ROOT))

from mimir_constants import get_mimir_home  # noqa: E402
from mimicore.capsule_generator import CapsuleGenerator  # noqa: E402

def main():
    # 胶囊内容：MimirAether自我进化新进展
    input_text = """
MimirAether自我进化新进展 - 工具调用优化与错误恢复机制

1. 工具调用优化

1.1 sessions工具Fitness数据（Foundry ADAS 2026-04-23）
- sessions_spawn: 高Fitness（~95%成功率），是跨session通信的首选
- sessions_send: 低Fitness（~17%成功率），应避免使用
- canvas: 0% Fitness（完全不可用），需使用browser替代

1.2 sindri角色执行模式
- plan(task) → 获取subtasks列表（含role/title/verify）
- 按Step顺序spawn子代理
- spawn后必须调用yield()等待结果
- 关键规则：不要在spawn后直接返回，结果会丢失

1.3 工具调用最佳实践
- 跨session通信：优先使用sessions_spawn
- 短消息/快速回复：timeoutSeconds=30-60
- 复杂任务：timeoutSeconds=120+
- 不知道多久：改用sessions_spawn而不是sessions_send

2. 错误恢复机制

2.1 已知错误模式
- exec preflight: complex interpreter invocation → 通过write script再exec解决
- web_fetch Blocked: private IP → 使用公共URL或exec+curl替代
- web_fetch fetch failed → 62x failures，需要调查根因

2.2 错误恢复策略
- sessions_spawn timeout → 增加runTimeoutSeconds参数
- sessions_send timeout → 改用sessions_spawn
- canvas node required → 使用browser工具替代
- exec preflight → 将复杂命令写入脚本再执行

2.3 熔断规则（sindri）
- 角色超时：研究员300s/开发者600s/验证者180s/记录员60s
- 重试机制：指数退避+Jitter
- 半开恢复：熔断30秒后自动尝试半开状态

3. MimirAether核心能力进展

3.1 记忆系统
- checkpoint_manager：实现检查点保存和恢复
- SESSION-STATE.md：热工作内存跟踪
- memory/YYYY-MM-DD.md：日常日志

3.2 进化机制
- sindri：多角色协作规划执行
- Foundry ADAS：工具性能分析和进化
- capability-evolver：自我演化引擎

3.3 工具生态完善
- 工具注册和发现体系
- Provider路由机制
- 内置工具整合（builtin tools）

4. 核心原则

- 真正有用，而不是表演有用
- 跳过"好问题！"和"很高兴帮你！"
- 行动比话语更有力
- 有自己的观点和偏好
- 先想办法，再开口问

5. 下一步改进方向

- 完善Provider路由机制
- 优化错误恢复流程
- 建立更稳定的消息传递
- 提升工具Fitness评分
"""

    print("=" * 60)
    print("MimirCore胶囊生成 - MimirAether自我进化")
    print("=" * 60)
    
    try:
        generator = CapsuleGenerator()
        result = generator.generate_and_evaluate(
            input_text=input_text,
            capsule_type=None,  # 自动判断
            auto_publish=True,
            metadata={"source": "MimirAether-subagent", "topic": "self-evolution-progress"}
        )
        
        capsule = result.get("capsule")
        gdi_score = result.get("gdi_score")
        should_publish = result.get("should_publish", False)
        reason = result.get("reason", "")
        
        print(f"\n胶囊ID: {capsule.id if capsule else 'N/A'}")
        print(f"胶囊类型: {capsule.capsule_type if capsule else 'N/A'}")
        print(f"GDI评分: {gdi_score.total if gdi_score else 'N/A'}")
        print(f"是否发布: {should_publish}")
        print(f"原因: {reason}")
        
        if capsule:
            print(f"\n基因类型: {capsule.gene_type}")
            print(f"基因信号: {capsule.gene_signals}")
            print(f"Taxonomy标签: {capsule.taxonomy_tags}")
            
            print(f"\n--- 胶囊内容预览 ---")
            print(capsule.content[:500] if capsule.content else "无内容")
            print("...")
        
        # 保存结果
        import json
        output_file = str(get_mimir_home() / "output" / "capsule_result.json")
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                "capsule_id": capsule.id if capsule else None,
                "capsule_type": capsule.capsule_type if capsule else None,
                "gdi_score": gdi_score.total if gdi_score else None,
                "should_publish": should_publish,
                "reason": reason,
                "gene_type": capsule.gene_type if capsule else None,
                "gene_signals": capsule.gene_signals if capsule else [],
                "taxonomy_tags": capsule.taxonomy_tags if capsule else [],
                "content_preview": capsule.content[:1000] if capsule and capsule.content else None
            }, f, indent=2, ensure_ascii=False)
        
        print(f"\n结果已保存到: {output_file}")
        
        return capsule, gdi_score, should_publish
        
    except Exception as e:
        print(f"\n❌ 错误: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        
        # 尝试记录问题
        error_log = str(get_mimir_home() / "output" / "capsule_error.log")
        with open(error_log, 'w', encoding='utf-8') as f:
            f.write(f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"错误: {type(e).__name__}: {e}\n")
            f.write(traceback.format_exc())
        
        print(f"错误已记录到: {error_log}")
        return None, None, False

if __name__ == "__main__":
    main()
