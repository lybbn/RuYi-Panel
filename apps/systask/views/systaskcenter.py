#!/bin/python
#coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2024-04-26
# +-------------------------------------------------------------------
# | EditDate: 2024-04-26
# +-------------------------------------------------------------------

# ------------------------------
# 应用商店
# ------------------------------
import os,json
from datetime import datetime
from rest_framework.views import APIView
from utils.customView import CustomAPIView
from utils.jsonResponse import ErrorResponse,DetailResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from utils.common import get_parameter_dic,formatdatetime,GetLogsPath,DeleteFile
from apps.systask.models import SysTaskCenter
from utils.pagination import CustomPagination
from apps.systask.scheduler import scheduler
from apps.syslogs.logutil import RuyiAddOpLog
from apps.systask.subprocessMg import job_subprocess_kill
from apps.system.views.common import executeNextTask
import logging
logger = logging.getLogger('apscheduler.scheduler')
    
class RYSystemTaskCenterView(CustomAPIView):
    """
    post:
    系统任务中心
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        reqData = get_parameter_dic(request)
        action = reqData.get("action","all")
        queryset = SysTaskCenter.objects.all()
        if action == 'all':
            pass
        elif action == 'ing':
            queryset = queryset.filter(status__in=[0,1]).order_by("id")
        elif action == 'end':
            queryset = queryset.filter(status__in=[2,3]).order_by("-id")
        else:
            return ErrorResponse(msg="参数错误")
        # # 1. 实例化分页器对象
        page_obj = CustomPagination()
        # # 2. 使用自己配置的分页器调用分页方法进行分页
        page_data = page_obj.paginate_queryset(queryset, request)
        data = []
        log_root = os.path.abspath(GetLogsPath())
        for m in page_data:
            params = m.get_params()
            soft_name = ""
            if m.type == 0:
                soft_name = params.get("name","")
            log_path = os.path.join(log_root,soft_name,m.log).replace("\\","/")
            data.append({
                'id':m.id,
                'status':m.status,
                'status_name':m.get_status_display(),
                'duration':m.duration,
                'name':m.name,
                'log_path':log_path,
                'create_at':formatdatetime(m.create_at)
            })
        return page_obj.get_paginated_response(data)
    
    def post(self, request):
        reqData = get_parameter_dic(request)
        action = reqData.get("action",'')
        if action == "del_task":
            id = reqData.get("id","")
            if not id:return ErrorResponse(msg="参数错误")
            ins = SysTaskCenter.objects.filter(id=id).first()
            if not ins:return ErrorResponse(msg="无此任务")
            job_id = ins.job_id
            try:
                job_subprocess_kill(job_id)
                try:
                    scheduler.remove_job(job_id)
                except:
                    pass
            except Exception as e:
                logger.info(f"删除任务 {ins.name}:{job_id} 错误: {str(e)}")
            finally:
                try:
                    params = ins.params
                    if job_id:
                        if params:
                            json_params = json.loads(params)
                            name = json_params['name']
                            log = job_id+".log"
                            logpath = os.path.join(os.path.abspath(GetLogsPath()),name,log)
                            DeleteFile(logpath,empty_tips=False)
                    ins.delete()
                    #执行下一个任务
                    executeNextTask()
                except Exception as e:
                    return ErrorResponse(msg=str(e))
            RuyiAddOpLog(request,msg="【任务中心】-【删除】=>"+ins.name,module="softmg")
            return DetailResponse(msg="删除成功")
        elif action == "stop_task":
            id = reqData.get("id","")
            if not id:return ErrorResponse(msg="参数错误")
            ins = SysTaskCenter.objects.filter(id=id).first()
            if not ins:return ErrorResponse(msg="无此任务")
            job_id = ins.job_id
            try:
                job_subprocess_kill(job_id)
                try:
                    scheduler.remove_job(job_id)
                except:
                    pass
            except Exception as e:
                logger.info(f"停止任务 {ins.name}:{job_id} 错误: {str(e)}")
            finally:
                try:
                    end_time = datetime.now()  # 记录任务结束时间
                    if ins.exec_at:
                        ins.duration = (end_time - ins.exec_at).total_seconds()
                    ins.status = 2
                    ins.save()
                    #执行下一个任务
                    executeNextTask()
                except Exception as e:
                    return ErrorResponse(msg=str(e))
            RuyiAddOpLog(request,msg="【任务中心】-【停止】=>"+ins.name,module="softmg")
            return DetailResponse(msg="停止成功")
        else:
            return ErrorResponse(msg="类型错误")