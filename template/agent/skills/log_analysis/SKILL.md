---
name: log_analysis
description: 日志分析技能，分析系统和应用日志，发现错误、异常和安全隐患，生成分析报告
---

# 日志分析

对服务器系统和应用日志进行全面分析，发现错误、异常和安全事件。

## 平台差异说明

- **Linux**：系统日志 `/var/log/syslog`、认证日志 `/var/log/auth.log`、内核日志 `dmesg`
- **Windows**：事件查看器 `Get-EventLog`/`Get-WinEvent`，应用程序/系统/安全日志
- **如意面板日志**：Linux `/ruyi/logs/`，Windows `{安装盘}:/RuyiSoft/logs/`
- **优先使用面板工具**：`get_system_logs` 已处理平台差异

## 分析流程

### 第一步：日志收集
1. 调用 `get_system_logs` 获取系统日志
2. 调用 `get_system_logs` 获取认证/安全日志
3. 调用 `get_system_logs` 获取Nginx错误日志
4. 调用 `get_system_logs` 获取Nginx访问日志
5. Linux: 调用 `execute_command` 执行 `dmesg | tail -50`
   Windows: 调用 `execute_command` 执行 `powershell "Get-WinEvent -LogName System -MaxEvents 50 2>$null | Format-Table TimeCreated,LevelDisplayName,Message -AutoSize"`

### 第二步：错误分析
1. 统计各类错误数量
2. 识别重复出现的错误模式
3. 分析错误发生的时间规律
4. 关联不同日志中的相关事件

### 第三步：安全事件分析
1. 检查认证失败记录
2. 检查异常访问IP
3. 检查可疑的请求模式（SQL注入、XSS等）
4. 检查文件变更记录

### 第四步：生成分析报告

```markdown
# 日志分析报告

## 日志概况
| 日志类型 | 文件大小 | 时间范围 | 错误数 | 警告数 |
|----------|----------|----------|--------|--------|

## 严重错误
| 时间 | 来源 | 错误信息 | 建议 |
|------|------|----------|------|

## 警告信息
| 时间 | 来源 | 警告信息 | 建议 |
|------|------|----------|------|

## 安全事件
| 时间 | 类型 | 详情 | 风险等级 |
|------|------|------|----------|

## 趋势分析
- 错误趋势：上升/下降/平稳
- 主要问题类型分布
```

## 注意事项
- 关注重复出现的错误，这通常表示系统性问题
- 安全事件需标注风险等级
- 对于大量日志，使用统计方式而非逐条列出
- Windows事件日志使用 `LevelDisplayName` 区分级别
