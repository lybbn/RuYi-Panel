#!/bin/python
#coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板
# +-------------------------------------------------------------------
# | Copyright (c) 如意面板 All rights reserved.
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------

import json
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from datetime import datetime, timedelta, date
from utils.viewset import CustomModelViewSet
from utils.customView import CustomAPIView
from utils.jsonResponse import SuccessResponse, DetailResponse, ErrorResponse
from apps.syswaf.models import (
    WafAttackLog, WafReport, WafReportSchedule
)
from apps.syswaf.serializers import (
    WafReportSerializer, WafReportScheduleSerializer
)
from apps.syslogs.logutil import RuyiAddOpLog


def _generate_report_data(date_start, date_end):
    """根据日期范围生成报表数据"""
    logs = WafAttackLog.objects.filter(
        create_at__date__gte=date_start,
        create_at__date__lte=date_end
    )

    attack_count = logs.count()
    block_count = logs.filter(action_taken='block').count()
    unique_ip_count = logs.values('src_ip').distinct().count()

    top_ips = list(logs.values('src_ip', 'src_location').annotate(
        count=Count('id')
    ).order_by('-count')[:10])

    attack_types = list(logs.values('attack_type').annotate(
        count=Count('id')
    ).order_by('-count')[:10])

    severity_breakdown = list(logs.values('severity').annotate(
        count=Count('id')
    ).order_by('-count'))

    trend_data = list(logs.annotate(
        date=TruncDate('create_at')
    ).values('date').annotate(
        count=Count('id'),
        blocked=Count('id', filter=Q(action_taken='block'))
    ).order_by('date'))
    for item in trend_data:
        if item.get('date'):
            item['date'] = item['date'].isoformat()

    return {
        'attack_count': attack_count,
        'block_count': block_count,
        'unique_ip_count': unique_ip_count,
        'top_ips': json.dumps(top_ips, ensure_ascii=False, default=str),
        'attack_types': json.dumps(attack_types, ensure_ascii=False, default=str),
        'severity_breakdown': json.dumps(severity_breakdown, ensure_ascii=False, default=str),
        'trend_data': json.dumps(trend_data, ensure_ascii=False, default=str),
    }


class WafReportViewSet(CustomModelViewSet):
    """
    WAF安全报表CRUD
    """
    queryset = WafReport.objects.all()
    serializer_class = WafReportSerializer
    filterset_fields = ('report_type', 'status', 'created_by')
    search_fields = ('name',)
    ordering_fields = ('create_at', 'attack_count')

    def get_queryset(self):
        queryset = super().get_queryset()
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(date_start__gte=start_date)
        if end_date:
            queryset = queryset.filter(date_end__lte=end_date)
        return queryset

    def _parse_date(self, date_str):
        """解析日期字符串，支持多种格式"""
        if not date_str:
            return None
        if isinstance(date_str, date):
            return date_str
        if isinstance(date_str, datetime):
            return date_str.date()
        try:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
        except (ValueError, AttributeError):
            pass
        for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d'):
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        raise ValueError(f"无法解析日期格式: {date_str}")

    def create(self, request, *args, **kwargs):
        name = request.data.get('name', '')
        report_type = request.data.get('report_type', 'daily')
        date_start = request.data.get('date_start')
        date_end = request.data.get('date_end')
        export_format = request.data.get('format', 'html')

        if not date_start or not date_end:
            today = date.today()
            if report_type == 'daily':
                date_start = today
                date_end = today
            elif report_type == 'weekly':
                date_start = today - timedelta(days=7)
                date_end = today
            elif report_type == 'monthly':
                date_start = today - timedelta(days=30)
                date_end = today
            else:
                return ErrorResponse(msg="自定义报表需要指定日期范围")

        try:
            if isinstance(date_start, str):
                date_start = self._parse_date(date_start)
            if isinstance(date_end, str):
                date_end = self._parse_date(date_end)
        except ValueError as e:
            return ErrorResponse(msg=str(e))

        if not name:
            type_names = {'daily': '日报', 'weekly': '周报', 'monthly': '月报', 'custom': '报表'}
            name = f"{date_start.strftime('%Y年%m月%d日')}安全{type_names.get(report_type, '报表')}"

        report_data = _generate_report_data(date_start, date_end)

        report = WafReport.objects.create(
            name=name,
            report_type=report_type,
            date_start=date_start,
            date_end=date_end,
            status='completed',
            format=export_format,
            created_by='manual',
            **report_data
        )

        RuyiAddOpLog(request, msg=f"【WAF防护】-【报表中心】生成报表: {name}", module="wafmg")
        serializer = self.get_serializer(report)
        return DetailResponse(data=serializer.data, msg="报表生成成功")

    @action(methods=['POST'], detail=True)
    def download(self, request, pk=None):
        instance = self.get_object()
        instance.download_count += 1
        instance.save()
        return DetailResponse(data={
            'report': self.get_serializer(instance).data
        }, msg="获取报表数据成功")

    @action(methods=['GET'], detail=False)
    def stats(self, request):
        total_reports = WafReport.objects.count()
        today = date.today()
        month_start = today.replace(day=1)
        monthly_reports = WafReport.objects.filter(create_at__date__gte=month_start).count()
        scheduled_count = WafReportSchedule.objects.filter(is_enabled=True).count()
        total_downloads = WafReport.objects.aggregate(total=Count('download_count'))['total'] or 0

        return DetailResponse(data={
            'total_reports': total_reports,
            'monthly_reports': monthly_reports,
            'scheduled_reports': scheduled_count,
            'download_count': total_downloads,
        })


class WafReportScheduleViewSet(CustomModelViewSet):
    """
    WAF定时报表CRUD
    """
    queryset = WafReportSchedule.objects.all()
    serializer_class = WafReportScheduleSerializer
    filterset_fields = ('report_type', 'is_enabled')
    search_fields = ('name',)

    def create(self, request, *args, **kwargs):
        result = super().create(request, *args, **kwargs)
        RuyiAddOpLog(request, msg="【WAF防护】-【定时报表】新增", module="wafmg")
        return result

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        name = instance.name
        result = super().update(request, *args, **kwargs)
        RuyiAddOpLog(request, msg=f"【WAF防护】-【定时报表】更新 {name}", module="wafmg")
        return result

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        name = instance.name
        result = super().destroy(request, *args, **kwargs)
        RuyiAddOpLog(request, msg=f"【WAF防护】-【定时报表】删除 {name}", module="wafmg")
        return result

    @action(methods=['POST'], detail=True)
    def toggle(self, request, pk=None):
        instance = self.get_object()
        instance.is_enabled = not instance.is_enabled
        instance.save()
        status_text = "启用" if instance.is_enabled else "禁用"
        RuyiAddOpLog(request, msg=f"【WAF防护】-【定时报表】{instance.name} {status_text}", module="wafmg")
        return DetailResponse(msg=f"定时报表已{status_text}")

    @action(methods=['POST'], detail=True)
    def run_now(self, request, pk=None):
        """立即执行定时报表"""
        instance = self.get_object()
        today = date.today()

        if instance.report_type == 'daily':
            date_start = today - timedelta(days=1)
            date_end = today - timedelta(days=1)
        elif instance.report_type == 'weekly':
            date_start = today - timedelta(days=7)
            date_end = today - timedelta(days=1)
        elif instance.report_type == 'monthly':
            date_start = today.replace(day=1) - timedelta(days=1)
            date_start = date_start.replace(day=1)
            date_end = today - timedelta(days=1)
        else:
            date_start = today - timedelta(days=1)
            date_end = today - timedelta(days=1)

        report_data = _generate_report_data(date_start, date_end)
        type_names = {'daily': '日报', 'weekly': '周报', 'monthly': '月报'}
        name = f"{date_start.strftime('%Y年%m月%d日')}安全{type_names.get(instance.report_type, '报表')}"

        report = WafReport.objects.create(
            name=name,
            report_type=instance.report_type,
            date_start=date_start,
            date_end=date_end,
            status='completed',
            created_by='scheduled',
            **report_data
        )

        instance.last_run = datetime.now()
        instance.run_count += 1
        instance.save()

        notify_channels = instance.get_notify_channels()
        if notify_channels:
            try:
                from apps.sysalert.models import AlertTask
                from apps.sysalert.notify import send_alert

                task = AlertTask.objects.filter(task_type='waf_attack', is_enabled=True).first()
                if task:
                    content = (
                        f"[WAF安全报表]\n"
                        f"报表: {name}\n"
                        f"统计周期: {date_start} ~ {date_end}\n"
                        f"攻击总数: {report_data['attack_count']}\n"
                        f"拦截数: {report_data['block_count']}\n"
                        f"独立攻击IP: {report_data['unique_ip_count']}"
                    )
                    send_alert(task, content)
            except Exception:
                pass

        RuyiAddOpLog(request, msg=f"【WAF防护】-【定时报表】手动执行: {instance.name}", module="wafmg")
        return DetailResponse(data={
            'report_id': report.id
        }, msg=f"报表 {name} 已生成")
