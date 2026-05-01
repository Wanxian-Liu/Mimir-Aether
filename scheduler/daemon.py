#!/usr/bin/env python3
"""
MimirAether调度器Daemon入口
"""
import sys
import os
import signal
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scheduler.scheduler import Scheduler

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    logger.info('MimirAether调度器启动')
    scheduler = Scheduler(tick_interval=60)
    
    def signal_handler(sig, frame):
        logger.info('收到停止信号...')
        scheduler.stop()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        scheduler.run_continuous()
    except Exception as e:
        logger.error(f'调度器异常: {e}')

if __name__ == '__main__':
    main()