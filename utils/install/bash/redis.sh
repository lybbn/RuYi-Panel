#!/bin/bash
#redis安装
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
export PATH
LANG=en_US.UTF-8

RUYI_TEMP_PATH="/ruyi/tmp"

action_type=$1
redis_version=$2
cpu_core=$(cat /proc/cpuinfo|grep processor|wc -l)

# 检查是否以 root 用户运行
if [ "$(id -u)" -ne 0 ]; then
    echo "请以 root 用户运行此脚本"
    exit 1
fi

Service_Add() {
	cat <<EOF > /etc/systemd/system/redis.service
[Unit]
Description=Redis RuYi Server
After=network.target

[Service]
ExecStart=/usr/bin/redis-server /ruyi/server/redis/redis.conf
User=redis
Group=redis
Restart=no

[Install]
WantedBy=multi-user.target
EOF

    # 重新加载 systemd 配置
    systemctl daemon-reload
    systemctl enable redis
}

Service_Del() {
	# 停止 Redis 服务
    systemctl stop redis

    # 禁用 Redis 服务
    systemctl disable redis

    # 删除 Redis 服务文件
    rm -f /etc/systemd/system/redis.service
    rm -rf /etc/systemd/system/multi-user.target.wants/redis.service

    # 重新加载 systemd 配置
    systemctl daemon-reload
}

Install_Soft() {
    if ! getent group redis > /dev/null; then
        groupadd redis
    fi
    if ! id -u redis > /dev/null 2>&1; then
        useradd -g redis -s /sbin/nologin redis
    fi
    rm -rf /ruyi/server/redis
    cd ${RUYI_TEMP_PATH}
    tar -zxf redis-$redis_version.tar.gz
    mv redis-$redis_version /ruyi/server/redis
    cd /ruyi/server/redis
    make -j${cpu_core}
    make install
    echo "正在配置redis..."
    ln -sf /ruyi/server/redis/src/redis-cli /usr/bin/redis-cli
    ln -sf /ruyi/server/redis/src/redis-server /usr/bin/redis-server
    cp /ruyi/server/redis/src/redis-cli /ruyi/server/redis/redis-cli
    cp /ruyi/server/redis/src/redis-server /ruyi/server/redis/redis-server
    cd ..
    chown -R redis.redis /ruyi/server/redis
    VM_OVERCOMMIT_MEMORY=$(cat /etc/sysctl.conf|grep vm.overcommit_memory)
    NET_CORE_SOMAXCONN=$(cat /etc/sysctl.conf|grep net.core.somaxconn)
    if [ -z "${VM_OVERCOMMIT_MEMORY}" ] && [ -z "${NET_CORE_SOMAXCONN}" ];then
        echo "vm.overcommit_memory = 1" >> /etc/sysctl.conf
        echo "net.core.somaxconn = 1024" >> /etc/sysctl.conf
        sysctl -p
    fi
    Service_Add
}

Uninstall_soft() {
    Service_Del
    rm -rf /usr/bin/redis-cli
    rm -rf /usr/bin/redis-server
    rm -rf /ruyi/server/redis
    rm -rf /etc/systemd/system/redis.service
}

if [ "$action_type" == 'install' ];then
    if [ -z "${redis_version}" ]; then
        exit
    fi
	Install_Soft
elif [ "$action_type" == 'uninstall' ];then
	Uninstall_soft
fi
