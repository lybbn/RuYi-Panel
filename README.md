
## 如意服务器面板介绍

系统全名【如意服务器面板】，简称【如意面板】，其中【如意】取自【葫芦兄弟】中"如意如意，随我心意，快快显灵"，意在"如意面板"如法宝如意一样，随心使用，称心如意，支持windows和linux（推荐）服务器运行，在运维中助你一臂之力。

## 面板安全（问题解答）

1、【安全入口】只能通过安全入口才能正常登录，其他返回404
2、【接口限制】默认对匿名用户和登录用户做接口限速
3、【token续时】默认token有效期1天，采用过期自动刷新机制（refresh_token有效期2天）（前提不关闭浏览器）
4、【token存储】默认token存储在cookie中，浏览器关闭后则自动过期
5、【CMD窗口】有时cmd命令窗口会卡住，解决方法：windows cmd窗口->属性->选项->编辑选项。取消勾选【快速编辑模式】。原因：cmd默认开启了“快速编辑模式”，只要当鼠标点击cmd任何区域时，就自动进入了编辑模式，之后的程序向控制台输入内容甚至后台的程序都会被阻塞。
6、【计划任务】同一计划任务如果上一个没执行完，下一个任务会覆盖上一个任务（只允许同任务单一执行，已最新为准）
7、【计划任务】默认有两个任务：检查网站是否过期、检查letsencrypt证书续签（不建议删除，可根据情况选择启用/停止）
8、【计划任务】检查letsencrypt证书续签，如果站点启用了SSL且证书类型为letsencrypt证书且证书有效期小于等于30天才会尝试续签
9、linux系统下可使用ruyi-cmd使用命令行功能，具体请使用ruyi-cmd --help 查看
10、目前支持amd64和x86_64位系统，其他安装和使用可能存在问题，后续根据情况考虑支持其他系统
11、如意面板支持windows和linux服务器，如要部署python项目，推荐使用linux服务器

## 安装方式

1、linux
## 如何运行

pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

2、windows

运行start.bat脚本（默认自启动）

## 已服务运行

###  windows
cmd 命令窗口（已管理员身份打开，否则会权限不足）
cd 项目根目录
python .\service.py --startup auto install
python .\service.py start
python .\service.py stop
python .\service.py restart
python .\service.py remove

### 支持系统

windows 7 以上
windows server 2008 及以上
linux centos7 centos8
其他系统暂未测试