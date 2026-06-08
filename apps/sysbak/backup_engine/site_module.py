import os
import json
import time
import shutil
import tarfile
from utils.common import ReadFile, WriteFile, current_os, GetWebRootPath, GetRuyiSetupPath, GetWindowsRealPath
from utils.ruyiclass.nginxClass import NginxClient
from utils.ruyiclass.webClass import WebClient
from apps.sysbak.backup_engine.base import BaseBackupModule


class SiteBackupModule(BaseBackupModule):
    """网站备份模块 - 备份网站记录、Nginx配置、SSL证书、源码、扩展配置"""

    def get_data_list(self):
        from apps.system.models import Sites
        sites = Sites.objects.all().order_by('-id')
        result = []
        for s in sites:
            size = 0
            if s.path and os.path.exists(s.path):
                for dirpath, dirnames, filenames in os.walk(s.path):
                    for f in filenames:
                        try:
                            size += os.path.getsize(os.path.join(dirpath, f))
                        except OSError:
                            pass
            result.append({
                'id': s.id,
                'name': s.name,
                'type': s.get_type_display(),
                'path': s.path,
                'size': size,
            })
        return result

    def backup(self, item_ids=None):
        from apps.system.models import Sites, SiteDomains

        results = {}
        sites = Sites.objects.filter(id__in=item_ids) if item_ids else Sites.objects.all()

        for site in sites:
            try:
                self.report_progress('site', site.id, 1, f'正在备份网站: {site.name}')
                self.log(f'开始备份网站: {site.name}')

                site_backup_dir = os.path.join(self.backup_dir, 'sites', site.name)
                os.makedirs(site_backup_dir, exist_ok=True)

                # 1. 备份数据库记录
                site_data = self._backup_site_record(site)
                WriteFile(os.path.join(site_backup_dir, 'site_data.json'), json.dumps(site_data, default=str, ensure_ascii=False))

                # 2. 备份Nginx配置
                self._backup_nginx_conf(site, site_backup_dir)

                # 3. 备份SSL证书
                self._backup_ssl_cert(site, site_backup_dir)

                # 4. 备份网站源码
                exclude_dirs = json.loads(self.backup_record.exclude_dirs or '[]')
                self._backup_site_files(site, site_backup_dir, exclude_dirs)

                # 5. 备份扩展配置（伪静态/重定向/反向代理/防盗链/流量限制）
                self._backup_site_extra_configs(site, site_backup_dir)

                self.report_progress('site', site.id, 2, f'网站备份完成: {site.name}')
                self.log(f'网站备份完成: {site.name}')
                results[site.id] = {'status': 2, 'error_msg': ''}
            except Exception as e:
                self.report_progress('site', site.id, 3, f'网站备份失败: {site.name} - {str(e)}')
                self.log(f'网站备份失败: {site.name} - {str(e)}')
                results[site.id] = {'status': 3, 'error_msg': str(e)}

        return results

    def restore(self, backup_dir, items_config, conflict_strategy='skip'):
        from apps.system.models import Sites, SiteDomains

        for site_data in items_config:
            site_name = site_data.get('name', '')
            if not site_name:
                continue

            existing = Sites.objects.filter(name=site_name).first()
            if existing:
                if conflict_strategy == 'skip':
                    self.log(f'跳过已存在的网站: {site_name}')
                    continue
                elif conflict_strategy == 'overwrite':
                    existing.delete()
                    self.log(f'删除已存在的网站: {site_name}')
                elif conflict_strategy == 'rename':
                    site_name = f"{site_name}_restored_{int(time.time())}"

            self.report_progress('site', site_data.get('id', ''), 1, f'正在还原网站: {site_name}')
            self.log(f'开始还原网站: {site_name}')

            try:
                site_path = site_data.get('path', '')
                # 跨平台路径适配
                if current_os == 'windows':
                    site_path = self._adapt_path_from_linux(site_path)
                elif current_os == 'linux':
                    site_path = self._adapt_path_from_windows(site_path)

                # 1. 还原网站源码
                source_tar = os.path.join(backup_dir, 'sites', site_data.get('name', ''), 'files', 'source.tar.gz')
                if site_path and os.path.exists(source_tar):
                    os.makedirs(site_path, exist_ok=True)
                    with tarfile.open(source_tar, 'r:gz') as tar:
                        for member in tar.getmembers():
                            member_path = os.path.join(site_path, member.name)
                            if os.path.abspath(member_path).startswith(os.path.abspath(site_path)):
                                tar.extract(member, site_path)
                    # Linux还原文件权限
                    if current_os != 'windows':
                        self._restore_file_permissions(site_path)

                # 2. 使用 NginxClient 创建网站
                nginx_client = NginxClient(siteName=site_name, sitePath=site_path)
                domain_list = [d['name'] + ':' + str(d.get('port', 80)) for d in site_data.get('domains', [])]
                try:
                    nginx_client.create_site(domainList=domain_list)
                except Exception as e:
                    self.log(f'NginxClient.create_site 失败，手动创建: {str(e)}')
                    new_site = Sites.objects.create(
                        name=site_name,
                        type=site_data.get('type', 0),
                        path=site_path,
                        remark=site_data.get('remark', ''),
                        status=site_data.get('status', True),
                        sslcfg=json.dumps(site_data.get('sslcfg', {})) if isinstance(site_data.get('sslcfg'), dict) else site_data.get('sslcfg', '{}'),
                        wafcfg=json.dumps(site_data.get('wafcfg', {})) if isinstance(site_data.get('wafcfg'), dict) else site_data.get('wafcfg', '{}'),
                        project_cfg=json.dumps(site_data.get('project_cfg', {})) if isinstance(site_data.get('project_cfg'), dict) else site_data.get('project_cfg', '{}'),
                    )
                    for domain_data in site_data.get('domains', []):
                        SiteDomains.objects.create(
                            name=domain_data['name'],
                            port=domain_data.get('port', 80),
                            site=new_site,
                        )

                # 3. 使用 NginxClient 还原各配置项

                # 还原Nginx配置（覆盖自动生成的配置）
                nginx_conf_src = os.path.join(backup_dir, 'sites', site_data.get('name', ''), f'{site_name}.conf')
                if os.path.exists(nginx_conf_src):
                    shutil.copy2(nginx_conf_src, nginx_client.confPath)

                # 还原SSL证书
                sslcfg = site_data.get('sslcfg')
                if sslcfg:
                    try:
                        if isinstance(sslcfg, str):
                            sslcfg = json.loads(sslcfg)
                        nginx_client.save_site_ssl_cert(sslcfg)
                    except Exception as e:
                        self.log(f'还原SSL证书失败: {str(e)}')

                # 还原扩展配置
                extra_dir = os.path.join(backup_dir, 'sites', site_data.get('name', ''), 'extra')
                self._restore_extra_configs(nginx_client, extra_dir)

                # 还原WAF配置
                if site_data.get('wafcfg'):
                    try:
                        nginx_client.set_site_waf(enabled=True, site_id=site_data.get('id'))
                    except Exception as e:
                        self.log(f'还原WAF配置失败: {str(e)}')

                # 重载Nginx
                try:
                    WebClient.reload_service(webserver='nginx')
                except Exception as e:
                    self.log(f'重载Nginx失败: {str(e)}')

                self.report_progress('site', site_data.get('id', ''), 2, f'网站还原完成: {site_name}')
                self.log(f'网站还原完成: {site_name}')
            except Exception as e:
                self.report_progress('site', site_data.get('id', ''), 3, f'网站还原失败: {site_name} - {str(e)}')
                self.log(f'网站还原失败: {site_name} - {str(e)}')

    # ==================== 备份辅助方法 ====================

    def _backup_site_record(self, site):
        """备份网站数据库记录"""
        from apps.system.models import SiteDomains
        site_data = {
            'id': site.id,
            'name': site.name,
            'type': site.type,
            'path': site.path,
            'remark': site.remark,
            'status': site.status,
            'sslcfg': site.sslcfg,
            'wafcfg': site.wafcfg,
            'project_cfg': site.project_cfg,
            'domains': [],
        }
        domains = SiteDomains.objects.filter(site_id=site.id)
        for d in domains:
            site_data['domains'].append({'name': d.name, 'port': d.port})
        return site_data

    def _backup_nginx_conf(self, site, site_backup_dir):
        """备份Nginx配置 - 使用 NginxClient 获取配置路径"""
        nginx_client = NginxClient(siteName=site.name, sitePath=site.path)
        conf_path = nginx_client.confPath
        if os.path.exists(conf_path):
            shutil.copy2(conf_path, os.path.join(site_backup_dir, f'{site.name}.conf'))
            self.log(f'备份Nginx配置: {site.name}')

    def _backup_ssl_cert(self, site, site_backup_dir):
        """备份SSL证书 - 使用 NginxClient 获取证书路径"""
        nginx_client = NginxClient(siteName=site.name, sitePath=site.path)
        ssl_dir = nginx_client.sslBasePath
        cert_backup_dir = os.path.join(site_backup_dir, 'ssl')
        if os.path.exists(ssl_dir):
            shutil.copytree(ssl_dir, cert_backup_dir, dirs_exist_ok=True)
            self.log(f'备份SSL证书: {site.name}')

    def _backup_site_files(self, site, site_backup_dir, exclude_dirs):
        """备份网站源码文件"""
        if not site.path or not os.path.exists(site.path):
            self.log(f'网站目录不存在，跳过源码备份: {site.name}')
            return

        files_dir = os.path.join(site_backup_dir, 'files')
        os.makedirs(files_dir, exist_ok=True)

        default_excludes = ['logs', 'cache', '__pycache__', '.git', 'node_modules', '.venv', 'tmp']
        all_excludes = list(set(default_excludes + exclude_dirs))

        tar_file = os.path.join(files_dir, 'source.tar.gz')
        if current_os == 'windows':
            with tarfile.open(tar_file, 'w:gz') as tar:
                for item in os.listdir(site.path):
                    if item.lower() not in [e.lower() for e in all_excludes]:
                        tar.add(os.path.join(site.path, item), arcname=item)
        else:
            from utils.common import RunCommand
            exclude_str = ' '.join([f'--exclude="{e}"' for e in all_excludes])
            cmd = f'tar -czf "{tar_file}" -C "{site.path}" {exclude_str} .'
            RunCommand(cmd, timeout=3600)

        self.log(f'备份网站源码: {site.name}')

    def _backup_site_extra_configs(self, site, site_backup_dir):
        """备份伪静态/重定向/反向代理/防盗链/流量限制"""
        nginx_client = NginxClient(siteName=site.name, sitePath=site.path)
        config_files = {
            'rewrite': nginx_client.rewritePath,
            'redirect': nginx_client.redirectPath,
            'proxy': nginx_client.proxyPath,
            'antichain': nginx_client.antichainPath,
            'ratelimit': nginx_client.ratelimitPath,
        }
        extra_dir = os.path.join(site_backup_dir, 'extra')
        os.makedirs(extra_dir, exist_ok=True)
        for key, path in config_files.items():
            if path and os.path.exists(path):
                shutil.copy2(path, os.path.join(extra_dir, f'{key}.json'))

    # ==================== 还原辅助方法 ====================

    def _restore_extra_configs(self, nginx_client, extra_dir):
        """还原扩展配置"""
        if not os.path.exists(extra_dir):
            return

        # 伪静态
        rewrite_file = os.path.join(extra_dir, 'rewrite.json')
        if os.path.exists(rewrite_file):
            try:
                nginx_client.set_site_rewrite({'rewrite': ReadFile(rewrite_file)})
                self.log('还原伪静态配置')
            except Exception as e:
                self.log(f'还原伪静态失败: {str(e)}')

        # 反向代理
        proxy_file = os.path.join(extra_dir, 'proxy.json')
        if os.path.exists(proxy_file):
            try:
                nginx_client.set_site_proxy(json.loads(ReadFile(proxy_file)))
                self.log('还原反向代理配置')
            except Exception as e:
                self.log(f'还原反向代理失败: {str(e)}')

        # 重定向
        redirect_file = os.path.join(extra_dir, 'redirect.json')
        if os.path.exists(redirect_file):
            try:
                nginx_client.set_site_redirect(json.loads(ReadFile(redirect_file)))
                self.log('还原重定向配置')
            except Exception as e:
                self.log(f'还原重定向失败: {str(e)}')

        # 防盗链
        antichain_file = os.path.join(extra_dir, 'antichain.json')
        if os.path.exists(antichain_file):
            try:
                nginx_client.set_antichain(json.loads(ReadFile(antichain_file)))
                self.log('还原防盗链配置')
            except Exception as e:
                self.log(f'还原防盗链失败: {str(e)}')

        # 流量限制
        ratelimit_file = os.path.join(extra_dir, 'ratelimit.json')
        if os.path.exists(ratelimit_file):
            try:
                nginx_client.set_site_ratelimit(json.loads(ReadFile(ratelimit_file)))
                self.log('还原流量限制配置')
            except Exception as e:
                self.log(f'还原流量限制失败: {str(e)}')

    def _adapt_path_from_linux(self, linux_path):
        """将Linux路径适配为Windows路径"""
        if not linux_path:
            return linux_path
        setup_path = GetRuyiSetupPath()
        return GetWindowsRealPath(setup_path, linux_path).replace('\\', '/')

    def _adapt_path_from_windows(self, windows_path):
        """将Windows路径适配为Linux路径"""
        if not windows_path:
            return windows_path
        www_root = GetWebRootPath()
        basename = os.path.basename(windows_path)
        return os.path.join(www_root, basename)

    def _restore_file_permissions(self, site_path):
        """还原文件权限（仅Linux）"""
        try:
            import pwd
            from utils.common import RunCommand
            www_user = 'www'
            try:
                pwd.getpwnam(www_user)
            except KeyError:
                www_user = 'nginx'
            RunCommand(f'chown -R {www_user}:{www_user} "{site_path}"')
        except Exception:
            pass
