---
name: website_deploy
description: 网站部署与管理技能，提供网站配置分析、SSL证书检查、性能优化和故障排查
---

# 网站部署与管理

提供网站配置分析、SSL证书检查、性能优化和故障排查的专业指导。

## 平台差异说明

- **网站根目录**：Linux `/ruyi/wwwroot`，Windows `{安装盘}:/RuyiSoft/wwwroot`
- **Nginx配置**：Linux `面板data/vhost/nginx/*.conf`，Windows `面板data\vhost\nginx\*.conf`
- **优先使用面板工具**：`panel_site_list`、`panel_site_create`、`get_website_config` 等已处理平台差异

## 工作流程

### 网站故障排查
当用户报告网站无法访问时：

1. **检查Nginx状态**：调用 `get_nginx_status` 确认Web服务器是否正常运行
2. **检查网站配置**：调用 `get_website_config` 查看配置文件是否有语法错误
3. **检查网站可访问性**：调用 `check_website_status` 测试HTTP响应
4. **查看错误日志**：调用 `get_system_logs` 查看 nginx_error 日志
5. **检查端口监听**：调用 `get_open_ports` 确认80/443端口是否正常监听

### 网站性能优化
当用户需要优化网站性能时：

1. **分析当前配置**：调用 `get_website_config` 获取Nginx配置
2. **检查资源使用**：调用 `get_system_info` 查看服务器资源
3. **检查连接数**：调用 `get_network_info` 查看网络连接状态
4. **给出优化建议**：基于数据给出具体的配置优化方案

### SSL证书检查
1. **检查网站HTTPS状态**：调用 `check_website_status` 测试443端口
2. **查看Nginx配置**：调用 `get_website_config` 检查SSL配置
3. **使用命令检查证书有效期**：调用 `execute_command` 执行 `openssl s_client -connect domain:443 -servername domain 2>/dev/null | openssl x509 -noout -dates`

## 常见问题排查

### 502 Bad Gateway
1. 检查后端服务是否运行
2. 检查Nginx upstream配置
3. 检查后端服务端口是否可达

### 403 Forbidden
1. 检查文件权限
2. 检查Nginx配置中的deny规则
3. Linux: 检查SELinux/AppArmor设置
   Windows: 检查NTFS权限和IIS配置

### 404 Not Found
1. 检查root目录配置
2. 检查try_files配置
3. 检查文件是否存在

## 注意事项
- 修改Nginx配置前，先用 `nginx -t` 测试配置语法
- 修改配置后需要 `nginx -s reload` 重载配置
- 不要直接删除配置文件，先备份再修改
- Windows下路径分隔符为 `\`，Nginx配置中需使用 `/`
