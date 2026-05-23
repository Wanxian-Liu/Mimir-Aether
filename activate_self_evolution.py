#!/usr/bin/env python3
"""
MimirAether 三环闭环激活器
激活自驱动演进机制，让MimirAether能够主动研发技能

使用方式:
    python3 activate_self_evolution.py          # 单次运行
    python3 activate_self_evolution.py --loop   # 持续运行
"""

import asyncio
import sys
import os
import argparse
import logging
from pathlib import Path

# 添加项目路径
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "skills" / "mimiraether" / "mimiraether-self_evolution"))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def activate_three_ring_loop():
    """激活三环闭环"""
    logger.info("=" * 60)
    logger.info("MimirAether 三环闭环激活器")
    logger.info("=" * 60)
    
    # 导入三环闭环模块
    try:
        from three_ring_architecture import ThreeRingClosedLoop
        logger.info("✅ 三环闭环模块加载成功")
    except ImportError as e:
        logger.error(f"❌ 三环闭环模块导入失败: {e}")
        return False
    
    # 导入自驱动引擎
    try:
        from mimicore.evolve.self_drive_engine import SelfDriveEngine
        logger.info("✅ 自驱动引擎模块加载成功")
    except ImportError as e:
        logger.warning(f"⚠️ 自驱动引擎模块导入失败: {e}")
        SelfDriveEngine = None
    
    # 创建三环闭环实例
    loop = ThreeRingClosedLoop()
    logger.info("✅ ThreeRingClosedLoop 实例创建成功")
    
    # 创建自驱动引擎
    if SelfDriveEngine:
        engine = SelfDriveEngine()
        logger.info("✅ SelfDriveEngine 实例创建成功")
    else:
        engine = None
        logger.warning("⚠️ 自驱动引擎未加载，三环闭环将以基本模式运行")
    
    # 运行单次闭环
    logger.info("\n启动三环闭环...")
    try:
        result = await loop.run()
        logger.info(f"✅ 三环闭环运行完成: {result}")
    except Exception as e:
        logger.error(f"❌ 三环闭环运行失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 持续运行模式
    if args.loop:
        logger.info("\n启动持续运行模式 (Ctrl+C 退出)...")
        try:
            await loop.run_continuous()
        except KeyboardInterrupt:
            logger.info("\n收到停止信号，三环闭环退出")
        except Exception as e:
            logger.error(f"❌ 持续运行失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    return True


async def activate_skill_self_research():
    """激活技能自研发机制"""
    logger.info("=" * 60)
    logger.info("技能自研发机制激活")
    logger.info("=" * 60)
    
    # 检查技能目录
    skills_dir = PROJECT_ROOT / "skills" / "mimiraether"
    if not skills_dir.exists():
        logger.warning(f"⚠️ 技能目录不存在: {skills_dir}")
        return False
    
    # 列出当前技能
    skills = list(skills_dir.iterdir())
    logger.info(f"当前技能数量: {len(skills)}")
    
    for skill in skills[:5]:  # 只显示前5个
        logger.info(f"  - {skill.name}")
    if len(skills) > 5:
        logger.info(f"  ... 还有 {len(skills) - 5} 个")
    
    # 技能自研发检查
    logger.info("\n检查技能自研发能力...")
    
    # 检查skills_hub
    try:
        from agent.skills_hub import SkillsHub
        hub = SkillsHub()
        
        # 检查create_skill_file方法
        if hasattr(hub, 'create_skill_file'):
            logger.info("✅ SkillsHub.create_skill_file 可用")
        else:
            logger.warning("⚠️ SkillsHub.create_skill_file 不可用")
        
        # 检查evolve_skill方法
        if hasattr(hub, 'evolve_skill'):
            logger.info("✅ SkillsHub.evolve_skill 可用")
        else:
            logger.warning("⚠️ SkillsHub.evolve_skill 不可用")
            
    except ImportError as e:
        logger.error(f"❌ SkillsHub导入失败: {e}")
        return False
    
    return True


def main():
    global args
    
    parser = argparse.ArgumentParser(description="MimirAether 三环闭环激活器")
    parser.add_argument("--loop", action="store_true", help="持续运行模式")
    parser.add_argument("--verbose", action="store_true", help="详细输出")
    parser.add_argument("--skill-only", action="store_true", help="仅激活技能自研发")
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    async def run():
        if args.skill_only:
            success = await activate_skill_self_research()
        else:
            # 先激活技能自研发
            await activate_skill_self_research()
            # 再激活三环闭环
            success = await activate_three_ring_loop()
        
        if success:
            logger.info("\n" + "=" * 60)
            logger.info("✅ MimirAether 自驱动演进机制已激活")
            logger.info("=" * 60)
        else:
            logger.error("\n" + "=" * 60)
            logger.error("❌ 激活失败")
            logger.error("=" * 60)
            sys.exit(1)
    
    asyncio.run(run())


if __name__ == "__main__":
    main()
