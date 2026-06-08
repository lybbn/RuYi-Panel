import os
import json
import time
import hashlib
import tarfile
import datetime
import psutil
from django.conf import settings
from rest_framework.permissions import IsAuthenticated
from utils.customView import CustomAPIView
from utils.jsonResponse import DetailResponse, ErrorResponse, SuccessResponse
from utils.common import (
    get_parameter_dic, format_size, GetBackupPath, GetRandomSet,
    ReadFile, WriteFile, DeleteDir, current_os
)
from utils.pagination import CustomPagination
from apps.sysbak.models import PanelBackup, BackupItemDetail, BackupSchedule
from apps.system.models import Sites, Databases, Config
from apps.systask.models import CrontabTask
from apps.sysshop.models import RySoftShop
from apps.syscloud.models import CloudStorageAccount
from apps.syslogs.logutil import RuyiAddOpLog
from apps.sysbak.backup_engine.manager import BackupOrchestrateManager
from apps.sysbak.tasks import run_backup_async, run_restore_async


def _get_panel_backup_base_path():
    backup_path = GetBackupPath()
    panel_backup_path = os.path.join(backup_path, 'panel_backup')
    if not os.path.exists(panel_backup_path):
        os.makedirs(panel_backup_path, exist_ok=True)
    return panel_backup_path


def _get_disk_free_space(path):
    try:
        usage = psutil.disk_usage(path)
        return usage.free
    except Exception:
        return 0


def _get_file_sha256(file_path):
    sha256_hash = hashlib.sha256()
    if not os.path.exists(file_path):
        return ''
    with open(file_path, 'rb') as f:
        for byte_block in iter(lambda: f.read(4096), b''):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def _get_cloud_accounts():
    accounts = CloudStorageAccount.objects.filter(status=0).values('id', 'name', 'provider')
    return list(accounts)


class PanelBackupManageView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        reqData = get_parameter_dic(request)
        action = reqData.get('action', '')

        if action == 'get_backup_list':
            return self._get_backup_list(request)

        elif action == 'get_backup_data_list':
            data = BackupOrchestrateManager.get_backup_data_list()
            cloud_accounts = _get_cloud_accounts()
            return DetailResponse(data={'data_list': data, 'cloud_accounts': cloud_accounts})

        elif action == 'get_disk_space':
            backup_path = GetBackupPath()
            free_space = _get_disk_free_space(backup_path)
            return DetailResponse(data={
                'free_space': free_space,
                'free_space_display': format_size(free_space),
                'backup_path': backup_path,
            })

        elif action == 'calculate_size':
            backup_config = reqData.get('backup_config', '{}')
            if isinstance(backup_config, str):
                try:
                    backup_config = json.loads(backup_config)
                except Exception:
                    backup_config = {}
            estimated_size = BackupOrchestrateManager.calculate_estimated_size(backup_config)
            backup_path = GetBackupPath()
            free_space = _get_disk_free_space(backup_path)
            return DetailResponse(data={
                'estimated_size': estimated_size,
                'estimated_size_display': format_size(estimated_size),
                'free_space': free_space,
                'free_space_display': format_size(free_space),
            })

        elif action == 'get_backup_detail':
            backup_id = reqData.get('id', '')
            ins = PanelBackup.objects.filter(id=backup_id).first()
            if not ins:
                return ErrorResponse(msg='备份记录不存在')
            data = self._format_backup_item(ins)
            try:
                backup_config = json.loads(ins.backup_config) if ins.backup_config else {}
                data['backup_config'] = backup_config
            except Exception:
                data['backup_config'] = {}
            # 获取备份项详情
            items = BackupItemDetail.objects.filter(backup_id=ins.id)
            data['items'] = [{
                'id': item.id,
                'module': item.module,
                'item_id': item.item_id,
                'item_name': item.item_name,
                'item_type': item.item_type,
                'status': item.status,
                'status_display': item.get_status_display(),
                'file_size': item.file_size,
                'error_msg': item.error_msg,
            } for item in items]
            return DetailResponse(data=data)

        elif action == 'get_backup_log':
            backup_id = reqData.get('id', '')
            ins = PanelBackup.objects.filter(id=backup_id).first()
            if not ins:
                return ErrorResponse(msg='备份记录不存在')
            return DetailResponse(data={
                'backup_log': ins.backup_log or '',
                'restore_log': ins.restore_log or '',
            })

        elif action == 'download_backup':
            backup_id = reqData.get('id', '')
            ins = PanelBackup.objects.filter(id=backup_id).first()
            if not ins:
                return ErrorResponse(msg='备份记录不存在')
            if not ins.file_path or not os.path.exists(ins.file_path):
                return ErrorResponse(msg='备份文件不存在')
            from django.http import FileResponse
            from django.utils.encoding import escape_uri_path
            file_size = os.path.getsize(ins.file_path)
            response = FileResponse(open(ins.file_path, 'rb'))
            response['content_type'] = "application/octet-stream"
            response['Content-Disposition'] = f'attachment;filename="{escape_uri_path(os.path.basename(ins.file_path))}"'
            response['Content-Length'] = file_size
            return response

        elif action == 'get_restore_detail':
            """获取还原详情 - 解析备份文件内容"""
            backup_id = reqData.get('id', '')
            ins = PanelBackup.objects.filter(id=backup_id).first()
            if not ins:
                return ErrorResponse(msg='备份记录不存在')
            if ins.backup_status != 2:
                return ErrorResponse(msg='只能还原已完成的备份')
            if not ins.file_path or not os.path.exists(ins.file_path):
                return ErrorResponse(msg='备份文件不存在')
            try:
                base_path = _get_panel_backup_base_path()
                extract_dir = os.path.join(base_path, f'preview_{ins.id}')
                with tarfile.open(ins.file_path, 'r:gz') as tar:
                    tar.extractall(extract_dir)
                backup_json_dirs = [d for d in os.listdir(extract_dir) if os.path.isdir(os.path.join(extract_dir, d))]
                if not backup_json_dirs:
                    return ErrorResponse(msg='备份文件格式错误')
                backup_dir = os.path.join(extract_dir, backup_json_dirs[0])
                backup_info_file = os.path.join(backup_dir, 'backup.json')
                if not os.path.exists(backup_info_file):
                    return ErrorResponse(msg='备份信息文件不存在')
                backup_info = json.loads(ReadFile(backup_info_file))
                data = {
                    'name': ins.name,
                    'file_size': ins.file_size,
                    'file_size_display': format_size(ins.file_size),
                    'create_at': ins.create_at.strftime('%Y-%m-%d %H:%M:%S') if ins.create_at else '',
                    'data_list': backup_info.get('data_list', {}),
                    'platform': backup_info.get('platform', {}),
                }
                return DetailResponse(data=data)
            except Exception as e:
                return ErrorResponse(msg=f'解析备份文件失败: {str(e)}')
            finally:
                if os.path.exists(extract_dir):
                    DeleteDir(extract_dir)

        return ErrorResponse(msg='参数错误')

    def post(self, request):
        reqData = get_parameter_dic(request)
        action = reqData.get('action', '')

        if action == 'create_backup':
            return self._create_backup(request)

        elif action == 'delete_backup':
            return self._delete_backup(request)

        elif action == 'batch_delete_backup':
            return self._batch_delete_backup(request)

        elif action == 'restore_backup':
            return self._restore_backup(request)

        elif action == 'upload_backup':
            return self._upload_backup(request)

        elif action == 'cancel_backup':
            return self._cancel_backup(request)

        return ErrorResponse(msg='参数错误')

    def _get_backup_list(self, request):
        queryset = PanelBackup.objects.all().order_by('-id')
        page_obj = CustomPagination()
        page_data = page_obj.paginate_queryset(queryset, request)
        data = []
        for ins in page_data:
            data.append(self._format_backup_item(ins))
        return page_obj.get_paginated_response(data)

    def _format_backup_item(self, ins):
        return {
            'id': ins.id,
            'name': ins.name,
            'store_type': ins.store_type,
            'store_type_display': ins.get_store_type_display(),
            'cloud_account_id': ins.cloud_account_id,
            'file_path': ins.file_path,
            'file_size': ins.file_size,
            'file_size_display': format_size(ins.file_size) if ins.file_size else '-',
            'file_sha256': ins.file_sha256,
            'backup_status': ins.backup_status,
            'backup_status_display': ins.get_backup_status_display(),
            'estimated_size': ins.estimated_size,
            'estimated_size_display': format_size(ins.estimated_size) if ins.estimated_size else '-',
            'error_msg': ins.error_msg,
            'done_time': ins.done_time.strftime('%Y-%m-%d %H:%M:%S') if ins.done_time else '',
            'total_time': ins.total_time,
            'create_at': ins.create_at.strftime('%Y-%m-%d %H:%M:%S') if ins.create_at else '',
            # 新增字段
            'backup_log': ins.backup_log,
            'restore_status': ins.restore_status,
            'restore_status_display': ins.get_restore_status_display(),
            'restore_done_time': ins.restore_done_time.strftime('%Y-%m-%d %H:%M:%S') if ins.restore_done_time else '',
            'restore_total_time': ins.restore_total_time,
            'backup_count_success': ins.backup_count_success,
            'backup_count_failed': ins.backup_count_failed,
            'is_encrypted': ins.is_encrypted,
            'is_scheduled': ins.is_scheduled,
            'exclude_dirs': ins.exclude_dirs,
            'pre_restore_backup_id': ins.pre_restore_backup_id,
        }

    def _create_backup(self, request):
        reqData = get_parameter_dic(request)
        backup_config = reqData.get('backup_config', '{}')
        if isinstance(backup_config, str):
            try:
                backup_config = json.loads(backup_config)
            except Exception:
                backup_config = {}
        store_type = reqData.get('store_type', 'local')
        cloud_account_id = reqData.get('cloud_account_id', '')
        exclude_dirs = reqData.get('exclude_dirs', '[]')
        if isinstance(exclude_dirs, str):
            try:
                exclude_dirs = json.loads(exclude_dirs)
            except Exception:
                exclude_dirs = []

        if store_type == 'cloud' and not cloud_account_id:
            return ErrorResponse(msg='请选择云存储账号')

        backup_data_list = []
        if backup_config.get('site_ids'):
            backup_data_list.append('site')
        if backup_config.get('db_ids'):
            backup_data_list.append('database')
        if backup_config.get('crontab_ids'):
            backup_data_list.append('crontab')
        if backup_config.get('firewall_ids'):
            backup_data_list.append('firewall')
        if backup_config.get('panel_config_ids'):
            backup_data_list.append('panel_config')
        if backup_config.get('terminal_config_ids'):
            backup_data_list.append('terminal_config')
        if backup_config.get('cluster_node_ids'):
            backup_data_list.append('cluster_nodes')
        if not backup_data_list:
            return ErrorResponse(msg='请至少选择一项备份数据')

        # 检查是否有正在执行的备份任务
        running_count = PanelBackup.objects.filter(backup_status=1).count()
        if running_count > 0:
            return ErrorResponse(msg='已有备份任务正在执行中，请等待完成后再创建')

        now = datetime.datetime.now()
        name = reqData.get('name', '') or f"备份-{now.strftime('%Y%m%d')}-{GetRandomSet(6)}"
        estimated_size = BackupOrchestrateManager.calculate_estimated_size(backup_config)

        ins = PanelBackup.objects.create(
            name=name,
            backup_data=json.dumps(backup_data_list),
            store_type=store_type,
            cloud_account_id=int(cloud_account_id) if cloud_account_id else None,
            backup_status=0,
            estimated_size=estimated_size,
            backup_config=json.dumps(backup_config),
            exclude_dirs=json.dumps(exclude_dirs),
        )

        # 异步执行备份
        run_backup_async(ins.id)

        RuyiAddOpLog(request, msg=f"【面板备份】- 创建备份：{name}", module="panelbackup")
        return DetailResponse(data={'id': ins.id}, msg='备份任务已创建，正在后台执行')

    def _delete_backup(self, request):
        reqData = get_parameter_dic(request)
        backup_id = reqData.get('id', '')
        if not backup_id:
            return ErrorResponse(msg='参数错误')
        ins = PanelBackup.objects.filter(id=backup_id).first()
        if not ins:
            return ErrorResponse(msg='备份记录不存在')
        if ins.backup_status == 1:
            return ErrorResponse(msg='备份进行中，无法删除')
        if ins.file_path and os.path.exists(ins.file_path):
            try:
                os.remove(ins.file_path)
            except Exception:
                pass
        ins.delete()
        RuyiAddOpLog(request, msg=f"【面板备份】- 删除备份：{ins.name}", module="panelbackup")
        return DetailResponse(msg='删除成功')

    def _batch_delete_backup(self, request):
        reqData = get_parameter_dic(request)
        ids = reqData.get('ids', [])
        if isinstance(ids, str):
            try:
                ids = json.loads(ids)
            except Exception:
                ids = [ids]
        if not ids:
            return ErrorResponse(msg='请选择要删除的备份')
        running_count = PanelBackup.objects.filter(id__in=ids, backup_status=1).count()
        if running_count > 0:
            return ErrorResponse(msg='选中的备份中有正在执行的任务，无法删除')
        backup_list = PanelBackup.objects.filter(id__in=ids)
        for ins in backup_list:
            if ins.file_path and os.path.exists(ins.file_path):
                try:
                    os.remove(ins.file_path)
                except Exception:
                    pass
        backup_list.delete()
        RuyiAddOpLog(request, msg=f"【面板备份】- 批量删除备份：{ids}", module="panelbackup")
        return DetailResponse(msg='批量删除成功')

    def _restore_backup(self, request):
        reqData = get_parameter_dic(request)
        backup_id = reqData.get('id', '')
        if not backup_id:
            return ErrorResponse(msg='参数错误')
        ins = PanelBackup.objects.filter(id=backup_id).first()
        if not ins:
            return ErrorResponse(msg='备份记录不存在')
        if ins.backup_status != 2:
            return ErrorResponse(msg='只能还原已完成的备份')
        if not ins.file_path or not os.path.exists(ins.file_path):
            return ErrorResponse(msg='备份文件不存在')

        # 检查是否有正在执行的还原任务
        running_count = PanelBackup.objects.filter(restore_status=1).count()
        if running_count > 0:
            return ErrorResponse(msg='已有还原任务正在执行中，请等待完成后再操作')

        restore_config = reqData.get('restore_config', '{}')
        if isinstance(restore_config, str):
            try:
                restore_config = json.loads(restore_config)
            except Exception:
                restore_config = {}
        conflict_strategy = reqData.get('conflict_strategy', 'skip')

        # 还原前自动备份（P0-7）
        pre_backup_id = self._create_pre_restore_backup(request)
        if pre_backup_id:
            PanelBackup.objects.filter(id=backup_id).update(pre_restore_backup_id=pre_backup_id)

        # 异步执行还原
        run_restore_async(backup_id, restore_config, conflict_strategy)

        RuyiAddOpLog(request, msg=f"【面板备份】- 还原备份：{ins.name}", module="panelbackup")
        return DetailResponse(data={'id': backup_id}, msg='还原任务已创建，正在后台执行')

    def _create_pre_restore_backup(self, request):
        """还原前自动创建当前状态备份"""
        try:
            from apps.system.models import TerminalServer, CommonCommands
            from apps.sysnode.models import ClusterNode
            now = datetime.datetime.now()
            name = f"还原前备份-{now.strftime('%Y%m%d-%H%M')}"
            terminal_config_ids = [ts.id for ts in TerminalServer.objects.all()]
            terminal_config_ids += [f'cmd_{cc.id}' for cc in CommonCommands.objects.all()]
            cluster_node_ids = list(ClusterNode.objects.values_list('id', flat=True))
            ins = PanelBackup.objects.create(
                name=name,
                backup_data='["site","database","crontab","firewall","panel_config","terminal_config","cluster_nodes"]',
                store_type='local',
                backup_status=0,
                backup_config=json.dumps({
                    'site_ids': list(Sites.objects.values_list('id', flat=True)),
                    'db_ids': list(Databases.objects.values_list('id', flat=True)),
                    'crontab_ids': list(CrontabTask.objects.filter(is_sys=False).values_list('id', flat=True)),
                    'firewall_ids': ['firewall_rules'],
                    'panel_config_ids': ['panel_settings', 'security_path'],
                    'terminal_config_ids': terminal_config_ids,
                    'cluster_node_ids': cluster_node_ids,
                }),
            )
            run_backup_async(ins.id)
            return ins.id
        except Exception:
            return None

    def _cancel_backup(self, request):
        """取消备份任务（仅标记状态）"""
        reqData = get_parameter_dic(request)
        backup_id = reqData.get('id', '')
        ins = PanelBackup.objects.filter(id=backup_id, backup_status=1).first()
        if not ins:
            return ErrorResponse(msg='未找到正在执行的备份任务')
        # 标记为失败（实际线程无法中断，但状态会阻止后续操作）
        PanelBackup.objects.filter(id=backup_id).update(
            backup_status=3, error_msg='用户手动取消'
        )
        return DetailResponse(msg='已标记取消')

    def _upload_backup(self, request):
        upload_file = request.FILES.get('file', None)
        if not upload_file:
            return ErrorResponse(msg='请选择要上传的备份文件')
        if not upload_file.name.endswith('.tar.gz'):
            return ErrorResponse(msg='仅支持.tar.gz格式的备份文件')
        base_path = _get_panel_backup_base_path()
        file_path = os.path.join(base_path, upload_file.name)
        with open(file_path, 'wb+') as destination:
            for chunk in upload_file.chunks():
                destination.write(chunk)
        file_size = os.path.getsize(file_path)
        file_sha256 = _get_file_sha256(file_path)
        now = datetime.datetime.now()
        name = f"上传备份-{now.strftime('%Y%m%d')}-{GetRandomSet(4)}"
        ins = PanelBackup.objects.create(
            name=name,
            backup_data='[]',
            store_type='local',
            file_path=file_path,
            file_size=file_size,
            file_sha256=file_sha256,
            backup_status=2,
            done_time=now,
            total_time=0,
        )
        RuyiAddOpLog(request, msg=f"【面板备份】- 上传备份文件：{upload_file.name}", module="panelbackup")
        return DetailResponse(data={'id': ins.id}, msg='上传成功')


class BackupScheduleManageView(CustomAPIView):
    """备份计划管理"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        reqData = get_parameter_dic(request)
        action = reqData.get('action', '')

        if action == 'list':
            queryset = BackupSchedule.objects.all().order_by('-id')
            page_obj = CustomPagination()
            page_data = page_obj.paginate_queryset(queryset, request)
            data = []
            for ins in page_data:
                data.append({
                    'id': ins.id,
                    'name': ins.name,
                    'schedule_type': ins.schedule_type,
                    'schedule_type_display': ins.get_schedule_type_display(),
                    'schedule_config': ins.schedule_config,
                    'backup_config': ins.backup_config,
                    'store_type': ins.store_type,
                    'cloud_account_id': ins.cloud_account_id,
                    'keep_count': ins.keep_count,
                    'is_enabled': ins.is_enabled,
                    'last_run_time': ins.last_run_time.strftime('%Y-%m-%d %H:%M:%S') if ins.last_run_time else '',
                    'create_at': ins.create_at.strftime('%Y-%m-%d %H:%M:%S') if ins.create_at else '',
                })
            return page_obj.get_paginated_response(data)

        return ErrorResponse(msg='参数错误')

    def post(self, request):
        reqData = get_parameter_dic(request)
        action = reqData.get('action', '')

        if action == 'create':
            return self._create_schedule(request)
        elif action == 'update':
            return self._update_schedule(request)
        elif action == 'delete':
            return self._delete_schedule(request)
        elif action == 'toggle':
            return self._toggle_schedule(request)

        return ErrorResponse(msg='参数错误')

    def _create_schedule(self, request):
        reqData = get_parameter_dic(request)
        name = reqData.get('name', '')
        if not name:
            return ErrorResponse(msg='请输入计划名称')
        schedule_type = reqData.get('schedule_type', 'daily')
        schedule_config = reqData.get('schedule_config', '{}')
        backup_config = reqData.get('backup_config', '{}')
        store_type = reqData.get('store_type', 'local')
        cloud_account_id = reqData.get('cloud_account_id', '')
        keep_count = int(reqData.get('keep_count', 3))

        ins = BackupSchedule.objects.create(
            name=name,
            schedule_type=schedule_type,
            schedule_config=schedule_config if isinstance(schedule_config, str) else json.dumps(schedule_config),
            backup_config=backup_config if isinstance(backup_config, str) else json.dumps(backup_config),
            store_type=store_type,
            cloud_account_id=int(cloud_account_id) if cloud_account_id else None,
            keep_count=keep_count,
        )

        # 创建关联的 CrontabTask 和 APScheduler 任务
        try:
            from apps.systask.views.crontab_task import scheduler, cronTask, resolvingCron
            from utils.common import make_uuid

            cron_req = self._build_cron_request(ins)
            cron_res = resolvingCron(cron_req)
            job_id = make_uuid()
            django_job = scheduler.add_job(
                cronTask, 'cron', id=job_id,
                second=cron_res.get("second", "*"),
                minute=cron_res.get("minute", "*"),
                hour=cron_res.get("hour", "*"),
                day=cron_res.get("day", "*"),
                month=cron_res.get("month", "*"),
                week=cron_res.get("week", "*"),
                args=[cron_req, job_id],
                max_instances=1, replace_existing=True,
                misfire_grace_time=3600, coalesce=True,
            )

            from apps.systask.models import CrontabTask
            cron_task = CrontabTask.objects.create(
                name=f'[备份计划] {name}',
                type=0,
                period_type=self._get_period_type(schedule_type),
                hour=cron_res.get("hour", "*"),
                minute=cron_res.get("minute", "0"),
                day=cron_res.get("day", "*"),
                month=cron_res.get("month", "*"),
                week=cron_res.get("week", "*"),
                job_id=django_job.id,
                status=True,
                is_sys=True,
                shell_body=f'backup_schedule:{ins.id}',
            )
            ins.cron_task = cron_task
            ins.save()
        except Exception as e:
            pass

        RuyiAddOpLog(request, msg=f"【备份计划】- 创建计划：{name}", module="panelbackup")
        return DetailResponse(data={'id': ins.id}, msg='创建成功')

    def _build_cron_request(self, schedule_ins):
        """构建 CrontabTask 所需的请求参数"""
        config = json.loads(schedule_ins.schedule_config) if isinstance(schedule_ins.schedule_config, str) else schedule_ins.schedule_config
        period_type = self._get_period_type(schedule_ins.schedule_type)
        return {
            'type': 0,
            'period_type': period_type,
            'hour': config.get('hour', '2'),
            'minute': config.get('minute', '0'),
            'day': config.get('day', '*'),
            'month': config.get('month', '*'),
            'week': config.get('week', '*'),
            'name': f'[备份计划] {schedule_ins.name}',
            'shell_body': f'backup_schedule:{schedule_ins.id}',
        }

    def _get_period_type(self, schedule_type):
        """将 BackupSchedule 的 schedule_type 映射为 CrontabTask 的 period_type"""
        mapping = {
            'daily': 1,
            'weekly': 2,
            'monthly': 3,
        }
        return mapping.get(schedule_type, 1)

    def _update_schedule(self, request):
        reqData = get_parameter_dic(request)
        schedule_id = reqData.get('id', '')
        ins = BackupSchedule.objects.filter(id=schedule_id).first()
        if not ins:
            return ErrorResponse(msg='计划不存在')
        if reqData.get('name'):
            ins.name = reqData['name']
        if reqData.get('schedule_type'):
            ins.schedule_type = reqData['schedule_type']
        if reqData.get('schedule_config'):
            ins.schedule_config = reqData['schedule_config'] if isinstance(reqData['schedule_config'], str) else json.dumps(reqData['schedule_config'])
        if reqData.get('backup_config'):
            ins.backup_config = reqData['backup_config'] if isinstance(reqData['backup_config'], str) else json.dumps(reqData['backup_config'])
        if reqData.get('store_type'):
            ins.store_type = reqData['store_type']
        if reqData.get('keep_count'):
            ins.keep_count = int(reqData['keep_count'])
        ins.save()
        RuyiAddOpLog(request, msg=f"【备份计划】- 更新计划：{ins.name}", module="panelbackup")
        return DetailResponse(msg='更新成功')

    def _delete_schedule(self, request):
        reqData = get_parameter_dic(request)
        schedule_id = reqData.get('id', '')
        ins = BackupSchedule.objects.filter(id=schedule_id).first()
        if not ins:
            return ErrorResponse(msg='计划不存在')
        # 清理关联的 CrontabTask 和 APScheduler 任务
        try:
            if ins.cron_task:
                from apps.systask.views.crontab_task import scheduler
                job = scheduler.get_job(ins.cron_task.job_id)
                if job:
                    scheduler.remove_job(ins.cron_task.job_id)
                ins.cron_task.delete()
        except Exception:
            pass
        ins.delete()
        RuyiAddOpLog(request, msg=f"【备份计划】- 删除计划", module="panelbackup")
        return DetailResponse(msg='删除成功')

    def _toggle_schedule(self, request):
        reqData = get_parameter_dic(request)
        schedule_id = reqData.get('id', '')
        ins = BackupSchedule.objects.filter(id=schedule_id).first()
        if not ins:
            return ErrorResponse(msg='计划不存在')
        ins.is_enabled = not ins.is_enabled
        ins.save()
        # 暂停/恢复 APScheduler 任务
        try:
            if ins.cron_task:
                from apps.systask.views.crontab_task import scheduler
                from apps.systask.tasks import pause_task, resume_task
                if ins.is_enabled:
                    resume_task(ins.cron_task.job_id)
                else:
                    pause_task(ins.cron_task.job_id)
        except Exception:
            pass
        return DetailResponse(data={'is_enabled': ins.is_enabled}, msg='操作成功')
