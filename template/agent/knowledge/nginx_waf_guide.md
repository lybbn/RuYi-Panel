# Nginx与WAF配置指南

tags: Nginx, WAF, 反向代理, IP访问, 站点, 防护, OpenResty

## 概述

本文档为AI提供Nginx反向代理和WAF防护的标准配置流程。

## Nginx安装规范

### 必须使用应用商店安装
```
✅ 正确：panel_shop_install("nginx")
❌ 禁止：execute_command("apt-get install nginx")
❌ 禁止：execute_command("yum install nginx")
❌ 禁止：execute_command("apt update")
```

### 安装后检查状态
```
panel_shop_task_status(task_id="任务ID")  # 查询安装进度
get_nginx_status()                        # 检查Nginx运行状态
```

## 反向代理配置

### 场景1：有域名的反向代理

**步骤**：
1. 创建站点：`panel_site_create(name="站点名", domains=["example.com"])`
2. 配置反向代理：`panel_site_proxy(site_id=ID, action="add", proxy_path="/", proxy_pass="http://127.0.0.1:端口")`
3. 配置SSL（可选）：`panel_site_ssl(site_id=ID, action="lets", domain="example.com")`

**示例**：
```
# 1. 创建站点
panel_site_create(name="my-site", domains=["example.com"])

# 2. 配置反向代理到WordPress
panel_site_proxy(
    site_id=1,
    action="add",
    proxy_name="wordpress",
    proxy_path="/",
    proxy_pass="http://127.0.0.1:18080",
    proxy_host="example.com"
)
```

### 场景2：无域名用IP访问的反向代理

**⚠️ 重要说明**：
- IP访问**不能**使用80端口（需要Nginx监听80）
- 建议直接使用应用端口访问，或配置Nginx使用其他端口

**IP获取规则**：
1. 默认使用`panel_environment_probe`返回的服务器IP（从系统网络接口获取）
2. 使用前**必须询问用户**：是否使用该IP，或提供其他IP
3. 示例询问："检测到服务器IP为 172.31.0.120，是否使用该IP配置站点？或提供其他IP？"

**方案A：直接使用应用端口（推荐）**
```
无需配置Nginx，直接访问 http://IP:应用端口
例如：http://172.31.0.120:18080
```

**方案B：配置Nginx非80端口反向代理**
```
# 1. 创建站点（使用非80端口）
panel_site_create(name="wordpress-ip", domains=["172.31.0.120:8080"])

# 2. 配置反向代理
panel_site_proxy(
    site_id=1,
    action="add",
    proxy_name="wordpress",
    proxy_path="/",
    proxy_pass="http://127.0.0.1:18080",
    proxy_host="172.31.0.120"
)

# 访问：http://172.31.0.120:8080
```

**方案C：使用默认站点（80端口）**
```
# 1. 编辑默认站点配置，添加反向代理
# 需要手动编辑Nginx配置文件或使用面板默认站点功能

# 2. 访问：http://172.31.0.120
```

### panel_site_proxy 参数说明

| 参数 | 说明 | 示例 |
|------|------|------|
| site_id | 站点ID（必填） | 1 |
| action | 操作：add/delete/update | "add" |
| proxy_name | 代理名称（必填） | "wordpress" |
| proxy_path | 代理路径（默认"/"） | "/" |
| proxy_pass | 后端地址（必填） | "http://127.0.0.1:18080" |
| proxy_host | Host头（可选） | "example.com" |

## WAF防护配置

### WAF依赖条件
- **必须先有Nginx站点**才能启用WAF
- WAF是基于站点的，不是全局的

### WAF配置流程

**步骤1：检查WAF全局状态**
```
waf_get_status()
```

**步骤2：查看站点WAF配置**
```
# 查看指定站点
waf_get_site_config(site_id=1)

# 查看所有站点概要
waf_get_site_config(site_id=0)  # site_id=0表示查询所有
```

**步骤3：启用WAF防护**
```
waf_set_site_status(site_id=1, status="protect")
```

**WAF模式说明**：
| 模式 | 说明 | 适用场景 |
|------|------|---------|
| off | 关闭 | 不需要防护 |
| observe | 观察模式 | 测试阶段，只记录不拦截 |
| protect | 防护模式 | 生产环境，拦截攻击 |

### WAF配置示例

**完整示例：为WordPress站点启用WAF**
```
# 1. 检查WAF全局状态
waf_get_status()

# 2. 查看站点列表，确认site_id
waf_get_site_config(site_id=0)

# 3. 启用防护模式
waf_set_site_status(site_id=2, status="protect")

# 4. 验证配置
waf_get_site_config(site_id=2)
```

### ⚠️ WAF配置注意事项

1. **不要重复调用waf_set_site_status**
   - 调用一次即可生效
   - 不需要调用reload_nginx，工具内部会自动处理

2. **site_id必须正确**
   - 使用waf_get_site_config(site_id=0)获取所有站点列表
   - 确认正确的site_id后再调用waf_set_site_status

3. **WAF配置会自动同步到Nginx**
   - 不需要手动reload_nginx
   - 工具内部会自动重载Nginx配置

## 常见问题

### 问题1：WAF配置后不生效
**原因**：Nginx配置未重载
**解决**：waf_set_site_status会自动重载，如果仍不生效，手动调用reload_nginx()

### 问题2：site_id=0的含义
**说明**：site_id=0是waf_get_site_config的默认值，表示查询所有站点配置概要
**不是bug**，这是正常的设计

### 问题3：IP访问配置反向代理
**建议**：
- 如果只是临时测试，直接用应用端口访问
- 如果需要80端口，必须配置默认站点
- 非80端口可以用panel_site_create创建站点

### 问题4：Nginx安装失败
**排查步骤**：
1. 检查网络连接：ping 8.8.8.8
2. 检查DNS解析：nslookup deb.debian.org
3. 重试安装：panel_shop_install("nginx")
4. **禁止**执行apt update或apt-get install

## 搜索本文档

当用户需要配置Nginx、反向代理、WAF时，使用search_docs搜索：
- search_docs(query="Nginx配置指南")
- search_docs(query="WAF防护配置")
- search_docs(query="IP反向代理")
- search_docs(query="反向代理配置")
