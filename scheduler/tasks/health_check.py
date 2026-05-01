"""
健康检查任务
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def run_health_check():
    print('执行MimirAether健康检查...')
    try:
        from health import HealthChecker
        checker = HealthChecker()
        result = checker.get_full_report()
        print(f'健康状态: {result.get("overall_status")}')
        return result.get('overall_status', 'unknown')
    except Exception as e:
        print(f'健康检查失败: {e}')
        return 'error'

if __name__ == '__main__':
    run_health_check()