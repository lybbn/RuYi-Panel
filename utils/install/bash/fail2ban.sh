#!/bin/bash
# Fail2Ban 环境安装脚本
# 支持平台: Ubuntu/Debian/CentOS/RHEL/Almalinux/Alpine/Arch
# 功能: 智能防火墙检测、智能日志检测、跨平台安装

PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
export PATH
LANG=en_US.UTF-8

RUYI_TEMP_PATH="/ruyi/tmp"
SOFT_INSTALL_PATH=/ruyi/server/fail2ban
SOFT_TMP_PATH=/ruyi/server/fail2ban/tmp
BASE_BIN_PATH=/usr/local/ruyi/python/bin
CONFIG_PATH=/etc/fail2ban
JAIL_CONFIG_PATH=/etc/fail2ban/jail.local
DATA_CONFIG_PATH=/ruyi/server/ruyi/data/fail2ban
action_type=$1
soft_version=$2
soft_file_name=$3
cpu_core=$(cat /proc/cpuinfo|grep processor|wc -l)

if [ "$(id -u)" -ne 0 ]; then
    echo "请以 root 用户运行此脚本" >&2
    exit 1
fi

Detect_Package_Manager() {
    if command -v apt-get &> /dev/null; then
        echo "apt"
    elif command -v yum &> /dev/null; then
        echo "yum"
    elif command -v dnf &> /dev/null; then
        echo "dnf"
    elif command -v apk &> /dev/null; then
        echo "apk"
    elif command -v pacman &> /dev/null; then
        echo "pacman"
    else
        echo "unknown"
    fi
}

Detect_Log_File() {
    if [ -f "/var/log/secure" ]; then
        echo "/var/log/secure"
    elif [ -f "/var/log/auth.log" ]; then
        echo "/var/log/auth.log"
    elif [ -f "/var/log/messages" ]; then
        echo "/var/log/messages"
    else
        echo "/var/log/secure"
    fi
}

Detect_Firewall() {
    local firewall_type=""
    
    if systemctl is-active --quiet firewalld 2>/dev/null && command -v firewall-cmd &> /dev/null; then
        firewall_type="firewalld"
    elif systemctl is-active --quiet ufw 2>/dev/null && command -v ufw &> /dev/null; then
        firewall_type="ufw"
    elif command -v iptables &> /dev/null; then
        firewall_type="iptables"
    else
        firewall_type="iptables"
    fi
    
    echo "$firewall_type"
}

Get_Firewall_Action() {
    local firewall=$1
    case $firewall in
        firewalld)
            echo "firewallcmd-multiport"
            ;;
        ufw)
            echo "ufw"
            ;;
        *)
            echo "iptables-multiport"
            ;;
    esac
}

Install_Package() {
    local pkg_manager=$(Detect_Package_Manager)
    echo "检测到包管理器: $pkg_manager"
    
    case $pkg_manager in
        apt)
            echo "更新软件包列表..."
            apt-get update -y
            echo "安装 fail2ban 及依赖..."
            apt-get install -y fail2ban iptables python3-systemd rsyslog
            ;;
        yum|dnf)
            echo "安装 EPEL 源..."
            if command -v yum &> /dev/null; then
                yum install -y epel-release
            else
                dnf install -y epel-release
            fi
            echo "安装 fail2ban 及依赖..."
            if command -v yum &> /dev/null; then
                yum install -y fail2ban iptables python3-systemd rsyslog
            else
                dnf install -y fail2ban iptables python3-systemd rsyslog
            fi
            ;;
        apk)
            echo "安装 fail2ban 及依赖..."
            apk add fail2ban iptables
            ;;
        pacman)
            echo "安装 fail2ban 及依赖..."
            pacman -Sy --noconfirm fail2ban iptables
            ;;
        *)
            echo "不支持的包管理器，尝试使用 pip 安装..."
            if command -v pip3 &> /dev/null; then
                pip3 install fail2ban
            else
                echo "错误: 无法找到合适的包管理器" >&2
                exit 1
            fi
            ;;
    esac
}

Uninstall_Package() {
    local pkg_manager=$(Detect_Package_Manager)
    
    case $pkg_manager in
        apt)
            apt-get purge -y fail2ban
            apt-get autoremove -y
            ;;
        yum)
            yum remove -y fail2ban
            yum autoremove -y
            ;;
        dnf)
            dnf remove -y fail2ban
            dnf autoremove -y
            ;;
        apk)
            apk del fail2ban
            ;;
        pacman)
            pacman -R --noconfirm fail2ban
            ;;
        *)
            if command -v pip3 &> /dev/null; then
                pip3 uninstall -y fail2ban
            fi
            ;;
    esac
}

Service_Add() {
    local firewall=$(Detect_Firewall)
    echo "检测到防火墙: $firewall"
    
    if [ -f "/etc/systemd/system/fail2ban.service" ] || [ -f "/lib/systemd/system/fail2ban.service" ]; then
        echo "系统服务文件已存在，跳过创建"
    else
        echo "创建 systemd 服务文件..."
        cat <<EOF > /etc/systemd/system/fail2ban.service
[Unit]
Description=Fail2Ban Service
After=network.target

[Service]
Type=forking
ExecStart=/usr/bin/fail2ban-server -c ${CONFIG_PATH} -x start
ExecStop=/usr/bin/fail2ban-server -c ${CONFIG_PATH} stop
ExecReload=/usr/bin/fail2ban-client reload
PIDFile=/run/fail2ban/fail2ban.pid
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
    fi
    
    systemctl daemon-reload
    systemctl enable fail2ban
}

Service_Del() {
    if systemctl is-active --quiet fail2ban 2>/dev/null; then
        systemctl stop fail2ban > /dev/null
    fi
    if systemctl is-enabled --quiet fail2ban 2>/dev/null; then
        systemctl disable fail2ban > /dev/null
    fi
}

Write_Jail_Config() {
    local log_file=$(Detect_Log_File)
    local firewall=$(Detect_Firewall)
    local banaction=$(Get_Firewall_Action $firewall)
    
    echo "检测到日志文件: $log_file"
    echo "使用防火墙动作: $banaction"
    
    mkdir -p ${CONFIG_PATH}
    mkdir -p ${CONFIG_PATH}/filter.d
    mkdir -p ${CONFIG_PATH}/action.d
    mkdir -p ${DATA_CONFIG_PATH}
    mkdir -p /run/fail2ban
    mkdir -p /var/log/fail2ban
    chmod 755 /run/fail2ban
    chmod 755 /var/log/fail2ban

    cat <<EOF > ${CONFIG_PATH}/fail2ban.conf
[Definition]
loglevel = INFO
logtarget = /var/log/fail2ban.log
socket = /var/run/fail2ban/fail2ban.sock
pidfile = /var/run/fail2ban/fail2ban.pid
dbfile = /var/lib/fail2ban/fail2ban.sqlite3
dbpurgeage = 86400
syslogsocket = auto
allowipv6 = auto

[Init]
journalmatch = _SYSTEMD_UNIT=fail2ban.service
EOF

    cat <<EOF > ${CONFIG_PATH}/jail.conf
[DEFAULT]
ignoreip = 127.0.0.1/8 ::1
bantime = 10m
findtime = 10m
maxretry = 5
backend = auto
usedns = warn
logencoding = auto
banaction = ${banaction}

[INCLUDES]
before = paths-debian.conf
after = jail.local
EOF

    cat <<EOF > ${JAIL_CONFIG_PATH}
[DEFAULT]
ignoreip = 127.0.0.1/8 ::1
bantime = 10m
findtime = 10m
maxretry = 5
backend = auto
usedns = warn
logencoding = auto
banaction = ${banaction}

[sshd]
enabled = true
port = 22
filter = sshd
logpath = ${log_file}
maxretry = 5
findtime = 10m
bantime = 1h
action = ${banaction}
EOF

    cat <<EOF > ${CONFIG_PATH}/filter.d/sshd.conf
[Definition]
failregex = ^.*sshd\[\d+\]: Failed password for .* from <HOST> port \d+.*$
            ^.*sshd\[\d+\]: Failed password for invalid user .* from <HOST> port \d+.*$
            ^.*sshd\[\d+\]: pam_unix\(sshd:auth\): authentication failure.*rhost=<HOST>.*$
            ^.*sshd\[\d+\]: Connection closed by authenticating user .* <HOST> port \d+.*$
            ^.*sshd\[\d+\]: Disconnected from invalid user <HOST> port \d+.*$
            ^.*sshd\[\d+\]: error: maximum authentication attempts exceeded for .* from <HOST> port \d+.*$
            ^.*sshd\[\d+\]: Invalid user .* from <HOST> port \d+.*$
            ^.*sshd\[\d+\]: User .* from <HOST> not allowed.*$
            ^.*Failed password for .* from <HOST> port \d+.*$
            ^.*authentication failure.*rhost=<HOST>.*$

ignoreregex = 

[Init]
maxlines = 10
EOF

    if [ ! -f "${CONFIG_PATH}/action.d/iptables.conf" ]; then
        cat <<EOF > ${CONFIG_PATH}/action.d/iptables.conf
# iptables action configuration
# This is a basic iptables action for fail2ban

[Definition]
actionstart = iptables -N f2b-<name> 2>/dev/null || true
              iptables -A f2b-<name> -j RETURN
              iptables -I INPUT -p <protocol> --dport <port> -j f2b-<name>
actionstop = iptables -D INPUT -p <protocol> --dport <port> -j f2b-<name> 2>/dev/null || true
             iptables -F f2b-<name> 2>/dev/null || true
             iptables -X f2b-<name> 2>/dev/null || true
actioncheck = iptables -C INPUT -p <protocol> --dport <port> -j f2b-<name> 2>/dev/null
actionban = iptables -I f2b-<name> 1 -s <ip> -j DROP
actionunban = iptables -D f2b-<name> -s <ip> -j DROP
protocol = tcp
port = ssh
name = default
returntype = RETURN
lockingopt = -w

[Init]
EOF
    fi

    if [ ! -f "${CONFIG_PATH}/action.d/iptables-multiport.conf" ]; then
        cat <<EOF > ${CONFIG_PATH}/action.d/iptables-multiport.conf
# iptables-multiport action configuration

[Definition]
actionstart = iptables -N f2b-<name> -L >/dev/null 2>&1 || iptables -N f2b-<name>
              iptables -A f2b-<name> -j RETURN
              iptables -I INPUT -p <protocol> -m multiport --dports <port> -j f2b-<name>
actionstop = iptables -D INPUT -p <protocol> -m multiport --dports <port> -j f2b-<name> 2>/dev/null || true
             iptables -F f2b-<name> 2>/dev/null || true
             iptables -X f2b-<name> 2>/dev/null || true
actioncheck = iptables -C INPUT -p <protocol> -m multiport --dports <port> -j f2b-<name> 2>/dev/null
actionban = iptables -I f2b-<name> 1 -s <ip> -j DROP
actionunban = iptables -D f2b-<name> -s <ip> -j DROP
protocol = tcp
port = ssh
name = default
returntype = RETURN

[Init]
EOF
    fi

    if [ ! -f "${CONFIG_PATH}/action.d/firewallcmd-multiport.conf" ]; then
        cat <<EOF > ${CONFIG_PATH}/action.d/firewallcmd-multiport.conf
# firewallcmd-multiport action configuration

[Definition]
actionstart = firewall-cmd --permanent --new-chain=f2b-<name>
              firewall-cmd --permanent --chain=f2b-<name> -j RETURN
              firewall-cmd --permanent --add-input=<name> -j f2b-<name>
              firewall-cmd --permanent --add-forward=<name> -j DROP
              firewall-cmd --reload
actionstop = firewall-cmd --permanent --delete-chain=f2b-<name>
             firewall-cmd --permanent --remove-input=<name>
             firewall-cmd --permanent --remove-forward=<name>
             firewall-cmd --reload
actioncheck = firewall-cmd --permanent --query-chain=f2b-<name>
actionban = firewall-cmd --permanent --add-source=<ip> --zone=trusted
            firewall-cmd --reload
actionunban = firewall-cmd --permanent --remove-source=<ip> --zone=trusted
             firewall-cmd --reload
protocol = tcp
port = ssh
name = default
zone = trusted

[Init]
EOF
    fi
}

Install_Soft() {
    echo "==================================================="
    echo "Fail2Ban 安装开始"
    echo "==================================================="
    
    cd ${RUYI_TEMP_PATH}
    rm -rf ${SOFT_INSTALL_PATH}
    mkdir -p ${SOFT_INSTALL_PATH}/bin
    
    Install_Package
    
    local fail2ban_path=$(which fail2ban-server 2>/dev/null)
    if [ -n "$fail2ban_path" ]; then
        echo "创建软链接..."
        ln -sf $fail2ban_path ${SOFT_INSTALL_PATH}/bin/fail2ban-server
        ln -sf $(which fail2ban-client) ${SOFT_INSTALL_PATH}/bin/fail2ban-client
        ln -sf $(which fail2ban-regex) ${SOFT_INSTALL_PATH}/bin/fail2ban-regex
    fi
    
    Write_Jail_Config
    
    echo "==================================================="
    echo "配置 systemd 服务..."
    Service_Add
    
    echo "==================================================="
    echo "启动服务..."
    if systemctl is-active --quiet fail2ban 2>/dev/null; then
        echo "停止现有服务..."
        systemctl stop fail2ban
    fi
    
    systemctl daemon-reload
    systemctl start fail2ban
    sleep 2
    
    if systemctl is-active --quiet fail2ban; then
        echo "服务启动成功"
        systemctl status fail2ban --no-pager | head -10
    else
        echo "服务启动失败，显示日志..."
        journalctl -u fail2ban -n 10 --no-pager
    fi
    
    echo "==================================================="
    echo "验证安装..."
    if command -v fail2ban-server &> /dev/null; then
        fail2ban-server --version 2>&1 | head -3
    fi
    
    echo "==================================================="
    echo "Fail2Ban 安装完成"
    echo "==================================================="
}

Uninstall_Soft() {
    echo "==================================================="
    echo "Fail2Ban 卸载开始"
    echo "==================================================="
    
    echo "停止服务..."
    Service_Del
    
    echo "卸载软件包..."
    Uninstall_Package
    
    echo "清理配置文件..."
    rm -rf ${SOFT_INSTALL_PATH}
    rm -rf ${DATA_CONFIG_PATH}
    rm -rf /ruyi/logs/fail2ban
    rm -rf /run/fail2ban
    rm -rf /var/log/fail2ban
    rm -rf /var/lib/fail2ban
    rm -f /etc/default/fail2ban
    rm -f /etc/logrotate.d/fail2ban
    rm -rf /etc/monit/monitrc.d/fail2ban
    rm -rf /etc/fail2ban
    rm -f /etc/init.d/fail2ban
    
    echo "==================================================="
    echo "Fail2Ban 卸载完成"
    echo "==================================================="
}

# 释放Linux文件系统缓存（page cache）
trap 'sync && echo 3 > /proc/sys/vm/drop_caches 2>/dev/null' EXIT

if [ "$action_type" == 'install' ]; then
    if [ -z "${soft_version}" ]; then
        echo "参数错误" >&2
        exit 1
    fi
    Install_Soft
elif [ "$action_type" == 'uninstall' ]; then
    Uninstall_Soft
else
    echo "用法: $0 {install|uninstall} [version]" >&2
    exit 1
fi
