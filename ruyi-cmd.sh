#!/bin/bash
#ruyi 如意面板工具v0.0.1

action=$1
Root_PATH=/ruyi
Panel_Root_Path=/ruyi/server/ruyi
Python_Bin=/usr/local/ruyi/python/bin/python3

echo
cat << EOF

 ███████████   █████  █████ █████ █████ █████
░░███░░░░░███ ░░███  ░░███ ░░███ ░░███ ░░███
 ░███    ░███  ░███   ░███  ░░███ ███   ░███
 ░██████████   ░███   ░███   ░░█████    ░███
 ░███░░░░░███  ░███   ░███    ░░███     ░███
 ░███    ░███  ░███   ░███     ░███     ░███
 █████   █████ ░░████████      █████    █████ sh v0.0.1
░░░░░   ░░░░░   ░░░░░░░░      ░░░░░    ░░░░░

===============================================

EOF

if [ "$(id -u)" -ne 0 ]; then
    echo "===================错误======================"
    echo "检测到非root用户权限执行，部分命令可能执行异常"
    echo "请使用root权限执行"
    echo "============================================="
    exit 0
fi

usage() {
    echo "RuYi 面板命令行"
    echo
    echo "Usage: "
    echo "ruyi-cmd [COMMAND]"
    echo "ruyi-cmd --help"
    echo
    echo "Example: "
    echo "ruyi-cmd status"
    echo
    echo "Commands(命令): ================================================================="
    echo "  status     查看运行状态          |        setport      修改面板端口"
    echo "  start      启动面板服务          |        setsafepath  修改面板安全入口"
    echo "  stop       停止面板服务          |        setkey       修改面板秘钥(SECRET_KEY)"  
    echo "  restart    重启面板服务          |        info         查看面板信息"
    echo "  uninstall  卸载面板服务          |        setuser      修改面板用户名"             
    echo "  version    查看版本信息          |        setpass      修改面板密码"
    echo "================================================================================"
}

status() {
    systemctl status ruyi.service
}

start() {
    systemctl start ruyi.service
    status
}

stop() {
    systemctl stop ruyi.service
    status
}

restart() {
    systemctl restart ruyi.service
    status
}

version() {
    cd $Panel_Root_Path
    $Python_Bin manage.py panelcli get_version
}

getinfo() {
    cd $Panel_Root_Path
    $Python_Bin manage.py panelcli get_panelinfo
}

resetpass() {
    read -p "请输入新的面板密码 : " newpassword
    if [ -z "$newpassword" ] || [ ${#newpassword} -lt 6 ]; then
        echo "密码长度不能少于6个字符！"
        exit 0
    fi
    cd $Panel_Root_Path
    $Python_Bin manage.py resetpass -p $newpassword
}

resetuser() {
    read -p "请输入新的面板用户名（为空表示自动生成）: " newusername
    if [ -z "$newusername" ] ; then
        newusername="ry"
        newusername+=$(head /dev/urandom | tr -dc 'A-Za-z0-9' | head -c 6)
        echo "用户名将自动随机生成！"
    elif [ ${#newusername} -lt 5 ]; then
        echo "用户名长度不能少于5个字符！"
        exit 0
    fi
    cd $Panel_Root_Path
    $Python_Bin manage.py panelcli set_username -d $newusername
}

setsafepath() {
    read -p "请输入新的面板安全入口（为空表示自动生成）: " newsafepath
    if [ -z "$newsafepath" ] ; then
        newsafepath=$(head /dev/urandom | tr -dc 'A-Za-z0-9' | head -c 7)
        echo "安全入口将自动随机生成！"
    elif [ ${#newsafepath} -lt 5 ]; then
        echo "安全入口长度不能少于5个字符！"
        exit 0
    fi
    cd $Panel_Root_Path
    $Python_Bin manage.py panelcli set_safepath -d $newsafepath
}

setport() {
    read -p "请输入新的面板端口（为空表示自动生成）: " newport
    if [ -z "$newport" ] ; then
        newport=$((RANDOM % (38999 - 30000 + 1) + 30000))
        echo "面板端口将自动随机生成！"
    fi
    cd $Panel_Root_Path
    $Python_Bin manage.py panelcli set_port -d $newport
}

setkey() {
    read -p "请输入新的面板秘钥（为空表示自动生成）: " newsecretkey
    if [ -z "$newsecretkey" ] ; then
        newsecretkey=$(head /dev/urandom | tr -dc 'A-Za-z0-9' | head -c 15)
        echo "面板秘钥将自动随机生成！"
    elif [ ${#newsecretkey} -lt 10 ]; then
        echo "面板秘钥长度不能少于10个字符！"
        exit 0
    fi
    cd $Panel_Root_Path
    $Python_Bin manage.py panelcli set_secretkey -d $newsecretkey
}

uninstall() {
    read -p "卸载将会完全清除 RuYi 服务和数据目录，是否继续 [y/n] : " ynstr
    if [ "$ynstr" == "Y" ] || [ "$ynstr" == "y" ]; then
        echo -e "================== 开始卸载 RuYi 服务器面板 =================="
        echo -e ""
        echo -e "1) 停止 RuYi 服务进程..."
        systemctl stop ruyi.service
        systemctl disable ruyi.service >/dev/null 2>&1
    else
        exit 0
    fi

    echo -e "2) 删除 RuYi 服务和数据目录..."
    rm -rf $Root_PATH/server/ruyi /etc/systemd/system/ruyi.service

    echo -e "3) 重新加载服务配置文件..."
    systemctl daemon-reload
    systemctl reset-failed

    echo -e ""
    echo -e "================================ 卸载完成 ================================"
}

main() {
    case "${action}" in
        version)
            version
            ;;
        info)
            getinfo
            ;;
        status)
            status
            ;;
        start)
            start
            ;;
        stop)
            stop
            ;;
        restart)
            restart
            ;;
        uninstall)
            uninstall
            ;;
        setpass)
            resetpass
            ;;
        setuser)
            resetuser
            ;;
        setsafepath)
            setsafepath
            ;;
        setport)
            setport
            ;;
        setkey)
            setkey
            ;;
        help)
            usage
            ;;
        --help)
            usage
            ;;
        "")
            usage
            ;;
        *)
        echo "不支持的参数，请使用 help 或 --help 参数获取帮助"
    esac
}

main