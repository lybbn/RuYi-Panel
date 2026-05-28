---
name: performance_tuning
description: 服务器性能调优技能，分析性能瓶颈，提供CPU、内存、磁盘、网络、数据库等优化方案
---

# 服务器性能调优

深度分析服务器性能瓶颈，提供系统级和应用级的优化方案。

## 平台差异说明

- **Linux**：`top`/`htop` 进程查看、`vmstat`/`iostat` 性能统计、`/proc` 文件系统
- **Windows**：`tasklist`/`Get-Process` 进程查看、性能计数器、`Get-Counter` 统计
- **优先使用面板工具**：`get_cpu_info`、`get_memory_info`、`get_disk_info`、`get_process_list` 等已处理平台差异

## 调优流程

### 第一步：性能数据收集
1. 调用 `get_cpu_info` 获取CPU使用情况
2. 调用 `get_memory_info` 获取内存使用情况
3. 调用 `get_disk_info` 获取磁盘使用和IO情况
4. 调用 `get_process_list` 获取资源占用最高的进程
5. Linux: 调用 `execute_command` 执行 `vmstat 1 5` 获取系统性能统计
   Windows: 调用 `execute_command` 执行 `powershell "Get-Counter '\Memory\Available MBytes','\Processor(_Total)\% Processor Time' -SampleInterval 1 -MaxSamples 5"`
6. Linux: 调用 `execute_command` 执行 `iostat -x 1 3 2>/dev/null` 获取磁盘IO统计
   Windows: 调用 `execute_command` 执行 `powershell "Get-Counter '\PhysicalDisk(_Total)\% Disk Time','\PhysicalDisk(_Total)\Disk Reads/sec','\PhysicalDisk(_Total)\Disk Writes/sec' -SampleInterval 1 -MaxSamples 3"`

### 第二步：瓶颈分析
1. **CPU瓶颈**：使用率持续>80%，检查是否有死循环或计算密集型进程
2. **内存瓶颈**：使用率>85%且Swap使用增加，检查内存泄漏
3. **磁盘IO瓶颈**：iowait>10%（Linux），磁盘时间>80%（Windows），检查是否有大量读写操作
4. **网络瓶颈**：带宽使用率>80%，检查是否有大流量传输

### 第三步：服务优化
1. 调用 `get_nginx_status` 检查Nginx连接数和请求处理
2. 调用 `get_service_status` 检查各服务资源使用
3. 调用 `get_system_logs` 查看错误日志中的性能相关错误

### 第四步：生成优化方案

```markdown
# 性能调优报告

## 当前性能概况
| 指标 | 当前值 | 状态 |
|------|--------|------|
| CPU使用率 | xx% | 正常/注意/危险 |
| 内存使用率 | xx% | 正常/注意/危险 |
| 磁盘IO等待 | xx% | 正常/注意/危险 |
| 网络带宽 | xx% | 正常/注意/危险 |

## 瓶颈识别
1. **主要瓶颈**：xxx
2. **次要瓶颈**：xxx

## 优化方案（按优先级排序）
### 高优先级
1. 具体优化步骤和预期效果

### 中优先级
1. 具体优化步骤和预期效果

### 低优先级
1. 具体优化步骤和预期效果
```

## 注意事项
- 优化前建议先备份相关配置文件
- 生产环境优化需在低峰期进行
- 每次只做一个优化，验证效果后再做下一个
- Windows和Linux性能分析工具不同，需根据平台选择合适的命令
