---
name: ssl_management
description: SSL证书管理技能，检查证书状态、有效期，提供证书申请、续期和配置指导
---

# SSL证书管理

管理服务器SSL证书，包括证书检查、到期预警、申请续期和配置优化。

## 平台路径对照

| 用途 | Linux路径 | Windows路径 |
|------|----------|------------|
| 面板SSL证书 | 面板data/key/ | 面板data\key\ |
| 网站SSL证书 | 面板data/vhost/cert/ 或 /etc/letsencrypt/live/ | 面板data\vhost\cert\ |
| Nginx配置 | 面板data/vhost/nginx/*.conf | 面板data\vhost\nginx\*.conf |

**注意**：优先使用面板工具（如 `panel_site_list`、`get_website_config`）获取SSL配置信息，避免硬编码路径。

## 管理流程

### 第一步：证书检查
1. 调用 `panel_site_list` 获取网站列表和SSL配置
2. Linux: 调用 `execute_command` 执行 `find /ruyi/server/ruyi/data/vhost/cert /etc/letsencrypt/live -name "*.pem" -o -name "*.crt" 2>/dev/null | head -20`
   Windows: 调用 `execute_command` 执行 `dir /s /b "D:\RuyiSoft\server\ruyi\data\vhost\cert\*.pem" "D:\RuyiSoft\server\ruyi\data\vhost\cert\*.crt" 2>nul`
3. 对每个证书调用 `execute_command` 执行 `openssl x509 -in <证书路径> -noout -dates -subject -issuer 2>/dev/null` 检查证书信息

### 第二步：到期检查
1. 计算每个证书的剩余有效天数
2. 标注即将到期的证书（30天内到期）
3. 标注已过期的证书

### 第三步：配置检查
1. 检查Nginx SSL配置是否正确
2. 检查是否启用HTTPS强制跳转
3. 检查TLS协议版本（建议TLSv1.2+）
4. 检查加密套件配置

### 第四步：生成报告

```markdown
# SSL证书管理报告

## 证书清单
| 域名 | 颁发者 | 到期时间 | 剩余天数 | 状态 |
|------|--------|----------|----------|------|

## 到期预警
| 域名 | 到期时间 | 剩余天数 | 建议 |
|------|----------|----------|------|

## 配置建议
1. SSL配置优化建议
2. 证书续期步骤
```

## 注意事项
- 证书到期前30天开始提醒续期
- 续期前备份现有证书和配置
- Let's Encrypt证书每90天需续期
- Windows下证书路径使用反斜杠
