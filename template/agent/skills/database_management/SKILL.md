---
name: database_management
description: 数据库管理技能，诊断数据库运行状态、性能问题，提供备份、优化和故障排查指导
---

# 数据库管理

诊断和管理MySQL/MariaDB/Redis等数据库服务，提供性能优化和故障排查。

## 平台差异说明

- **Linux**：MySQL配置通常在 `/etc/my.cnf` 或 `/etc/mysql/`，数据目录 `/var/lib/mysql/`
- **Windows**：MySQL配置通常在安装目录下 `my.ini`，数据目录在安装目录下 `data/`
- **优先使用面板工具**：`mysql_status`、`mysql_list_databases`、`redis_status` 等已处理平台差异

## 诊断流程

### 第一步：数据库状态检查
1. 调用 `get_service_status` 检查MySQL/MariaDB服务状态
2. Linux: 调用 `execute_command` 执行 `ps aux | grep -E 'mysql|mariadb' | grep -v grep`
   Windows: 调用 `execute_command` 执行 `tasklist /fi "imagename eq mysqld.exe" 2>nul`
3. Linux: 调用 `execute_command` 执行 `ss -tan | grep :3306 | wc -l` 检查数据库连接数
   Windows: 调用 `execute_command` 执行 `powershell "(Get-NetTCPConnection -LocalPort 3306 -ErrorAction SilentlyContinue).Count"`
4. 调用 `get_system_info` 检查系统资源占用

### 第二步：性能诊断
1. 调用 `mysql_status` 获取MySQL运行状态
2. 调用 `execute_command` 执行 `mysql -e "SHOW PROCESSLIST;" 2>/dev/null | head -30` 查看当前查询
3. 调用 `execute_command` 执行 `mysql -e "SHOW VARIABLES LIKE 'max_connections';" 2>/dev/null` 检查最大连接数
4. 调用 `get_system_logs` 查看MySQL错误日志

### 第三步：Redis检查
1. 调用 `redis_status` 获取Redis运行状态
2. 调用 `execute_command` 执行 `redis-cli INFO stats 2>/dev/null | head -20` 获取Redis统计信息
3. 调用 `execute_command` 执行 `redis-cli INFO memory 2>/dev/null | head -10` 检查Redis内存使用

### 第四步：生成诊断报告

```markdown
# 数据库诊断报告

## 数据库概况
| 项目 | 值 |
|------|------|
| 数据库类型 | MySQL/MariaDB |
| 运行状态 | 正常/警告/异常 |
| 当前连接数 | xx |
| 最大连接数 | xx |
| 连接使用率 | xx% |

## 性能指标
| 指标 | 当前值 | 状态 |
|------|--------|------|
| 慢查询数 | xx | 正常/警告 |
| 缓存命中率 | xx% | 正常/警告 |
| 锁等待 | xx | 正常/警告 |

## 优化建议
1. 具体优化步骤
```

## 注意事项
- 数据库操作需谨慎，修改配置前先备份
- 生产环境不要直接执行ALTER TABLE等DDL操作
- 优化建议需考虑当前服务器资源情况
- Windows下MySQL服务名可能为 `mysql` 或 `mysql56`/`mysql80`
