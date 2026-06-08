import os
import subprocess
import platform
import logging

from .rclone_config import write_rclone_conf, get_rclone_config_path

logger = logging.getLogger(__name__)

DEFAULT_MOUNT_BASE_LINUX = '/mnt/ruyi_cloud'
DEFAULT_MOUNT_BASE_WINDOWS = 'R:'


def get_mount_base_path():
    if platform.system() == 'Windows':
        return DEFAULT_MOUNT_BASE_WINDOWS
    return DEFAULT_MOUNT_BASE_LINUX


def check_rclone_installed():
    from apps.syscloud.cloud_providers.sdk_manager import SDKManager
    return SDKManager.check_installed('rclone')


def check_fuse_available():
    from apps.syscloud.cloud_providers.sdk_manager import SDKManager
    return SDKManager._check_fuse_available()


def mount_cloud_storage(account, mount_path, options=None):
    if not check_rclone_installed():
        return False, "rclone未安装，请先安装rclone"

    if not check_fuse_available():
        if platform.system() == 'Windows':
            return False, "WinFSP未安装，Windows挂载需要安装WinFSP。下载地址: https://winfsp.dev/rel/"
        return False, "FUSE未安装，Linux挂载需要安装fuse3。执行: apt install fuse3 / yum install fuse3"

    config_path = write_rclone_conf([account])
    section_name = "cloud_{}".format(account.id)

    if not os.path.exists(mount_path):
        try:
            os.makedirs(mount_path, exist_ok=True)
        except Exception as e:
            return False, "创建挂载目录失败: {}".format(str(e)[:200])

    remote_path = "{}:".format(section_name)
    if account.bucket:
        remote_path = "{}:{}/".format(section_name, account.bucket)

    cmd = [
        'rclone', 'mount',
        remote_path,
        mount_path,
        '--config', config_path,
        '--allow-other',
        '--vfs-cache-mode', 'full',
        '--vfs-cache-max-size', '1G',
        '--vfs-read-chunk-size', '128M',
        '--vfs-read-ahead', '256M',
        '--buffer-size', '64M',
    ]

    if options:
        if isinstance(options, str) and options.strip():
            cmd.extend(options.strip().split())
        elif isinstance(options, dict):
            if options.get('read_only'):
                cmd.append('--read-only')
            if options.get('no_modtime'):
                cmd.append('--no-modtime')
            cache_max_size = options.get('cache_max_size', '1G')
            cmd.extend(['--vfs-cache-max-size', cache_max_size])

    if platform.system() == 'Windows':
        cmd.extend(['--volname', account.name])
    else:
        cmd.append('--daemon')

    try:
        if platform.system() == 'Windows':
            subprocess.Popen(
                cmd,
                creationflags=subprocess.CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30,
            )
            if result.returncode != 0:
                return False, "挂载失败: {}".format(result.stderr[:200])

        return True, "挂载成功"
    except Exception as e:
        return False, "挂载异常: {}".format(str(e)[:200])


def unmount_cloud_storage(mount_path):
    if platform.system() == 'Windows':
        try:
            result = subprocess.run(
                ['rclone', 'umount', mount_path],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0:
                return True, "卸载成功"
            return False, "卸载失败: {}".format(result.stderr[:200])
        except Exception as e:
            return False, "卸载异常: {}".format(str(e)[:200])
    else:
        try:
            result = subprocess.run(
                ['fusermount', '-uz', mount_path],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0:
                return True, "卸载成功"
            result = subprocess.run(
                ['umount', '-l', mount_path],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0:
                return True, "卸载成功"
            return False, "卸载失败: {}".format(result.stderr[:200])
        except Exception as e:
            return False, "卸载异常: {}".format(str(e)[:200])


def get_mount_status(mount_path):
    if not os.path.exists(mount_path):
        return 'not_exist'
    if platform.system() == 'Windows':
        if len(mount_path) == 2 and mount_path[1] == ':':
            try:
                result = subprocess.run(
                    ['rclone', 'ls', mount_path, '--max-depth', '1'],
                    capture_output=True, text=True, timeout=10,
                )
                return 'mounted' if result.returncode == 0 else 'error'
            except Exception:
                return 'error'
    else:
        try:
            with open('/proc/mounts', 'r') as f:
                mounts = f.read()
            if mount_path in mounts:
                return 'mounted'
        except Exception:
            pass
    return 'unmounted'
