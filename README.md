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

### 🌐 网站管理
- **多站点管理**：支持创建、删除、暂停、启用多个网站
- **域名绑定**：支持多域名绑定、子域名管理
- **SSL证书**：支持Let's Encrypt免费证书自动申请与续签，支持自定义证书上传
- **伪静态规则**：内置常用伪静态规则（WordPress、Laravel、ThinkPHP等）
- **防盗链设置**：自定义防盗链规则，保护网站资源
- **重定向配置**：支持URL重定向、域名跳转
- **访问限制**：基于IP、User-Agent的访问控制
- **WAF防护**：内置Web应用防火墙，防护SQL注入、XSS、命令执行等攻击

### 🛡️ WAF防火墙
- **攻击防护**：SQL注入、XSS攻击、命令执行、路径遍历、敏感文件访问等
- **CC防护**：高频访问限制、恶意容忍度设置、错误频率限制
- **IP黑白名单**：支持IP段、IP组管理
- **地域封锁**：基于地理位置的访问控制
- **Bot管理**：爬虫识别与拦截
- **扫描器拦截**：自动识别SQLMap、Nmap等扫描工具
- **攻击日志**：详细的攻击记录与统计分析
- **拦截页面**：自定义拦截页面，支持显示/隐藏详细信息

### 🗄️ 数据库管理
- **MySQL管理**：数据库创建、用户管理、权限控制
- **Redis管理**：Redis实例管理、数据查看
- **远程访问**：支持配置远程访问权限
- **备份恢复**：数据库备份与恢复功能

### 📦 容器管理
- **Docker管理**：容器生命周期管理（创建、启动、停止、重启、删除）
- **镜像管理**：镜像拉取、删除、导入导出
- **容器编排**：支持docker-compose编排
- **网络管理**：容器网络配置
- **卷管理**：数据卷管理
- **应用商店**：一键安装常用应用（Playwright、MySQL、Redis等）

### 📁 文件管理
- **在线文件管理**：上传、下载、编辑、压缩、解压
- **权限管理**：文件权限设置
- **在线编辑**：支持代码高亮的在线编辑器
- **回收站**：文件删除保护机制

### ⚙️ 系统管理
- **系统监控**：CPU、内存、磁盘、网络实时监控
- **进程管理**：进程查看与结束
- **服务管理**：系统服务启停管理
- **计划任务**：Crontab计划任务管理，支持Shell、Python脚本
- **SSH管理**：SSH服务配置、密钥管理
- **防火墙**：系统防火墙规则管理

### 🔒 安全管理
- **Fail2Ban**：暴力破解防护，支持SSH、Mysql等服务的自动封禁
- **登录日志**：面板登录记录审计
- **操作日志**：用户操作记录追踪
- **安全入口**：面板安全入口保护

### 🛠️ 软件商店
- **环境安装**：Nginx、MySQL、Go、Redis、Python等一键安装
- **版本管理**：多版本Go共存与切换
- **Python环境**：Python版本管理与虚拟环境

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
