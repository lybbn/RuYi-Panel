#!/bin/bash
#go环境安装
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
export PATH
LANG=en_US.UTF-8

RUYI_TEMP_PATH="/ruyi/tmp"
RUYI_DATA_PATH="/ruyi/data/docker"

action_type=$1
soft_version=$2
sys_type_arch=$(uname -m)

cpu_core=$(cat /proc/cpuinfo|grep processor|wc -l)

# 检查是否以 root 用户运行
if [ "$(id -u)" -ne 0 ]; then
    echo "请以 root 用户运行此脚本"
    exit 1
fi

Service_Add() {
	cat <<EOF > /etc/systemd/system/docker.service
[Unit]
Description=docker RuYi Server
After=network-online.target docker.socket containerd.service time-set.target
Wants=network-online.target containerd.service
Requires=docker.socket

[Service]
Type=notify
ExecStart=/usr/bin/dockerd -H unix://var/run/docker.sock --containerd=/var/run/containerd/containerd.sock --data-root=${RUYI_DATA_PATH} --config-file=/etc/docker/daemon.json
ExecReload=/bin/kill -s HUP \$MAINPID
TimeoutStartSec=0
RestartSec=2
Restart=always

StartLimitBurst=3

StartLimitInterval=60s

LimitNOFILE=infinity
LimitNPROC=infinity
LimitCORE=infinity

TasksMax=infinity

Delegate=yes

KillMode=process
OOMScoreAdjust=-500

[Install]
WantedBy=multi-user.target
EOF

cat <<EOF > /etc/systemd/system/docker.socket
[Unit]
Description=Docker Socket for the API RuYi Server

[Socket]
ListenStream=/var/run/docker.sock
SocketMode=0660
SocketUser=root
SocketGroup=docker

[Install]
WantedBy=sockets.target
EOF

cat <<EOF > /etc/systemd/system/containerd.service
[Unit]
Description=docker-containerd RuYi Server

[Service]
ExecStartPre=-/sbin/modprobe overlay
ExecStart=/usr/bin/containerd

Type=notify
Delegate=yes
KillMode=process
Restart=always
RestartSec=5
LimitNPROC=infinity
LimitCORE=infinity
LimitNOFILE=infinity
TasksMax=infinity
OOMScoreAdjust=-999

[Install]
WantedBy=multi-user.target
EOF

    if [ ! -f "/etc/docker/daemon.json" ]; then
        mkdir -p /etc/docker
        touch /etc/docker/daemon.json
        cat > /etc/docker/daemon.json <<EOF
{
"registry-mirrors": [
    "https://docker.1ms.run",
    "https://docker.aityp.com"
]
}
EOF
    fi

    systemctl daemon-reload
    systemctl enable docker.service
    systemctl enable docker.socket
    systemctl enable containerd.service
    rm -rf /ruyi/server/docker
}

# 测试镜像源可用性
Select_Mirror() {
    echo "==================================================="
    echo "选择docker-ce镜像源地址..."
    echo "==================================================="
    declare -a MIRROR_LIST=(
        "https://mirrors.aliyun.com/docker-ce"
        "https://mirrors.tencent.com/docker-ce"
        "https://mirrors.huaweicloud.com/docker-ce"
        "https://download.docker.com"
    )
    for mirror in "${MIRROR_LIST[@]}"; do
        if curl -s --connect-timeout 5 "$mirror" >/dev/null; then
            SELECTED_MIRROR=$mirror
            echo "选择镜像源: $SELECTED_MIRROR"
            return 0
        fi
    done
    echo "安装错误：所有镜像源均不可用！" >&2
    exit 1
}

Select_Compose_Mirror() {
    echo "==================================================="
    echo "选择docker-compose加速地址..."
    echo "==================================================="
    declare -a MIRROR_COMPOSE_LIST=(
        "https://ghfast.top"
        "https://github.moeyy.xyz"
        "https://ghproxy.cfd"
    )
    for mirrorm in "${MIRROR_COMPOSE_LIST[@]}"; do
        if curl -s --connect-timeout 5 "$mirrorm" >/dev/null; then
            SELECTED_COMPOSE_MIRROR=$mirrorm
            echo "选择docker-compose加速地址: $SELECTED_COMPOSE_MIRROR"
            return 0
        fi
    done
    echo "安装错误：所有加速地址均不可用！" >&2
    exit 1
}

Install_Soft() {
    Select_Mirror

    if ! getent group docker > /dev/null; then
        groupadd docker
    fi

    cd ${RUYI_TEMP_PATH}
    Soft_file_name=docker-${soft_version}.tgz
    Soft_download_url=${SELECTED_MIRROR}/linux/static/stable/${sys_type_arch}/${Soft_file_name}
    # 清理旧版本
    rm -rf ${RUYI_TEMP_PATH}/docker-*.tgz
    curl -L "${Soft_download_url}" -o ${RUYI_TEMP_PATH}/${Soft_file_name}
    if [ $? -eq 0 ] ; then
        echo "下载 Docker-CE 成功！路径：${RUYI_TEMP_PATH}/${Soft_file_name}"
    else
        echo "错误：下载 Docker-CE 失败！" >&2
        exit 1
    fi
    
    tar -xzf ${Soft_file_name}
    cp docker/* /usr/bin/

    echo "下载 docker-compose ..."
    
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose

    if [ $? -eq 0 ]; then
        echo "下载 docker-compose 成功！路径：/usr/local/bin/docker-compose"
    else
        Select_Compose_Mirror
        curl -L "${SELECTED_COMPOSE_MIRROR}/https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        if [ $? -eq 0 ]; then
            echo "下载 docker-compose 成功！路径：/usr/local/bin/docker-compose"
        else
            echo "错误：下载 docker-compose 失败！" >&2
            exit 1
        fi
    fi
    chmod +x /usr/local/bin/docker-compose

    rm -rf ${RUYI_TEMP_PATH}/docker*

    if [ -d "${RUYI_DATA_PATH}" ]; then
        echo "data目录${RUYI_DATA_PATH}已存在"
    else
        mkdir -p ${RUYI_DATA_PATH}
        echo "创建data目录${RUYI_DATA_PATH}"
    fi

    Service_Add

    Start_soft

    /usr/bin/docker network create ruyi-network > /dev/null 2>&1
    
    echo "==================================================="
    echo "docker-ce $soft_version 安装完成"
    echo "==================================================="
}

Start_soft() {
    systemctl start containerd.service
    systemctl start docker.socket
    systemctl start docker.service
}

Stop_soft() {
    systemctl stop docker.service
    systemctl stop docker.socket
    systemctl stop containerd.service
}

Restart_soft() {
    systemctl restart docker.service
    systemctl restart docker.socket
    systemctl restart containerd.service
}

Uninstall_soft() {
    systemctl stop docker.service
    systemctl disable docker.service
    systemctl disable docker.socket
    systemctl disable containerd.service
    systemctl daemon-reload
}

if [ "$action_type" == 'install' ];then
    if [ -z "${soft_version}" ]; then
        exit 1
    fi
	Install_Soft
elif [ "$action_type" == 'uninstall' ];then
    if [ -z "${soft_version}" ];then
        exit 1
    fi
	Uninstall_soft
elif [ "$action_type" == 'start' ];then
    Start_soft
elif [ "$action_type" == 'stop' ];then
    Stop_soft
elif [ "$action_type" == 'restart' ];then
    Restart_soft
fi