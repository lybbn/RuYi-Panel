---
name: backup_recovery
description: 备份恢复技能，提供网站文件、数据库、配置文件的备份策略和恢复指导
---

# 备份与恢复

制定和执行服务器备份策略，确保数据安全可恢复。

## 平台路径对照

如意面板路径取决于安装时用户选择的安装目录，不同平台路径不同：

| 变量 | Linux默认 | Windows默认 | 获取方式 |
|------|----------|------------|---------|
| 网站根目录 | /ruyi/wwwroot | {安装盘}:/RuyiSoft/wwwroot | 面板工具 `panel_site_list` |
| 数据目录 | /ruyi/data | {安装盘}:/RuyiSoft/data | 面板API |
| 备份目录 | /ruyi/backup | {安装盘}:/RuyiSoft/backup | 面板API |
| 日志目录 | /ruyi/logs | {安装盘}:/RuyiSoft/logs | 面板API |
| 面板目录 | /ruyi/server/ruyi | {安装盘}:/RuyiSoft/server/ruyi | 面板API |
| Nginx配置 | 面板data/vhost/nginx/ | 面板data\vhost\nginx\ | 面板工具 `get_website_config` |

**重要**：Windows下路径由安装向导自定义（如 `D:/RuyiSoft`），不要硬编码路径。优先使用面板工具获取站点信息。

## 管理流程

### 第一步：备份现状检查
1. 调用 `get_disk_info` 检查磁盘空间是否足够备份
2. Linux: 调用 `execute_command` 执行 `find /ruyi/backup -type f -mtime -7 2>/dev/null | head -20`
   Windows: 调用 `execute_command` 执行 `dir /s /b D:\RuyiSoft\backup\*.zip 2>nul | findstr /r "202[0-9]" | sort /r`
3. Linux: 调用 `execute_command` 执行 `crontab -l 2>/dev/null | grep -i backup`
   Windows: 调用 `execute_command` 执行 `schtasks /query /fo LIST 2>nul | findstr /i backup`

### 第二步：备份需求分析
1. 调用 `panel_site_list` 获取网站列表，确定需备份的网站
2. Linux: 调用 `execute_command` 执行 `du -sh /ruyi/wwwroot/* 2>/dev/null | head -20`
   Windows: 调用 `execute_command` 执行 `powershell "Get-ChildItem D:\RuyiSoft\wwwroot | ForEach-Object { '{0:N1} MB - {1}' -f ((Get-ChildItem $_.FullName -Recurse | Measure-Object Length -Sum).Sum/1MB), $_.Name }"`
3. Linux: 调用 `execute_command` 执行 `du -sh /ruyi/data 2>/dev/null`
   Windows: 调用 `execute_command` 执行 `powershell "'{0:N1} MB' -f ((Get-ChildItem D:\RuyiSoft\data -Recurse | Measure-Object Length -Sum).Sum/1MB)"`

### 第三步：备份策略建议
1. **网站文件**：建议每日增量备份 + 每周全量备份
2. **数据库**：建议每日全量备份 + binlog实时备份（Linux）
3. **配置文件**：建议每次修改前手动备份
4. **保留策略**：保留最近7天日备份 + 最近4周周备份 + 最近3月月备份

### 第四步：生成报告

```markdown
# 备份与恢复报告

## 备份现状
| 项目 | 状态 | 说明 |
|------|------|------|
| 自动备份 | 是/否 | 是否有定时备份任务 |
| 最近备份 | 日期 | 最近一次备份时间 |
| 备份空间 | xx GB | 可用备份空间 |

## 需备份数据
| 类型 | 路径 | 大小 | 优先级 |
|------|------|------|--------|
| 网站文件 | {WWWROOT} | xx GB | 高 |
| 数据目录 | {DATA} | xx GB | 高 |
| 配置文件 | {PANEL}/data/vhost | xx MB | 中 |

## 备份建议
1. 具体备份命令和策略
2. 恢复验证步骤
```

## 注意事项
- 备份前确保有足够磁盘空间
- 定期验证备份可恢复性
- 重要数据建议异地备份
- 备份文件需设置适当权限防止未授权访问
- Windows下路径分隔符为 `\`，命令需使用PowerShell语法
