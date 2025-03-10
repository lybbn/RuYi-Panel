import os
import signal
from django.conf import settings
import logging
logger = logging.getLogger('apscheduler.scheduler')

def job_subprocess_add(job_id,subps):
    """
    subps: subprocess.Popen 的返回process
    """
    try:
        pid = subps.pid
        if job_id in settings.TASK_JOB_PROCESSES:
            settings.TASK_JOB_PROCESSES[job_id].append(pid)
        else:
            settings.TASK_JOB_PROCESSES[job_id] = [pid]
    except:
        pass
    
def job_subprocess_del(job_id):
    try:
        del settings.TASK_JOB_PROCESSES[job_id]  # 从字典中移除已终止的进程
    except:
        pass

def job_subprocess_kill(job_id):
    if job_id and job_id in settings.TASK_JOB_PROCESSES:
        process_pids = settings.TASK_JOB_PROCESSES[job_id]
        if process_pids:
            try:
                for processpid in process_pids:
                    logger.info(f"Job {job_id}: 停止 subprocess with PID {processpid} ...")
                    os.killpg(os.getpgid(processpid), signal.SIGTERM)
                    job_subprocess_del(job_id)
                    logger.info(f"Job {job_id}: 停止 subprocess with PID {processpid} 停止成功")
            except Exception as e:
                logger.info(f"停止{job_id} subprocess 错误: {str(e)}")