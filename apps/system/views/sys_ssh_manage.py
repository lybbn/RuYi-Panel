import datetime
import gzip
import os
import re
import subprocess
from glob import glob

from django.http import HttpResponse
from rest_framework.permissions import IsAuthenticated

from apps.syslogs.logutil import RuyiAddOpLog
from utils.common import (
    GetLocalSSHPort,
    RunCommand,
    RunCommandReturnCode,
    SetSSHServiceStatus,
    WriteFile,
    ReadFile,
    current_os,
    get_parameter_dic,
    isSSHRunning,
)
from utils.customView import CustomAPIView
from utils.jsonResponse import DetailResponse, ErrorResponse, SuccessResponse


_MONTHS = {
    'Jan': 1,
    'Feb': 2,
    'Mar': 3,
    'Apr': 4,
    'May': 5,
    'Jun': 6,
    'Jul': 7,
    'Aug': 8,
    'Sep': 9,
    'Oct': 10,
    'Nov': 11,
    'Dec': 12,
}


def _is_linux():
    return current_os != 'windows'


def _get_sshd_config_path():
    return '/etc/ssh/sshd_config'


def _read_sshd_config():
    return ReadFile(_get_sshd_config_path()) or ''


def _write_sshd_config(conf: str):
    WriteFile(_get_sshd_config_path(), conf)


def _parse_yes_no(v, default=None):
    if v is None:
        return default
    s = str(v).strip().lower()
    if s in ['yes', 'true', '1', 'on']:
        return True
    if s in ['no', 'false', '0', 'off']:
        return False
    return default


def _get_directive_value(conf: str, key: str):
    rep = rf'^\s*#?\s*{re.escape(key)}\s+(.+?)\s*$'
    found = None
    for m in re.finditer(rep, conf, re.M):
        found = m.group(1).strip()
    return found


def _set_directive(conf: str, key: str, value: str):
    lines = conf.splitlines()
    out = []
    replaced = False
    rep = re.compile(rf'^\s*#?\s*{re.escape(key)}\b', re.I)
    for line in lines:
        if rep.match(line):
            if not replaced:
                out.append(f'{key} {value}')
                replaced = True
            continue
        out.append(line)
    if not replaced:
        if out and out[-1].strip() != '':
            out.append('')
        out.append(f'{key} {value}')
    return '\n'.join(out) + ('\n' if conf.endswith('\n') else '')


def _get_ssh_config_view():
    conf = _read_sshd_config()
    password_auth = _parse_yes_no(_get_directive_value(conf, 'PasswordAuthentication'), default=True)
    pubkey_auth = _parse_yes_no(_get_directive_value(conf, 'PubkeyAuthentication'), default=True)
    port = GetLocalSSHPort()
    permit_root_login = (_get_directive_value(conf, 'PermitRootLogin') or 'yes').strip()
    
    return {
        'port': port,
        'password_auth': bool(password_auth),
        'pubkey_auth': bool(pubkey_auth),
        'permit_root_login': permit_root_login,
    }


def _restart_sshd():
    SetSSHServiceStatus(action='restart')


def _parse_syslog_datetime(now: datetime.datetime, mon: str, day: str, timestr: str):
    month = _MONTHS.get(mon)
    if not month:
        return None
    try:
        hour, minute, second = [int(x) for x in timestr.split(':')]
        dt = datetime.datetime(now.year, month, int(day), hour, minute, second)
        if dt - now > datetime.timedelta(days=1):
            dt = datetime.datetime(now.year - 1, month, int(day), hour, minute, second)
        return dt
    except Exception:
        return None


_SSHD_LINE_RE = re.compile(
    r'^(?P<mon>[A-Z][a-z]{2})\s+(?P<day>\d{1,2})\s+(?P<time>\d{2}:\d{2}:\d{2})\s+(?P<host>\S+)\s+(?P<proc>sshd(?:\[\d+\])?):\s+(?P<msg>.*)$'
)

_SSHD_JOURNAL_LINE_RE = re.compile(
    r'^(?P<date>\d{4}-\d{2}-\d{2})(?:T|\s+)(?P<time>\d{2}:\d{2}:\d{2})(?:\.\d+)?(?:[+-]\d{2}:?\d{2}|Z)?\s+(?P<host>\S+)\s+(?P<proc>sshd(?:\[\d+\])?):\s+(?P<msg>.*)$'
)

_SSH_ACCEPT_RE = re.compile(
    r'\bAccepted\s+(?P<method>password|publickey|keyboard-interactive/pam)\s+for\s+(?P<user>[\w\-\.\@]+)\s+from\s+(?P<ip>[0-9a-fA-F:\.]+)\b'
)

_SSH_FAILED_RE = re.compile(
    r'\bFailed\s+(?P<method>password|publickey|keyboard-interactive/pam)\s+for\s+(?:invalid user\s+)?(?P<user>[\w\-\.\@]+)\s+from\s+(?P<ip>[0-9a-fA-F:\.]+)\b'
)

_SSH_AUTH_FAILURE_RE = re.compile(
    r'authentication failure;.*\brhost=(?P<ip>[0-9a-fA-F:\.]+)\s+user=(?P<user>\S+)',
    re.I,
)

_SSH_INVALID_USER_RE = re.compile(
    r'\bInvalid user\s+(?P<user>[\w\-\.\@]+)\s+from\s+(?P<ip>[0-9a-fA-F:\.]+)\b'
)


def _detect_primary_log_path():
    for p in ['/var/log/auth.log', '/var/log/secure', '/var/log/messages', '/var/log/syslog', '/var/log/daemon.log']:
        if os.path.exists(p):
            return p
    return None


def _tail_journal_lines(max_lines: int):
    max_lines = int(max_lines)
    cmd = f"journalctl -u ssh -u sshd --no-pager -o short-iso -n {max_lines}"
    out, err = RunCommand(cmd)
    content = out if out else ''
    return content.splitlines()


def _tail_log_lines(path: str, max_lines: int):
    if not path:
        return _tail_journal_lines(max_lines=max_lines)
    cmd = f"tail -n {int(max_lines)} '{path}'"
    out, err = RunCommand(cmd)
    content = out if out else ''
    return content.splitlines()


def _parse_iso_datetime(date_str: str, time_str: str):
    if not date_str or not time_str:
        return None
    t = time_str.split('.')[0]
    try:
        return datetime.datetime.strptime(f'{date_str} {t}', '%Y-%m-%d %H:%M:%S')
    except Exception:
        return None


def _extract_ssh_event(line: str, now: datetime.datetime):
    msg = None
    dt = None
    m = _SSHD_LINE_RE.match(line)
    if m:
        msg = m.group('msg')
        dt = _parse_syslog_datetime(now, m.group('mon'), m.group('day'), m.group('time'))
    else:
        m = _SSHD_JOURNAL_LINE_RE.match(line)
        if not m:
            return None
        msg = m.group('msg')
        dt = _parse_iso_datetime(m.group('date'), m.group('time'))
    if not dt:
        return None

    m1 = _SSH_ACCEPT_RE.search(msg)
    if m1:
        return {
            'timestamp': int(dt.timestamp()),
            'time': dt.strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'success',
            'username': m1.group('user'),
            'ip': m1.group('ip'),
            'method': m1.group('method'),
            'message': msg,
        }

    m2 = _SSH_FAILED_RE.search(msg)
    if m2:
        return {
            'timestamp': int(dt.timestamp()),
            'time': dt.strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'fail',
            'username': m2.group('user'),
            'ip': m2.group('ip'),
            'method': m2.group('method'),
            'message': msg,
        }

    m3 = _SSH_INVALID_USER_RE.search(msg)
    if m3:
        return {
            'timestamp': int(dt.timestamp()),
            'time': dt.strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'fail',
            'username': m3.group('user'),
            'ip': m3.group('ip'),
            'method': '',
            'message': msg,
        }

    m4 = _SSH_AUTH_FAILURE_RE.search(msg)
    if m4:
        return {
            'timestamp': int(dt.timestamp()),
            'time': dt.strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'fail',
            'username': m4.group('user'),
            'ip': m4.group('ip'),
            'method': '',
            'message': msg,
        }

    return None


def _iter_log_paths(limit_files: int = 20):
    primary = _detect_primary_log_path()
    if not primary:
        return []

    paths = []
    for p in glob(primary + '*'):
        if os.path.isfile(p):
            paths.append(p)
    paths.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    return paths[:limit_files]


def _iter_file_lines(path: str):
    try:
        if path.endswith('.gz'):
            with gzip.open(path, 'rt', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    yield line.rstrip('\n')
        else:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    yield line.rstrip('\n')
    except Exception:
        return


def _calc_stats():
    now = datetime.datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - datetime.timedelta(days=1)
    last7_start = today_start - datetime.timedelta(days=6)

    stats = {
        'today': {'success': 0, 'fail': 0},
        'yesterday': {'success': 0, 'fail': 0},
        'last7': {'success': 0, 'fail': 0},
        'total': {'success': 0, 'fail': 0},
    }

    def apply_event(event):
        is_success = event['status'] == 'success'
        k = 'success' if is_success else 'fail'
        stats['total'][k] += 1

        dt = datetime.datetime.fromtimestamp(event['timestamp'])
        if dt >= today_start:
            stats['today'][k] += 1
        elif dt >= yesterday_start and dt < today_start:
            stats['yesterday'][k] += 1
        if dt >= last7_start:
            stats['last7'][k] += 1

    event_count = 0
    log_paths = _iter_log_paths(limit_files=20)
    if log_paths:
        for p in log_paths:
            for line in _iter_file_lines(p):
                event = _extract_ssh_event(line, now)
                if not event:
                    continue
                event_count += 1
                apply_event(event)

    if event_count == 0:
        for line in _tail_log_lines(None, max_lines=100000):
            event = _extract_ssh_event(line, now)
            if not event:
                continue
            event_count += 1
            apply_event(event)

    stats['today']['total'] = stats['today']['success'] + stats['today']['fail']
    stats['yesterday']['total'] = stats['yesterday']['success'] + stats['yesterday']['fail']
    stats['last7']['total'] = stats['last7']['success'] + stats['last7']['fail']
    stats['total']['total'] = stats['total']['success'] + stats['total']['fail']
    return stats


def _get_root_key_paths():
    base = '/root/.ssh'
    return {
        'dir': base,
        'private': os.path.join(base, 'id_rsa'),
        'public': os.path.join(base, 'id_rsa.pub'),
    }


def _ensure_root_keypair():
    paths = _get_root_key_paths()
    if os.path.exists(paths['private']) and os.path.exists(paths['public']):
        return True
    RunCommandReturnCode(f"mkdir -p '{paths['dir']}'")
    RunCommandReturnCode(f"chmod 700 '{paths['dir']}'")
    code = RunCommandReturnCode(f"ssh-keygen -t rsa -b 2048 -N '' -f '{paths['private']}'")
    if code != 0:
        return False
    RunCommandReturnCode(f"chmod 600 '{paths['private']}'")
    RunCommandReturnCode(f"chmod 644 '{paths['public']}'")
    return os.path.exists(paths['private']) and os.path.exists(paths['public'])


def _read_root_private_key():
    paths = _get_root_key_paths()
    if not os.path.exists(paths['private']):
        return ''
    return ReadFile(paths['private']) or ''


def _set_root_password(password: str):
    if not password:
        return False, '密码不能为空'
    try:
        p = subprocess.Popen(
            ['chpasswd'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        out, err = p.communicate(f'root:{password}\n', timeout=10)
        if p.returncode == 0:
            return True, '设置成功'
        msg = (err or out or '').strip()
        return False, msg if msg else '设置失败'
    except Exception:
        return False, '设置失败'


class RYSysSSHManageView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _is_linux():
            return ErrorResponse(msg='当前系统不支持')

        req = get_parameter_dic(request)
        action = req.get('action', 'overview')

        if action == 'overview':
            data = {
                'running': bool(isSSHRunning()),
                'config': _get_ssh_config_view(),
                'stats': _calc_stats(),
            }
            return DetailResponse(data=data)

        if action == 'root_key':
            return DetailResponse(data={'root_key': _read_root_private_key()})

        if action == 'logs':
            status = (req.get('status', '') or '').strip()
            ip = (req.get('ip', '') or '').strip()
            username = (req.get('username', '') or '').strip()
            page = int(req.get('page', 1) or 1)
            limit = int(req.get('limit', 20) or 20)
            max_lines = int(req.get('max_lines', 20000) or 20000)
            max_lines = min(max_lines, 100000)

            def collect_events(lines):
                now = datetime.datetime.now()
                items = []
                for line in lines:
                    event = _extract_ssh_event(line, now)
                    if not event:
                        continue
                    if status in ['success', 'fail'] and event['status'] != status:
                        continue
                    if ip and ip not in event['ip']:
                        continue
                    if username and username not in event['username']:
                        continue
                    items.append(event)
                return items

            log_path = _detect_primary_log_path()
            lines = _tail_log_lines(log_path, max_lines=max_lines)
            events = collect_events(lines)
            if not events and log_path:
                events = collect_events(_tail_journal_lines(max_lines=max_lines))

            events.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
            total = len(events)
            start = (page - 1) * limit
            end = start + limit
            page_data = events[start:end]
            return SuccessResponse(data=page_data, page=page, limit=limit, total=total)

        return ErrorResponse(msg='类型错误')

    def post(self, request):
        if not _is_linux():
            return ErrorResponse(msg='当前系统不支持')

        req = get_parameter_dic(request)
        action = req.get('action', '')

        if action == 'set_service':
            enable = bool(req.get('enable', True))
            SetSSHServiceStatus(action='start' if enable else 'stop')
            RuyiAddOpLog(request, msg=f"【安全】-【SSH管理】- {'开启' if enable else '关闭'}SSH服务", module='safe')
            return DetailResponse(data={'running': bool(isSSHRunning())}, msg='设置成功')

        if action == 'set_config':
            port = int(req.get('port', 22) or 22)
            if port < 1 or port > 65535:
                return ErrorResponse(msg='端口范围错误')

            password_auth = bool(req.get('password_auth', True))
            pubkey_auth = bool(req.get('pubkey_auth', True))
            
            # 支持 permit_root_login 直接传入，兼容旧的 root_mode
            permit_root_login = req.get('permit_root_login', '').strip()
            
            if not permit_root_login:
                root_mode = req.get('root_mode', 'pass_key')
                if root_mode == 'no':
                    permit_root_login = 'no'
                elif root_mode == 'key_only':
                    permit_root_login = 'prohibit-password'
                else:
                    permit_root_login = 'yes'
            
            # 验证 permit_root_login 的值是否合法
            valid_permits = ['yes', 'no', 'without-password', 'prohibit-password', 'forced-commands-only']
            if permit_root_login not in valid_permits:
                 # 尝试修正或默认为 yes
                 permit_root_login = 'yes'

            conf = _read_sshd_config()
            conf = _set_directive(conf, 'Port', str(port))
            conf = _set_directive(conf, 'PasswordAuthentication', 'yes' if password_auth else 'no')
            conf = _set_directive(conf, 'PubkeyAuthentication', 'yes' if pubkey_auth else 'no')
            conf = _set_directive(conf, 'PermitRootLogin', permit_root_login)
            _write_sshd_config(conf)
            _restart_sshd()

            RuyiAddOpLog(request, msg='【安全】-【SSH管理】- 保存SSH基础设置', module='safe')
            return DetailResponse(data={'config': _get_ssh_config_view(), 'running': bool(isSSHRunning())}, msg='保存成功')

        if action == 'set_root_password':
            password = req.get('password', '')
            ok, msg = _set_root_password(password)
            if ok:
                RuyiAddOpLog(request, msg='【安全】-【SSH管理】- 设置root密码', module='safe')
                return DetailResponse(msg=msg)
            return ErrorResponse(msg=msg)

        if action == 'gen_root_key':
            if _ensure_root_keypair():
                RuyiAddOpLog(request, msg='【安全】-【SSH管理】- 生成root密钥', module='safe')
                return DetailResponse(data={'root_key': _read_root_private_key()}, msg='生成成功')
            return ErrorResponse(msg='生成失败')

        if action == 'download_root_key':
            if not _ensure_root_keypair():
                return ErrorResponse(msg='密钥不存在')
            key_content = _read_root_private_key()
            if not key_content:
                return ErrorResponse(msg='密钥不存在')
            resp = HttpResponse(key_content, content_type='application/octet-stream')
            resp['Content-Disposition'] = 'attachment; filename="root_id_rsa"'
            return resp

        return ErrorResponse(msg='类型错误')

