from apps.systask.models import SysTaskCenter
from django_apscheduler.models import DjangoJob
from django.db import transaction
import logging
logger = logging.getLogger('apscheduler.scheduler')

def executeNextTask(check_task=False):
    """
    顺序执行安装任务，确保任务状态与调度器一致
    :param check_task: 是否检查运行中任务是否实际存在
    :return: True
    """
    logger.info("开始检查安装任务....")
    if check_task:
        running_tasks = SysTaskCenter.objects.filter(status=1, type=0)
        for task in running_tasks:
            if not DjangoJob.objects.filter(id=task.job_id).exists():
                with transaction.atomic():
                    logger.info(f"处理异常任务-[{task.name}]，改为安装失败状态！")
                    task.status = 2
                    task.save()
    
    # 获取当前正在执行的任务（确保原子操作）
    with transaction.atomic():
        # 使用 select_for_update 锁定记录，避免并发冲突
        current_task = SysTaskCenter.objects.filter(
            status=1, type=0
        ).select_for_update(skip_locked=True).order_by("create_at").first()
        
        if current_task:
            # 已有任务正在执行，无需处理
            return True
        
        # 查找下一个待处理任务并执行
        next_task = SysTaskCenter.objects.filter(
            status=0, type=0
        ).select_for_update(skip_locked=True).order_by("create_at").first()
        
        if next_task:
            logger.info(f"开始执行下一个安装任务-[{next_task.name}]")
            next_task.execute_task()
    logger.info("安装任务检查执行完毕！！！")
    return True
    