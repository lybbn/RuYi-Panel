import json
from datetime import datetime, timedelta
from django.db.models import Count, Q
from django.db.models.functions import TruncDate, TruncHour
from apps.sysai.tools.base import register_tool


@register_tool(id='waf_get_status', category='waf', name_cn='WAF状态', risk_level='low')
def waf_get_status():
    """获取WAF全局防护状态，包括WAF开关、防护模式、各模块配置概要。当用户询问WAF防护状态、是否开启WAF时使用。"""
    try:
        from apps.syswaf.models import WafGlobalConfig, WafSiteConfig
        config = WafGlobalConfig.get_instance()
        status_map = {'off': '关闭', 'observe': '观察模式', 'protect': '防护模式'}

        cc = config.get_config('cc_config')
        request_limit = config.get_config('request_limit_config')
        geo = config.get_config('geo_config')
        rule = config.get_config('rule_config')

        site_count = WafSiteConfig.objects.count()
        site_protected = WafSiteConfig.objects.exclude(waf_status='off').count()

        return {
            'waf_status': config.waf_status,
            'waf_status_display': status_map.get(config.waf_status, config.waf_status),
            'log_retention_days': config.log_retention_days,
            'cc_enabled': any(v.get('enabled', False) for v in cc.values() if isinstance(v, dict)),
            'request_limit_enabled': request_limit.get('enabled', False),
            'geo_enabled': geo.get('enabled', False),
            'rule_categories': {k: v.get('mode', 0) for k, v in rule.items()},
            'site_count': site_count,
            'site_protected': site_protected,
        }
    except Exception as e:
        return {'error': f'获取WAF状态失败: {str(e)}'}


@register_tool(id='waf_set_status', category='waf', name_cn='WAF模式切换', risk_level='high')
def waf_set_status(status: str):
    """切换WAF全局防护模式。⚠️此为高危操作，切换到防护模式可能影响正常业务流量。当用户要求开启/关闭WAF或切换防护模式时使用。

    Args:
        status: 防护模式，off(关闭)、observe(观察模式，仅记录不拦截)、protect(防护模式，拦截攻击)
    """
    if status not in ('off', 'observe', 'protect'):
        return {'error': '无效的防护模式，可选: off(关闭)、observe(观察模式)、protect(防护模式)'}

    try:
        from apps.syswaf.models import WafGlobalConfig
        from apps.syswaf.services import WafConfigSync

        config = WafGlobalConfig.get_instance()
        old_status = config.waf_status
        config.waf_status = status
        config.save()

        sync = WafConfigSync()
        sync.sync_global_config()

        status_map = {'off': '关闭', 'observe': '观察模式', 'protect': '防护模式'}
        return {
            'success': True,
            'old_status': status_map.get(old_status, old_status),
            'new_status': status_map.get(status, status),
            'message': f'WAF已从{status_map.get(old_status, old_status)}切换为{status_map.get(status, status)}',
        }
    except Exception as e:
        return {'error': f'切换WAF状态失败: {str(e)}'}


@register_tool(id='waf_get_dashboard', category='waf', name_cn='WAF仪表盘', risk_level='low')
def waf_get_dashboard(time_range: str = '24h'):
    """获取WAF防护仪表盘数据，包括攻击统计、拦截率、攻击类型分布、Top攻击IP等。当用户需要查看WAF防护概览、攻击趋势时使用。

    Args:
        time_range: 时间范围，24h(最近24小时)、7d(最近7天)、30d(最近30天)
    """
    try:
        from apps.syswaf.models import WafAttackLog, WafGlobalConfig

        today = datetime.now().date()
        today_start = datetime.combine(today, datetime.min.time())

        if time_range == '7d':
            start_time = today_start - timedelta(days=7)
        elif time_range == '30d':
            start_time = today_start - timedelta(days=30)
        else:
            start_time = today_start - timedelta(hours=24)

        today_attacks = WafAttackLog.objects.filter(create_at__gte=today_start).count()
        today_blocked = WafAttackLog.objects.filter(
            create_at__gte=today_start, action_taken='block'
        ).count()

        yesterday_start = today_start - timedelta(days=1)
        yesterday_attacks = WafAttackLog.objects.filter(
            create_at__gte=yesterday_start, create_at__lt=today_start
        ).count()

        total_attacks = WafAttackLog.objects.filter(create_at__gte=start_time).count()
        total_blocked = WafAttackLog.objects.filter(
            create_at__gte=start_time, action_taken='block'
        ).count()

        unique_attackers = WafAttackLog.objects.filter(
            create_at__gte=start_time
        ).values('src_ip').distinct().count()

        attack_types = list(WafAttackLog.objects.filter(
            create_at__gte=start_time
        ).values('attack_type').annotate(count=Count('id')).order_by('-count')[:10])

        severity_breakdown = list(WafAttackLog.objects.filter(
            create_at__gte=start_time
        ).values('severity').annotate(count=Count('id')).order_by('-count'))

        top_ips = list(WafAttackLog.objects.filter(
            create_at__gte=start_time
        ).values('src_ip', 'src_location').annotate(count=Count('id')).order_by('-count')[:10])

        top_urls = list(WafAttackLog.objects.filter(
            create_at__gte=start_time
        ).values('dst_url').annotate(count=Count('id')).order_by('-count')[:10])

        block_rate = round((today_blocked / today_attacks * 100), 1) if today_attacks > 0 else 0
        trend_percent = round(((today_attacks - yesterday_attacks) / yesterday_attacks * 100), 1) if yesterday_attacks > 0 else 0

        waf_config = WafGlobalConfig.get_instance()

        return {
            'waf_status': waf_config.waf_status,
            'stats': {
                'today_attacks': today_attacks,
                'today_blocked': today_blocked,
                'total_attacks': total_attacks,
                'total_blocked': total_blocked,
                'unique_attackers': unique_attackers,
                'block_rate': block_rate,
                'trend_percent': trend_percent,
            },
            'attack_types': attack_types,
            'severity_breakdown': severity_breakdown,
            'top_ips': top_ips,
            'top_urls': top_urls,
        }
    except Exception as e:
        return {'error': f'获取WAF仪表盘数据失败: {str(e)}'}


@register_tool(id='waf_get_attack_logs', category='waf', name_cn='WAF攻击日志', risk_level='low')
def waf_get_attack_logs(attack_type: str = '', severity: str = '', src_ip: str = '', limit: int = 20):
    """查询WAF攻击日志，支持按攻击类型、危险等级、来源IP筛选。当用户需要查看攻击记录、分析攻击详情时使用。

    Args:
        attack_type: 攻击类型筛选，如sql、xss、cmd、path、scan、bot、file
        severity: 危险等级筛选，critical(严重)、high(高危)、medium(中危)、low(低危)
        src_ip: 来源IP筛选
        limit: 返回条数，默认20
    """
    try:
        from apps.syswaf.models import WafAttackLog

        queryset = WafAttackLog.objects.all()
        if attack_type:
            queryset = queryset.filter(attack_type__icontains=attack_type)
        if severity:
            queryset = queryset.filter(severity=severity)
        if src_ip:
            queryset = queryset.filter(src_ip=src_ip)

        queryset = queryset.order_by('-create_at')[:limit]
        logs = list(queryset.values(
            'id', 'attack_type', 'severity', 'src_ip', 'src_location',
            'dst_domain', 'dst_url', 'request_method', 'action_taken',
            'matched_pattern', 'create_at'
        ))

        for log in logs:
            if log.get('create_at'):
                log['create_at'] = log['create_at'].strftime('%Y-%m-%d %H:%M:%S')

        return {
            'total': len(logs),
            'logs': logs,
        }
    except Exception as e:
        return {'error': f'查询攻击日志失败: {str(e)}'}


@register_tool(id='waf_manage_ip', category='waf', name_cn='WAF IP管理', risk_level='high')
def waf_manage_ip(action: str, ip: str = '', list_type: str = 'blacklist', remark: str = '', expire_hours: int = 0):
    """管理WAF的IP黑白名单，支持添加、删除、查询。⚠️此为高危操作，错误的IP封禁可能影响正常用户访问。当用户需要封禁IP、解封IP、添加IP白名单时使用。

    Args:
        action: 操作类型，add(添加)、remove(删除)、list(查询列表)
        ip: IP地址或CIDR，add/remove时必填
        list_type: 名单类型，blacklist(黑名单)、whitelist(白名单)
        remark: 备注说明
        expire_hours: 过期时间(小时)，0表示永久
    """
    try:
        from apps.syswaf.models import WafIpList
        from apps.syswaf.services import WafConfigSync

        if action == 'list':
            queryset = WafIpList.objects.filter(list_type=list_type, site_id=None)
            if ip:
                queryset = queryset.filter(ip__icontains=ip)
            items = list(queryset.values('id', 'ip', 'list_type', 'remark', 'source', 'enabled', 'location', 'expire_at', 'create_at'))
            for item in items:
                if item.get('create_at'):
                    item['create_at'] = item['create_at'].strftime('%Y-%m-%d %H:%M:%S')
                if item.get('expire_at'):
                    item['expire_at'] = item['expire_at'].strftime('%Y-%m-%d %H:%M:%S')
            return {'total': len(items), 'items': items}

        if action == 'add':
            if not ip:
                return {'error': '添加IP时ip参数不能为空'}
            exists = WafIpList.objects.filter(ip=ip, list_type=list_type).exists()
            if exists:
                return {'error': f'IP {ip} 已在{("黑名单" if list_type == "blacklist" else "白名单")}中'}

            expire_at = None
            if expire_hours > 0:
                expire_at = datetime.now() + timedelta(hours=expire_hours)

            entry = WafIpList(
                ip=ip,
                list_type=list_type,
                remark=remark or 'AI助手添加',
                source='manual',
                expire_at=expire_at,
            )
            entry.save()

            try:
                from utils.ip_util import IPQQwry
                results = IPQQwry.get_local_ips_area([ip.split('/')[0]])
                if results and results[0]:
                    entry.location = results[0]
                    entry.save()
            except Exception:
                pass

            sync = WafConfigSync()
            sync.sync_ip_lists()

            return {
                'success': True,
                'id': entry.id,
                'ip': ip,
                'list_type': list_type,
                'remark': remark,
                'expire_at': expire_at.strftime('%Y-%m-%d %H:%M:%S') if expire_at else '永久',
                'message': f'IP {ip} 已添加到{("黑名单" if list_type == "blacklist" else "白名单")}',
            }

        if action == 'remove':
            if not ip:
                return {'error': '删除IP时ip参数不能为空'}
            deleted = WafIpList.objects.filter(ip=ip, list_type=list_type).delete()
            if deleted[0] > 0:
                sync = WafConfigSync()
                sync.sync_ip_lists()
                return {'success': True, 'message': f'IP {ip} 已从{("黑名单" if list_type == "blacklist" else "白名单")}移除'}
            return {'error': f'IP {ip} 不在{("黑名单" if list_type == "blacklist" else "白名单")}中'}

        return {'error': f'无效操作: {action}，可选: add、remove、list'}
    except Exception as e:
        return {'error': f'IP管理操作失败: {str(e)}'}


@register_tool(id='waf_manage_rule', category='waf', name_cn='WAF规则管理', risk_level='high')
def waf_manage_rule(action: str, rule_id: str = '', category: str = '', enabled: bool = True):
    """管理WAF防护规则，支持查询、启用/禁用规则。⚠️此为高危操作，禁用关键规则可能导致服务器暴露在攻击之下。当用户需要查看WAF规则、开关某类防护规则时使用。

    Args:
        action: 操作类型，list(查询规则)、toggle(启用/禁用规则)、stats(规则统计)
        rule_id: 规则ID，toggle时必填，如sql-001、xss-001
        category: 规则分类筛选，sql、xss、cmd、path、scan、bot、file
        enabled: toggle操作时，True启用、False禁用
    """
    try:
        from apps.syswaf.models import WafRule, WafRuleCategory

        if action == 'stats':
            total = WafRule.objects.count()
            enabled_count = WafRule.objects.filter(enabled=True).count()
            by_category = list(WafRule.objects.values('category__name', 'category__code').annotate(
                total=Count('id'),
                enabled=Count('id', filter=Q(enabled=True))
            ).order_by('category__sort'))
            by_severity = list(WafRule.objects.values('severity').annotate(count=Count('id')))
            return {
                'total': total,
                'enabled': enabled_count,
                'disabled': total - enabled_count,
                'by_category': by_category,
                'by_severity': by_severity,
            }

        if action == 'list':
            queryset = WafRule.objects.select_related('category').all()
            if category:
                queryset = queryset.filter(category__code=category)
            if rule_id:
                queryset = queryset.filter(rule_id=rule_id)

            queryset = queryset.order_by('-severity', 'id')[:50]
            rules = list(queryset.values(
                'id', 'rule_id', 'name', 'category__name', 'severity',
                'enabled', 'is_builtin', 'trigger_count', 'description'
            ))
            return {'total': len(rules), 'rules': rules}

        if action == 'toggle':
            if not rule_id:
                return {'error': 'toggle操作需要指定rule_id'}
            rule = WafRule.objects.filter(rule_id=rule_id).first()
            if not rule:
                return {'error': f'规则 {rule_id} 不存在'}
            rule.enabled = enabled
            rule.save()
            from apps.syswaf.services import WafConfigSync
            sync = WafConfigSync()
            sync.sync_rules()
            return {
                'success': True,
                'rule_id': rule_id,
                'name': rule.name,
                'enabled': enabled,
                'message': f'规则 {rule.name} 已{"启用" if enabled else "禁用"}',
            }

        return {'error': f'无效操作: {action}，可选: list、toggle、stats'}
    except Exception as e:
        return {'error': f'规则管理操作失败: {str(e)}'}


@register_tool(id='waf_manage_url_rule', category='waf', name_cn='WAF URL规则管理', risk_level='medium')
def waf_manage_url_rule(action: str, url: str = '', list_type: str = 'blacklist', match_type: str = 'prefix', remark: str = ''):
    """管理WAF的URL黑白名单，支持添加、删除、查询。当用户需要拦截或放行特定URL路径时使用。

    Args:
        action: 操作类型，add(添加)、remove(删除)、list(查询列表)
        url: URL路径，add/remove时必填
        list_type: 名单类型，blacklist(黑名单)、whitelist(白名单)
        match_type: 匹配类型，exact(精确匹配)、prefix(前缀匹配)、regex(正则匹配)
        remark: 备注说明
    """
    try:
        from apps.syswaf.models import WafUrlBlacklist, WafUrlWhitelist
        from apps.syswaf.services import WafConfigSync

        model_map = {
            'blacklist': WafUrlBlacklist,
            'whitelist': WafUrlWhitelist,
        }
        model = model_map.get(list_type)
        if not model:
            return {'error': f'无效的名单类型: {list_type}'}

        if action == 'list':
            queryset = model.objects.filter(site_id=None)
            if url:
                queryset = queryset.filter(url__icontains=url)
            items = list(queryset.values('id', 'url', 'match_type', 'remark', 'enabled', 'create_at'))
            for item in items:
                if item.get('create_at'):
                    item['create_at'] = item['create_at'].strftime('%Y-%m-%d %H:%M:%S')
            return {'total': len(items), 'items': items}

        if action == 'add':
            if not url:
                return {'error': '添加URL时url参数不能为空'}
            entry = model(
                url=url,
                match_type=match_type,
                remark=remark or 'AI助手添加',
            )
            if hasattr(entry, 'response_code'):
                entry.response_code = 403
            entry.save()
            sync = WafConfigSync()
            sync.sync_url_lists()
            return {
                'success': True,
                'id': entry.id,
                'url': url,
                'list_type': list_type,
                'match_type': match_type,
                'message': f'URL {url} 已添加到{("黑名单" if list_type == "blacklist" else "白名单")}',
            }

        if action == 'remove':
            if not url:
                return {'error': '删除URL时url参数不能为空'}
            deleted = model.objects.filter(url=url, site_id=None).delete()
            if deleted[0] > 0:
                sync = WafConfigSync()
                sync.sync_url_lists()
                return {'success': True, 'message': f'URL {url} 已从{("黑名单" if list_type == "blacklist" else "白名单")}移除'}
            return {'error': f'URL {url} 不在{("黑名单" if list_type == "blacklist" else "白名单")}中'}

        return {'error': f'无效操作: {action}，可选: add、remove、list'}
    except Exception as e:
        return {'error': f'URL规则管理操作失败: {str(e)}'}


@register_tool(id='waf_get_site_config', category='waf', name_cn='WAF站点配置', risk_level='low')
def waf_get_site_config(site_id: int = 0):
    """获取WAF站点防护配置，包括站点WAF开关、CC防护、地域限制等。当用户需要查看某个网站的WAF配置时使用。

    Args:
        site_id: 站点ID，0表示查询所有站点配置概要
    """
    try:
        from apps.syswaf.models import WafSiteConfig, WafGlobalConfig

        if site_id:
            config = WafSiteConfig.objects.filter(site_id=site_id).first()
            if not config:
                return {'error': f'站点ID {site_id} 的WAF配置不存在'}
            effective = config.get_all_effective_configs()
            return {
                'site_id': config.site_id,
                'site_name': config.site_name,
                'waf_status': config.waf_status,
                'effective_configs': effective,
            }

        configs = WafSiteConfig.objects.all()
        result = []
        for config in configs:
            result.append({
                'site_id': config.site_id,
                'site_name': config.site_name,
                'waf_status': config.waf_status,
                'stats_blocked_today': config.stats_blocked_today,
                'stats_blocked_total': config.stats_blocked_total,
            })
        return {'total': len(result), 'sites': result}
    except Exception as e:
        return {'error': f'获取站点WAF配置失败: {str(e)}'}


@register_tool(id='waf_set_site_status', category='waf', name_cn='WAF站点模式切换', risk_level='high')
def waf_set_site_status(site_id: int, status: str):
    """切换指定站点的WAF防护模式。⚠️此为高危操作。当用户需要为某个网站单独开启/关闭WAF时使用。

    Args:
        site_id: 站点ID
        status: 防护模式，off(关闭)、observe(观察模式)、protect(防护模式)
    """
    if status not in ('off', 'observe', 'protect'):
        return {'error': '无效的防护模式，可选: off、observe、protect'}

    try:
        from apps.syswaf.models import WafSiteConfig

        config = WafSiteConfig.objects.filter(site_id=site_id).first()
        if not config:
            return {'error': f'站点ID {site_id} 的WAF配置不存在'}

        old_status = config.waf_status
        config.waf_status = status
        config.save()

        old_enabled = old_status != 'off'
        new_enabled = status != 'off'
        if old_enabled != new_enabled:
            site = config.site
            if site:
                from utils.ruyiclass.nginxClass import NginxClient
                nginx = NginxClient(siteName=site.name)
                ok, msg = nginx.set_site_waf(enabled=new_enabled, site_id=site_id)
                if not ok:
                    config.waf_status = old_status
                    config.save()
                    return {'error': f'Nginx配置失败: {msg}'}

        status_map = {'off': '关闭', 'observe': '观察模式', 'protect': '防护模式'}
        return {
            'success': True,
            'site_id': site_id,
            'site_name': config.site_name,
            'old_status': status_map.get(old_status, old_status),
            'new_status': status_map.get(status, status),
            'message': f'站点 {config.site_name} WAF已切换为{status_map.get(status, status)}',
        }
    except Exception as e:
        return {'error': f'切换站点WAF状态失败: {str(e)}'}


@register_tool(id='waf_ip_attack_analysis', category='waf', name_cn='WAF IP攻击分析', risk_level='low')
def waf_ip_attack_analysis(ip: str):
    """分析指定IP的攻击行为，包括攻击次数、攻击类型、首次/最近攻击时间等。当用户需要分析某个可疑IP的攻击行为时使用。

    Args:
        ip: 要分析的IP地址
    """
    try:
        from apps.syswaf.models import WafAttackLog, WafIpList

        total_attacks = WafAttackLog.objects.filter(src_ip=ip).count()
        if total_attacks == 0:
            return {'ip': ip, 'total_attacks': 0, 'message': f'IP {ip} 无攻击记录'}

        today = datetime.now().date()
        today_start = datetime.combine(today, datetime.min.time())
        today_attacks = WafAttackLog.objects.filter(src_ip=ip, create_at__gte=today_start).count()

        first_seen = WafAttackLog.objects.filter(src_ip=ip).order_by('create_at').first()
        last_seen = WafAttackLog.objects.filter(src_ip=ip).order_by('-create_at').first()

        attack_types = list(WafAttackLog.objects.filter(src_ip=ip).values('attack_type').annotate(
            count=Count('id')
        ).order_by('-count')[:5])

        target_domains = list(WafAttackLog.objects.filter(src_ip=ip).values('dst_domain').annotate(
            count=Count('id')
        ).order_by('-count')[:5])

        severity_breakdown = list(WafAttackLog.objects.filter(src_ip=ip).values('severity').annotate(
            count=Count('id')
        ))

        is_blacklisted = WafIpList.objects.filter(ip=ip, list_type='blacklist').exists()
        is_whitelisted = WafIpList.objects.filter(ip=ip, list_type='whitelist').exists()

        return {
            'ip': ip,
            'total_attacks': total_attacks,
            'today_attacks': today_attacks,
            'first_seen': first_seen.create_at.strftime('%Y-%m-%d %H:%M:%S') if first_seen else None,
            'last_seen': last_seen.create_at.strftime('%Y-%m-%d %H:%M:%S') if last_seen else None,
            'attack_types': attack_types,
            'target_domains': target_domains,
            'severity_breakdown': severity_breakdown,
            'is_blacklisted': is_blacklisted,
            'is_whitelisted': is_whitelisted,
            'recommendation': '建议加入黑名单' if total_attacks > 10 and not is_blacklisted else ('已在黑名单中' if is_blacklisted else '攻击次数较少，建议持续观察'),
        }
    except Exception as e:
        return {'error': f'IP攻击分析失败: {str(e)}'}
