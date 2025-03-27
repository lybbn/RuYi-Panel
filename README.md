
# 如意服务器运维面板

[![img](https://img.shields.io/badge/python-%3E=3.12.x-green.svg)](https://python.org/)  [![PyPI - Django Version badge](https://img.shields.io/badge/django%20versions-4.x-blue)](https://docs.djangoproject.com/zh-hans/4.0/) [![img](https://img.shields.io/badge/node-%3E%3D%2014.0.0-brightgreen)](https://nodejs.org/zh-cn/)

[ 官方文档 ](https://ruyi.lybbn.cn/) | [ 演示 ](http://demoruyi.lybbn.cn/)| [捐赠](https://gitee.com/lybbn/django-vue-lyadmin/wikis/pages?sort_id=5264497&doc_id=2214316) 

## 如意服务器面板介绍

系统全名【如意服务器面板】，简称【如意面板】，其中【如意】取自【葫芦兄弟】中"如意如意，随我心意，快快显灵"，意在"如意面板"如法宝如意一样，随心使用，称心如意，支持windows和linux（推荐）服务器运行，在运维中助你一臂之力。

## 技术架构

```
Vue3 + Vite + Python3 + Django
```

## 面板安全（问题解答）

```text
- 【安全入口】只能通过安全入口才能正常登录，其他返回404
- 【接口限制】默认对匿名用户和登录用户做接口限速
- 【token续时】默认token有效期1天，采用过期自动刷新机制（refresh_token有效期2天）（前提不关闭浏览器）
- 【token存储】默认token存储在cookie中，浏览器关闭后则自动过期
- 【CMD窗口】有时cmd命令窗口会卡住，解决方法：windows cmd窗口->属性->选项->编辑选项。取消勾选【快速编辑模式】。原因：cmd默认开启了“快速编辑模式”，只要当鼠标点击cmd任何区域时，就自动进入了编辑模式，之后的程序向控制台输入内容甚至后台的程序都会被阻塞。
- 【计划任务】同一计划任务如果上一个没执行完，下一个任务会覆盖上一个任务（只允许同任务单一执行，已最新为准）
- 【计划任务】默认有两个任务：检查网站是否过期、检查letsencrypt证书续签（不建议删除，可根据情况选择启用/停止）
- 【计划任务】检查letsencrypt证书续签，如果站点启用了SSL且证书类型为letsencrypt证书且证书有效期小于等于30天才会尝试续签
- linux系统下可使用ruyi-cmd使用命令行功能，具体请使用ruyi-cmd --help 查看
- 目前支持amd64和x86_64位系统，其他安装和使用可能存在问题，后续根据情况考虑支持其他系统
- 如意面板支持windows和linux服务器，如要部署python项目，推荐使用linux服务器
- linux默认防火墙开启
```

### 支持系统

- windows 10 及以上 x64
- windows server 2008 及以上 x64
- centos7-8-9 debian11-12 ubuntu22-24 alinux 树莓派(x64)
- 其他系统暂未测试安装调试

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

## 功能预览

### 首页

<img src="https://foruda.gitee.com/images/1738813129276998940/d8beb4f2_4823422.jpeg" referrerpolicy="no-referrer" />

### 网站

<img src="https://foruda.gitee.com/images/1738813212161749528/6a548a53_4823422.jpeg" referrerpolicy="no-referrer" />

### 容器

<img src="https://foruda.gitee.com/images/1741523756230508106/12ebab70_4823422.png" referrerpolicy="no-referrer" />

### 计划任务

<img src="https://foruda.gitee.com/images/1738813406022412860/0bb914b4_4823422.jpeg" referrerpolicy="no-referrer" />

### 日志审计

<img src="https://foruda.gitee.com/images/1738813428277156383/b541ac59_4823422.jpeg" referrerpolicy="no-referrer" />


### 应用商店

<img src="https://foruda.gitee.com/images/1738813465814599623/b4c983a6_4823422.jpeg" referrerpolicy="no-referrer" />

[更多预览](https://gitee.com/lybbn/RuYi-Panel/wikis/pages?sort_id=13387675&doc_id=6451384)

