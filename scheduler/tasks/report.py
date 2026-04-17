#!/usr/bin/env python3
"""
报告生成任务
生成MimirAether状态报告，包括总体状态和六维指标。
"""

import sys
import os
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def run_report():
    """生成状态报告"""
    print("生成MimirAether状态报告...")
    try:
        from health import HealthChecker
        checker = HealthChecker()
        result = checker.get_full_report()
        
        report = f"""
=== MimirAether状态报告 ===
时间: {datetime.now().isoformat()}
总体状态: {result.get('overall_status')}
六维指标:
- 任务成功率: {result.get('six_dimensions', {}).get('task_success_rate')}
- 工具失败率: {result.get('six_dimensions', {}).get('tool_failure_rate')}
- 验证通过率: {result.get('six_dimensions', {}).get('verification_pass_rate')}
"""
        print(report)
        return report
    except Exception as e:
        print(f"报告生成失败: {e}")
        return f"error: {e}"

if __name__ == "__main__":
    run_report()