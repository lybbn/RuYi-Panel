# AI助手

tags: AI,助手,聊天,工具,MCP,技能,知识库,Agent,大模型,提示词,定时任务

## AI聊天

### 基本使用
- 「AI」页面提供AI对话功能
- 输入问题，AI自动调用工具获取信息并回答
- 支持多轮对话，上下文关联
- 支持对话历史查看和管理
- 支持对话标题自动生成

### 工具调用
- AI可自动调用面板工具执行操作
- 常见操作：查看已安装应用、管理网站、查看系统状态
- 高风险操作（删除、重启等）需用户确认
- 工具调用结果实时展示

### 对话模型
- 支持多种AI模型切换
- 支持OpenAI兼容接口
- 支持自定义API地址和密钥
- 支持模型参数调整（温度、最大Token等）

## 工具管理

### 工具集模式
- 「AI」→「工具」页面
- 核心工具：始终加载（搜索文档、执行命令等）
- 按需加载：根据用户意图动态加载对应工具组
- 全量加载：所有工具全部注册（消耗更多Token）

### 面板工具分类

#### 应用商店工具
- `panel_shop_list`：获取应用商店软件列表
- `panel_shop_install`：安装应用商店软件
- `panel_shop_manage`：管理应用（启停/卸载/配置）
- `panel_shop_task_status`：查询安装任务状态

#### Docker广场工具
- `panel_docker_square_list`：获取已安装Docker应用
- `panel_docker_square_catalog`：获取可安装应用目录
- `panel_docker_square_install`：一键安装Docker应用
- `panel_docker_square_manage`：管理Docker应用

#### 网站管理工具
- `panel_site_create`：创建网站
- `panel_site_list`：获取网站列表
- `panel_site_manage`：管理网站（启停/配置/备份）

#### 数据库工具
- `panel_database_create`：创建数据库
- `panel_database_list`：获取数据库列表
- `panel_database_manage`：管理数据库

#### 系统工具
- `get_system_info`：获取系统信息
- `get_disk_info`：获取磁盘信息
- `get_process_info`：获取进程信息
- `execute_command`：执行系统命令（高危）

#### 文件工具
- `read_file`：读取文件内容
- `write_file`：写入文件内容
- `list_files`：列出目录文件

#### 安全工具
- `get_firewall_status`：获取防火墙状态
- `get_ssh_config`：获取SSH配置
- `get_login_history`：获取登录历史
- `vuln_check_kernel`：检查内核漏洞

#### WAF工具
- `waf_get_status`：获取WAF状态
- `waf_set_status`：切换WAF模式
- `waf_get_dashboard`：获取WAF仪表盘数据

#### 告警工具
- `alert_list`：获取告警任务列表
- `alert_create`：创建告警任务
- `alert_update`：更新告警任务
- `notify_channel_list`：获取通知渠道列表

#### 定时任务工具
- `crontab_list`：获取定时任务列表
- `crontab_create`：创建定时任务
- `crontab_update`：更新定时任务
- `crontab_delete`：删除定时任务

#### 网络工具
- `web_search`：搜索互联网获取信息

#### 知识库工具
- `search_docs`：搜索面板知识库文档

### MCP服务
- 「AI」→「工具」→「MCP」选项卡
- 支持配置外部MCP服务（Model Context Protocol）
- 传输方式：stdio / http
- 添加MCP服务后，AI可使用该服务提供的工具
- 支持MCP服务启停管理

### 技能进化
- 「AI」→「工具」→「进化」选项卡
- 系统自动记录工具使用情况
- 高频工具自动沉淀为技能
- 可查看工具调用统计
- 支持技能导入导出

## AI配置

### 基本设置
- 「AI」→「设置」页面
- 配置AI模型API地址和密钥
- 选择默认模型
- 设置工具集模式
- 开关Web搜索功能
- 设置对话历史保留数量

### 高级设置
- 设置AI回复最大Token数
- 设置工具调用超时时间
- 设置是否启用流式输出
- 设置是否显示工具调用过程

## 知识库

- AI内置面板操作知识库
- 用户询问面板功能时自动检索相关文档
- 知识库内容基于如意面板实际功能编写
- 支持知识库文档更新

### 知识库内容
- 系统管理文档
- Docker管理文档
- 网站管理文档
- 数据库管理文档
- 文件管理文档
- 备份恢复文档
- WAF防护文档
- 应用商店文档
- AI助手文档

## 定时AI任务

### 创建AI定时任务
- 在「计划任务」页面创建AI任务类型
- 配置AI提示词（prompt）
- 设置执行周期
- 支持设置上下文来源（系统信息、监控数据等）

### AI任务执行
- 定时触发AI执行任务
- AI自动调用工具完成任务
- 记录执行结果和日志
- 支持失败重试

### AI任务场景
- 每日系统巡检报告
- 定期安全检查
- 自动化运维操作
- 智能告警分析

## AI使用技巧

### 常用指令示例
- "查看服务器状态"
- "安装MySQL 8.0"
- "创建一个WordPress网站"
- "查看WAF防护状态"
- "备份所有数据库"
- "检查服务器安全漏洞"
- "查看Docker容器状态"
- "设置CPU使用率超过90%告警"

### 高级用法
- "分析最近7天的攻击日志，找出最频繁的攻击IP"
- "检查所有网站的SSL证书，哪些即将过期"
- "优化MySQL配置，提升数据库性能"
- "部署一个AI知识库应用"
