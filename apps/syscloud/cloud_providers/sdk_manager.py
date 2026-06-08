import importlib
import logging
import os
import subprocess
import platform
import tempfile

logger = logging.getLogger(__name__)

SDK_DEPS = {
    'boto3': {
        'package': 'boto3',
        'import_name': 'boto3',
        'version': '>=1.34.0',
        'providers': [
            'cloudflare_r2', 'huawei_obs', 'baidu_bos', 'ctyun_zos',
            'ks_ks3', 'jd_oss', 'google_gcs', 'minio',
        ],
        'size_mb': '~40MB',
        'description': 'S3兼容客户端，支持 Cloudflare R2、华为云OBS、百度云BOS、天翼云ZOS、金山云KS3、京东云OSS、谷歌云GCS、MinIO 等8+云厂商',
        'display_name': 'S3兼容客户端 (boto3)',
        'sdk_type': 'pip',
    },
    'oss2': {
        'package': 'oss2',
        'import_name': 'oss2',
        'version': '>=2.18.0',
        'providers': ['aliyun_oss'],
        'size_mb': '~5MB',
        'description': '阿里云OSS官方SDK，支持图片处理、跨区域复制等高级功能',
        'display_name': '阿里云OSS SDK (oss2)',
        'sdk_type': 'pip',
    },
    'cos-python-sdk-v5': {
        'package': 'cos-python-sdk-v5',
        'import_name': 'qcloud_cos',
        'version': '>=1.9.0',
        'providers': ['tencent_cos'],
        'size_mb': '~8MB',
        'description': '腾讯云COS官方SDK，支持CDN刷新、跨区域复制等高级功能',
        'display_name': '腾讯云COS SDK (cos-python-sdk-v5)',
        'sdk_type': 'pip',
    },
    'qiniu': {
        'package': 'qiniu',
        'import_name': 'qiniu',
        'version': '>=7.12.0',
        'providers': ['qiniu_kodo'],
        'size_mb': '~3MB',
        'description': '七牛云官方SDK，支持上传策略、CDN融合等高级功能',
        'display_name': '七牛云 SDK (qiniu)',
        'sdk_type': 'pip',
    },
    'webdavclient3': {
        'package': 'webdavclient3',
        'import_name': 'webdav3',
        'version': '>=3.14.0',
        'providers': ['webdav'],
        'size_mb': '~2MB',
        'description': 'WebDAV协议客户端，支持连接各类WebDAV服务（如AList）',
        'display_name': 'WebDAV客户端 (webdavclient3)',
        'sdk_type': 'pip',
    },
    'msal': {
        'package': 'msal',
        'import_name': 'msal',
        'version': '>=1.24.0',
        'providers': ['onedrive'],
        'size_mb': '~4MB',
        'description': 'Microsoft认证库，用于OneDrive OAuth2认证',
        'display_name': 'OneDrive认证库 (msal)',
        'sdk_type': 'pip',
    },
    'rclone': {
        'package': 'rclone',
        'import_name': '',
        'version': '>=1.65.0',
        'providers': [],
        'size_mb': '~50MB',
        'description': '云存储挂载工具，支持将各类云存储挂载为本地磁盘。Linux依赖FUSE，Windows依赖WinFSP',
        'display_name': '云存储挂载工具 (rclone)',
        'sdk_type': 'tool',
    },
}


def get_sdk_for_provider(provider_key):
    from .factory import PROVIDER_REGISTRY
    provider_info = PROVIDER_REGISTRY.get(provider_key)
    if not provider_info:
        return None
    return provider_info.get('sdk')


def get_providers_for_sdk(sdk_name):
    sdk_info = SDK_DEPS.get(sdk_name)
    if not sdk_info:
        return []
    return sdk_info.get('providers', [])


class SDKManager:

    @staticmethod
    def check_installed(sdk_name):
        sdk_info = SDK_DEPS.get(sdk_name)
        if not sdk_info:
            return False
        sdk_type = sdk_info.get('sdk_type', 'pip')
        if sdk_type == 'tool':
            return SDKManager._check_tool_installed(sdk_name)
        import_name = sdk_info.get('import_name', sdk_name)
        if not import_name:
            return False
        try:
            importlib.import_module(import_name)
            return True
        except ImportError:
            return False

    @staticmethod
    def _check_tool_installed(sdk_name):
        if sdk_name == 'rclone':
            try:
                result = subprocess.run(
                    ['rclone', 'version'],
                    capture_output=True, text=True, timeout=10,
                )
                return result.returncode == 0
            except (FileNotFoundError, subprocess.TimeoutExpired):
                return False
        return False

    @staticmethod
    def _check_fuse_available():
        if platform.system() == 'Windows':
            try:
                result = subprocess.run(
                    ['sc', 'query', 'WinFSP'],
                    capture_output=True, text=True, timeout=5,
                )
                return 'RUNNING' in result.stdout or 'STOPPED' in result.stdout
            except Exception:
                return False
        else:
            try:
                result = subprocess.run(
                    ['which', 'fusermount3'],
                    capture_output=True, text=True, timeout=5,
                )
                if result.returncode == 0:
                    return True
                result = subprocess.run(
                    ['which', 'fusermount'],
                    capture_output=True, text=True, timeout=5,
                )
                return result.returncode == 0
            except Exception:
                return False

    @staticmethod
    def get_installed_version(sdk_name):
        sdk_info = SDK_DEPS.get(sdk_name)
        if not sdk_info:
            return ''
        sdk_type = sdk_info.get('sdk_type', 'pip')
        if sdk_type == 'tool':
            return SDKManager._get_tool_version(sdk_name)
        import_name = sdk_info.get('import_name', sdk_name)
        try:
            mod = importlib.import_module(import_name)
            return getattr(mod, '__version__', '')
        except (ImportError, AttributeError):
            return ''

    @staticmethod
    def _get_tool_version(sdk_name):
        if sdk_name == 'rclone':
            try:
                result = subprocess.run(
                    ['rclone', 'version'],
                    capture_output=True, text=True, timeout=10,
                )
                if result.returncode == 0:
                    first_line = result.stdout.strip().split('\n')[0]
                    version = first_line.split()[-1] if first_line else ''
                    return version.strip('v')
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
        return ''

    @staticmethod
    def install_sdk(sdk_name):
        from apps.syscloud.models import CloudSdkRecord, CloudStorageAccount
        from django.utils import timezone

        sdk_info = SDK_DEPS.get(sdk_name)
        if not sdk_info:
            return False, "未知的SDK: {}".format(sdk_name)

        if SDKManager.check_installed(sdk_name):
            CloudSdkRecord.objects.update_or_create(
                sdk_name=sdk_name,
                defaults={
                    'install_status': 1,
                    'install_time': timezone.now(),
                    'sdk_version': SDKManager.get_installed_version(sdk_name),
                    'provider_keys': ','.join(sdk_info.get('providers', [])),
                    'error_msg': '',
                }
            )
            return True, "SDK已安装"

        record, _ = CloudSdkRecord.objects.get_or_create(
            sdk_name=sdk_name,
            defaults={
                'install_status': 2,
                'provider_keys': ','.join(sdk_info.get('providers', [])),
            }
        )
        record.install_status = 2
        record.error_msg = ''
        record.save(update_fields=['install_status', 'error_msg'])

        try:
            sdk_type = sdk_info.get('sdk_type', 'pip')
            if sdk_type == 'tool':
                success, msg = SDKManager._install_tool(sdk_name)
            else:
                from utils.common import pip_install_package
                success, msg = pip_install_package(sdk_info['package'])

            if not success:
                record.install_status = 3
                record.error_msg = msg[:500]
                record.save(update_fields=['install_status', 'error_msg'])
                return False, "安装失败: {}".format(msg[:200])

            installed_version = SDKManager.get_installed_version(sdk_name)
            record.install_status = 1
            record.install_time = timezone.now()
            record.sdk_version = installed_version
            record.error_msg = ''
            record.save(update_fields=[
                'install_status', 'install_time', 'sdk_version', 'error_msg'
            ])
            # 更新关联账号的sdk_installed状态
            provider_keys = sdk_info.get('providers', [])
            if provider_keys:
                CloudStorageAccount.objects.filter(
                    provider__in=provider_keys
                ).update(sdk_installed=True)
            return True, "安装成功 (版本: {})".format(installed_version) if installed_version else "安装成功"

        except Exception as e:
            record.install_status = 3
            record.error_msg = str(e)[:500]
            record.save(update_fields=['install_status', 'error_msg'])
            return False, "安装异常: {}".format(str(e)[:200])

    @staticmethod
    def _install_tool(sdk_name):
        if sdk_name == 'rclone':
            return SDKManager._install_rclone()
        return False, "未知的工具: {}".format(sdk_name)

    @staticmethod
    def _install_rclone():
        is_windows = platform.system() == 'Windows'
        try:
            if is_windows:
                return SDKManager._install_rclone_windows()
            else:
                return SDKManager._install_rclone_linux()
        except Exception as e:
            return False, "安装rclone异常: {}".format(str(e)[:200])

    @staticmethod
    def _install_rclone_linux():
        install_script = """
curl -s https://rclone.org/install.sh -o /tmp/rclone_install.sh && \
chmod +x /tmp/rclone_install.sh && \
sh /tmp/rclone_install.sh && \
rm -f /tmp/rclone_install.sh
"""
        try:
            result = subprocess.run(
                ['sh', '-c', install_script],
                capture_output=True, text=True, timeout=300,
            )
            if result.returncode == 0:
                return True, "rclone安装成功"
            return False, "rclone安装失败: {}".format(result.stderr[:300])
        except subprocess.TimeoutExpired:
            return False, "rclone安装超时"
        except Exception as e:
            return False, "rclone安装异常: {}".format(str(e)[:200])

    @staticmethod
    def _install_rclone_windows():
        import requests
        from utils.common import GetInstallPath

        try:
            result = subprocess.run(
                ['winget', 'install', 'Rclone.Rclone', '--accept-source-agreements', '--accept-package-agreements'],
                capture_output=True, text=True, timeout=300,
            )
            if result.returncode == 0:
                return True, "rclone安装成功"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        try:
            rclone_url = "https://downloads.rclone.org/rclone-current-windows-amd64.zip"
            tmp_dir = tempfile.mkdtemp(prefix='rclone_')
            zip_path = os.path.join(tmp_dir, 'rclone.zip')

            resp = requests.get(rclone_url, timeout=120, stream=True)
            resp.raise_for_status()
            with open(zip_path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)

            import zipfile
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(tmp_dir)

            install_dir = os.path.join(os.path.abspath(GetInstallPath()), 'rclone')
            os.makedirs(install_dir, exist_ok=True)

            for root, dirs, files in os.walk(tmp_dir):
                for fname in files:
                    if fname == 'rclone.exe':
                        src = os.path.join(root, fname)
                        dst = os.path.join(install_dir, fname)
                        import shutil
                        shutil.copy2(src, dst)
                        break

            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)

            rclone_exe = os.path.join(install_dir, 'rclone.exe')
            if not os.path.exists(rclone_exe):
                return False, "未找到rclone.exe，安装可能失败"

            current_path = os.environ.get('PATH', '')
            if install_dir not in current_path:
                try:
                    import winreg
                    key = winreg.OpenKey(
                        winreg.HKEY_LOCAL_MACHINE,
                        r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment',
                        0, winreg.KEY_SET_VALUE,
                    )
                    existing_path, _ = winreg.QueryValueEx(key, 'Path')
                    if install_dir not in existing_path:
                        new_path = existing_path.rstrip(';') + ';' + install_dir
                        winreg.SetValueEx(key, 'Path', 0, winreg.REG_EXPAND_SZ, new_path)
                    winreg.CloseKey(key)
                    os.environ['PATH'] = current_path.rstrip(';') + ';' + install_dir
                except Exception:
                    pass

            return True, "rclone安装成功，路径: {}".format(install_dir)

        except Exception as e:
            return False, "rclone下载安装失败: {}".format(str(e)[:200])

    @staticmethod
    def uninstall_sdk(sdk_name):
        from apps.syscloud.models import CloudSdkRecord, CloudStorageAccount

        sdk_info = SDK_DEPS.get(sdk_name)
        if not sdk_info:
            return False, "未知的SDK: {}".format(sdk_name)

        try:
            sdk_type = sdk_info.get('sdk_type', 'pip')
            if sdk_type == 'tool':
                success, msg = SDKManager._uninstall_tool(sdk_name)
            else:
                import sys
                cmd = [
                    sys.executable, '-m', 'pip', 'uninstall',
                    sdk_info['package'], '-y',
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                if result.returncode != 0:
                    return False, "卸载失败: {}".format(result.stderr[:200] if result.stderr else "未知错误")
                # 用pip show验证是否真正卸载（避免sys.modules缓存导致误判）
                check_cmd = [sys.executable, '-m', 'pip', 'show', sdk_info['package']]
                check_result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=30)
                if check_result.returncode == 0:
                    return False, "卸载失败：SDK仍然存在，可能被其他包依赖"
                # 清除当前进程的模块缓存
                import_name = sdk_info.get('import_name', sdk_info['package'])
                if import_name and import_name in sys.modules:
                    del sys.modules[import_name]
                success, msg = True, "卸载成功"

            # 更新SDK记录状态
            CloudSdkRecord.objects.filter(sdk_name=sdk_name).update(
                install_status=0,
                sdk_version='',
                error_msg='',
            )
            # 更新关联账号的sdk_installed状态
            provider_keys = sdk_info.get('providers', [])
            if provider_keys:
                CloudStorageAccount.objects.filter(
                    provider__in=provider_keys
                ).update(sdk_installed=False)
            return success, msg
        except Exception as e:
            return False, "卸载失败: {}".format(str(e)[:200])

    @staticmethod
    def _uninstall_tool(sdk_name):
        if sdk_name == 'rclone':
            return SDKManager._uninstall_rclone()
        return False, "未知的工具: {}".format(sdk_name)

    @staticmethod
    def _uninstall_rclone():
        is_windows = platform.system() == 'Windows'
        try:
            if is_windows:
                try:
                    result = subprocess.run(
                        ['winget', 'uninstall', 'Rclone.Rclone'],
                        capture_output=True, text=True, timeout=60,
                    )
                    if result.returncode == 0:
                        return True, "rclone卸载成功"
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    pass

                from utils.common import GetInstallPath
                install_dir = os.path.join(os.path.abspath(GetInstallPath()), 'rclone')
                if os.path.exists(install_dir):
                    import shutil
                    shutil.rmtree(install_dir, ignore_errors=True)
                return True, "rclone卸载成功"
            else:
                result = subprocess.run(
                    ['sh', '-c', 'which rclone && rm -f $(which rclone)'],
                    capture_output=True, text=True, timeout=30,
                )
                if result.returncode == 0:
                    return True, "rclone卸载成功"
                return False, "rclone卸载失败: {}".format(result.stderr[:200])
        except Exception as e:
            return False, "rclone卸载异常: {}".format(str(e)[:200])

    @staticmethod
    def ensure_sdk(provider_key):
        sdk_name = get_sdk_for_provider(provider_key)
        if not sdk_name:
            return False, "未找到该云厂商对应的SDK"
        if SDKManager.check_installed(sdk_name):
            return True, "SDK已就绪"
        sdk_info = SDK_DEPS.get(sdk_name)
        desc = sdk_info.get('description', '') if sdk_info else ''
        size = sdk_info.get('size_mb', '') if sdk_info else ''
        return False, "需要安装 {} (约{})。{}".format(
            sdk_info.get('display_name', sdk_name), size, desc
        )

    @staticmethod
    def get_all_sdk_status():
        result = []
        for sdk_name, sdk_info in SDK_DEPS.items():
            installed = SDKManager.check_installed(sdk_name)
            version = SDKManager.get_installed_version(sdk_name) if installed else ''
            result.append({
                'sdk_name': sdk_name,
                'display_name': sdk_info.get('display_name', sdk_name),
                'package': sdk_info['package'],
                'version': version,
                'installed': installed,
                'size_mb': sdk_info.get('size_mb', ''),
                'description': sdk_info.get('description', ''),
                'providers': sdk_info.get('providers', []),
                'sdk_type': sdk_info.get('sdk_type', 'pip'),
            })
        return result
