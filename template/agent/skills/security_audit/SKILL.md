---
name: security_audit
description: 服务器安全审计技能，全面检查系统安全配置、漏洞风险、入侵迹象，生成安全评估报告
---

# 服务器安全审计

对服务器进行全面的安全检查和风险评估，发现潜在的安全隐患并提供加固建议。

## 平台差异说明

- **Linux**：使用 `iptables/ufw/firewalld` 防火墙、`/etc/passwd` 用户管理、`journalctl` 日志
- **Windows**：使用 `netsh advfirewall` 防火墙、`net user` 用户管理、事件查看器日志
- **优先使用面板工具**：`get_firewall_status`、`get_ssh_config`、`get_open_ports` 等已处理平台差异

## 审计流程

### 第一步：基础安全检查
1. 调用 `get_firewall_status` 检查防火墙状态和规则
2. 调用 `get_ssh_config` 检查SSH安全配置（仅Linux）
3. 调用 `get_open_ports` 检查开放端口
4. 调用 `get_login_history` 检查登录历史和异常登录

### 第二步：系统安全检查
1. Linux: 调用 `execute_command` 执行 `find / -perm -4000 -o -perm -2000 2>/dev/null` 检查SUID/SGID文件
   Windows: 调用 `execute_command` 执行 `powershell "Get-ChildItem -Path C:\ -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.Attributes -match 'System' } | Select-Object FullName | Format-Table -AutoSize"`
2. Linux: 调用 `execute_command` 执行 `cat /etc/passwd | grep -E '/bin/bash|/bin/sh'` 检查可登录用户
   Windows: 调用 `execute_command` 执行 `net user`
3. Linux: 调用 `execute_command` 执行 `lastb 2>/dev/null | head -20` 检查失败登录记录
   Windows: 调用 `execute_command` 执行 `powershell "Get-EventLog -LogName Security -EntryType FailureAudit -Newest 20 2>$null | Format-Table TimeGenerated,Message -AutoSize"`
4. 调用 `get_system_info` 检查是否有异常资源占用

### 第三步：内核漏洞检测（仅Linux）

1. 调用 `execute_command` 执行 `uname -r` 获取内核版本
2. 调用 `execute_command` 执行 `lsmod | grep -E "algif_aead|esp4|esp6|espintcp|rxrpc" || echo "NO_VULN_MODULES_LOADED"` 检查漏洞模块加载状态
3. 调用 `execute_command` 执行 `cat /etc/modprobe.d/*.conf 2>/dev/null | grep -E "install.*(algif_aead|esp4|esp6|rxrpc).*/bin/false" || echo "NO_MITIGATION_FOUND"` 检查缓解措施
4. 调用 `execute_command` 执行 `cat /proc/sys/kernel/unprivileged_userns_clone 2>/dev/null; cat /proc/sys/user/max_user_namespaces 2>/dev/null` 检查用户命名空间限制

重点检查以下高危内核漏洞：
- **Copy Fail** (CVE-2026-31431)：algif_aead 模块，影响内核 4.14-6.18.21，CVSS 7.8
- **Dirty Frag** (QVD-2026-24699)：esp4/esp6 + rxrpc 模块，CVSS 8.8/7.8
- **Fragnesia** (CVE-2026-46300)：esp4/esp6/espintcp 模块，CVSS 7.8

如需完整检测流程和漏洞知识库，调用 Skills 工具加载 `linux_vuln_check` 技能。

### 第四步：Web安全检查
1. 调用 `panel_site_list` 检查网站安全配置
2. Linux: 调用 `execute_command` 执行 `find /ruyi/wwwroot -name "*.php" -type f -mtime -1 2>/dev/null | head -20` 检查最近修改的PHP文件
   Windows: 调用 `execute_command` 执行 `powershell "Get-ChildItem D:\RuyiSoft\wwwroot -Recurse -Filter *.php -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTime -gt (Get-Date).AddDays(-1) } | Select-Object FullName,LastWriteTime | Format-Table -AutoSize"`
3. 调用 `get_system_logs` 查看Web错误日志中的异常请求

### 第五步：生成安全报告

```markdown
# 服务器安全审计报告

## 安全评分
- 综合评分：xx/100
- 防火墙：安全/注意/危险
- SSH安全：安全/注意/危险（仅Linux）
- 端口安全：安全/注意/危险
- 登录安全：安全/注意/危险
- 内核漏洞：安全/注意/危险（仅Linux）

## 内核漏洞检测结果（仅Linux）
| 漏洞 | CVE | 状态 | 风险等级 |
|------|-----|------|----------|
| Copy Fail | CVE-2026-31431 | 受影响/已缓解/已修补 | 高 |
| Dirty Frag | QVD-2026-24699 | 受影响/已缓解/已修补 | 高 |
| Fragnesia | CVE-2026-46300 | 受影响/已缓解/已修补 | 高 |

## 高危风险
| 风险项 | 描述 | 修复建议 |
|--------|------|----------|

## 中危风险
| 风险项 | 描述 | 修复建议 |
|--------|------|----------|

## 安全项
- 已正确配置的安全项列表

## 加固建议
1. 具体可操作的加固步骤
```

## 注意事项
- 安全审计只做检查和报告，不自动修改配置
- 发现高危风险时需明确标注并给出紧急修复建议
- 所有修改操作必须经用户确认
- Windows和Linux安全检查项不同，需根据平台调整
