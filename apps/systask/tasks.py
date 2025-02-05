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
import datetime
import time
import requests
import shutil
import zipfile
import tarfile
from apps.systask.tasklogger import tasklogger
from utils.security.safe_filter import filter_xss1
from utils.common import RunCommand,ast_convert,GetRandomSet,current_os,GetRandomSet,GetBackupPath,format_size
from apps.systask.models import CrontabTask
from django_apscheduler.jobstores import DjangoJobStore,register_events
from apscheduler.triggers.date import DateTrigger
from utils.serializers import CustomModelSerializer
from django.conf import settings
from apps.systask.scheduler import scheduler
from pytz import timezone
from apps.system.models import Config,Sites,Databases
from apps.sysbak.models import RuyiBackup
from apps.system.views.common import executeNextTask
from utils.install.mysql import RY_BACKUP_MYSQL_DATABASE
import logging
logger = logging.getLogger('apscheduler.scheduler')

# scheduler = BackgroundScheduler(timezone=settings.TIME_ZONE)
# scheduler.add_jobstore(DjangoJobStore(), 'default')
# # 删除所有已过期的任务
# scheduler.remove_all_jobs(jobstore="default", next_run_time__lte=datetime.now())
# 在主线程中执行定时任务（避免多线程部署下，重复运行任务）-低效
# # 注册调度器事件（仅在主进程中注册,确保多进程下不重复运行任务）
# if multiprocessing.current_process().name == 'MainProcess':
#     register_events(scheduler)
# # 启动调度器（仅在主进程中启动,确保多进程下不重复运行任务）
# if multiprocessing.current_process().name == 'MainProcess':
#     scheduler.start()
#把具体时间解析成cron表达式
def resolvingCron(reqData):
    """
    @name 解析前端提交周期为cron标准时间
    @author lybbn<2024-01-27>
    """
    second = reqData.get("second","*")
    minute = reqData.get("minute","*")
    hour = reqData.get("hour","*")
    day = reqData.get("day","*")
    month = reqData.get("month","*")
    week = reqData.get("week","*")
    year = reqData.get("year","*")
    period_type = int(reqData.get("period_type",0))
    if period_type not in [1,2,3,4,5,6,7,8]:
        raise ValueError("period type error")
    if period_type == 1:#每天
        if int(minute) >59 or int(minute)<0:
            raise ValueError("分钟的取值范围为[0-59]")
        if int(hour) >23 or int(hour)<0:
            raise ValueError("小时的取值范围为[0-23]")
        year = "*"
        week = "*"
        month = "*"
        day = "*"
        second = "0"
    elif period_type == 2:#每周
        if int(week) >6 or int(week)<0:
            raise ValueError("星期的取值范围为[0-6]")
        if int(minute) >59 or int(minute)<0:
            raise ValueError("分钟的取值范围为[0-59]")
        if int(hour) >23 or int(hour)<0:
            raise ValueError("小时的取值范围为[0-23]")
        year = "*"
        month = "*"
        day = "*"
        second = "0"
    elif period_type == 3:#每月
        if int(day) >31 or int(day)<1:
            raise ValueError("日的取值范围为[1-31]")
        if int(minute) >59 or int(minute)<0:
            raise ValueError("分钟的取值范围为[0-59]")
        if int(hour) >23 or int(hour)<0:
            raise ValueError("小时的取值范围为[0-23]")
        year = "*"
        month = "*"
        week = "*"
        second = "0"
    elif period_type == 4:#每小时
        if int(minute) >59 or int(minute)<0:
            raise ValueError("分钟的取值范围为[0-59]")
        year = "*"
        month = "*"
        week = "*"
        second = "0"
        day= "*"
        hour= "*"
    elif period_type == 5:#每隔N天
        if int(day) >31 or int(day)<1:
            raise ValueError("日的取值范围为[1-31]")
        year = "*"
        month = "*"
        week = "*"
        second = "*"
        day= day
    elif period_type == 6:#每隔N时
        if int(hour) >23 or int(hour)<0:
            raise ValueError("小时的取值范围为[0-23]")
        year = "*"
        month = "*"
        week = "*"
        second = "*"
        day= "*"
        hour= hour
    elif period_type == 7:#每隔N分
        if int(minute) >59 or int(minute)<0:
            raise ValueError("分钟的取值范围为[0-59]")
        year = "*"
        month = "*"
        week = "*"
        second = "*"
        day= "*"
        hour= "*"
        minute = minute
    elif period_type == 8:#每隔N秒
        if int(second) >59 or int(second)<0:
            raise ValueError("秒的取值范围为[0-59]")
        year = "*"
        month = "*"
        week = "*"
        second = second
        day= "*"
        hour= "*"
        minute = "*"

    result = {
        "second":second,
        "minute":minute,
        "hour":hour,
        "day":day,
        "month":month,
        "week":week,
        "year":year
    }
    return result

def cronTask(obj,job_id):
    """
    @name 定时任务
    @author lybbn<2024-01-27>
    """
    taskloggers = tasklogger(job_id)
    type = int(obj.get("type",0))
    job_name = obj.get("name","")
    taskloggers.info("------------------------【%s】任务开始------------------------"%job_name)
    if type == 0:#shell
        stdout, stderr = RunCommand(obj.get("shell_body"))
        if stderr:
            taskloggers.info("【%s】执行脚本失败，返回内容：\n%s"%(job_name,stderr))
        else:
            taskloggers.info("【%s】执行脚本成功，返回内容：\n%s"%(job_name,stdout))
        
    elif type == 1:#bk_database
        settings_bk_counts = int(obj.get("saveNums",3))
        db_type = int(obj.get("db_type",0))
        db_ids = obj.get("database","")
        db_ids_list = []
        if db_ids == "ALL":
            db_ids_list = list(Databases.objects.filter(db_type=db_type,is_remote=False).values_list("id",flat=True))
        else:
            db_ids_list = str(site_ids).split(",")
        if not db_ids_list:
            taskloggers.info("暂无数据库需要备份，已跳过！！！")
        else:
            is_windows = True if current_os == "windows" else False
            cron_ins = CrontabTask.objects.filter(job_id=job_id).first()
            for db_id in db_ids_list:
                db_info = {}
                s_ins = Databases.objects.filter(id=db_id).first()
                if not s_ins:return False,f"--id:{db_id} 数据库不存在，已跳过"
                db_info['id'] = db_id
                db_info['db_name'] = s_ins.db_name
                db_info['db_host'] = s_ins.db_host
                db_info['db_user'] = s_ins.db_user
                db_info['db_pass'] = s_ins.db_pass
                db_info['db_port'] = s_ins.db_port
                db_info['format'] = s_ins.format
                #backup_base_path = os.path.join(GetBackupPath(),"ruyitask","databases")
                try:
                    isok,dst_file_path,dst_file_size,bak_ins = RY_BACKUP_MYSQL_DATABASE(db_info=db_info,is_windows=is_windows,return_bk_ins=True)
                    if cron_ins:
                        bak_ins.cron_id = cron_ins.id
                        bak_ins.save()
                    taskloggers.info(f"【{db_info['db_name']}】备份数据库成功，大小{format_size(dst_file_size)}，备份后压缩文件：{dst_file_path}")
                except Exception as e:
                    taskloggers.info(f"{db_info['db_name']}备份失败，失败内容：\n{e}")
        
    elif type == 2:#bk_website
        settings_bk_counts = int(obj.get("saveNums",3))
        exclude_dirs = obj.get("exclude_rules",[])
        site_ids = obj.get("website","")
        site_ids_list = []
        if site_ids == "ALL":
            site_ids_list = list(Sites.objects.filter(type=0).values_list("id",flat=True))
        else:
            site_ids_list = str(site_ids).split(",")
        if not site_ids_list:
            taskloggers.info("暂无网站需要备份，已跳过！！！")
        else:
            for site_id in site_ids_list:
                isok,msg = backupSite(site_id=site_id,exclude_dirs=exclude_dirs,job_id=job_id)
                taskloggers.info(msg)
                backup_counts = RuyiBackup.objects.filter(job_id=job_id).count()
                s_nums = backup_counts - settings_bk_counts
                if s_nums > 0:
                    for i in range(0,s_nums):
                        old_file_ins = RuyiBackup.objects.filter(job_id=job_id,type=2,fid=site_id).order_by("create_at").first()
                        if old_file_ins:
                            old_filename = old_file_ins.filename
                            r_old_filename = r'%s'%old_filename
                            if os.path.isfile(r_old_filename):
                                os.remove(r_old_filename)
                                taskloggers.info("已清理过期的网站备份文件：%s"%(old_filename))
                            old_file_ins.delete()
    elif type == 3:#bk_dir
        source_dir = obj.get("dir","")
        if not source_dir or not os.path.exists(source_dir):
            taskloggers.info("【%s】备份目录失败，源目录不存在"%(job_name))
        else:
            settings_bk_counts = int(obj.get("saveNums",3))
            exclude_dirs = obj.get("exclude_rules",[])
            if not exclude_dirs:
                exclude_dirs = []
            else:
                exclude_dirs = exclude_dirs.split("\n")
            backup_base_path =GetBackupPath()
            backup_dir_root_path = os.path.join(backup_base_path,"ruyitask","dirs")
            if not os.path.exists(backup_dir_root_path):
                os.makedirs(backup_dir_root_path)
            name = os.path.basename(source_dir)
            zip_filename = f"dir_{name}_{time.strftime('%Y%m%d_%H%M%S',time.localtime())}_{GetRandomSet(5)}.zip"
            zip_filename_path = os.path.join(backup_dir_root_path, zip_filename)
            backup_directory(source_dir=source_dir,backup_dir=backup_dir_root_path,zip_filename=zip_filename_path,exclude_patterns=exclude_dirs)
            dst_file_size = os.path.getsize(zip_filename_path)
            bak_ins = RuyiBackup.objects.create(name=zip_filename,filename=zip_filename_path,size=dst_file_size,job_id=job_id,type=3)
            backup_counts = RuyiBackup.objects.filter(job_id=job_id).count()
            s_nums = backup_counts - settings_bk_counts
            if s_nums > 0:
                for i in range(0,s_nums):
                    old_file_ins = RuyiBackup.objects.filter(job_id=job_id).order_by("create_at").first()
                    if old_file_ins:
                        old_filename = old_file_ins.filename
                        r_old_filename = r'%s'%old_filename
                        if os.path.isfile(r_old_filename):
                            os.remove(r_old_filename)
                            taskloggers.info("【%s】已清理过期的备份文件：%s"%(job_name,old_filename))
                        old_file_ins.delete()
            if not os.path.exists(zip_filename_path):
                taskloggers.info("【%s】备份目录失败，未发现备份后压缩文件"%(job_name))
            else:
                taskloggers.info("【%s】备份目录成功，大小%s，备份后压缩文件：%s"%(job_name,format_size(dst_file_size),zip_filename_path))
            
            cron_ins = CrontabTask.objects.filter(job_id=job_id).first()
            if cron_ins:
                bak_ins.cron_id = cron_ins.id
                bak_ins.save()
            
    elif type == 4:#access_url
        result = access_url(obj.get("url"))
        status_text = "成功" if result["status"] else "失败"
        taskloggers.info("【%s】任务执行成功，访问URL%s,返回内容：\n%s"%(job_name,status_text,result['content']))
    else:
        pass
    taskloggers.info("------------------------【%s】任务结束------------------------"%job_name)

def installTask(job_id,job_func,func_args=[]):
    """
    @name 应用商店安装任务
    @author lybbn<2024-08-11>
    """
    # 创建一个 DateTrigger，设置为现在的时间
    trigger = DateTrigger(run_date=datetime.datetime.now())
    django_job = scheduler.add_job(job_func,trigger,id=job_id,args=func_args,max_instances=1,replace_existing=True,misfire_grace_time=1,coalesce=True)
    return django_job

def access_url(url):
    """
    @name 访问指定url
    @author lybbn<2024-02-08>
    """
    try:
        start_time = time.time()
        res = requests.get(url, timeout=3)
        res.encoding = 'utf-8'
        end_time = time.time()
        duration = str(int(round(end_time - start_time, 2) * 1000))#耗时，单位毫秒ms
        status = False
        if res.status_code == 200:
            status = True
        return {"status":status,"content":filter_xss1(res.text),"status_code":res.status_code,"duration": duration + "ms"}
    except Exception as e:
        return {"status":False,"content":str(e),"status_code":"","duration": "0ms"}

def backup_directory(source_dir,backup_dir,zip_filename=None,exclude_patterns=[]):
    """
    @name 备份目录并压缩
    @author lybbn<2024-02-08>
    @param exclude_patterns 排除目录或文件,支持通配符如 ：['file1.txt', 'dir1','*.log', 'temp_*', 'dir?', 'file[1-3].txt']
    """
    # 创建临时目录用于存放备份文件
    temp_dir = os.path.join(backup_dir, 'temp_backup_%s'%GetRandomSet(10).lower())
    # 备份目录
    shutil.copytree(source_dir, temp_dir,ignore=shutil.ignore_patterns(*exclude_patterns))

    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, temp_dir)
                zipf.write(file_path, rel_path)
    # 删除临时备份文件
    shutil.rmtree(temp_dir)

def func_zip(zip_filename,items,zip_type):
    """
    @name 压缩
    @author lybbn<2024-03-07>
    @param zip_filename 压缩后的文件名（含路径）
    @param items 需要压缩的文件或目录列表['/var/log/ruyi.log']
    @param zip_type 压缩类型(tar 格式.tar.gz、zip 格式 .zip)
    """
    if not items:
        raise ValueError("需要压缩的文件或目录不能为空")
    if zip_type == "zip":
        zip_directories_and_files(zip_filename,items)
    elif zip_type == "tar":
        create_tar_gz(zip_filename,items)
    else:
        raise ValueError("不支持的压缩格式")

def func_unzip(zip_filename,extract_path):
    """
    @name 解压
    @author lybbn<2024-03-07>
    @param zip_filename 压缩文件名（含路径）
    @param extract_path 需要解压的目标目录
    """
    if current_os == "windows":
        #解除占用
        from utils.server.windows import kill_cmd_if_working_dir
        kill_cmd_if_working_dir(extract_path)
    _, ext = os.path.splitext(zip_filename)
    if ext in ['.tar.gz','.tgz','.tar.bz2','.tbz']:
        with tarfile.open(zip_filename, 'r') as tar:
            tar.extractall(extract_path)
    elif ext == '.zip':
        with zipfile.ZipFile(zip_filename, 'r') as zipf:
            zipf.extractall(extract_path)
    else:
        raise ValueError("不支持的文件格式")

def zip_directories_and_files(zip_filename, items):
    with zipfile.ZipFile(zip_filename, 'w') as zipf:
        for item in items:
            if os.path.isfile(item):
                zipf.write(item, os.path.basename(item))
            elif os.path.isdir(item):
                for root, _, files in os.walk(item):
                    for file in files:
                        file_path = os.path.join(root, file)
                        zipf.write(file_path, os.path.relpath(file_path, os.path.dirname(item)))

def create_tar_gz(tar_filename, items):
    with tarfile.open(tar_filename, "w:gz") as tar:
        for item in items:
            if os.path.isfile(item):
                tar.add(item, arcname=os.path.basename(item))
            elif os.path.isdir(item):
                tar.add(item, arcname=os.path.basename(item))
                
def backupSite(site_id=None,backup_path=None,exclude_dirs=[],job_id=None):
    """
    @name 备份网站
    @author lybbn<2024-11-13>
    @param site_name 备份网站名称
    """
    s_ins = Sites.objects.filter(id=site_id).first()
    if not s_ins:return False,f"--id:{site_id} 站点不存在，已跳过"
    site_path = s_ins.path
    site_name = s_ins.name
    if not os.path.exists(site_path):return False,f"【{site_name}】站点路径不存在，已跳过"
    if not backup_path:
        backup_base_path = os.path.join(GetBackupPath(),"ruyitask","sites")
    else:
        backup_base_path = backup_path
    if not os.path.exists(backup_base_path):
        os.makedirs(backup_base_path)
    zip_filename = f"site_{site_name}_{time.strftime('%Y%m%d_%H%M%S',time.localtime())}_{GetRandomSet(5)}.zip"
    zip_filename_path = os.path.join(backup_base_path, zip_filename)
    backup_directory(source_dir=site_path,backup_dir=backup_base_path,zip_filename=zip_filename_path,exclude_patterns=exclude_dirs)
    if not os.path.exists(zip_filename_path):
        return False,f"备份网站{site_name}失败，未发现备份后压缩文件"
    else:
        dst_file_size = os.path.getsize(zip_filename_path)
        bak_ins = RuyiBackup.objects.create(name=zip_filename,filename=zip_filename_path,size=dst_file_size,job_id=job_id,type=2,fid=site_id)
        cron_ins = CrontabTask.objects.filter(job_id=job_id).first()
        if cron_ins:
            bak_ins.cron_id = cron_ins.id
            bak_ins.save()
        return True,f"{site_name}备份成功，大小{format_size(dst_file_size)}，备份后压缩文件：{zip_filename_path}"
    
    
def run_task(data,job_id=""):
    job = scheduler.get_job(job_id) 
    job.func(data,job_id)

def remove_task(job_id):
    scheduler.remove_job(job_id)

def pause_task(job_id):
    scheduler.pause_job(job_id)

def resume_task(job_id):
    scheduler.resume_job(job_id)

def start_scheduler():
    scheduler.add_jobstore(DjangoJobStore(), 'default')
    scheduler._logger = logger
    scheduler.start()
    executeNextTask()

def stop_scheduler():
    scheduler.shutdown(wait=False)