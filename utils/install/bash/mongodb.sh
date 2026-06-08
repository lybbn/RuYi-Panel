#!/bin/bash
#MongoDB安装
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
export PATH
LANG=en_US.UTF-8

RUYI_TEMP_PATH="/ruyi/tmp"
MONGODB_INSTALL_PATH="/ruyi/server/mongodb"
MONGODB_DATA_PATH="/ruyi/server/mongodb/data"
MONGODB_LOG_PATH="/ruyi/server/mongodb/logs"
MONGODB_CONF_PATH="/ruyi/server/mongodb/mongod.conf"

action_type=$1
mongodb_version=$2

if [ "$(id -u)" -ne 0 ]; then
    echo "请以 root 用户运行此脚本" >&2
    exit 1
fi

Return_Error() {
    echo '================================================='
    echo "$@" >&2
    exit 1
}

Service_Add() {
    cat <<EOF > /etc/systemd/system/mongod.service
[Unit]
Description=MongoDB RuYi Server
After=network.target

[Service]
Type=forking
User=mongod
Group=mongod
ExecStart=${MONGODB_INSTALL_PATH}/bin/mongod --config ${MONGODB_CONF_PATH} --fork
ExecStop=${MONGODB_INSTALL_PATH}/bin/mongod --config ${MONGODB_CONF_PATH} --shutdown
PIDFile=${MONGODB_DATA_PATH}/mongod.pid
Restart=no

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable mongod
}

Service_Del() {
    systemctl stop mongod
    systemctl disable mongod
    rm -f /etc/systemd/system/mongod.service
    rm -rf /etc/systemd/system/multi-user.target.wants/mongod.service
    systemctl daemon-reload
}

Install_Deps() {
    echo "正在安装运行依赖..."
    if [ -f "/usr/bin/yum" ]; then
        yum install -y libcurl openssl-libs
    elif [ -f "/usr/bin/apt-get" ]; then
        apt-get install -y libcurl4 libssl3
    elif [ -f "/usr/bin/dnf" ]; then
        dnf install -y libcurl openssl-libs
    else
        echo "无法确定包管理器，请手动安装 libcurl openssl-libs" >&2
    fi
    echo "运行依赖安装完成"
}

Install_Soft() {
    if ! getent group mongod > /dev/null; then
        groupadd mongod
    fi
    if ! id -u mongod > /dev/null 2>&1; then
        useradd -g mongod -s /bin/bash -M mongod
    fi
    Install_Deps
    rm -rf ${MONGODB_INSTALL_PATH}
    cd ${RUYI_TEMP_PATH}
    tarfile=$(ls mongodb-linux-*.tgz 2>/dev/null | head -1)
    if [ -z "${tarfile}" ]; then
        echo "未找到MongoDB安装包"
        exit 1
    fi
    tar -zxf ${tarfile}
    extracted_dir=$(ls -d mongodb-linux-* 2>/dev/null | head -1)
    if [ -z "${extracted_dir}" ]; then
        echo "解压MongoDB失败"
        exit 1
    fi
    mv ${extracted_dir} ${MONGODB_INSTALL_PATH}
    mkdir -p ${MONGODB_DATA_PATH}
    mkdir -p ${MONGODB_LOG_PATH}
    touch ${MONGODB_LOG_PATH}/mongodb.log
    cat <<EOF > ${MONGODB_CONF_PATH}
storage:
  dbPath: ${MONGODB_DATA_PATH}
systemLog:
  destination: file
  path: ${MONGODB_LOG_PATH}/mongodb.log
  logAppend: true
net:
  port: 27017
  bindIp: 0.0.0.0
security:
  authorization: disabled
EOF
    chown -R mongod:mongod ${MONGODB_INSTALL_PATH}
    Service_Add
    echo "正在启动MongoDB..."
    systemctl start mongod
    sleep 2
    if systemctl is-active --quiet mongod; then
        echo "MongoDB安装完成"
    else
        Return_Error "MongoDB启动失败，请检查日志: ${MONGODB_LOG_PATH}/mongodb.log"
    fi
}

Uninstall_soft() {
    Service_Del
    userdel -r mongod 2>/dev/null
    groupdel mongod 2>/dev/null
    rm -rf ${MONGODB_INSTALL_PATH}
    rm -f /etc/systemd/system/mongod.service
}

trap 'sync && echo 3 > /proc/sys/vm/drop_caches 2>/dev/null' EXIT

if [ "$action_type" == 'install' ];then
    if [ -z "${mongodb_version}" ]; then
        exit
    fi
    Install_Soft
elif [ "$action_type" == 'uninstall' ];then
    Uninstall_soft
fi
