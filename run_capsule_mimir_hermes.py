#!/usr/bin/env python3
"""生成MimirAether与Hermes对标胶囊"""

import sys
import os

# 添加MimirCore路径
MIMIR_CORE_PATH = os.path.expanduser("~/.openclaw/projects/MimirAether/mimicore")
sys.path.insert(0, MIMIR_CORE_PATH)

from mimicore.capsule_generator import CapsuleGenerator, CapsuleType

def main():
    # 胶囊内容：MimirAether与Hermes对标
    input_text = """
MimirAether与Hermes核心能力对标报告

1. 核心能力对齐状态

1.1 消息处理
- Hermes: 支持流式输出、多provider路由、错误恢复
- MimirAether: 需要完整实现流式输出、Provider路由、错误恢复
- 差距: 核心功能缺失，功能对齐率约40%

1.2 会话管理
- Hermes: sessions_send(17%成功率), sessions_spawn(95%成功率)
- MimirAether: 需要实现sessions_spawn/sessions_send封装
- 差距: 缺少稳定的消息传递机制

1.3 工具生态
- Hermes: 完整的工具注册、发现、执行体系
- MimirAether: 需要完善工具生态，包括builtin tools整合
- 差距: 工具生态不完整

1.4 记忆系统
- Hermes: 记忆殿堂、checkpoint恢复机制
- MimirAether: 需要继承和改进记忆系统
- 差距: 需要确保记忆跨会话连续性

2. 工具Fitness数据（Foundry ADAS 2026-04-23）
- sessions_spawn: 高Fitness, ~95%成功率
- sessions_send: 低Fitness, ~17%成功率（避免使用）
- canvas: 0% Fitness（完全不可用，需替代方案）

3. 关键发现
- sindri角色模式：plan()→subtasks→spawn()→yield()
- sessions_send成功率过低，不应作为主要通信方式
- subagent是可靠的执行单元

4. 改进方向
- 优先实现sessions_spawn封装
- 避免依赖sessions_send
- 使用browser替代canvas
- 建立稳定的Provider路由机制

5. 核心原则
- 真正有用，而不是表演有用
- 跳过"好问题！"和"很高兴帮你！"
- 行动比话语更有力
"""

    print("=" * 60)
    print("MimirCore胶囊生成 - MimirAether与Hermes对标")
    print("=" * 60)
    
    generator = CapsuleGenerator()
    result = generator.generate_and_evaluate(
        input_text=input_text,
        capsule_type=None,  # 自动判断
        auto_publish=True,
        metadata={"source": "MimirAether-subagent", "topic": "hermes-alignment"}
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
    output_file = os.path.expanduser("~/.openclaw/projects/MimirAether/output/capsule_result.json")
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, 'w') as f:
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

if __name__ == "__main__":
    main()
