# 如意服务器运维面板

[![img](https://img.shields.io/badge/python-%3E=3.12.x-green.svg)](https://python.org/)  [![PyPI - Django Version badge](https://img.shields.io/badge/django%20versions-4.x-blue)](https://docs.djangoproject.com/zh-hans/4.0/) [![img](https://img.shields.io/badge/node-%3E%3D%2014.0.0-brightgreen)](https://nodejs.org/zh-cn/)

[ 官方文档 ](https://ruyi.lybbn.cn/) | [ 演示 ](http://demoruyi.lybbn.cn/)| [捐赠](https://gitee.com/lybbn/django-vue-lyadmin/wikis/pages?sort_id=5264497&doc_id=2214316) 

## 产品简介

**如意服务器面板**（简称**如意面板**）是一款高效便捷的服务器运维管理工具，支持Windows和Linux系统运行。名称灵感来源于"葫芦兄弟"中的法宝"如意"，寓意本面板能如如意法宝般随您心意，助您轻松完成服务器运维工作。

## 技术架构

```
Vue3 + Vite + Python3 + Django
```

## 核心功能

### 🤖 AI智能助手
- **多模型支持**：OpenAI、DeepSeek、Ollama、OpenRouter、vLLM、LongCat等主流AI模型接入
- **智能对话**：自然语言交互，支持流式输出与深度思考（Reasoning）模式
- **专业智能体**：内置10+领域专家智能体，一键诊断分析
  - 进程分析专家、安全专家、站点分析专家、磁盘分析专家
  - 流量分析专家、SSL检测专家、日志分析专家、DNS分析专家
  - 数据库诊断专家、定时任务诊断专家、性能瓶颈分析专家
- **工具系统**：50+内置运维工具，覆盖系统、服务、Docker、数据库、网站、安全、WAF等场景
- **智能工具路由**：根据用户意图自动匹配工具集，支持关键词匹配、智能模式、手动选择三种模式
- **工具集模式**：最小模式、开发模式、运维模式、面板模式、全量模式
- **网络搜索**：集成Bing、Google、SerpAPI、Tavily、博查AI等搜索引擎
- **MCP协议**：支持Model Context Protocol，可扩展接入外部工具服务
- **技能系统**：可自定义AI技能，渐进式加载，支持技能的创建、启用、禁用
- **上下文压缩**：自动压缩长对话上下文，保留关键信息，降低Token消耗
- **记忆系统**：基于向量嵌入的长期记忆，跨会话知识召回
- **面板文档搜索**：内置面板操作文档知识库，AI可检索面板使用说明
- **附件处理**：支持本地文件/目录上传，自动读取内容注入对话上下文
- **命令确认**：高危操作需用户确认，保障服务器安全
- **GPU监控**：NVIDIA GPU状态监控，驱动版本、CUDA版本、显存使用等

### 🌐 网站管理
- **多站点管理**：支持创建、删除、暂停、启用多个网站
- **多类型站点**：静态站点、Python项目、Node.js项目、PHP站点、Go项目
- **站点分组**：支持站点分组管理
- **域名绑定**：支持多域名绑定、子域名管理
- **SSL证书**：支持Let's Encrypt免费证书自动申请与续签，支持自定义证书上传、自签名证书
- **伪静态规则**：内置常用伪静态规则（WordPress、Laravel、ThinkPHP等）
- **防盗链设置**：自定义防盗链规则，保护网站资源
- **重定向配置**：支持URL重定向、域名跳转
- **访问限制**：基于IP、User-Agent的访问控制
- **反向代理**：支持配置反向代理
- **流量限制**：网站并发与速率限制
- **默认站点**：可设置默认站点
- **网站备份**：站点数据备份与恢复

### 🛡️ WAF防火墙
- **攻击防护**：SQL注入、XSS攻击、命令执行、路径遍历、敏感文件访问等
- **CC防护**：高频访问限制、恶意容忍度设置、错误频率限制
- **IP黑白名单**：支持IP段、IP组管理
- **URL黑白名单**：URL级别的访问控制
- **地域封锁**：基于地理位置的访问控制
- **Bot管理**：爬虫识别与拦截
- **扫描器拦截**：自动识别SQLMap、Nmap等扫描工具
- **攻击日志**：详细的攻击记录与统计分析
- **攻击分析**：IP攻击趋势分析、攻击来源统计
- **拦截页面**：自定义拦截页面，支持显示/隐藏详细信息
- **站点级配置**：每个站点独立的WAF防护配置与开关
- **CDN适配**：支持CDN场景下的真实IP获取与地理位置定位
- **WAF仪表盘**：攻击统计总览、趋势图表

### 🗄️ 数据库管理
- **MySQL管理**：数据库创建、用户管理、权限控制、远程访问配置
- **Redis管理**：Redis实例管理、数据查看
- **备份恢复**：数据库备份与恢复功能
- **Root密码管理**：MySQL Root密码重置
- **数据库导入**：支持SQL文件导入

### 📦 容器管理
- **Docker管理**：容器生命周期管理（创建、启动、停止、重启、删除）
- **镜像管理**：镜像拉取、删除、导入导出
- **容器编排**：支持docker-compose编排
- **网络管理**：容器网络配置
- **卷管理**：数据卷管理
- **仓库管理**：Docker镜像仓库配置
- **容器终端**：在线容器Shell终端
- **容器设置**：容器资源限制、环境变量、端口映射等配置
- **GPU支持**：NVIDIA GPU容器分配
- **应用商店**：一键安装常用应用（WordPress、Nextcloud、GitLab、Jenkins、MySQL、Redis等）
- **应用备份**：Docker应用数据备份与恢复

### 📁 文件管理
- **在线文件管理**：上传、下载、编辑、压缩、解压
- **权限管理**：文件权限设置
- **在线编辑**：支持代码高亮的在线编辑器
- **回收站**：文件删除保护机制
- **批量操作**：批量复制、移动、删除
- **文件搜索**：快速搜索定位文件

### ⚙️ 系统管理
- **系统监控**：CPU、内存、磁盘IO、网络IO实时监控与历史趋势
- **进程管理**：进程查看、详情查看与结束
- **网络连接**：网络连接状态查看与筛选
- **服务管理**：系统服务启停管理
- **计划任务**：Crontab计划任务管理，支持Shell、Python脚本
- **SSH管理**：SSH服务配置、密钥管理
- **防火墙**：系统防火墙规则管理（Linux iptables/ufw、Windows防火墙）
- **守护进程**：Supervisor进程守护管理

### 🔒 安全管理
- **Fail2Ban**：暴力破解防护，支持SSH、MySQL等服务的自动封禁
- **登录日志**：面板登录记录审计
- **操作日志**：用户操作记录追踪
- **安全入口**：面板安全入口保护

### 🚨 告警通知
- **多渠道通知**：邮件、钉钉、飞书、企业微信、短信、Webhook
- **资源告警**：CPU、内存、磁盘使用率、磁盘IO、网络流量、系统负载
- **网站监控**：SSL证书过期、网站宕机、网站响应慢
- **安全告警**：WAF攻击、SSH登录失败、SSH新IP登录、面板登录失败
- **任务告警**：定时任务执行失败通知
- **灵活配置**：告警阈值、静默时间、每日推送上限、检查间隔
- **告警恢复**：自动检测恢复并发送恢复通知
- **告警日志**：完整的告警发送记录与状态追踪

### 💻 终端管理
- **SSH终端**：在线SSH终端，支持密码和密钥认证
- **RDP远程桌面**：在线RDP远程桌面连接（基于Guacamole协议）
- **服务器管理**：多服务器终端配置与管理
- **常用命令**：自定义快捷命令收藏

### 💾 备份管理
- **数据库备份**：MySQL数据库定时备份
- **网站备份**：网站文件定时备份
- **目录备份**：指定目录定时备份
- **应用备份**：Docker应用数据备份
- **本地/远程存储**：支持本地和远程备份存储

### 🛠️ 软件商店
- **环境安装**：Nginx、MySQL、Go、Redis、Python、PHP等一键安装
- **版本管理**：多版本Go共存与切换
- **Python环境**：Python版本管理与虚拟环境
- **图片工具**：在线图片处理工具

### 📊 监控系统
- **实时监控**：CPU、内存、磁盘IO、网络IO实时数据采集
- **历史趋势**：监控数据历史趋势图表
- **自定义采集**：可配置采集间隔、监控网卡与磁盘
- **自动清理**：监控数据自动清理，可配置保存天数

### ⚙️ 面板设置
- **面板配置**：面板端口、绑定地址、安全入口设置
- **用户管理**：用户名、密码修改
- **SSL配置**：面板SSL证书配置
- **OpenAPI**：开放API接口配置
- **授权许可**：商业授权管理

## 面板安全（问题解答）

```text
- 【安全入口】只能通过安全入口才能正常登录，其他返回404
- 【接口限制】默认对匿名用户和登录用户做接口限速
- 【token续时】默认token有效期1天，采用过期自动刷新机制（refresh_token有效期2天）（前提不关闭浏览器）
- 【token存储】默认token存储在cookie中，浏览器关闭后则自动过期
- 【CMD窗口】有时cmd命令窗口会卡住，解决方法：windows cmd窗口->属性->选项->编辑选项。取消勾选【快速编辑模式】。原因：cmd默认开启了"快速编辑模式"，只要当鼠标点击cmd任何区域时，就自动进入了编辑模式，之后的程序向控制台输入内容甚至后台的程序都会被阻塞。
- 【计划任务】同一计划任务如果上一个没执行完，下一个任务会覆盖上一个任务（只允许同任务单一执行，已最新为准）
- 【计划任务】默认有两个任务：检查网站是否过期、检查letsencrypt证书续签（不建议删除，可根据情况选择启用/停止）
- 【计划任务】检查letsencrypt证书续签，如果站点启用了SSL且证书类型为letsencrypt证书且证书有效期小于等于30天才会尝试续签
- linux系统下可使用ruyi-cmd使用命令行功能，具体请使用ruyi-cmd --help 查看
- 目前支持amd64和x86_64位系统，其他安装和使用可能存在问题，后续根据情况考虑支持其他系统
- 如意面板支持windows和linux服务器，如要部署python项目，推荐使用linux服务器
- linux默认防火墙开启
```

## 系统支持

### 已验证系统
- **Windows**:
  - Windows 10+ x64
  - Windows Server 2012R2+ x64
  
- **Linux**:
  - CentOS 7/8/9
  - Debian 11/12
  - Ubuntu 22.04/24.04
  - Alinux
  - 树莓派(x64)

## 查看演示

[点击查看](http://demoruyi.lybbn.cn/)

- 账号：demo
- 密码：ruyi123456

## 立即安装

支持windows和linux系统

 - [点击安装](https://ruyi.lybbn.cn/doc/ruyi/onlineInstall.html)

## 交流
- 开发者QQ号：1042594286

- QQ群：

1. 如意服务器运维面板群1：746326385

## 视频教程

| 序号 | 教程名称 | 观看链接 |
|------|---------|---------|
| 1 | 面板安装 | [观看](https://www.bilibili.com/video/BV1iVPUeAEsw) |
| 2 | 面板升级 | [观看](https://www.bilibili.com/video/BV1oVNpecEnG) |
| 3 | 命令行工具 | [观看](https://www.bilibili.com/video/BV14cN4edEPP) |
| 4 | 软件安装 | [观看](https://www.bilibili.com/video/BV1uhNVeZERS) |
| 5 | Python项目部署 | [观看](https://www.bilibili.com/video/BV1b1KNeuEQG) |
| ... | 更多教程持续更新中 | |

## 功能预览

### 首页

<img src="https://foruda.gitee.com/images/1738813129276998940/d8beb4f2_4823422.jpeg" referrerpolicy="no-referrer" />

### Waf防火墙

<img src="https://foruda.gitee.com/images/1772073000035694789/caed6251_4823422.png" referrerpolicy="no-referrer" />

### fail2ban 暴力破解防护

<img src="https://foruda.gitee.com/images/1772073056156005458/c5e632d7_4823422.png" referrerpolicy="no-referrer" />

### ssh管理

<img src="https://foruda.gitee.com/images/1772073089088942449/3ddfe9e6_4823422.png" referrerpolicy="no-referrer" />

### 网站管理

<img src="https://foruda.gitee.com/images/1738813212161749528/6a548a53_4823422.jpeg" referrerpolicy="no-referrer" />

### 容器管理

<img src="https://foruda.gitee.com/images/1741523756230508106/12ebab70_4823422.png" referrerpolicy="no-referrer" />

### 计划任务

<img src="https://foruda.gitee.com/images/1738813406022412860/0bb914b4_4823422.jpeg" referrerpolicy="no-referrer" />

### 日志审计

<img src="https://foruda.gitee.com/images/1738813428277156383/b541ac59_4823422.jpeg" referrerpolicy="no-referrer" />

### 应用商店

<img src="https://foruda.gitee.com/images/1738813465814599623/b4c983a6_4823422.jpeg" referrerpolicy="no-referrer" />

[更多预览](https://gitee.com/lybbn/RuYi-Panel/wikis/pages?sort_id=13387675&doc_id=6451384)

## 鸣谢

感谢以下开源项目提供的支持：
- [Vue.js](https://vuejs.org/)
- [Django](https://www.djangoproject.com/)
- [Element Plus](https://element-plus.org/)
- [Nginx](https://nginx.org/)
- [OpenResty](https://openresty.org/)
