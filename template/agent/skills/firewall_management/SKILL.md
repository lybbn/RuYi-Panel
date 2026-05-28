---
name: firewall_management
description: 防火墙管理技能，配置和管理服务器防火墙规则，确保端口安全和服务可访问性
---

# 防火墙管理

配置和管理服务器防火墙，确保安全性和服务可访问性的平衡。

## 平台差异说明

- **Linux**：使用 `ufw`/`iptables`/`firewalld` 防火墙
- **Windows**：使用 `netsh advfirewall` 防火墙
- **优先使用面板工具**：`get_firewall_status`、`manage_firewall_rule` 等已处理平台差异

## 管理流程

### 第一步：防火墙状态检查
1. 调用 `get_firewall_status` 获取当前防火墙状态和规则
2. 调用 `get_open_ports` 获取当前开放端口列表
3. Linux: 调用 `execute_command` 执行 `ufw status verbose 2>/dev/null || iptables -L -n -v 2>/dev/null | head -50`
   Windows: 调用 `execute_command` 执行 `netsh advfirewall show allprofiles state`

### 第二步：端口审计
1. 列出所有开放端口
2. 标注每个端口对应的服务
3. 识别不必要的开放端口
4. 检查高危端口（22/3306/6379/27017等）是否对外开放

### 第三步：规则分析
1. 检查是否有过于宽松的规则（如允许所有IP访问）
2. 检查是否有重复或冲突的规则
3. 检查默认策略是否安全

### 第四步：生成报告

```markdown
# 防火墙管理报告

## 防火墙概况
| 项目 | 值 |
|------|------|
| 防火墙类型 | ufw/iptables/firewalld/netsh |
| 状态 | 已启用/未启用 |
| 默认入站策略 | ACCEPT/DROP/REJECT |
| 规则总数 | xx |

## 端口审计
| 端口 | 服务 | 协议 | 来源限制 | 风险评估 |
|------|------|------|----------|----------|

## 安全风险
| 风险项 | 描述 | 建议 |
|--------|------|----------|

## 优化建议
1. 具体规则优化建议
```

## 注意事项
- 修改防火墙规则前确保有备用访问方式
- 不要同时关闭SSH端口和防火墙
- 规则修改后立即验证服务可访问性
- Windows防火墙使用入站/出站规则概念，与Linux不同
