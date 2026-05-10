import json
import os
from pathlib import Path
from datetime import datetime

from mimir_constants import get_mimir_home

DELIVERY_DIR = get_mimir_home() / "cron" / "delivery"

class DeliveryResult:
    def __init__(self, job_id, status, message):
        self.job_id = job_id
        self.status = status
        self.message = message
        self.timestamp = datetime.now().isoformat()
    
    def to_dict(self):
        return {
            "job_id": self.job_id,
            "status": self.status,
            "message": self.message,
            "timestamp": self.timestamp
        }

def deliver_local(job_result):
    """保存作业结果到本地默认目录"""
    DELIVERY_DIR.mkdir(parents=True, exist_ok=True)
    filename = DELIVERY_DIR / f"{job_result['job_id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, "w") as f:
        json.dump(job_result, f, indent=2)
    return str(filename)

def deliver_file(job_result, filepath):
    """保存作业结果到指定文件"""
    with open(filepath, "w") as f:
        json.dump(job_result, f, indent=2)
    return filepath

def deliver_hook(job_result, webhook_url, timeout=10):
    """发送作业结果到webhook（默认10秒超时，避免无限等待）"""
    import urllib.request
    import urllib.error
    
    data = json.dumps(job_result).encode("utf-8")
    req = urllib.request.Request(
        webhook_url, 
        data=data, 
        headers={"Content-Type": "application/json"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return {
                "status": "success",
                "status_code": resp.status,
                "response": resp.read().decode("utf-8")
            }
    except TimeoutError:
        return {
            "status": "error",
            "error": f"请求超时（{timeout}秒）"
        }
    except urllib.error.HTTPError as e:
        return {
            "status": "error",
            "status_code": e.code,
            "error": str(e)
        }
    except urllib.error.URLError as e:
        return {
            "status": "error",
            "error": str(e)
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }