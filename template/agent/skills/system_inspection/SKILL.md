---
name: system_inspection
description: 服务器系统巡检技能，提供全面的系统健康检查、性能分析、安全审计和优化建议
---

# 服务器系统巡检

对服务器进行全面的健康检查和性能分析，生成专业的巡检报告。

## 平台差异说明

- **Linux**：`/proc` 文件系统、`systemctl` 服务管理、`journalctl` 日志
- **Windows**：WMI/性能计数器、`sc`/`Get-Service` 服务管理、事件查看器日志
- **优先使用面板工具**：`get_system_info`、`get_cpu_info`、`get_memory_info` 等已处理平台差异

## 巡检流程

### 第一步：收集系统基础信息
1. 调用 `get_system_info` 获取系统概况
2. 调用 `get_cpu_info` 获取CPU详情
3. 调用 `get_memory_info` 获取内存详情
4. 调用 `get_disk_info` 获取磁盘详情
5. 调用 `get_network_info` 获取网络详情

### 第二步：检查服务状态
1. 调用 `list_services` 获取运行中的服务
2. 对关键服务（nginx、mysql、redis、docker等）调用 `get_service_status` 检查状态

### 第三步：安全检查
1. 调用 `get_firewall_status` 检查防火墙
2. Linux: 调用 `get_ssh_config` 检查SSH安全配置
   Windows: 调用 `execute_command` 执行 `powershell "Get-Service sshd 2>$null | Select-Object Status,StartType | Format-List"`
3. 调用 `get_open_ports` 检查开放端口
4. 调用 `get_login_history` 检查登录历史

### 第四步：生成巡检报告

按照以下格式生成报告：

```markdown
# 服务器巡检报告

## 基本信息
| 项目 | 值 |
|------|------|
| 主机名 | xxx |
| 操作系统 | xxx |
| 运行时间 | xxx |
| CPU使用率 | xx% |
| 内存使用率 | xx% |

## CPU 状态
- 物理核心数：xx
- 逻辑核心数：xx
- 总使用率：xx%
- 各核心使用率：[xx%, xx%, ...]

## 内存状态
- 总内存：xx GB
- 已用：xx GB (xx%)
- 可用：xx GB
- Swap使用：xx GB (xx%)（仅Linux）

## 磁盘状态
| 挂载点 | 总容量 | 已用 | 使用率 |
|--------|--------|------|--------|
| / 或 C: | xx GB | xx GB | xx% |

## 网络状态
- 网络接口：xx个
- 活动连接：xx个
- IO统计：发送xx GB / 接收xx GB

## 服务状态
| 服务 | 状态 | 开机自启 |
|------|------|----------|
| nginx | 运行中/已停止 | 是/否 |

## 安全检查
- 防火墙：已启用 / 未启用
- SSH端口：xx（仅Linux）
- Root登录：禁止/允许（仅Linux）
- 开放端口：xx, xx, xx

## 风险提示
- [列出发现的问题]

## 优化建议
- [列出优化建议]
```

## 注意事项
- 巡检过程中如果某个工具调用失败，记录错误但继续执行其他检查
- 对于高危操作（如修改配置），只给出建议，不要自动执行
- 报告中的数据必须是实时获取的真实数据，不要编造
- Windows和Linux巡检项有差异，需根据平台调整检查内容
