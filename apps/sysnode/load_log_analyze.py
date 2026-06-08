# -*- coding: utf-8 -*-

"""
@Remark: 负载均衡Nginx日志分析 - QPS/响应时间/错误率/按节点统计
@author lybbn<2026-06-03>
"""
import os
import re
import time
from collections import defaultdict
from datetime import datetime, timedelta

from utils.common import is_windows


def _get_nginx_log_path():
    """获取Nginx日志目录路径"""
    try:
        from utils.install.nginx import get_nginx_path_info
        info = get_nginx_path_info()
        return info.get('log_abspath_path', '')
    except Exception:
        return ''


def _parse_nginx_access_line(line):
    """解析单行Nginx access log（combined格式）
    示例: 192.168.1.1 - - [03/Jun/2026:10:00:01 +0800] "GET /api/ HTTP/1.1" 200 1234 "http://ref" "Mozilla/5.0" upstream_addr
    """
    pattern = (
        r'(?P<remote_addr>\S+)\s+\S+\s+\S+\s+'
        r'\[(?P<time>[^\]]+)\]\s+'
        r'"(?P<method>\S+)\s+(?P<uri>\S+)\s+\S+"\s+'
        r'(?P<status>\d+)\s+(?P<body_bytes>\d+)\s+'
        r'"(?P<referer>[^"]*)"\s+'
        r'"(?P<user_agent>[^"]*)"'
    )
    m = re.match(pattern, line)
    if not m:
        return None
    data = m.groupdict()
    data['status'] = int(data['status'])
    data['body_bytes'] = int(data['body_bytes'])

    # 尝试提取upstream_addr（如果日志中有）
    upstream_match = re.search(r'upstream_addr:\s*(?P<upstream>\S+)', line)
    if upstream_match:
        data['upstream'] = upstream_match.group('upstream')
    else:
        data['upstream'] = ''

    # 尝试提取request_time（如果日志中有）
    rt_match = re.search(r'request_time:\s*(?P<rt>[\d.]+)', line)
    if rt_match:
        data['request_time'] = float(rt_match.group('rt'))
    else:
        data['request_time'] = 0

    return data


def analyze_access_log(log_file=None, minutes=30, site_name=None):
    """
    分析Nginx access log
    返回: {
        total_requests: 总请求数,
        qps: 每秒请求数,
        avg_response_time: 平均响应时间,
        error_rate: 错误率(5xx),
        status_distribution: 状态码分布,
        upstream_stats: 按upstream节点统计,
        time_series: 时间序列数据(每分钟),
    }
    """
    if not log_file:
        log_dir = _get_nginx_log_path()
        if not log_dir or not os.path.isdir(log_dir):
            return {"error": "Nginx日志目录不存在"}
        # 优先使用站点专属日志，否则使用全局日志
        if site_name:
            site_log = os.path.join(log_dir, f"{site_name}.log")
            if os.path.exists(site_log):
                log_file = site_log
        if not log_file:
            log_file = os.path.join(log_dir, "access.log")

    if not os.path.exists(log_file):
        return {"error": f"日志文件不存在: {log_file}"}

    # 计算时间范围
    now = datetime.now()
    start_time = now - timedelta(minutes=minutes)

    total_requests = 0
    total_response_time = 0.0
    error_count = 0
    status_dist = defaultdict(int)
    upstream_stats = defaultdict(lambda: {"requests": 0, "errors": 0, "total_rt": 0.0})
    time_series = defaultdict(lambda: {"requests": 0, "errors": 0, "total_rt": 0.0})

    try:
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parsed = _parse_nginx_access_line(line)
                if not parsed:
                    continue

                total_requests += 1

                # 状态码统计
                status = parsed['status']
                status_dist[status] += 1
                if status >= 500:
                    error_count += 1

                # 响应时间
                rt = parsed.get('request_time', 0)
                total_response_time += rt

                # 按upstream节点统计
                upstream = parsed.get('upstream', '')
                if upstream:
                    us = upstream_stats[upstream]
                    us['requests'] += 1
                    us['total_rt'] += rt
                    if status >= 500:
                        us['errors'] += 1

                # 时间序列（按分钟）
                try:
                    log_time = datetime.strptime(
                        parsed['time'].split()[0], "%d/%b/%Y:%H:%M:%S"
                    )
                    if log_time >= start_time:
                        minute_key = log_time.strftime("%H:%M")
                        ts = time_series[minute_key]
                        ts['requests'] += 1
                        ts['total_rt'] += rt
                        if status >= 500:
                            ts['errors'] += 1
                except (ValueError, IndexError):
                    pass
    except Exception as e:
        return {"error": f"读取日志失败: {str(e)}"}

    # 计算汇总
    qps = round(total_requests / (minutes * 60), 2) if minutes > 0 else 0
    avg_rt = round(total_response_time / total_requests, 3) if total_requests > 0 else 0
    error_rate = round(error_count / total_requests * 100, 2) if total_requests > 0 else 0

    # 格式化upstream统计
    upstream_result = []
    for addr, stats in upstream_stats.items():
        upstream_result.append({
            "address": addr,
            "requests": stats['requests'],
            "errors": stats['errors'],
            "error_rate": round(stats['errors'] / stats['requests'] * 100, 2) if stats['requests'] > 0 else 0,
            "avg_response_time": round(stats['total_rt'] / stats['requests'], 3) if stats['requests'] > 0 else 0,
        })

    # 格式化时间序列
    ts_result = []
    for minute_key in sorted(time_series.keys()):
        stats = time_series[minute_key]
        ts_result.append({
            "time": minute_key,
            "requests": stats['requests'],
            "errors": stats['errors'],
            "avg_response_time": round(stats['total_rt'] / stats['requests'], 3) if stats['requests'] > 0 else 0,
        })

    return {
        "total_requests": total_requests,
        "qps": qps,
        "avg_response_time": avg_rt,
        "error_rate": error_rate,
        "error_count": error_count,
        "status_distribution": dict(status_dist),
        "upstream_stats": upstream_result,
        "time_series": ts_result,
        "minutes": minutes,
    }


def analyze_error_log(log_file=None, lines=100):
    """分析Nginx error log，返回最近的错误信息"""
    if not log_file:
        log_dir = _get_nginx_log_path()
        if not log_dir or not os.path.isdir(log_dir):
            return {"error": "Nginx日志目录不存在"}
        log_file = os.path.join(log_dir, "error.log")

    if not os.path.exists(log_file):
        return {"error": f"日志文件不存在: {log_file}"}

    errors = []
    try:
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            all_lines = f.readlines()
            for line in all_lines[-lines:]:
                line = line.strip()
                if not line:
                    continue
                # 提取错误级别
                level_match = re.search(r'\[(\w+)\]', line)
                level = level_match.group(1) if level_match else 'unknown'
                errors.append({
                    "level": level,
                    "message": line,
                })
    except Exception as e:
        return {"error": f"读取错误日志失败: {str(e)}"}

    return {
        "total": len(errors),
        "errors": errors,
    }
