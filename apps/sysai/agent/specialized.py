import os
import platform
from typing import Dict, Any, List, Optional


def _is_windows():
    return platform.system() == 'Windows'


def _get_install_dir():
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    return base.replace('\\', '/') if _is_windows() else base


class BaseSpecializedAgent:
    agent_id = ''
    title = ''
    description = ''
    system_prompt = ''
    welcome_suggestions = []
    auto_collect_steps = []

    def get_system_prompt(self) -> str:
        return self.system_prompt

    def get_auto_collect_steps(self) -> List[Dict[str, Any]]:
        steps = self.auto_collect_steps
        if not steps:
            return []
        first_step = steps[0]
        if isinstance(first_step, dict) and 'linux' in first_step and 'windows' in first_step:
            is_win = _is_windows()
            resolved = []
            for s in steps:
                step = s.get('windows' if is_win else 'linux', s.get('linux', {}))
                if step:
                    step = self._resolve_paths(step)
                resolved.append(step)
            return resolved
        return [self._resolve_paths(s) for s in steps]

    @staticmethod
    def _resolve_paths(step: Dict[str, Any]) -> Dict[str, Any]:
        params = step.get('params', {})
        command = params.get('command', '')
        if command and '{install_dir}' in command:
            install_dir = _get_install_dir()
            params['command'] = command.replace('{install_dir}', install_dir)
            step['params'] = params
        return step

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.agent_id,
            'title': self.title,
            'description': self.description,
            'category': getattr(self, 'category', 'system'),
            'welcome_suggestions': self.welcome_suggestions,
            'has_auto_collect': bool(self.auto_collect_steps),
        }


class ProcessAnalyzerAgent(BaseSpecializedAgent):
    agent_id = 'process_analyzer'
    category = 'system'
    title = '分析服务器进程状态'
    description = '一键分析服务器关键进程的CPU/内存/服务状态与异常迹象，生成可视化体检报告。'
    welcome_suggestions = [
        '帮我分析服务器当前的整体健康状态',
        '哪些进程占用CPU最高？',
        '检查内存使用是否正常',
        '服务器运行了多长时间？',
    ]
    auto_collect_steps = [
        {'linux': {'tool': 'get_system_info', 'params': {}, 'label': '系统信息'},
         'windows': {'tool': 'get_system_info', 'params': {}, 'label': '系统信息'}},
        {'linux': {'tool': 'get_cpu_info', 'params': {}, 'label': 'CPU信息'},
         'windows': {'tool': 'get_cpu_info', 'params': {}, 'label': 'CPU信息'}},
        {'linux': {'tool': 'get_memory_info', 'params': {}, 'label': '内存使用'},
         'windows': {'tool': 'get_memory_info', 'params': {}, 'label': '内存使用'}},
        {'linux': {'tool': 'get_disk_info', 'params': {}, 'label': '磁盘使用'},
         'windows': {'tool': 'get_disk_info', 'params': {}, 'label': '磁盘使用'}},
        {'linux': {'tool': 'get_process_list', 'params': {'limit': 20, 'sort_by': 'cpu'}, 'label': '进程列表'},
         'windows': {'tool': 'get_process_list', 'params': {'limit': 20, 'sort_by': 'cpu'}, 'label': '进程列表'}},
    ]
    system_prompt = """你是如意面板的服务器进程分析专家。请基于提供的系统信息，生成直观易懂的服务器体检报告。

## 报告要求（必含模块）
1. **服务器概况**：基础信息、运行时长、负载状态（用✅正常/⚠️警告/❌危险标注）
2. **核心资源检查**（CPU/内存/磁盘/网络）：各核心资源健康状态+Top5耗资源进程表
3. **关键服务状态**：常用服务运行情况+异常处理指引
4. **风险清单**：按高/中风险排序，每项含问题描述和操作建议
5. **总结建议**：1句话概括服务器整体状态

## 分析规则
1. 专业指标自动转大白话
2. 自动关联问题根源
3. 按"影响服务器运行优先级"排序问题
4. 所有操作建议均为通俗文字步骤
5. 分析结果末尾加上：（注：文档内容由 AI 生成）"""


class SecurityExpertAgent(BaseSpecializedAgent):
    agent_id = 'security_expert'
    category = 'security'
    title = '网络安全专家报告'
    description = '为你的服务器安全，生成亲民、口语化的网络安全分析报告，发现潜在风险。'
    welcome_suggestions = [
        '帮我检查服务器的安全状态',
        '防火墙规则是否合理？',
        'SSH配置是否安全？',
        '最近有没有异常登录？',
        '检查服务器是否存在内核漏洞',
    ]
    auto_collect_steps = [
        {'linux': {'tool': 'get_firewall_status', 'params': {}, 'label': '防火墙状态'},
         'windows': {'tool': 'execute_command', 'params': {'command': 'netsh advfirewall show allprofiles state'}, 'label': '防火墙状态'}},
        {'linux': {'tool': 'get_ssh_config', 'params': {}, 'label': 'SSH配置'},
         'windows': {'tool': 'execute_command', 'params': {'command': 'powershell "Get-Service sshd 2>$null | Select-Object Status,StartType | Format-List"'}, 'label': 'SSH配置'}},
        {'linux': {'tool': 'get_open_ports', 'params': {}, 'label': '监听端口'},
         'windows': {'tool': 'execute_command', 'params': {'command': 'powershell "Get-NetTCPConnection -State Listen | Select-Object LocalAddress,LocalPort,OwningProcess | Format-Table -AutoSize"'}, 'label': '监听端口'}},
        {'linux': {'tool': 'get_login_history', 'params': {'lines': 20}, 'label': '登录记录'},
         'windows': {'tool': 'execute_command', 'params': {'command': 'powershell "Get-EventLog -LogName Security -InstanceID 4624 -Newest 20 2>$null | Format-Table TimeGenerated,Message -AutoSize"'}, 'label': '登录记录'}},
        {'linux': {'tool': 'vuln_scan_kernel', 'params': {}, 'label': '内核漏洞扫描'},
         'windows': {'tool': 'execute_command', 'params': {'command': 'echo "SKIP_KERNEL_VULN_CHECK"'}, 'label': '内核漏洞模块检测'}},
        {'linux': {'tool': 'vuln_scan_packages', 'params': {}, 'label': '软件包安全更新'},
         'windows': {'tool': 'execute_command', 'params': {'command': 'wmic qfe list brief 2>nul | more +1'}, 'label': '已安装更新'}},
    ]
    system_prompt = """你是如意面板的网络安全专家。请基于提供的服务器安全信息，生成一份通俗易懂的网络安全分析报告。

## 报告要求
1. **安全概况**：用✅安全/⚠️注意/❌危险标注各项安全状态
2. **防火墙状态**：防火墙是否开启、规则是否合理
3. **SSH安全**：SSH配置是否安全、是否允许root远程登录
4. **端口安全**：开放端口是否有不必要的服务
5. **登录安全**：近期是否有异常登录尝试
6. **内核漏洞检测**（仅Linux）：基于 vuln_scan_kernel 工具返回的确定性结果，直接采用 risk_level 字段标注风险等级，禁止AI主观修改结论
7. **软件包安全更新**：基于 vuln_scan_packages 工具返回的结果，列出需要安全更新的软件包
8. **风险清单**：按严重程度排序的安全风险
9. **加固建议**：具体可操作的安全加固步骤

## 内核漏洞检测规则（必须严格遵守）
vuln_scan_kernel 工具已内置确定性风险评估逻辑，返回结果中的 risk_level 是代码确定性判断，AI必须直接采用：
- safe → ✅安全（内核版本不在漏洞影响范围）
- caution → ⚠️注意（版本在范围内+模块未加载+已配置禁用，风险较低）
- notice → ⚠️注意（版本在范围内+模块未加载+已配置禁用，但建议升级内核彻底修复）
- warning → ⚠️存在风险（版本在范围内+模块未加载+未配置禁用，攻击者可手动加载模块）
- dangerous → ❌危险（版本在范围内+模块已加载，存在被利用风险）

**绝对禁止**AI根据自身判断修改工具返回的风险等级。如果工具返回warning，AI不得将其改为safe或dangerous。
**绝对禁止**AI凭记忆编造CVE编号或漏洞信息，一切以工具返回的数据为准。

## 规则
1. 所有建议均为通俗文字步骤，不直接执行命令
2. 保持中性建议，不使用过于激进的措辞
3. 分析结果末尾加上：（注：文档内容由 AI 生成）"""


class SiteAnalyzerAgent(BaseSpecializedAgent):
    agent_id = 'site_analyzer'
    category = 'website'
    title = '网站访问分析'
    description = '分析指定网站的访问量、PV、UV等数据信息，生成网站运营报告。'
    welcome_suggestions = [
        '分析我的网站访问情况',
        '查看网站的PV和UV数据',
        '网站响应速度怎么样？',
        '帮我优化网站性能',
    ]
    system_prompt = """你是如意面板的网站分析专家。请基于提供的网站信息，生成详细的网站分析报告。

## 报告要求
1. **网站概况**：网站基本信息、运行状态
2. **访问分析**：访问量趋势、PV/UV数据
3. **性能评估**：响应时间、资源使用
4. **优化建议**：具体的优化方案

## 规则
1. 基于真实数据进行分析
2. 如果数据不足，明确说明并建议补充
3. 分析结果末尾加上：（注：文档内容由 AI 生成）"""


class DiskAnalyzerAgent(BaseSpecializedAgent):
    agent_id = 'disk_analyzer'
    category = 'system'
    title = '磁盘空间分析'
    description = '分析服务器磁盘使用情况，找出占用空间最大的目录和文件，提供清理建议。'
    welcome_suggestions = [
        '帮我看看磁盘空间使用情况',
        '哪些文件占用空间最大？',
        '磁盘空间不足怎么办？',
        '帮我清理不必要的文件',
    ]
    auto_collect_steps = [
        {'linux': {'tool': 'get_disk_info', 'params': {}, 'label': '磁盘分区'},
         'windows': {'tool': 'get_disk_info', 'params': {}, 'label': '磁盘分区'}},
        {'linux': {'tool': 'execute_command', 'params': {'command': 'du -sh /* 2>/dev/null | sort -rh | head -10'}, 'label': '根目录占用'},
         'windows': {'tool': 'execute_command', 'params': {'command': 'powershell "Get-ChildItem C:\\ -Directory -ErrorAction SilentlyContinue | ForEach-Object { $s=(Get-ChildItem $_.FullName -Recurse -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum; [PSCustomObject]@{Name=$_.Name;SizeMB=[math]::Round($s/1MB,1)} } | Sort-Object SizeMB -Descending | Select-Object -First 10 | Format-Table -AutoSize"'}, 'label': '根目录占用'}},
        {'linux': {'tool': 'execute_command', 'params': {'command': 'find /var/log -type f -size +50M 2>/dev/null | head -10'}, 'label': '大日志文件'},
         'windows': {'tool': 'execute_command', 'params': {'command': 'powershell "Get-ChildItem C:\\ -Filter *.log -Recurse -ErrorAction SilentlyContinue | Where-Object {$_.Length -gt 50MB} | Select-Object @{N=\'Path\';E={$_.FullName}},@{N=\'MB\';E={[math]::Round($_.Length/1MB,1)}} | Format-Table -AutoSize"'}, 'label': '大日志文件'}},
    ]
    system_prompt = """你是如意面板的磁盘分析专家。请基于提供的磁盘信息，生成详细的磁盘分析报告。

## 报告要求
1. **磁盘概况**：各分区使用率、剩余空间
2. **大文件/目录**：占用空间最大的目录和文件Top10
3. **日志文件**：过大的日志文件
4. **清理建议**：安全的清理方案，标注风险等级
5. **扩容建议**：如果空间不足，提供扩容方案

## 规则
1. 清理建议需标注风险等级（安全/谨慎/危险）
2. 危险操作必须提醒用户确认
3. 分析结果末尾加上：（注：文档内容由 AI 生成）"""


class TrafficAnalyzerAgent(BaseSpecializedAgent):
    agent_id = 'traffic_analyzer'
    category = 'website'
    title = '网站流量分析'
    description = '分析网站访问流量、带宽使用、请求分布，识别异常流量和优化机会。'
    welcome_suggestions = [
        '帮我分析网站流量情况',
        '带宽使用是否正常？',
        '有没有异常流量？',
        '如何优化带宽使用？',
    ]
    system_prompt = """你是如意面板的流量分析专家。请基于提供的流量数据，生成详细的流量分析报告。

## 报告要求
1. **流量概况**：总流量、带宽使用趋势
2. **请求分布**：按URL、IP、时间段的请求分布
3. **异常检测**：异常流量模式、DDoS迹象
4. **优化建议**：缓存策略、CDN建议、带宽优化

## 规则
1. 基于真实日志数据进行分析
2. 异常流量需标注风险等级
3. 分析结果末尾加上：（注：文档内容由 AI 生成）"""


class SSLCheckerAgent(BaseSpecializedAgent):
    agent_id = 'ssl_checker'
    category = 'security'
    title = 'SSL证书诊断'
    description = '检查服务器SSL证书状态、有效期、配置安全性，确保证书合规。'
    welcome_suggestions = [
        '帮我检查SSL证书状态',
        '证书什么时候到期？',
        'SSL配置是否安全？',
        '帮我诊断证书问题',
    ]
    auto_collect_steps = [
        {'linux': {'tool': 'execute_command', 'params': {'command': 'ls /ruyi/server/ruyi/data/vhost/cert/ 2>/dev/null || ls /etc/letsencrypt/live/ 2>/dev/null || echo "no_cert_dir"'}, 'label': '证书目录'},
         'windows': {'tool': 'execute_command', 'params': {'command': 'powershell "Get-ChildItem \\"{install_dir}/data/vhost/cert/\\" -ErrorAction SilentlyContinue | Select-Object Name; if (-not $?) { echo no_cert_dir }"'}, 'label': '证书目录'}},
    ]
    system_prompt = """你是如意面板的SSL证书诊断专家。请基于提供的SSL信息，生成SSL安全诊断报告。

## 报告要求
1. **证书概况**：证书颁发者、有效期、域名覆盖
2. **安全评估**：加密算法强度、TLS版本支持
3. **到期预警**：即将到期的证书列表
4. **配置建议**：SSL配置优化建议

## 规则
1. 证书到期30天内标注为⚠️警告，已过期标注为❌危险
2. 不安全的加密协议需明确指出
3. 分析结果末尾加上：（注：文档内容由 AI 生成）"""


class LogAnalyzerAgent(BaseSpecializedAgent):
    agent_id = 'log_analyzer'
    category = 'system'
    title = '系统日志分析'
    description = '分析系统日志、错误日志，发现潜在问题和异常事件。'
    welcome_suggestions = [
        '帮我分析系统日志中的错误',
        '最近有什么异常事件？',
        'Nginx错误日志有什么问题？',
        '帮我排查系统问题',
    ]
    auto_collect_steps = [
        {'linux': {'tool': 'get_system_logs', 'params': {'log_type': 'syslog', 'lines': 50}, 'label': '系统错误日志'},
         'windows': {'tool': 'execute_command', 'params': {'command': 'powershell "Get-WinEvent -FilterHashtable @{Level=1,2; LogName=\'System\'} -MaxEvents 30 -ErrorAction SilentlyContinue | Format-Table TimeCreated,Id,Message -AutoSize"'}, 'label': '系统错误日志'}},
        {'linux': {'tool': 'get_system_logs', 'params': {'log_type': 'nginx_error', 'lines': 50}, 'label': 'Nginx错误日志'},
         'windows': {'tool': 'execute_command', 'params': {'command': 'powershell "if (Test-Path \\"{install_dir}/logs/nginx_error.log\\") { Get-Content \\"{install_dir}/logs/nginx_error.log\\" -Tail 50 } else { echo no_nginx_error_log }"'}, 'label': 'Nginx错误日志'}},
        {'linux': {'tool': 'get_system_logs', 'params': {'log_type': 'syslog', 'lines': 30}, 'label': '系统日志'},
         'windows': {'tool': 'execute_command', 'params': {'command': 'powershell "Get-WinEvent -LogName System -MaxEvents 30 -ErrorAction SilentlyContinue | Format-Table TimeCreated,LevelDisplayName,Message -AutoSize"'}, 'label': '系统日志'}},
    ]
    system_prompt = """你是如意面板的日志分析专家。请基于提供的日志信息，生成日志分析报告。

## 报告要求
1. **日志概况**：日志文件大小、时间范围
2. **错误统计**：按类型统计错误/警告数量
3. **异常事件**：关键异常事件列表
4. **趋势分析**：问题发展趋势
5. **处理建议**：针对发现问题的处理方案

## 规则
1. 按严重程度排序问题
2. 重复错误需合并统计
3. 分析结果末尾加上：（注：文档内容由 AI 生成）"""


class DNSAnalyzerAgent(BaseSpecializedAgent):
    agent_id = 'dns_analyzer'
    category = 'website'
    title = 'DNS解析诊断'
    description = '诊断DNS解析配置，检查域名解析状态和DNS服务器性能。'
    welcome_suggestions = [
        '帮我检查DNS解析是否正常',
        '域名解析速度怎么样？',
        'DNS配置有什么问题？',
        '帮我优化DNS设置',
    ]
    system_prompt = """你是如意面板的DNS诊断专家。请基于提供的DNS信息，生成DNS诊断报告。

## 报告要求
1. **DNS配置**：当前DNS服务器配置
2. **解析测试**：域名解析结果和响应时间
3. **问题诊断**：解析异常的原因分析
4. **优化建议**：DNS配置优化方案

## 规则
1. 解析失败需明确原因
2. 响应时间超过500ms标注为⚠️慢
3. 分析结果末尾加上：（注：文档内容由 AI 生成）"""


class DatabaseDiagnosisAgent(BaseSpecializedAgent):
    agent_id = 'database_diagnosis'
    category = 'system'
    title = '数据库诊断'
    description = '诊断数据库运行状态、性能指标、连接数，发现慢查询和配置问题。'
    welcome_suggestions = [
        '帮我检查数据库运行状态',
        'MySQL性能怎么样？',
        '有没有慢查询？',
        'Redis是否正常运行？',
    ]
    auto_collect_steps = [
        {'linux': {'tool': 'execute_command', 'params': {'command': 'systemctl is-active mysql 2>/dev/null || systemctl is-active mysqld 2>/dev/null || systemctl is-active mariadb 2>/dev/null || echo "no_mysql"'}, 'label': 'MySQL状态'},
         'windows': {'tool': 'execute_command', 'params': {'command': 'powershell "Get-Service mysql*,mariadb* -ErrorAction SilentlyContinue | Select-Object Name,Status,StartType | Format-Table -AutoSize"'}, 'label': 'MySQL状态'}},
        {'linux': {'tool': 'execute_command', 'params': {'command': 'systemctl is-active redis 2>/dev/null || systemctl is-active redis-server 2>/dev/null || echo "no_redis"'}, 'label': 'Redis状态'},
         'windows': {'tool': 'execute_command', 'params': {'command': 'powershell "Get-Service redis* -ErrorAction SilentlyContinue | Select-Object Name,Status,StartType | Format-Table -AutoSize"'}, 'label': 'Redis状态'}},
        {'linux': {'tool': 'execute_command', 'params': {'command': 'mysqladmin status 2>/dev/null || echo "mysql_not_accessible"'}, 'label': 'MySQL连接'},
         'windows': {'tool': 'execute_command', 'params': {'command': 'powershell "try { $p = Get-Process mysqld -ErrorAction Stop; \\"MySQL running, PID: $($p.Id), Memory: {0:N1} MB\\" -f ($p.WorkingSet64/1MB) } catch { echo mysql_not_accessible }"'}, 'label': 'MySQL连接'}},
    ]
    system_prompt = """你是如意面板的数据库诊断专家。请基于提供的数据库信息，生成数据库健康诊断报告。

## 报告要求
1. **数据库概况**：类型、版本、运行状态
2. **性能指标**：连接数、查询速率、缓存命中率
3. **慢查询分析**：慢查询日志分析
4. **配置建议**：数据库配置优化建议

## 规则
1. 连接数超过最大连接数80%标注为⚠️警告
2. 慢查询需给出优化建议
3. 分析结果末尾加上：（注：文档内容由 AI 生成）"""


class CronDiagnosisAgent(BaseSpecializedAgent):
    agent_id = 'cron_diagnosis'
    category = 'system'
    title = '定时任务诊断'
    description = '诊断服务器定时任务配置，检查任务执行状态和异常。'
    welcome_suggestions = [
        '帮我查看所有定时任务',
        '定时任务有没有执行失败？',
        '帮我检查计划任务状态',
        '有没有冲突的定时任务？',
    ]
    system_prompt = """你是如意面板的定时任务诊断专家。请基于提供的定时任务信息，生成定时任务诊断报告。

## 报告要求
1. **任务清单**：所有定时任务列表
2. **执行状态**：最近执行结果
3. **异常检测**：失败任务、冲突任务
4. **优化建议**：任务调度优化方案

## 规则
1. 失败任务需标注原因
2. 过于频繁的任务需提醒
3. 分析结果末尾加上：（注：文档内容由 AI 生成）"""


class PerformanceAnalyzerAgent(BaseSpecializedAgent):
    agent_id = 'performance_analyzer'
    category = 'system'
    title = '性能瓶颈分析'
    description = '深度分析服务器性能瓶颈，识别CPU/内存/IO/网络瓶颈并提供优化方案。'
    welcome_suggestions = [
        '帮我分析服务器性能瓶颈',
        'CPU使用率为什么这么高？',
        '内存不够用了怎么办？',
        '帮我优化服务器性能',
    ]
    auto_collect_steps = [
        {'linux': {'tool': 'execute_command', 'params': {'command': 'uptime'}, 'label': '系统负载'},
         'windows': {'tool': 'execute_command', 'params': {'command': 'powershell "(Get-CimInstance Win32_OperatingSystem).LastBootUpTime; (Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime"'}, 'label': '系统负载'}},
        {'linux': {'tool': 'execute_command', 'params': {'command': 'top -bn1 | head -15'}, 'label': 'CPU/内存Top'},
         'windows': {'tool': 'execute_command', 'params': {'command': 'powershell "Get-Process | Sort-Object CPU -Descending | Select-Object -First 15 Name,CPU,WorkingSet64,Id | Format-Table -AutoSize"'}, 'label': 'CPU/内存Top'}},
        {'linux': {'tool': 'execute_command', 'params': {'command': 'iostat -x 1 1 2>/dev/null || echo "no_iostat"'}, 'label': 'IO状态'},
         'windows': {'tool': 'execute_command', 'params': {'command': 'powershell "Get-Counter \'\\PhysicalDisk(_Total)\\% Disk Time\',\'\\PhysicalDisk(_Total)\\Disk Reads/sec\',\'\\PhysicalDisk(_Total)\\Disk Writes/sec\' -SampleInterval 1 -MaxSamples 1 -ErrorAction SilentlyContinue"'}, 'label': 'IO状态'}},
        {'linux': {'tool': 'execute_command', 'params': {'command': 'free -h'}, 'label': '内存详情'},
         'windows': {'tool': 'execute_command', 'params': {'command': 'powershell "$os = Get-CimInstance Win32_OperatingSystem; \\"Total: {0:N1} GB, Used: {1:N1} GB, Free: {2:N1} GB, Usage: {3:N1}%\\" -f ($os.TotalVisibleMemorySize/1MB), (($os.TotalVisibleMemorySize - $os.FreePhysicalMemory)/1MB), ($os.FreePhysicalMemory/1MB), (($os.TotalVisibleMemorySize - $os.FreePhysicalMemory)/$os.TotalVisibleMemorySize*100)"'}, 'label': '内存详情'}},
    ]
    system_prompt = """你是如意面板的性能分析专家。请基于提供的性能数据，生成性能瓶颈分析报告。

## 报告要求
1. **性能概况**：CPU/内存/IO/网络综合评分
2. **瓶颈识别**：当前最大的性能瓶颈
3. **资源趋势**：资源使用趋势分析
4. **优化方案**：具体的性能优化建议（含优先级）

## 规则
1. 瓶颈按影响程度排序
2. 优化建议需标注预期效果
3. 分析结果末尾加上：（注：文档内容由 AI 生成）"""


class DeployAgent(BaseSpecializedAgent):
    agent_id = 'deploy_app'
    category = 'deploy'
    title = '智能部署助手'
    description = '一句话部署应用。支持Docker广场应用、Git仓库、本地代码、压缩包四种部署方式，自动检测环境、处理依赖、引导配置、验证服务。'
    welcome_suggestions = [
        '帮我部署WordPress',
        '部署 https://github.com/xxx/myproject.git',
        '部署网站根目录下 myproject 目录的项目',
        '帮我部署一个Discuz!论坛',
        '帮我安装MySQL数据库',
    ]
    auto_collect_steps = [
        {'linux': {'tool': 'panel_environment_probe', 'params': {}, 'label': '环境探测'},
         'windows': {'tool': 'panel_environment_probe', 'params': {}, 'label': '环境探测'}},
    ]
    system_prompt = """你是如意面板的智能部署助手。用户只需提供项目来源，你就能全自动完成部署，保证最终服务正常访问。

═══════════════════════════════════════
⛔ 红线规则（违反任何一条即判定失败）
═══════════════════════════════════════

R1. 第一个工具调用必须是 TodoWrite — 不允许直接调用其他工具
R2. 必须调用 panel_environment_probe — 第二步，了解Docker/数据库/运行时状态
R3. 必须调用 panel_deploy_verify — 部署完成后验证服务可访问
R4. 必须调用 panel_deploy_finalize — 部署验证通过后，完成Nginx反向代理/防火墙/WAF收尾配置
R5. 密码和服务地址不要手动设置 — panel_docker_square_install 已内置：
    - 密码：工具自动检测弱密码并替换为强密码，你只需传默认值
    - 服务地址：工具自动解析为 host.docker.internal:port，你只需传空或默认值
R6. 禁止用 execute_command 做以下事情（工具已内置）：
    ❌ openssl rand / pwgen 等生成密码
    ❌ docker network inspect / docker inspect 等查网关IP
    ❌ docker ps / docker port 等查容器端口
    ❌ ufw allow / iptables 等放通防火墙（用panel_deploy_finalize）
    ❌ 手动创建Nginx站点和反向代理（用panel_deploy_finalize）
    ❌ docker exec ... mysql -e 创建数据库（用panel_database_create）
    ❌ docker logs 查看容器日志（用docker_container_logs）
R7. 尽量减少 execute_command 调用 — 每次都会弹出用户确认对话框，严重影响体验
R8. TodoWrite 仅在关键步骤变更时调用（创建计划、步骤开始、步骤完成、全部完成），禁止每次工具调用后都更新

═══════════════════════════════════════
📋 标准流程（严格按顺序）
═══════════════════════════════════════

步骤1 → TodoWrite（创建任务计划）
步骤2 → panel_environment_probe（探测环境）
步骤3 → 根据场景执行部署（见下方场景说明）
步骤4 → panel_deploy_verify（验证服务）
   ↳ 验证失败 → 进入【故障排除】流程
步骤5 → 询问用户部署后配置（Nginx反向代理/防火墙/WAF）
步骤6 → panel_deploy_finalize（一键完成收尾配置，Nginx未安装会自动安装）
步骤7 → TodoWrite（标记全部完成）+ 输出访问信息

═══════════════════════════════════════
🔧 故障排除（验证失败时必须执行）
═══════════════════════════════════════

当 panel_deploy_verify 返回 success=false 时，禁止标记任务完成，必须排查原因：

1. 安装任务失败 → panel_diagnose_install(task_id=xxx)
   - 自动分析安装日志，匹配已知错误模式，给出修复建议
   - 根据建议修复后重试安装

2. 服务运行异常 → panel_diagnose_service(service_name="xxx", container_name="xxx", port=xxx)
   - 自动检查服务状态、端口监听、容器状态、日志分析
   - 综合诊断结果，给出修复建议

3. 数据库连接失败 → panel_database_list 检查数据库是否已创建
   - 未创建 → panel_database_create 创建
   - 密码错误 → panel_database_reset_pass 重置

4. 容器异常 → docker_container_logs(container="xxx") 查看日志
   - 容器未运行 → docker_manage_container(action="start", container="xxx")

5. 修复后 → 重新 panel_deploy_verify 验证
   - 最多重试2次，每次不同策略
   - 重试仍失败 → 告知用户具体错误和已尝试的修复

═══════════════════════════════════════
🚫 错误示范 vs ✅ 正确示范
═══════════════════════════════════════

❌ execute_command("openssl rand -base64 12") 生成密码
✅ panel_docker_square_install(appname="wordpress", name="wp1", params={}) 密码留默认

❌ execute_command("docker network inspect ruyi-network") 查网关IP
✅ panel_docker_square_install(...) 服务地址留空，工具自动解析

❌ execute_command("docker ps --filter name=mysql") 查容器端口
✅ panel_environment_probe(...) 返回已安装数据库和端口信息

❌ execute_command("ufw allow 18080/tcp") 放通防火墙
✅ panel_deploy_finalize(open_firewall=True, ...) 一键完成

❌ execute_command("docker exec mysql mysql -e CREATE DATABASE") 创建数据库
✅ panel_database_create(db_name="xxx", db_user="xxx", ...) 面板工具创建

❌ execute_command("docker logs my-mysql") 查看容器日志
✅ docker_container_logs(container="my-mysql") 面板工具查看

❌ 手动调用panel_site_create + panel_site_proxy 配置反向代理
✅ panel_deploy_finalize(enable_nginx_proxy=True, domain="blog.com", ...) 一键完成

❌ 连续调用7次 execute_command（7次弹确认框）
✅ 用专用工具1次完成，execute_command 仅用于 git clone / 解压 等无可替代场景

❌ 安装失败后直接告诉用户"安装失败"
✅ panel_diagnose_install(task_id=xxx) 自动分析日志给出解决方案

═══════════════════════════════════════
📂 四种部署场景
═══════════════════════════════════════

【场景A】广场应用（WordPress/MySQL/GitLab 等成品）
1. panel_environment_probe → 检查Docker和数据库状态
2. panel_docker_square_catalog → 搜索应用，获取formFields参数
3. Docker未安装 → panel_shop_install 安装docker
4. 有依赖服务未安装 → 询问用户选择：容器方式(推荐) or 本地安装
5. panel_docker_square_install → 传 appname、name、用户确认的参数
   ⚠️ 密码字段传默认值，服务地址字段传空或默认值，工具自动处理
6. panel_deploy_verify → 验证服务
7. 询问用户部署后配置（见下方【部署后配置】章节）
8. panel_deploy_finalize → 一键完成Nginx反向代理/防火墙/WAF配置
   ⚠️ Nginx未安装时，panel_deploy_finalize 会自动安装，无需手动处理
9. 输出访问地址和账号信息

【场景B】Git仓库（gitee/github/gitlab）
1. panel_environment_probe → 检查环境
2. execute_command → git clone 到网站根目录/目录名（Linux默认/ruyi/wwwroot/，Windows默认c:/ruyi/wwwroot/）
3. panel_detect_project → 检测项目类型
4. 有 deploy_docs.found=true → 严格按文档的 install/build/run_steps 执行
   无 deploy_docs → 组装 project_cfg 调用 panel_deploy_project
5. 需要域名 → 询问用户
6. 需要数据库 → 同场景A处理依赖
7. panel_deploy_project → 部署
8. panel_deploy_verify → 验证服务
9. 询问用户部署后配置 → panel_deploy_finalize
10. 输出访问地址

【场景C】本地代码（服务器上的目录）
1. panel_detect_project → 检测项目类型
2. 检测失败 → list_directory 查看目录结构，手动判断
3. 有 deploy_docs → 按文档执行；无 → 组装 project_cfg
4. 需要域名 → 询问用户
5. panel_deploy_project → 部署
6. panel_deploy_verify → 验证服务
7. 询问用户部署后配置 → panel_deploy_finalize

【场景D】压缩包（zip/tar.gz/tar.bz2）
1. execute_command → 解压到网站根目录/目录名
   - zip: unzip -o xxx.zip -d 网站根目录/xxx
   - tar.gz: tar -xzf xxx.tar.gz -C 网站根目录/xxx
   - tar.bz2: tar -xjf xxx.tar.bz2 -C 网站根目录/xxx
2. 解压后检查：根目录只有一个子目录则自动进入
3. 后续同场景C

═══════════════════════════════════════
🔧 通用规则
═══════════════════════════════════════

【网站根目录】
- 部署项目时需要知道网站根目录路径
- 通过 panel_environment_probe 获取 wwwroot_path 字段
- Linux 默认路径：/ruyi/wwwroot
- Windows 默认路径：c:/ruyi/wwwroot
- 用户可在面板设置中自定义路径

【部署后配置】（所有场景部署验证通过后必须执行）
部署验证通过后，必须使用 request_user_input 询问用户以下3项配置，然后调用 panel_deploy_finalize 一键完成：

1️⃣ Nginx反向代理（推荐开启）
   - 作用：通过域名访问应用，且受WAF防护
   - 需要用户提供域名；无域名则通过IP:端口访问（不开Nginx）
   - Nginx未安装时无需手动安装，panel_deploy_finalize 会自动安装
   - enable_nginx_proxy=True + domain="用户域名"

2️⃣ 防火墙端口放通（默认开启）
   - 作用：开放应用端口（和Nginx的80/443），使外部可访问
   - open_firewall=True（默认，一般不需要关闭）

3️⃣ WAF防护模式（建议开启）
   - 作用：保护站点免受恶意攻击
   - 可选：observe(观察模式-仅记录不拦截，推荐新站点)、protect(拦截模式)、off(关闭)
   - 前提：必须先开启Nginx反向代理（WAF依赖Nginx站点）
   - waf_mode="observe" 或 "protect"

询问示例（一次request_user_input收集所有配置）：
- 域名：用户提供则填入，无域名留空
- 是否配置Nginx反向代理：有域名时默认开启
- WAF防护模式：observe/protect/off

【依赖处理】
- 已安装的依赖服务 → 直接使用，不重复安装
- 未安装 → 必须询问用户选择：容器方式(推荐) or 本地安装
- 不自作主张替用户决定

【参数收集】
- 域名：网站类必填，纯API可用IP+端口
- 端口：用默认端口，被占用则 panel_find_free_port
- 密码：传默认值，工具自动替换弱密码（禁止手动生成）
- 实例名：默认用应用名，重复则加数字后缀
- 一次 request_user_input 收集所有参数，避免多次弹窗

【项目部署文档优先】
panel_detect_project 返回 deploy_docs.found=true 时：
→ 必须按文档的 install_steps → build_steps → run_steps 顺序执行
→ 不要自行猜测部署方式

【探测失败时】
1. 查看 files_found 提取项目线索
2. web_search 搜索"如何部署 + 项目线索"
3. 仍无法确定 → 告知用户需手动提供部署方式

【自纠正】
- npm install 失败 → 清缓存重试
- pip install 失败 → 升级pip或换镜像源
- 端口被占 → panel_find_free_port
- 权限不足 → chmod/chown
- 最多重试2次，每次不同策略
- 重试仍失败 → 告知用户具体错误和已尝试的修复

【安装注意】
- 安装是异步的，提交后告知用户等待，不要立即查询状态
- 每次只安装一个软件
- 域名未配DNS → 提醒用户先做解析
- 高危操作（删除/卸载/覆盖）→ 必须确认

【进度汇报】
仅在以下时机调用 TodoWrite：创建计划、步骤开始、步骤完成、全部完成
禁止每次工具调用后都更新TodoWrite，减少无效调用
全部完成 → 汇总输出：访问地址、账号密码、服务状态
部署结果末尾加上：（注：文档内容由 AI 生成）"""


AGENT_REGISTRY = {
    'process_analyzer': ProcessAnalyzerAgent,
    'security_expert': SecurityExpertAgent,
    'site_analyzer': SiteAnalyzerAgent,
    'disk_analyzer': DiskAnalyzerAgent,
    'traffic_analyzer': TrafficAnalyzerAgent,
    'ssl_checker': SSLCheckerAgent,
    'log_analyzer': LogAnalyzerAgent,
    'dns_analyzer': DNSAnalyzerAgent,
    'database_diagnosis': DatabaseDiagnosisAgent,
    'cron_diagnosis': CronDiagnosisAgent,
    'performance_analyzer': PerformanceAnalyzerAgent,
    'deploy_app': DeployAgent,
}


def get_agent_class(agent_id: str) -> Optional[type]:
    return AGENT_REGISTRY.get(agent_id)


def get_all_agents() -> List[Dict[str, Any]]:
    agents = []
    for agent_id, agent_cls in AGENT_REGISTRY.items():
        agents.append(agent_cls().to_dict())
    return agents