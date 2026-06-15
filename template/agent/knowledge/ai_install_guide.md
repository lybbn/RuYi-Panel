# AI安装指南

tags: 安装,应用商店,Docker广场,panel_shop_install,panel_docker_square_install,依赖,部署

## 概述

本文档为AI提供软件安装的标准流程和规范，避免重复试错。安装软件有两种方式：
1. **应用商店**（panel_shop_install）：安装原生软件（Nginx、MySQL、Redis等）
2. **Docker广场**（panel_docker_square_install）：安装Docker容器应用（WordPress、GitLab等）

## 应用商店安装（panel_shop_install）

### 适用场景
- 安装Web服务器（Nginx/OpenResty）
- 安装数据库（MySQL、Redis、PostgreSQL、MongoDB）
- 安装运行环境（Python、Go、PHP、Node.js）
- 安装系统工具（Docker、Supervisor、Fail2Ban）

### 标准流程
```
1. 查询已安装状态：panel_shop_list(soft_name="nginx")
2. 如果未安装：panel_shop_install(soft_name="nginx")
3. 等待安装完成（异步任务，不要立即查询状态）
```

### 重要规则
- **禁止使用execute_command执行apt/yum/dnf安装**
- **禁止使用systemctl管理服务，使用panel_shop_manage**
- Nginx只能安装OpenResty版本，无需指定version_id
- 每次只安装一个软件，不要连续调用多次

### 常用安装命令
```
panel_shop_install(soft_name="nginx")      # 安装Nginx（自动选择OpenResty）
panel_shop_install(soft_name="mysql")      # 安装MySQL
panel_shop_install(soft_name="redis")      # 安装Redis
panel_shop_install(soft_name="docker")     # 安装Docker
panel_shop_install(soft_name="python")     # 安装Python
panel_shop_install(soft_name="php")        # 安装PHP
```

## Docker广场安装（panel_docker_square_install）

### 适用场景
- 安装WordPress、Discuz等建站应用
- 安装GitLab、Jenkins等开发工具
- 安装Ollama、Dify等AI应用
- 安装任何容器化应用

### 标准流程
```
1. 查询应用目录：panel_docker_square_catalog(search="wordpress")
2. 检查依赖关系：查看has_dependency和form_fields中的selectapps字段
3. 如果有依赖且未安装：先安装依赖服务
4. 安装应用：panel_docker_square_install(appname="wordpress", name="my-wordpress", params={...})
```

### 依赖服务处理规则

#### 规则1：panel_service_type必须传实例名称
```
❌ 错误：{"panel_service_type": "mysql"}
✅ 正确：{"panel_service_type": "my-mysql"}
```
panel_service_type传入的是依赖服务的**实例名称**（安装时指定的name），不是应用名称。

#### 规则2：服务地址不要手动指定
```
❌ 错误：{"wordpress_db_host": "172.18.0.1:13306"}
❌ 错误：{"wordpress_db_host": "my-mysql"}
❌ 错误：{"wordpress_db_host": ""}
✅ 正确：不传此参数，系统自动填充为host.docker.internal:端口
```

#### 规则3：密码传默认值
```
❌ 错误：手动生成密码
✅ 正确：传默认值，工具自动替换弱密码
```

### 完整示例：安装WordPress（依赖MySQL）

**步骤1：安装MySQL**
```
panel_docker_square_install(
    appname="mysql",
    name="my-mysql",
    params={
        "mysql_port": 13306,
        "mysql_root_password": "Ruyi@Mysql2026#Db"
    }
)
```

**步骤2：安装WordPress**
```
panel_docker_square_install(
    appname="wordpress",
    name="my-wordpress",
    params={
        "wordpress_port": 18080,
        "mysql_database": "ry",
        "mysql_user": "ry",
        "mysql_password": "Ruyi@Db2026#Pwd",
        "panel_service_type": "my-mysql"  # 注意：传实例名称
    }
)
```

### 完整示例：安装GitLab（无依赖）
```
panel_docker_square_install(
    appname="gitlab",
    name="my-gitlab",
    params={
        "gitlab_port": 18929,
        "gitlab_ssh_port": 10022
    }
)
```

## 依赖服务查找规则

当应用依赖其他服务时，按以下顺序查找：

1. **先查Docker广场已安装应用**：panel_docker_square_list
2. **再查应用商店已安装软件**：panel_shop_list
3. **都未安装**：返回need_dependency=true，询问用户选择安装方式

### 依赖服务类型映射
| 依赖服务 | Docker广场appname | 应用商店name |
|---------|------------------|-------------|
| MySQL | mysql | mysql |
| PostgreSQL | postgresql | pgsql, postgresql |
| MongoDB | mongodb | mongodb |
| Redis | redis | redis |
| MariaDB | mariadb | mariadb, mysql |

## 常见错误和解决方案

### 错误1：need_dependency
**原因**：依赖服务未安装
**解决**：先安装依赖服务，再安装目标应用

### 错误2：已存在同名应用实例
**原因**：name参数重复
**解决**：更换name参数，如从"wordpress"改为"my-wordpress"

### 错误3：容器广场中不存在应用
**原因**：appname错误或应用不在广场中
**解决**：用panel_docker_square_catalog查询可用应用列表

### 错误4：安装失败
**原因**：镜像拉取失败、端口冲突等
**解决**：用panel_docker_square_list查看状态，用panel_diagnose_install诊断

## 部署后配置

安装完成后，必须执行部署后配置：

### 使用panel_deploy_finalize一站式完成
```
panel_deploy_finalize(
    app_name="wordpress",
    app_port=18080,
    open_firewall=True,           # 放通防火墙端口
    enable_nginx_proxy=False,     # 暂不配置反向代理
    enable_waf=False              # 暂不启用WAF
)
```

### 或分步执行
1. **防火墙放通**：panel_deploy_finalize(open_firewall=True)
2. **Nginx反向代理**（需要域名）：先panel_shop_install("nginx")，再panel_site_create
3. **WAF防护**（需要Nginx站点）：waf_set_status
4. **SSL证书**（需要域名）：panel_site_ssl

## Nginx安装规范

### 必须使用panel_shop_install
```
❌ 禁止：execute_command("apt-get install nginx")
❌ 禁止：execute_command("yum install nginx")
✅ 正确：panel_shop_install("nginx")
```

### Nginx版本说明
- 只支持安装OpenResty版本（内置Lua/WAF支持）
- 无需指定version_id，系统自动选择
- Linux支持两种安装方式：编译安装和快速安装

## 禁止的操作

| 操作 | 禁止方式 | 正确方式 |
|------|---------|---------|
| 安装软件 | execute_command("apt install xxx") | panel_shop_install("xxx") |
| 启停服务 | execute_command("systemctl start xxx") | panel_shop_manage(name="xxx", action="start") |
| 查看容器 | execute_command("docker ps") | panel_docker_square_list |
| 运行容器 | execute_command("docker run ...") | panel_docker_square_install |
| 创建数据库 | execute_command("mysql -e 'CREATE ...'") | panel_database_create |
| 写入文件 | execute_command("cat > file") | write_file |
| 生成密码 | execute_command("openssl rand ...") | 传默认值，工具自动生成 |

## 搜索本文档

当用户要求安装软件、部署应用时，使用search_docs搜索：
- search_docs(query="AI安装指南")  ← 推荐，精确匹配标题
- search_docs(query="安装应用")
- search_docs(query="Docker广场安装")
- search_docs(query="panel_shop_install")
- search_docs(query="依赖服务")
