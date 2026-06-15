# 智能部署

tags: 部署,一键部署,Docker广场,Git部署,项目部署,WordPress,Discuz,GitLab,部署项目,部署应用

## 部署概述

如意面板AI助手支持三种部署方式，根据用户需求自动选择最佳方案：

1. **Docker广场部署**：部署成品应用（WordPress、Discuz、GitLab等）
2. **Git仓库部署**：从Gitee/GitHub/GitLab克隆代码并部署
3. **本地代码部署**：部署服务器上已有的代码项目

## 网站根目录

部署项目时需要知道网站根目录路径，用于存放项目代码。

**获取方式**：
- 调用 `panel_environment_probe` 获取 `wwwroot_path` 字段
- 该路径是用户在面板设置中配置的网站根目录

**默认路径**：
- Linux：`/ruyi/wwwroot`
- Windows：`c:/ruyi/wwwroot`

**使用场景**：
- Git 仓库部署：克隆代码到 `网站根目录/项目名`
- 压缩包部署：解压到 `网站根目录/项目名`
- 本地代码部署：项目已在网站根目录下

## 部署流程

### 场景A：Docker广场应用部署

适用于用户说"帮我部署WordPress/Discuz/GitLab"等成品应用。

1. 调用 `panel_environment_probe` 探测环境
2. 检查Docker是否安装运行，未安装则引导安装
3. 调用 `panel_docker_square_catalog` 搜索应用
4. 检查依赖（MySQL/PostgreSQL/Redis等），已安装则复用，未安装则询问用户选择容器方式或本地安装
5. 收集参数（域名、实例名、密码等）
6. 调用 `panel_docker_square_install` 安装
7. 验证结果，给出访问地址和账号信息
8. **检查依赖数据库是否已创建**：
   - 如果应用依赖数据库（如WordPress依赖MySQL），使用 `panel_database_list` 检查数据库是否已创建
   - 如果数据库不存在，使用 `panel_database_create` 自动创建数据库和用户
   - 创建后重新验证服务是否正常
9. **部署后配置（必须主动推荐）**：
   - 使用 `panel_deploy_finalize` 一站式完成部署后配置
   - 询问用户是否需要：域名绑定、Nginx反向代理、防火墙端口放通、WAF防护
   - 如果用户有域名，推荐配置反向代理+SSL，提升安全性和访问体验
   - 如果是内网服务，推荐放通防火墙端口

### 场景B：Git仓库部署

适用于用户提供Git仓库地址，如"部署 https://gitee.com/xxx/myproject.git"。

1. 调用 `panel_environment_probe` 探测环境，获取 `wwwroot_path` 字段
2. 用 `execute_command` 执行 `git clone` 克隆代码到 `wwwroot_path/目录名`
3. 调用 `panel_detect_project` 检测项目类型
4. 根据检测结果组装 `project_cfg`
5. 询问域名，处理数据库依赖
6. 调用 `panel_deploy_project` 部署
7. 验证结果，给出访问地址
8. **部署后配置（必须主动推荐）**：
   - 使用 `panel_deploy_finalize` 一站式完成部署后配置
   - 询问用户是否需要：域名绑定、Nginx反向代理、防火墙端口放通、WAF防护

### 场景C：本地代码部署

适用于用户提供服务器目录路径，如"部署网站根目录/myproject"。

1. 调用 `panel_detect_project` 检测项目类型
2. 根据检测结果组装 `project_cfg`
3. 询问域名，处理数据库依赖
4. 调用 `panel_deploy_project` 部署
5. 验证结果，给出访问地址
6. **部署后配置（必须主动推荐）**：
   - 使用 `panel_deploy_finalize` 一站式完成部署后配置
   - 询问用户是否需要：域名绑定、Nginx反向代理、防火墙端口放通、WAF防护

## 环境探测

部署前必须调用 `panel_environment_probe` 了解服务器环境：

- **Docker状态**：是否安装、是否运行、版本号
- **Web服务器**：Nginx/OpenResty是否安装
- **数据库**：MySQL/PostgreSQL/Redis/MongoDB是否安装及运行状态
- **运行环境**：PHP/Python/Go/Node.js是否安装及版本
- **端口占用**：常用端口（80/443/3306/6379/8080等）是否被占用
- **磁盘空间**：可用空间是否足够

## 项目类型检测

对Git仓库或本地代码，使用 `panel_detect_project` 自动检测：

| 项目类型 | 检测文件 | 支持框架 |
|---------|---------|---------|
| Python | requirements.txt, setup.py, pyproject.toml, manage.py | Django, Flask, FastAPI, Tornado, Aiohttp |
| Node.js | package.json | Express, Koa, NestJS, Next.js, Nuxt, Vue, React, Angular |
| Go | go.mod, main.go | Gin, Echo, Fiber, Beego |
| PHP | composer.json | Laravel, Symfony, Yii2, ThinkPHP |
| Docker | Dockerfile, docker-compose.yml | Docker Compose |

检测结果直接可用于 `panel_deploy_project` 的 `project_cfg` 参数。

## 依赖处理规则

1. 已安装的依赖服务（如本地MySQL）直接复用，不重复安装
2. 未安装的依赖，询问用户选择：
   - **容器方式（推荐）**：通过Docker广场安装，简单快捷
   - **本地安装**：通过应用商店安装，性能更好
3. 用户不确定时推荐容器方式

## 部署参数说明

### panel_deploy_project 参数

| 参数 | 说明 | 必填 |
|------|------|------|
| name | 项目名称 | 是 |
| project_type | python/node/go/php | 是 |
| project_cfg | 项目配置（由panel_detect_project生成） | 是 |
| domains | 域名列表，格式 ["domain:80"] | 是 |
| path | 项目根目录 | 否（自动生成） |
| enable_ssl | 是否启用SSL | 否 |
| ssl_type | letsencrypt/selfsigned/custom | 否 |

### panel_docker_square_install 参数

| 参数 | 说明 | 必填 |
|------|------|------|
| appname | 应用名称（如wordpress） | 是 |
| name | 实例名称 | 是 |
| params | 应用参数（含依赖配置） | 否 |

## 部署后配置

部署完成后，**必须主动执行以下配置**，不要只文字推荐就结束：

### 执行流程（必须按顺序执行）

1. **防火墙端口放通**（必须执行）：直接调用 `panel_deploy_finalize(open_firewall=True)` 放通应用端口
2. **询问用户是否有域名**：
   - 有域名 → 检查 Nginx 是否已安装
     - Nginx 未安装 → 先调用 `panel_shop_install("nginx")` 安装 Nginx
     - Nginx 已安装 → 调用 `panel_deploy_finalize(enable_nginx_proxy=True, domain=用户域名)`
   - 无域名 → 仅放通防火墙端口即可
3. **询问是否启用 WAF**：
   - 启用 → 调用 `panel_deploy_finalize(waf_mode="observe")` 设置观察模式
   - 不启用 → 跳过
4. **询问是否配置 SSL**：
   - 启用 → 调用 SSL 相关工具申请证书

### 重要提醒

- **不要只文字推荐就结束对话**，必须实际调用工具执行配置
- **防火墙端口放通是必须的**，不问用户直接执行
- **Nginx 未安装时不能配置反向代理**，需要先安装 Nginx
- **WAF 依赖 Nginx 站点**，没有 Nginx 站点无法启用 WAF
- 可以多次调用 `panel_deploy_finalize` 分别完成不同配置

### 常见部署后配置组合

- **博客/网站**：防火墙放通 + 域名 + 反向代理 + SSL + WAF（观察模式）
- **API服务**：防火墙放通 + 反向代理（可选）
- **内网工具**：仅防火墙放通
- **数据库**：不开放端口（通过应用连接）

## 常见问题

### Docker未安装
引导用户通过 `panel_shop_install` 安装Docker，安装完成后继续部署流程。

### 端口被占用
自动递增寻找可用端口，或询问用户指定端口。

### 域名未解析
提醒用户先配置DNS解析，否则无法通过域名访问和申请SSL证书。

### 项目类型无法识别
调用 `list_directory` 查看目录结构，手动判断项目类型并组装配置。
