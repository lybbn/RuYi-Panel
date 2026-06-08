import re
import os
import time
from collections import Counter
from datetime import datetime
from django.conf import settings
from django.db.models import Q
from django.http import FileResponse
from django.utils.encoding import escape_uri_path
from apps.syslogs.models import OperationLog
from rest_framework.views import APIView
from utils.customView import CustomAPIView
from utils.jsonResponse import ErrorResponse,DetailResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from utils.common import get_parameter_dic,formatdatetime,GetLogsPath
from utils.pagination import CustomPagination
from apps.syslogs.logutil import RuyiDelOpLog
from utils.server.system import system
from apps.syslogs.logutil import RuyiAddOpLog
from apps.system.models import Sites
from apps.sysshop.models import RySoftShop
from utils.ruyiclass.webClass import WebClient


XSS_PATTERNS = [
    re.compile(r'<\s*script', re.IGNORECASE),
    re.compile(r'javascript\s*:', re.IGNORECASE),
    re.compile(r'on(error|click|load|mouseover|focus|blur|submit|change|keyup|keydown|mouseout)\s*=', re.IGNORECASE),
    re.compile(r'document\.(cookie|location|write)', re.IGNORECASE),
    re.compile(r'eval\s*\(', re.IGNORECASE),
    re.compile(r'alert\s*\(', re.IGNORECASE),
    re.compile(r'<\s*img[^>]+on\w+\s*=', re.IGNORECASE),
    re.compile(r'<\s*svg[^>]+on\w+\s*=', re.IGNORECASE),
    re.compile(r'<\s*iframe', re.IGNORECASE),
]

SQL_PATTERNS = [
    re.compile(r"(\bunion\b.*\bselect\b)", re.IGNORECASE),
    re.compile(r"(\bselect\b.*\bfrom\b)", re.IGNORECASE),
    re.compile(r"(\binsert\b.*\binto\b)", re.IGNORECASE),
    re.compile(r"(\bdrop\b\s+(table|database))", re.IGNORECASE),
    re.compile(r"(\bdelete\b.*\bfrom\b)", re.IGNORECASE),
    re.compile(r"(\bupdate\b.*\bset\b)", re.IGNORECASE),
    re.compile(r"(\bor\b\s+1\s*=\s*1)", re.IGNORECASE),
    re.compile(r"(\band\b\s+1\s*=\s*1)", re.IGNORECASE),
    re.compile(r"('\s*(or|and)\s+.*--)", re.IGNORECASE),
    re.compile(r"(\bexec\b\s*\()", re.IGNORECASE),
    re.compile(r"(\bexecute\b\s*\()", re.IGNORECASE),
    re.compile(r"(information_schema)", re.IGNORECASE),
    re.compile(r"(sleep\s*\(\s*\d+\s*\))", re.IGNORECASE),
    re.compile(r"(benchmark\s*\()", re.IGNORECASE),
]

SCAN_PATTERNS = [
    re.compile(r'(\.env|\.git|\.svn|\.htaccess|\.htpasswd|wp-config\.php|web\.config)', re.IGNORECASE),
    re.compile(r'(/admin|/phpmyadmin|/phpinfo|/manager|/console|/actuator)', re.IGNORECASE),
    re.compile(r'(\.bak|\.backup|\.old|\.swp|\.tar|\.zip|\.rar|\.sql)', re.IGNORECASE),
    re.compile(r'(\/\.\.\/|\.\.\/|\.\.\\)', re.IGNORECASE),
    re.compile(r'(\/etc\/passwd|\/proc\/self|\/var\/log)', re.IGNORECASE),
    re.compile(r'(/wp-login|/xmlrpc\.php|/wp-content|/wp-includes)', re.IGNORECASE),
    re.compile(r'(/\.DS_Store|/Thumbs\.db|/desktop\.ini)', re.IGNORECASE),
    re.compile(r'(/api/v1/|/swagger|/api-docs|/graphql)', re.IGNORECASE),
]

MALICIOUS_UA_PATTERNS = [
    re.compile(r'(sqlmap|nmap|masscan|nikto|dirbuster|gobuster|wfuzz|feroxbuster)', re.IGNORECASE),
    re.compile(r'(zgrab|nuclei|httpx|subfinder|crawlergo|xray)', re.IGNORECASE),
    re.compile(r'(python-requests|curl|wget|httpclient|go-http)', re.IGNORECASE),
    re.compile(r'(bot|crawler|spider|scraper)', re.IGNORECASE),
    re.compile(r'(Mozilla/[45]\.0\s*$)', re.IGNORECASE),
]

SENSITIVE_PATH_PATTERNS = [
    re.compile(r'(\.php|\.asp|\.aspx|\.jsp)\b', re.IGNORECASE),
    re.compile(r'(/config\.(json|yaml|yml|ini|conf))', re.IGNORECASE),
    re.compile(r'(/debug|/trace|/heapdump|/threaddump|/jolokia)', re.IGNORECASE),
    re.compile(r'(/\.well-known/security\.txt|/robots\.txt|/sitemap\.xml)', re.IGNORECASE),
]

CC_ATTACK_THRESHOLD = 50

PHP_ATTACK_PATTERNS = [
    re.compile(r'(\$_(GET|POST|REQUEST|COOKIE|SERVER)\s*\[)', re.IGNORECASE),
    re.compile(r'(base64_decode\s*\()', re.IGNORECASE),
    re.compile(r'(system\s*\(|exec\s*\(|passthru\s*\(|shell_exec\s*\(|popen\s*\()', re.IGNORECASE),
    re.compile(r'(eval\s*\(|assert\s*\()', re.IGNORECASE),
    re.compile(r'(file_(get|put)_contents\s*\()', re.IGNORECASE),
    re.compile(r'(fopen\s*\(|fread\s*\(|fwrite\s*\()', re.IGNORECASE),
    re.compile(r'(include\s*\(|require\s*\(|include_once\s*\(|require_once\s*\()', re.IGNORECASE),
    re.compile(r'(preg_replace\s*\(.*/e)', re.IGNORECASE),
    re.compile(r'(create_function\s*\()', re.IGNORECASE),
    re.compile(r'(call_user_func\s*\()', re.IGNORECASE),
]

NGINX_LOG_IP_RE = re.compile(r'^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})')
NGINX_LOG_URL_RE = re.compile(r'"(?:GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s+(\S+)\s+HTTP')
NGINX_LOG_UA_RE = re.compile(r'"([^"]*)"(?:\s+"[^"]*")?\s*$')
NGINX_LOG_STATUS_RE = re.compile(r'"\s+HTTP/\d\.\d"\s+(\d{3})')


def _scan_log_lines(lines, max_lines=50000):
    xss_count = 0
    sql_count = 0
    scan_count = 0
    php_count = 0
    malicious_ua_count = 0
    sensitive_path_count = 0
    cc_attack_ips = 0
    ip_counter = Counter()
    url_counter = Counter()
    malicious_details = []

    check_lines = lines[:max_lines]
    ip_minute_counter = Counter()

    for line in check_lines:
        if not line.strip():
            continue

        ip_match = NGINX_LOG_IP_RE.match(line)
        ip = ip_match.group(1) if ip_match else None
        if ip:
            ip_counter[ip] += 1

        url_match = NGINX_LOG_URL_RE.search(line)
        url = url_match.group(1) if url_match else None
        if url:
            url_counter[url] += 1

        ua_match = NGINX_LOG_UA_RE.search(line)
        ua = ua_match.group(1) if ua_match else ''

        status_match = NGINX_LOG_STATUS_RE.search(line)
        status_code = status_match.group(1) if status_match else ''

        for pattern in XSS_PATTERNS:
            if pattern.search(line):
                xss_count += 1
                malicious_details.append({'type': 'XSS', 'ip': ip, 'url': url, 'detail': line.strip()[:300]})
                break

        for pattern in SQL_PATTERNS:
            if pattern.search(line):
                sql_count += 1
                malicious_details.append({'type': 'SQL', 'ip': ip, 'url': url, 'detail': line.strip()[:300]})
                break

        for pattern in SCAN_PATTERNS:
            if pattern.search(line):
                scan_count += 1
                malicious_details.append({'type': 'SCAN', 'ip': ip, 'url': url, 'detail': line.strip()[:300]})
                break

        for pattern in PHP_ATTACK_PATTERNS:
            if pattern.search(line):
                php_count += 1
                malicious_details.append({'type': 'PHP', 'ip': ip, 'url': url, 'detail': line.strip()[:300]})
                break

        for pattern in MALICIOUS_UA_PATTERNS:
            if pattern.search(ua):
                malicious_ua_count += 1
                malicious_details.append({'type': 'UA', 'ip': ip, 'url': url, 'detail': ua[:200]})
                break

        for pattern in SENSITIVE_PATH_PATTERNS:
            if url and pattern.search(url):
                sensitive_path_count += 1
                malicious_details.append({'type': 'PATH', 'ip': ip, 'url': url, 'detail': line.strip()[:300]})
                break

    for ip, count in ip_counter.items():
        if count >= CC_ATTACK_THRESHOLD:
            cc_attack_ips += 1
            malicious_details.append({'type': 'CC', 'ip': ip, 'url': '', 'detail': f'{ip} 请求 {count} 次'})

    top_ips = ip_counter.most_common(100)
    top_urls = url_counter.most_common(100)

    total = xss_count + sql_count + scan_count + php_count + malicious_ua_count + sensitive_path_count + cc_attack_ips

    return {
        'xss': xss_count,
        'sql': sql_count,
        'scan': scan_count,
        'php': php_count,
        'malicious_ua': malicious_ua_count,
        'sensitive_path': sensitive_path_count,
        'cc_attack': cc_attack_ips,
        'total': total,
        'top_ips': [{'ip': ip, 'count': count} for ip, count in top_ips],
        'top_urls': [{'url': url, 'count': count} for url, count in top_urls],
        'malicious_details': malicious_details[:500],
    }

class RYOPLogsManageView(CustomAPIView):
    """
    get:
    操作日志管理
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        reqData = get_parameter_dic(request)
        search = reqData.get("search",None)
        module = reqData.get("module",None)
        status = int(reqData.get("status",-1))
        queryset = OperationLog.objects.all().order_by("-id")
        if module:
            queryset = queryset.filter(module = module)
        if not status == -1:
            queryset = queryset.filter(status = status)
        if search:
            queryset = queryset.filter(Q(ip__icontains=search) | Q(msg__icontains=search))
        page_obj = CustomPagination()
        page_data = page_obj.paginate_queryset(queryset, request)
        data = []
        for m in page_data:
            data.append({
                'id':m.id,
                'username':m.username,
                'ip':m.ip,
                'ip_area':m.ip_area,
                'path':m.path,
                'body':m.body,
                'request_os': m.request_os,
                'browser': m.browser,
                'msg':m.msg,
                'status':m.status,
                'module':m.get_module_display(),
                'create_at':formatdatetime(m.create_at)
            })
        return page_obj.get_paginated_response(data)
    
    def post(self, request):
        reqData = get_parameter_dic(request)
        action = reqData.get("action",None)
        
        if action == "op_del_all":
            RuyiDelOpLog(request)
            return DetailResponse(msg="操作成功")
        elif action == "del_given_log":
            type = reqData.get("type","")
            if type == "syslogServer":
                name = 'server.log'
            elif type == "syslogError":
                name = 'error.log'
            elif type == "syslogTask":
                name = 'task.log'
            elif type == "syslogAccess":
                name = 'ry_access.log'
            else:
                return ErrorResponse(msg="类型错误")
            log_path = os.path.join(settings.BASE_DIR,'logs',name)
            with open(log_path, 'r+') as f:
                f.truncate(0)
            RuyiAddOpLog(request,msg="【清空日志】-【%s】"%name,module="dellog")
            return DetailResponse(msg="清空成功")
        elif action == "get_runserver_log":
            log_path = os.path.join(settings.BASE_DIR,'logs','server.log')
            num = 5000
            data = system.GetFileLastNumsLines(log_path,num)
            return DetailResponse(data=data,msg="success")
        elif action == "get_runerror_log":
            log_path = os.path.join(settings.BASE_DIR,'logs','error.log')
            num = 5000
            data = system.GetFileLastNumsLines(log_path,num)
            return DetailResponse(data=data,msg="success")
        elif action == "get_runtask_log":
            log_path = os.path.join(settings.BASE_DIR,'logs','task.log')
            num = 5000
            data = system.GetFileLastNumsLines(log_path,num)
            return DetailResponse(data=data,msg="success")
        elif action == "get_runaccess_log":
            log_path = os.path.join(settings.BASE_DIR,'logs','ry_access.log')
            num = 5000
            data = system.GetFileLastNumsLines(log_path,num)
            return DetailResponse(data=data,msg="success")
        return ErrorResponse(msg="类型错误")


def _get_site_log_info(site_ins, webServer):
    log_base_path = GetLogsPath()
    access_log_path = os.path.join(log_base_path, site_ins.name + ".log").replace("\\", "/")
    error_log_path = os.path.join(log_base_path, site_ins.name + ".error.log").replace("\\", "/")
    access_log_size = 0
    error_log_size = 0
    if os.path.exists(access_log_path):
        try:
            access_log_size = os.path.getsize(access_log_path)
        except OSError:
            pass
    if os.path.exists(error_log_path):
        try:
            error_log_size = os.path.getsize(error_log_path)
        except OSError:
            pass
    return {
        'id': site_ins.id,
        'name': site_ins.name,
        'path': site_ins.path,
        'status': site_ins.status,
        'access_log': site_ins.access_log,
        'error_log': site_ins.error_log,
        'access_log_path': access_log_path,
        'error_log_path': error_log_path,
        'access_log_size': access_log_size,
        'error_log_size': error_log_size,
        'access_log_exists': os.path.exists(access_log_path),
        'error_log_exists': os.path.exists(error_log_path),
    }


def _format_file_size(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return "%.2f %s" % (size, unit)
        size /= 1024.0
    return "%.2f TB" % size


def _extract_date_from_log_line(line):
    date_patterns = [
        r'\[(\d{2}/\w{3}/\d{4}:\d{2}:\d{2}:\d{2})',
        r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})',
        r'(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2})',
        r'(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})',
    ]
    for pattern in date_patterns:
        match = re.search(pattern, line)
        if match:
            raw = match.group(1)
            for fmt in ('%d/%b/%Y:%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M:%S'):
                try:
                    from datetime import datetime
                    dt = datetime.strptime(raw, fmt)
                    return dt.strftime('%Y-%m-%d')
                except (ValueError, ImportError):
                    continue
    return None


class RYSiteLogsManageView(CustomAPIView):
    """
    get:
    网站日志列表
    post:
    网站日志管理
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        reqData = get_parameter_dic(request)
        search = reqData.get("search", None)
        queryset = Sites.objects.all().order_by("-id")
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(remark__icontains=search))
        webServerIns = RySoftShop.objects.filter(type=3).first()
        webServer = ""
        if webServerIns is not None:
            webServer = webServerIns.name
        page_obj = CustomPagination()
        page_data = page_obj.paginate_queryset(queryset, request)
        data = []
        for m in page_data:
            info = _get_site_log_info(m, webServer)
            info['remark'] = m.remark
            info['type'] = m.get_type_display()
            info['access_log_size_display'] = _format_file_size(info['access_log_size'])
            info['error_log_size_display'] = _format_file_size(info['error_log_size'])
            info['create_at'] = formatdatetime(m.create_at)
            data.append(info)
        return page_obj.get_paginated_response(data)

    def post(self, request):
        reqData = get_parameter_dic(request)
        action = reqData.get("action", "")
        webServerIns = RySoftShop.objects.filter(type=3).first()
        webServer = ""
        if webServerIns is not None:
            webServer = webServerIns.name

        if action == "get_site_log_content":
            site_id = reqData.get("id", "")
            log_type = reqData.get("log_type", "access")
            search = reqData.get("search", "")
            start_date = reqData.get("start_date", "")
            end_date = reqData.get("end_date", "")
            if not site_id:
                return ErrorResponse(msg="参数错误")
            s_ins = Sites.objects.filter(id=site_id).first()
            if not s_ins:
                return ErrorResponse(msg="无此站点")
            log_base_path = GetLogsPath()
            if log_type == "access":
                log_path = os.path.join(log_base_path, s_ins.name + ".log").replace("\\", "/")
            else:
                log_path = os.path.join(log_base_path, s_ins.name + ".error.log").replace("\\", "/")
            if not os.path.exists(log_path):
                return DetailResponse(data="", msg="success")
            num = 5000
            data = system.GetFileLastNumsLines(log_path, num)
            if data and (search or start_date or end_date):
                lines = data.split('\n')
                filtered = []
                for line in lines:
                    if not line.strip():
                        continue
                    if search and search.lower() not in line.lower():
                        continue
                    if start_date or end_date:
                        date_match = _extract_date_from_log_line(line)
                        if start_date and date_match and date_match < start_date:
                            continue
                        if end_date and date_match and date_match > end_date + " 23:59:59":
                            continue
                    filtered.append(line)
                data = '\n'.join(filtered)
            return DetailResponse(data=data, msg="success")

        elif action == "clear_site_log":
            site_id = reqData.get("id", "")
            log_type = reqData.get("log_type", "access")
            if not site_id:
                return ErrorResponse(msg="参数错误")
            s_ins = Sites.objects.filter(id=site_id).first()
            if not s_ins:
                return ErrorResponse(msg="无此站点")
            log_base_path = GetLogsPath()
            access_log_path = os.path.join(log_base_path, s_ins.name + ".log").replace("\\", "/")
            error_log_path = os.path.join(log_base_path, s_ins.name + ".error.log").replace("\\", "/")
            if log_type == "access":
                if not os.path.exists(access_log_path):
                    return ErrorResponse(msg="日志文件不存在")
                with open(access_log_path, 'r+') as f:
                    f.truncate(0)
                RuyiAddOpLog(request, msg="【网站日志】-【清空访问日志】%s" % s_ins.name, module="dellog")
            elif log_type == "error":
                if not os.path.exists(error_log_path):
                    return ErrorResponse(msg="日志文件不存在")
                with open(error_log_path, 'r+') as f:
                    f.truncate(0)
                RuyiAddOpLog(request, msg="【网站日志】-【清空错误日志】%s" % s_ins.name, module="dellog")
            elif log_type == "all":
                for lp in [access_log_path, error_log_path]:
                    if os.path.exists(lp):
                        with open(lp, 'r+') as f:
                            f.truncate(0)
                RuyiAddOpLog(request, msg="【网站日志】-【清空所有日志】%s" % s_ins.name, module="dellog")
            else:
                return ErrorResponse(msg="类型错误")
            return DetailResponse(msg="清空成功")

        elif action == "download_site_log":
            site_id = reqData.get("id", "")
            log_type = reqData.get("log_type", "access")
            if not site_id:
                return ErrorResponse(msg="参数错误")
            s_ins = Sites.objects.filter(id=site_id).first()
            if not s_ins:
                return ErrorResponse(msg="无此站点")
            log_base_path = GetLogsPath()
            if log_type == "access":
                log_path = os.path.join(log_base_path, s_ins.name + ".log").replace("\\", "/")
            else:
                log_path = os.path.join(log_base_path, s_ins.name + ".error.log").replace("\\", "/")
            if not os.path.exists(log_path):
                return ErrorResponse(msg="日志文件不存在")
            try:
                response = FileResponse(open(log_path, 'rb'))
                filename = os.path.basename(log_path)
                response['Content-Type'] = 'application/octet-stream'
                response['Content-Disposition'] = 'attachment;filename="%s"' % escape_uri_path(filename)
                return response
            except Exception as e:
                return ErrorResponse(msg="下载失败：%s" % str(e))

        elif action == "site_log_open":
            site_id = reqData.get("id", "")
            log_type = reqData.get("log_type", "access_log")
            status = reqData.get("status", False)
            if isinstance(status, str):
                status = status.lower() in ('true', '1', 'yes')
            status_name = "start" if status else "stop"
            status_name2 = "开启" if status else "关闭"
            if not site_id:
                return ErrorResponse(msg="参数错误")
            s_ins = Sites.objects.filter(id=site_id).first()
            if not s_ins:
                return ErrorResponse(msg="无此站点")
            if log_type not in ["access_log", "error_log"]:
                return ErrorResponse(msg="类型错误")
            if not webServer:
                return ErrorResponse(msg="无Web环境")
            isok, null = WebClient.site_log_open(webserver=webServer, siteName=s_ins.name, sitePath=s_ins.path, action=status_name, type=log_type)
            if not isok:
                return ErrorResponse(msg="设置失败")
            if log_type == "access_log":
                s_ins.access_log = status
                s_ins.save()
            else:
                s_ins.error_log = status
                s_ins.save()
            RuyiAddOpLog(request, msg="【网站日志】-【日志开关】%s => %s %s" % (s_ins.name, status_name2, log_type), module="sitemg")
            WebClient.reload_service(webserver=webServer)
            return DetailResponse(msg="设置成功")

        elif action == "get_site_log_dir_info":
            log_base_path = GetLogsPath()
            total_size = 0
            file_count = 0
            if os.path.exists(log_base_path):
                for f in os.listdir(log_base_path):
                    fp = os.path.join(log_base_path, f)
                    if os.path.isfile(fp):
                        try:
                            total_size += os.path.getsize(fp)
                            file_count += 1
                        except OSError:
                            pass
            return DetailResponse(data={
                'log_dir': log_base_path.replace("\\", "/"),
                'total_size': total_size,
                'total_size_display': _format_file_size(total_size),
                'file_count': file_count,
            }, msg="success")

        elif action == "clear_all_site_logs":
            log_base_path = GetLogsPath()
            cleared_count = 0
            if os.path.exists(log_base_path):
                for f in os.listdir(log_base_path):
                    fp = os.path.join(log_base_path, f)
                    if os.path.isfile(fp) and (f.endswith('.log') or f.endswith('.error.log')):
                        try:
                            with open(fp, 'r+') as lf:
                                lf.truncate(0)
                            cleared_count += 1
                        except OSError:
                            pass
            RuyiAddOpLog(request, msg="【网站日志】-【清空所有Nginx日志】共清空 %d 个文件" % cleared_count, module="dellog")
            return DetailResponse(msg="共清空 %d 个日志文件" % cleared_count)

        elif action == "scan_site_log":
            site_id = reqData.get("id", "")
            log_type = reqData.get("log_type", "access")
            if not site_id:
                return ErrorResponse(msg="参数错误")
            s_ins = Sites.objects.filter(id=site_id).first()
            if not s_ins:
                return ErrorResponse(msg="无此站点")
            log_base_path = GetLogsPath()
            start_time = time.time()
            all_lines = []
            scan_log_types = []
            if log_type == "all":
                scan_log_types = ["access", "error"]
            else:
                scan_log_types = [log_type]
            for lt in scan_log_types:
                if lt == "access":
                    log_path = os.path.join(log_base_path, s_ins.name + ".log").replace("\\", "/")
                else:
                    log_path = os.path.join(log_base_path, s_ins.name + ".error.log").replace("\\", "/")
                if os.path.exists(log_path):
                    data = system.GetFileLastNumsLines(log_path, 50000)
                    if data:
                        all_lines.extend(data.split('\n'))
            if not all_lines:
                return ErrorResponse(msg="日志文件不存在或为空")
            scan_result = _scan_log_lines(all_lines)
            elapsed = time.time() - start_time
            scan_result['scan_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            scan_result['elapsed'] = round(elapsed, 2)
            scan_result['site_name'] = s_ins.name
            scan_result['log_type'] = log_type
            RuyiAddOpLog(request, msg="【网站日志】-【日志扫描】%s %s日志，发现 %d 条可疑记录" % (s_ins.name, log_type, scan_result['total']), module="sitemg")
            return DetailResponse(data=scan_result, msg="success")

        elif action == "get_site_log_for_ai":
            site_id = reqData.get("id", "")
            log_type = reqData.get("log_type", "access")
            max_lines = int(reqData.get("max_lines", 200))
            if not site_id:
                return ErrorResponse(msg="参数错误")
            s_ins = Sites.objects.filter(id=site_id).first()
            if not s_ins:
                return ErrorResponse(msg="无此站点")
            log_base_path = GetLogsPath()
            if log_type == "access":
                log_path = os.path.join(log_base_path, s_ins.name + ".log").replace("\\", "/")
            else:
                log_path = os.path.join(log_base_path, s_ins.name + ".error.log").replace("\\", "/")
            if not os.path.exists(log_path):
                return DetailResponse(data="", msg="success")
            data = system.GetFileLastNumsLines(log_path, max_lines)
            return DetailResponse(data=data, msg="success")

        return ErrorResponse(msg="类型错误")
