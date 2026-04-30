#!/bin/python
#coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2025-02-25
# +-------------------------------------------------------------------
# | EditDate: 2025-02-25
# +-------------------------------------------------------------------

# ------------------------------
# Fail2Ban管理
# ------------------------------
import os
import re
import json
from datetime import datetime, timedelta
from utils.customView import CustomAPIView
from utils.common import get_parameter_dic, current_os, ReadFile, WriteFile
from utils.jsonResponse import ErrorResponse, DetailResponse, SuccessResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from utils.install.fail2ban import (
    get_fail2ban_path_info, get_fail2ban_status, is_fail2ban_installed,
    Start_Fail2Ban, Stop_Fail2Ban, Restart_Fail2Ban, Reload_Fail2Ban,
    Get_Fail2Ban_Jails, Get_Fail2Ban_Jail_Status, Get_Fail2Ban_Banned_IPs, Get_Fail2Ban_Banned_IPs_With_Details,
    Ban_IP, Unban_IP, Read_Jail_Config, Write_Jail_Config,
    Toggle_Jail, Set_Jail_Config, Get_Ignore_IP_List, Add_Ignore_IP, Remove_Ignore_IP
)
from utils.ip_util import IPQQwry
from apps.syslogs.logutil import RuyiAddOpLog

def _is_linux():
    return current_os != 'windows'

def _parse_time_value(value):
    """解析时间值，支持 1h, 10m, 3600s 等格式，返回秒数"""
    if not value:
        return 0
    
    value = str(value).strip()
    
    # 如果是纯数字，直接返回
    if value.isdigit():
        return int(value)
    
    # 解析带单位的格式
    match = re.match(r'^(\d+)\s*([smhdw])$', value.lower())
    if match:
        num = int(match.group(1))
        unit = match.group(2)
        multipliers = {
            's': 1,           # 秒
            'm': 60,          # 分钟
            'h': 3600,        # 小时
            'd': 86400,       # 天
            'w': 604800       # 周
        }
        return num * multipliers.get(unit, 1)
    
    # 尝试直接转换
    try:
        return int(value)
    except ValueError:
        return 0

def _parse_jail_config():
    config_content = Read_Jail_Config()
    if not config_content:
        return {}
    
    config = {
        'default': {},
        'jails': {}
    }
    
    current_section = None
    # 统一换行符并分割
    lines = config_content.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        
        section_match = re.match(r'\[([\w\-]+)\]', line)
        if section_match:
            current_section = section_match.group(1)
            if current_section not in config['jails'] and current_section != 'DEFAULT':
                config['jails'][current_section] = {}
            continue
        
        if current_section and '=' in line:
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip()
            target = config['default'] if current_section == 'DEFAULT' else config['jails'].get(current_section, {})
            target[key] = value
    
    return config

def _get_banned_list_with_details():
    jails = Get_Fail2Ban_Jails()
    banned_data = []
    
    for jail in jails:
        ips = Get_Fail2Ban_Banned_IPs(jail)
        for ip in ips:
            banned_data.append({
                'ip': ip,
                'jail': jail,
                'ban_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
    
    return banned_data

def _get_banned_list_with_details():
    """获取封禁列表，包含剩余时间和IP归属地"""
    jails = Get_Fail2Ban_Jails()
    banned_data = []
    
    # 初始化IP归属地查询工具
    ip_qqwry = IPQQwry()
    
    for jail in jails:
        details = Get_Fail2Ban_Banned_IPs_With_Details(jail)
        for item in details:
            # 将时间戳转换为可读格式
            ban_time_ts = item.get('ban_time', 0)
            if ban_time_ts > 0:
                ban_time_str = datetime.fromtimestamp(ban_time_ts).strftime('%Y-%m-%d %H:%M:%S')
            else:
                ban_time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 查询IP归属地
            location = ip_qqwry.lookup(item['ip'])
            location_parts = location.split('–') if location else ['', '']
            country = location_parts[0] if len(location_parts) > 0 else ''
            province = location_parts[1] if len(location_parts) > 1 else ''
            city = location_parts[2] if len(location_parts) > 2 else ''
            
            # 格式化归属地显示
            if country and province and city and city != '未知':
                location_str = f"{country} {province} {city}"
            elif country and province and province != '未知':
                location_str = f"{country} {province}"
            elif country and country != '未知':
                location_str = country
            else:
                location_str = '未知'
            
            banned_data.append({
                'ip': item['ip'],
                'jail': item['jail'],
                'ban_time': ban_time_str,
                'remaining_time': item['remaining_time'],
                'location': location_str,
                'country': country,
                'province': province,
                'city': city
            })
    
    return banned_data

def _format_remaining_time(seconds):
    """格式化剩余时间为可读字符串"""
    if seconds <= 0:
        return '即将解封'
    
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    if days > 0:
        return f'{days}天{hours}小时'
    elif hours > 0:
        return f'{hours}小时{minutes}分钟'
    elif minutes > 0:
        return f'{minutes}分钟{secs}秒'
    else:
        return f'{secs}秒'

def _parse_fail2ban_log(limit=100):
    log_path = '/var/log/fail2ban.log'
    if not os.path.exists(log_path):
        return []
    
    try:
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()[-limit:]
        
        logs = []
        for line in lines:
            log_entry = _parse_log_line(line)
            if log_entry:
                logs.append(log_entry)
        
        return logs
    except:
        return []

def _parse_log_line(line):
    patterns = [
        (r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+).*\[(\w+)\].*Ban\s+([\d.]+)', 'ban'),
        (r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+).*\[(\w+)\].*Unban\s+([\d.]+)', 'unban'),
        (r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+).*\[(\w+)\].*Found\s+([\d.]+)', 'found'),
        (r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+).*\[(\w+)\].*NOTICE\s+(.+)', 'notice'),
    ]
    
    for pattern, action_type in patterns:
        match = re.search(pattern, line)
        if match:
            groups = match.groups()
            return {
                'time': groups[0],
                'jail': groups[1],
                'action': action_type,
                'ip': groups[2] if len(groups) > 2 else '',
                'raw': line.strip()
            }
    
    return None

def _get_jail_type(jail_name):
    """根据 jail 名称判断类型"""
    if jail_name.startswith('sshd'):
        return 'ssh'
    elif jail_name.startswith('mysqld'):
        return 'mysql'
    return 'other'

def _get_jail_stats():
    # 从配置文件获取所有 jail 配置
    config = _parse_jail_config()
    config_jails = config.get('jails', {})
    
    # 从运行状态获取当前活跃的 jail
    active_jails = Get_Fail2Ban_Jails()
    active_jails_set = set(active_jails)
    
    stats = []
    
    # 合并配置文件和运行状态的 jail
    all_jails = set(config_jails.keys()) | active_jails_set
    
    for jail in all_jails:
        jail_config = config_jails.get(jail, {})
        is_active = jail in active_jails_set
        
        currently_failed = 0
        total_failed = 0
        currently_banned = 0
        total_banned = 0
        
        # 如果 jail 正在运行，获取实时统计
        if is_active:
            status_output = Get_Fail2Ban_Jail_Status(jail)
            if status_output:
                cf_match = re.search(r'Currently failed:\s*(\d+)', status_output)
                if cf_match:
                    currently_failed = int(cf_match.group(1))
                
                tf_match = re.search(r'Total failed:\s*(\d+)', status_output)
                if tf_match:
                    total_failed = int(tf_match.group(1))
                
                cb_match = re.search(r'Currently banned:\s*(\d+)', status_output)
                if cb_match:
                    currently_banned = int(cb_match.group(1))
                
                tb_match = re.search(r'Total banned:\s*(\d+)', status_output)
                if tb_match:
                    total_banned = int(tb_match.group(1))
        
        # 从配置文件中读取配置
        enabled = jail_config.get('enabled', 'false').lower() == 'true'
        maxretry = int(jail_config.get('maxretry', 5))
        bantime = _parse_time_value(jail_config.get('bantime', 3600))
        findtime = _parse_time_value(jail_config.get('findtime', 600))
        
        # 判断 jail 类型并设置默认端口
        jail_type = _get_jail_type(jail)
        if jail_type == 'ssh':
            default_port = '22'
        elif jail_type == 'mysql':
            default_port = '3306'
        else:
            default_port = ''
        
        port = jail_config.get('port', default_port)
        filter_name = jail_config.get('filter', 'sshd' if jail_type == 'ssh' else 'mysqld-auth')
        
        stats.append({
            'name': jail,
            'type': jail_type,
            'currently_failed': currently_failed,
            'total_failed': total_failed,
            'currently_banned': currently_banned,
            'total_banned': total_banned,
            'enabled': enabled,
            'maxretry': maxretry,
            'bantime': bantime,
            'findtime': findtime,
            'port': port,
            'filter': filter_name
        })
    
    return stats

class RYFail2BanManageView(CustomAPIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        if not _is_linux():
            return ErrorResponse(msg='当前系统不支持')
        
        req = get_parameter_dic(request)
        action = req.get('action', 'overview')
        
        if action == 'overview':
            status = get_fail2ban_status()
            jails = _get_jail_stats() if status['running'] else []
            banned_count = sum(j['currently_banned'] for j in jails)
            
            data = {
                'installed': status['installed'],
                'running': status['running'],
                'version': status['version'],
                'jails': jails,
                'banned_count': banned_count,
            }
            return DetailResponse(data=data)
        
        if action == 'jails':
            jails = _get_jail_stats()
            return DetailResponse(data=jails)
        
        if action == 'banned':
            page = int(req.get('page', 1))
            limit = int(req.get('limit', 20))
            jail = req.get('jail', '')
            
            banned_list = _get_banned_list_with_details()
            
            if jail:
                banned_list = [b for b in banned_list if b['jail'] == jail]
            
            # 格式化剩余时间
            for item in banned_list:
                item['remaining_time_formatted'] = _format_remaining_time(item.get('remaining_time', 0))
            
            total = len(banned_list)
            start = (page - 1) * limit
            end = start + limit
            page_data = banned_list[start:end]
            
            return SuccessResponse(data=page_data, page=page, limit=limit, total=total)
        
        if action == 'logs':
            limit = int(req.get('limit', 100))
            logs = _parse_fail2ban_log(limit)
            return DetailResponse(data=logs)
        
        if action == 'config':
            config = Read_Jail_Config()
            return DetailResponse(data={'config': config})
        
        if action == 'ignoreip':
            ips = Get_Ignore_IP_List()
            return DetailResponse(data=ips)
        
        return ErrorResponse(msg='类型错误')
    
    def post(self, request):
        if not _is_linux():
            return ErrorResponse(msg='当前系统不支持')
        
        req = get_parameter_dic(request)
        action = req.get('action', '')
        
        if not is_fail2ban_installed():
            return ErrorResponse(msg='Fail2Ban未安装，请先在应用商店安装')
        
        if action == 'start':
            try:
                Start_Fail2Ban()
                RuyiAddOpLog(request, msg="【工具箱】-【Fail2Ban】- 启动服务", module='tools')
                return DetailResponse(msg='启动成功')
            except Exception as e:
                return ErrorResponse(msg=str(e))
        
        if action == 'stop':
            try:
                Stop_Fail2Ban()
                RuyiAddOpLog(request, msg="【工具箱】-【Fail2Ban】- 停止服务", module='tools')
                return DetailResponse(msg='停止成功')
            except Exception as e:
                return ErrorResponse(msg=str(e))
        
        if action == 'restart':
            try:
                Restart_Fail2Ban()
                RuyiAddOpLog(request, msg="【工具箱】-【Fail2Ban】- 重启服务", module='tools')
                return DetailResponse(msg='重启成功')
            except Exception as e:
                return ErrorResponse(msg=str(e))
        
        if action == 'reload':
            try:
                Reload_Fail2Ban()
                RuyiAddOpLog(request, msg="【工具箱】-【Fail2Ban】- 重载配置", module='tools')
                return DetailResponse(msg='重载成功')
            except Exception as e:
                return ErrorResponse(msg=str(e))
        
        if action == 'ban':
            ip = req.get('ip', '')
            jail = req.get('jail', 'sshd')
            if not ip:
                return ErrorResponse(msg='IP地址不能为空')
            
            if Ban_IP(ip, jail):
                RuyiAddOpLog(request, msg=f"【工具箱】-【Fail2Ban】- 手动封禁IP: {ip}", module='tools')
                return DetailResponse(msg='封禁成功')
            return ErrorResponse(msg='封禁失败')
        
        if action == 'unban':
            ip = req.get('ip', '')
            jail = req.get('jail', 'sshd')
            if not ip:
                return ErrorResponse(msg='IP地址不能为空')
            
            if Unban_IP(ip, jail):
                RuyiAddOpLog(request, msg=f"【工具箱】-【Fail2Ban】- 解封IP: {ip}", module='tools')
                return DetailResponse(msg='解封成功')
            return ErrorResponse(msg='解封失败')
        
        if action == 'save_config':
            config = req.get('config', '')
            if not config:
                return ErrorResponse(msg='配置内容不能为空')
            
            try:
                Write_Jail_Config(config)
                RuyiAddOpLog(request, msg="【工具箱】-【Fail2Ban】- 保存配置", module='tools')
                return DetailResponse(msg='保存成功')
            except Exception as e:
                return ErrorResponse(msg=str(e))
        
        if action == 'toggle_jail':
            jail = req.get('jail', '')
            enabled = req.get('enabled', False)
            if not jail:
                return ErrorResponse(msg='Jail名称不能为空')
            
            if Toggle_Jail(jail, enabled):
                status = '启用' if enabled else '禁用'
                RuyiAddOpLog(request, msg=f"【工具箱】-【Fail2Ban】- {status}防护: {jail}", module='tools')
                return DetailResponse(msg=f'{status}成功')
            return ErrorResponse(msg='操作失败')
        
        if action == 'set_jail_config':
            jail = req.get('jail', '')
            if not jail:
                return ErrorResponse(msg='Jail名称不能为空')
            
            maxretry = int(req.get('maxretry', 5))
            bantime = int(req.get('bantime', 3600))
            findtime = int(req.get('findtime', 600))
            port = req.get('port', None)
            
            if Set_Jail_Config(jail, maxretry, bantime, findtime, port):
                RuyiAddOpLog(request, msg=f"【工具箱】-【Fail2Ban】- 更新配置: {jail}", module='tools')
                return DetailResponse(msg='配置已更新')
            return ErrorResponse(msg='配置更新失败')
        
        if action == 'add_ignoreip':
            ip = req.get('ip', '')
            if not ip:
                return ErrorResponse(msg='IP地址不能为空')
            
            if Add_Ignore_IP(ip):
                RuyiAddOpLog(request, msg=f"【工具箱】-【Fail2Ban】- 添加白名单IP: {ip}", module='tools')
                return DetailResponse(msg='添加成功')
            return ErrorResponse(msg='添加失败')
        
        if action == 'remove_ignoreip':
            ip = req.get('ip', '')
            if not ip:
                return ErrorResponse(msg='IP地址不能为空')
            
            if Remove_Ignore_IP(ip):
                RuyiAddOpLog(request, msg=f"【工具箱】-【Fail2Ban】- 移除白名单IP: {ip}", module='tools')
                return DetailResponse(msg='移除成功')
            return ErrorResponse(msg='移除失败')
        
        if action == 'create_jail':
            jail_type = req.get('type', '')
            port = req.get('port', '')
            if not jail_type or not port:
                return ErrorResponse(msg='类型和端口不能为空')
            
            if jail_type not in ['ssh', 'mysql']:
                return ErrorResponse(msg='不支持的防护类型')
            
            result = _create_custom_jail(jail_type, port)
            if result['success']:
                RuyiAddOpLog(request, msg=f"【工具箱】-【Fail2Ban】- 创建自定义防护: {result['jail_name']} (端口: {port})", module='tools')
                return DetailResponse(data={'jail_name': result['jail_name']}, msg='创建成功')
            return ErrorResponse(msg=result.get('msg', '创建失败'))
        
        if action == 'delete_jail':
            jail = req.get('jail', '')
            if not jail:
                return ErrorResponse(msg='Jail名称不能为空')
            
            # 只允许删除自定义 jail（非 sshd/mysqld 基础 jail）
            if jail in ['sshd', 'mysqld']:
                return ErrorResponse(msg='不能删除基础防护配置')
            
            if _delete_jail(jail):
                RuyiAddOpLog(request, msg=f"【工具箱】-【Fail2Ban】- 删除自定义防护: {jail}", module='tools')
                return DetailResponse(msg='删除成功')
            return ErrorResponse(msg='删除失败')
        
        return ErrorResponse(msg='类型错误')


def _create_custom_jail(jail_type, port):
    """创建自定义 jail"""
    try:
        # 生成唯一的 jail 名称
        base_name = 'sshd' if jail_type == 'ssh' else 'mysqld'
        
        # 读取现有配置
        config_content = Read_Jail_Config()
        existing_jails = set()
        if config_content:
            for line in config_content.split('\n'):
                match = re.match(r'\[([\w\-]+)\]', line.strip())
                if match:
                    existing_jails.add(match.group(1))
        
        # 查找可用的 jail 名称
        counter = 1
        jail_name = f"{base_name}-{port}"
        while jail_name in existing_jails:
            jail_name = f"{base_name}-{port}-{counter}"
            counter += 1
        
        # 创建 jail 配置
        if jail_type == 'ssh':
            jail_config = {
                'enabled': 'true',
                'port': str(port),
                'filter': 'sshd',
                'logpath': '/var/log/auth.log',
                'maxretry': '5',
                'bantime': '3600',
                'findtime': '600'
            }
        else:  # mysql
            jail_config = {
                'enabled': 'true',
                'port': str(port),
                'filter': 'mysqld-auth',
                'logpath': '/var/log/mysql/error.log',
                'maxretry': '5',
                'bantime': '3600',
                'findtime': '600'
            }
        
        # 追加到配置文件
        new_section = f"\n\n[{jail_name}]\n"
        for key, value in jail_config.items():
            new_section += f"{key} = {value}\n"
        
        if not config_content:
            config_content = ""
        config_content = config_content.rstrip() + new_section
        Write_Jail_Config(config_content)
        
        return {'success': True, 'jail_name': jail_name}
    except Exception as e:
        return {'success': False, 'msg': str(e)}


def _delete_jail(jail_name):
    """删除 jail 配置"""
    try:
        config_content = Read_Jail_Config()
        if not config_content:
            return False
        
        lines = config_content.split('\n')
        new_lines = []
        in_target_jail = False
        
        for line in lines:
            stripped = line.strip()
            
            # 检查是否是目标 jail 的节
            if stripped == f'[{jail_name}]':
                in_target_jail = True
                continue
            
            # 检查是否进入下一个节
            if in_target_jail and stripped.startswith('[') and stripped.endswith(']'):
                in_target_jail = False
            
            # 跳过目标 jail 的所有配置行
            if in_target_jail:
                continue
            
            new_lines.append(line)
        
        Write_Jail_Config('\n'.join(new_lines))
        return True
    except Exception as e:
        print(f"Delete jail error: {e}")
        return False
