import os
import re
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_IS_WINDOWS = os.name == 'nt'

_LINUX_DENIED_WRITE_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r'^/etc/sudoers$',
        r'^/etc/sudoers\.d/',
        r'^/etc/passwd$',
        r'^/etc/shadow$',
        r'^/etc/group$',
        r'^/etc/gshadow$',
        r'^/etc/ssh/sshd_config$',
        r'^/etc/pam\.d/',
        r'^/etc/systemd/',
        r'^/etc/fstab$',
        r'^/etc/crontab$',
        r'^/boot/',
        r'^/proc/',
        r'^/sys/',
        r'^/dev/',
    ]
]

_WINDOWS_DENIED_WRITE_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r'^[a-zA-Z]:\\windows\\system32\\config\\',
        r'^[a-zA-Z]:\\windows\\system32\\drivers\\etc\\',
        r'^[a-zA-Z]:\\windows\\system32\\drivers\\etc$',
        r'^[a-zA-Z]:\\windows\\system32\\hal\.dll$',
        r'^[a-zA-Z]:\\windows\\system32\\ntdll\.dll$',
        r'^[a-zA-Z]:\\windows\\system32\\kernel32\.dll$',
        r'^[a-zA-Z]:\\windows\\system32\\winload\.exe$',
        r'^[a-zA-Z]:\\windows\\explorer\.exe$',
        r'^[a-zA-Z]:\\windows\\regedit\.exe$',
        r'^[a-zA-Z]:\\windows\\system32\\reg\.exe$',
        r'^[a-zA-Z]:\\windows\\system32\\net\.exe$',
        r'^[a-zA-Z]:\\windows\\system32\\net1\.exe$',
        r'^[a-zA-Z]:\\windows\\system32\\cmd\.exe$',
        r'^[a-zA-Z]:\\windows\\system32\\windowspowershell\\',
        r'^[a-zA-Z]:\\windows\\syswow64\\',
        r'^[a-zA-Z]:\\windows\\winsxs\\',
        r'^[a-zA-Z]:\\bootmgr$',
        r'^[a-zA-Z]:\\boot\\',
        r'^[a-zA-Z]:\\\$recycle\.bin\\',
        r'^[a-zA-Z]:\\system volume information\\',
        r'^[a-zA-Z]:\\pagefile\.sys$',
        r'^[a-zA-Z]:\\hiberfil\.sys$',
        r'^[a-zA-Z]:\\swapfile\.sys$',
        r'^[a-zA-Z]:\\ntldr$',
        r'^[a-zA-Z]:\\ntdetect\.com$',
    ]
]

_DENIED_WRITE_SUFFIXES_UNIX = [
    '/.ssh/authorized_keys',
    '/.ssh/id_rsa',
    '/.ssh/id_ed25519',
    '/.ssh/id_ecdsa',
    '/.ssh/config',
    '/.bashrc',
    '/.zshrc',
    '/.profile',
    '/.bash_profile',
    '/.zprofile',
    '/.netrc',
    '/.pgpass',
    '/.npmrc',
    '/.pypirc',
    '/.aws/credentials',
    '/.aws/config',
    '/.gnupg/',
    '/.kube/config',
    '/.docker/config.json',
]

_DENIED_WRITE_SUFFIXES_WINDOWS = [
    '\\.ssh\\authorized_keys',
    '\\.ssh\\id_rsa',
    '\\.ssh\\id_ed25519',
    '\\.ssh\\id_ecdsa',
    '\\.ssh\\config',
    '\\.gitconfig',
    '\\.npmrc',
    '\\.pypirc',
    '\\.aws\\credentials',
    '\\.aws\\config',
    '\\.kube\\config',
    '\\.docker\\config.json',
    '\\.wslconfig',
    '\\Microsoft\\Windows\\Start Menu\\Programs\\Startup\\',
]

_LINUX_DENIED_COMMAND_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r'\brm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)?(/|/etc|/boot|/usr|/var|/home|/root|/opt|/srv)',
        r'\brm\s+-[a-zA-Z]*r[a-zA-Z]*\s+(/|/etc|/boot|/usr|/var|/home|/root|/opt|/srv)',
        r'\bdd\s+if=',
        r'\bmkfs\.',
        r'\bfdisk\s+',
        r'\bparted\s+',
        r'\bshutdown\b',
        r'\breboot\b',
        r'\binit\s+[06]',
        r'\bchmod\s+(-[a-zA-Z]*\s+)?(000|777)\s+(/|/etc|/boot|/usr)',
        r'\bchown\s+.*\s+(/|/etc|/boot|/usr)',
        r'\buserdel\s+(-[a-zA-Z]*\s+)?root\b',
        r'\bpasswd\s+root\b',
        r'\bvisudo\b',
        r'\bsed\s+-i\s+.*sudoers',
        r'\bcp\s+/dev/null\s+(/etc/passwd|/etc/shadow|/etc/sudoers)',
        r'\bmv\s+.*(/etc/passwd|/etc/shadow|/etc/sudoers)',
        r'>\s*/etc/passwd',
        r'>\s*/etc/shadow',
        r'>\s*/etc/sudoers',
        r'>\s*/etc/ssh/sshd_config',
        r'>\s*/boot/',
    ]
]

_WINDOWS_DENIED_COMMAND_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r'\bformat\s+[a-zA-Z]:',
        r'\brd\s+/s\s+/q\s+[a-zA-Z]:\\',
        r'\brmdir\s+/s\s+/q\s+[a-zA-Z]:\\',
        r'\bdel\s+/[a-zA-Z]*f[a-zA-Z]*\s+/[a-zA-Z]*s[a-zA-Z]*\s+[a-zA-Z]:\\windows',
        r'\bdel\s+/[a-zA-Z]*f[a-zA-Z]*\s+/[a-zA-Z]*s[a-zA-Z]*\s+[a-zA-Z]:\\',
        r'\bshutdown\b',
        r'\breboot\b',
        r'\breg\s+(add|delete|import)\s+.*(HKLM|HKEY_LOCAL_MACHINE)',
        r'\bnet\s+user\s+\S+\s+\S+\s+/add',
        r'\bnet\s+user\s+administrator\b',
        r'\bnet\s+localgroup\s+administrators\s+\S+\s+/add',
        r'\bnetsh\s+(advfirewall|firewall)\s+',
        r'\bpowershell\s+.*-command\s+.*remove-item.*-recurse.*-force',
        r'\bpowershell\s+.*-command\s+.*stop-computer',
        r'\bpowershell\s+.*-command\s+.*restart-computer',
        r'\bsfc\s+/scannow',
        r'\bbcdedit\s+',
        r'\bdiskpart\s+',
        r'>\s*[a-zA-Z]:\\windows\\',
        r'>\s*[a-zA-Z]:\\pagefile\.sys',
        r'>\s*[a-zA-Z]:\\hiberfil\.sys',
    ]
]

LINUX_DENIED_READ_PATHS = [
    '/etc/shadow',
    '/etc/gshadow',
]

WINDOWS_DENIED_READ_PATHS = [
    re.compile(p, re.IGNORECASE) for p in [
        r'^[a-zA-Z]:\\windows\\system32\\config\\sam$',
        r'^[a-zA-Z]:\\windows\\system32\\config\\system$',
        r'^[a-zA-Z]:\\windows\\system32\\config\\security$',
        r'^[a-zA-Z]:\\windows\\repair\\',
    ]
]


def is_write_denied(path: str) -> Optional[str]:
    resolved = _resolve_path(path)
    if resolved is None:
        return None

    normalized = resolved.replace('\\', '/')

    if _IS_WINDOWS:
        for pattern in _WINDOWS_DENIED_WRITE_PATTERNS:
            if pattern.match(resolved):
                return f'安全防护：禁止写入系统关键路径 {path}'
    else:
        for pattern in _LINUX_DENIED_WRITE_PATTERNS:
            if pattern.match(normalized):
                return f'安全防护：禁止写入系统关键路径 {path}'

    home = _get_home()
    if home:
        home_resolved = _resolve_path(home)
        if home_resolved:
            if _IS_WINDOWS:
                check_path = resolved.lower()
                home_lower = home_resolved.lower()
                for suffix in _DENIED_WRITE_SUFFIXES_WINDOWS:
                    denied_full = home_lower + suffix.lower().rstrip('\\')
                    if check_path == denied_full or check_path.startswith(denied_full + '\\'):
                        return f'安全防护：禁止写入用户关键文件 {path}'
            else:
                check_path = normalized.lower()
                home_lower = home_resolved.replace('\\', '/').lower()
                for suffix in _DENIED_WRITE_SUFFIXES_UNIX:
                    denied_full = home_lower + suffix.lower().rstrip('/')
                    if check_path == denied_full or check_path.startswith(denied_full + '/'):
                        return f'安全防护：禁止写入用户关键文件 {path}'

    return None


def is_command_denied(command: str) -> Optional[str]:
    if _IS_WINDOWS:
        for pattern in _WINDOWS_DENIED_COMMAND_PATTERNS:
            if pattern.search(command):
                return f'安全防护：禁止执行危险命令（可能破坏系统关键文件或导致系统不可用）'
    else:
        for pattern in _LINUX_DENIED_COMMAND_PATTERNS:
            if pattern.search(command):
                return f'安全防护：禁止执行危险命令（可能破坏系统关键文件或导致系统不可用）'

    return None


def is_read_denied(path: str) -> Optional[str]:
    resolved = _resolve_path(path)
    if resolved is None:
        return None

    if _IS_WINDOWS:
        for pattern in WINDOWS_DENIED_READ_PATHS:
            if pattern.match(resolved):
                return f'安全防护：禁止读取系统敏感文件 {path}'
    else:
        normalized = resolved.replace('\\', '/')
        for denied in LINUX_DENIED_READ_PATHS:
            if normalized == denied:
                return f'安全防护：禁止读取系统敏感文件 {path}'

    return None


def _resolve_path(path: str) -> Optional[str]:
    try:
        return str(Path(path).expanduser().resolve())
    except Exception:
        return None


def _get_home() -> Optional[str]:
    try:
        return str(Path.home())
    except Exception:
        return None
