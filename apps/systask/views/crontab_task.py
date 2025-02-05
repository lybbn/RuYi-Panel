#!/bin/python
#coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2024-01-27
# +-------------------------------------------------------------------
# | EditDate: 2024-01-27
# +-------------------------------------------------------------------

# ------------------------------
# 计划任务
# ------------------------------

import os
import uuid
from rest_framework.views import APIView
from utils.customView import CustomAPIView
from utils.common import get_parameter_dic,formatdatetime,formatTimestamp2Datetime,GetLogsPath
from utils.pagination import CustomPagination
from django_apscheduler.models import DjangoJobExecution
from apps.systask.models import CrontabTask
from rest_framework import serializers
from utils.serializers import CustomModelSerializer
from utils.viewset import CustomModelViewSet
from utils.jsonResponse import SuccessResponse,ErrorResponse,DetailResponse
from django.db import transaction
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from apps.systask.tasks import resolvingCron,cronTask,pause_task,resume_task,remove_task,run_task
from apps.systask.scheduler import scheduler
from utils.server.system import system
from apps.systask.tasklogger import deleteTaskLogs
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apps.syslogs.logutil import RuyiAddOpLog

def make_uuid():
    # .hex 将生成的uuid字符串中的 － 删除，带-是36位字符，不带-是32位随机字符串
    return str(uuid.uuid4().hex)

class CrontabTasksSerializer(CustomModelSerializer):
    """
    计划任务 简单序列化器
    """
    next_run_time = serializers.SerializerMethodField()
    last_run_time = serializers.SerializerMethodField()

    def get_next_run_time(self,obj):
        try:
            return formatdatetime(obj.job.next_run_time)
        except:
            return ""
    
    def get_last_run_time(self,obj):
        try:
            last_execution = DjangoJobExecution.objects.filter(job=obj.job).order_by('-run_time').first()
            if last_execution:
                last_execution_time = last_execution.run_time
                return  formatdatetime(last_execution_time)
            else:
                return ""
        except:
            return ""

    class Meta:
        model = CrontabTask
        fields = "__all__"
        read_only_fields = ["id"]

class CrontabTaskViewSet(CustomModelViewSet):
    """
    @name 计划任务后台接口
    @author lybbn<2024-01-27>
    """
    queryset = CrontabTask.objects.all().order_by('-create_at')
    serializer_class = CrontabTasksSerializer

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        reqData = request.data
        type = int(reqData.get("type",0))
        if type not in [0,1,2,3,4]:
            return ErrorResponse(msg="type error")
        cron_res = resolvingCron(reqData)
        second = cron_res.get("second","*")
        minute = cron_res.get("minute","*")
        hour = cron_res.get("hour","*")
        day = cron_res.get("day","*")
        month = cron_res.get("month","*")
        week = cron_res.get("week","*")
        year = cron_res.get("year","*")
        job_id = make_uuid()
        period_type = int(reqData.get("period_type",0))
        #coalesce=True 积攒的任务只跑一次
        #max_instances = 10 支持10个实例并发
        #misfire_grace_time = 600 600秒的任务超时容错，超过这个时间认为该任务过期，不再执行
        if period_type in [1,2,3,4]:
            django_job = scheduler.add_job(cronTask,'cron',id=job_id,second=second, minute=minute, hour=hour, day=day, month=month, week=week, year=year,args=[reqData,job_id],max_instances=1,replace_existing=True,misfire_grace_time=1,coalesce=True)
        elif period_type == 5:
            django_job = scheduler.add_job(cronTask,'interval',id=job_id,days=day,hours=hour,minutes=minute,args=[reqData,job_id],max_instances=1,replace_existing=True,misfire_grace_time=1,coalesce=True)
        elif period_type == 6:
            django_job = scheduler.add_job(cronTask,'interval',id=job_id,hours=hour,minutes=minute,args=[reqData,job_id],max_instances=1,replace_existing=True,misfire_grace_time=1,coalesce=True)
        elif period_type == 7:
            django_job = scheduler.add_job(cronTask,'interval',id=job_id,minutes=minute,args=[reqData,job_id],max_instances=1,replace_existing=True,misfire_grace_time=1,coalesce=True)
        elif period_type == 8:
            django_job = scheduler.add_job(cronTask,'interval',id=job_id,seconds=second,args=[reqData,job_id],max_instances=1,replace_existing=True,misfire_grace_time=1,coalesce=True)
        reqData['job'] = django_job.id
        serializer = CrontabTasksSerializer(data=reqData)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        result = serializer.data
        RuyiAddOpLog(request,msg="【计划任务】-【新增】=>"+reqData.get('name',""),module="taskmg")
        return DetailResponse(msg="添加成功", data=result)
    
    @transaction.atomic
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, request=request, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}
        
        reqData = request.data
        cron_res = resolvingCron(reqData)
        second = cron_res.get("second",None)
        minute = cron_res.get("minute",None)
        hour = cron_res.get("hour",None)
        day = cron_res.get("day",None)
        month = cron_res.get("month",None)
        week = cron_res.get("week",None)
        year = cron_res.get("year",None)
        job_id = serializer.data.get("job")
        job = scheduler.get_job(job_id)
        period_type = int(reqData.get("period_type",0))
        pause_task(job_id)
        if period_type in [1,2,3,4]:
            if not day or day == "*":
                day = None
            if not hour or hour == "*":
                hour = None
            if not minute or minute == "*":
                minute = None
            if not second or second == "*":
                second = None
            if not month or month == "*":
                month = None
            if not week or week == "*":
                week = None
            if not year or year == "*":
                year = None
            trigger = CronTrigger(second=second, minute=minute, hour=hour, day=day, month=month, week=week, year=year)
            job.modify(trigger=trigger,args=[reqData,job_id])
        elif period_type == 5:
            if not day or day == "*":
                day = 0
            if not hour or hour == "*":
                hour = 0
            if not minute or minute == "*":
                minute = 0
            trigger = IntervalTrigger(days=int(day),hours=int(hour),minutes=int(minute))
            job.modify(trigger=trigger,args=[reqData,job_id])
        elif period_type == 6:
            if not hour or hour == "*":
                hour = 0
            if not minute or minute == "*":
                minute = 0
            trigger = IntervalTrigger(hours=int(hour),minutes=int(minute))
            job.modify(trigger=trigger,args=[reqData,job_id])
        elif period_type == 7:
            trigger = IntervalTrigger(minutes=int(minute))
            job.modify(trigger=trigger,args=[reqData,job_id])
        elif period_type == 8:
            trigger = IntervalTrigger(seconds=int(second))
            job.modify(trigger=trigger,args=[reqData,job_id])
        resume_task(job_id)
        RuyiAddOpLog(request,msg="【计划任务】-【修改】=>"+serializer.data.get("name",""),module="taskmg")
        return DetailResponse(data=None, msg="更新成功")

    def destroy(self, request, *args, **kwargs):
        """
        删除任务
        """
        instance = self.get_object()
        taskname = instance.name
        self.perform_destroy(instance)
        job_id = instance.job_id
        pause_task(job_id)
        remove_task(job_id)
        deleteTaskLogs(job_id)
        RuyiAddOpLog(request,msg="【计划任务】-【删除】=>"+taskname,module="taskmg")
        return DetailResponse(data=[], msg="删除成功")
    
    def runtask(self,request,*args,**kwargs):
        """
        立即执行任务
        """
        instance = self.get_object()
        job_id = instance.job_id
        serializer = CrontabTasksSerializer(instance=instance)
        run_task(serializer.data,job_id)
        RuyiAddOpLog(request,msg="【计划任务】-【执行】=>"+serializer.data.get("name",""),module="taskmg")
        return DetailResponse(msg="任务已启动", data=None)

    def status(self,request,*args,**kwargs):
        """
        开始/暂停任务
        """
        instance = self.get_object()
        job_id = instance.job_id
        reqData = request.data
        status = reqData.get('status')
        status_name = "启用"
        if status == 0:
            status_name = "停止"
            pause_task(job_id)
        else:
            resume_task(job_id)
        instance.status = reqData.get('status')
        instance.save()
        RuyiAddOpLog(request,msg=f"【计划任务】-【状态】=>【{status_name}】{instance.name}",module="taskmg")
        return DetailResponse(msg="修改成功", data=None)
    
    def deleteLogs(self, request, *args, **kwargs):
        """
        删除任务日志
        """
        reqData = get_parameter_dic(request)
        job_id = reqData.get("job_id",None)
        if not job_id:#清空所有任务日志
            queryset = DjangoJobExecution.objects.all()
            deleteTaskLogs()
        else:#清空指定任务日志
            queryset = DjangoJobExecution.objects.filter(job_id=job_id)
            deleteTaskLogs(job_id)
        queryset.delete()
        RuyiAddOpLog(request,msg=f"【计划任务】- 删除任务日志 ："+job_id,module="taskmg")
        return DetailResponse(msg="清空成功")
    
    def run_logs(self,request, *args, **kwargs):
        """
        取执行日志
        """
        reqData = get_parameter_dic(request)
        job_id = reqData.get("job_id",None)
        if not job_id:
            return ErrorResponse(msg="参数错误")
        task_log_root_path = os.path.join(GetLogsPath(),"ruyitask")
        task_log_path = os.path.join(task_log_root_path,job_id+".log")
        data = system.GetFileLastNumsLines(task_log_path,2000)
        return DetailResponse(data=data,msg="success")

def getTaskCNStatus(status):
    """
    @name 获取计划任务的中文意思
    @author lybbn<2024-02-07>
    """
    if status == "Executed":
        return "成功"
    elif status == "Error!":
        return "失败"
    elif status == "Missed!":
        return "过期"
    elif status == "Started execution":
        return "开始"
    elif status == "Max instances!":
        return "过载"
    else:
        return "未知"


class GetDjangoJobExecutionView(CustomAPIView):
    """
    get
    获取执行日志
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        reqData = get_parameter_dic(request)
        job_id = reqData.get("job_id",None)
        status = reqData.get("status",None)
        beginAt = reqData.get("beginAt",None)
        endAt = reqData.get("endAt",None)
        queryset = DjangoJobExecution.objects.all().order_by("-run_time")
        if job_id:
            queryset = queryset.filter(job_id = job_id)
        if status:
            queryset = queryset.filter(status = status)
        if beginAt or endAt:
            queryset = queryset.filter(run_time__range = (beginAt,endAt))
        # # 1. 实例化分页器对象
        page_obj = CustomPagination()
        # # 2. 使用自己配置的分页器调用分页方法进行分页
        page_data = page_obj.paginate_queryset(queryset, request)
        data = []
        for m in page_data:
            data.append({
                'id':m.id,
                'status':getTaskCNStatus(m.status),
                'duration':m.duration,
                'exception':m.exception,
                'finished':formatTimestamp2Datetime(m.finished),
                'run_time': formatdatetime(m.run_time)
            })
        return page_obj.get_paginated_response(data)