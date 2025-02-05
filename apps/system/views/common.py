from apps.systask.models import SysTaskCenter
from django_apscheduler.models import DjangoJobExecution

def executeNextTask(check_task=False):
    """
    顺序执行安装任务
    check_task 是否检查任务是否已结束，但未正常关闭状态
    """
    tasking_ins = SysTaskCenter.objects.filter(status=1,type=0).order_by("create_at").first()
    if tasking_ins:
        if check_task:
            job_id = tasking_ins.job_id
            if job_id:
                if not DjangoJobExecution.objects.filter(job_id=job_id).exists():
                    tasking_ins.status =3
            else:
                tasking_ins.status =3
            tasking_ins.save()
        return True
    else:
        taskwating_ins = SysTaskCenter.objects.filter(status=0,type=0).order_by("create_at").first()
        if taskwating_ins is not None:
            taskwating_ins.execute_task()
        return True
    