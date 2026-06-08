#!/bin/bash
#PostgreSQL安装
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
export PATH
LANG=en_US.UTF-8

RUYI_TEMP_PATH="/ruyi/tmp"
PGSQL_INSTALL_PATH="/ruyi/server/pgsql"
PGSQL_DATA_PATH="/ruyi/server/pgsql/data"
PGSQL_LOG_PATH="/ruyi/server/pgsql/logs"

action_type=$1
pgsql_version=$2
cpu_core=$(cat /proc/cpuinfo|grep processor|wc -l)

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
	cat <<EOF > /etc/systemd/system/postgresql.service
[Unit]
Description=PostgreSQL RuYi Server
After=network.target

[Service]
Type=forking
User=postgres
Group=postgres
ExecStart=${PGSQL_INSTALL_PATH}/bin/pg_ctl start -D ${PGSQL_DATA_PATH} -l ${PGSQL_LOG_PATH}/postgresql.log
ExecReload=${PGSQL_INSTALL_PATH}/bin/pg_ctl reload -D ${PGSQL_DATA_PATH}
ExecStop=${PGSQL_INSTALL_PATH}/bin/pg_ctl stop -D ${PGSQL_DATA_PATH} -m fast
PIDFile=${PGSQL_DATA_PATH}/postmaster.pid
Restart=no

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable postgresql
}

Service_Del() {
    systemctl stop postgresql
    systemctl disable postgresql
    rm -f /etc/systemd/system/postgresql.service
    rm -rf /etc/systemd/system/multi-user.target.wants/postgresql.service
    systemctl daemon-reload
}

Install_Deps() {
    echo "正在安装编译依赖..."
    if [ -f "/usr/bin/yum" ]; then
        yum install -y gcc make flex bison openssl-devel zlib-devel readline-devel
    elif [ -f "/usr/bin/apt-get" ]; then
        apt-get install -y gcc make flex bison libssl-dev zlib1g-dev libreadline-dev
    elif [ -f "/usr/bin/dnf" ]; then
        dnf install -y gcc make flex bison openssl-devel zlib-devel readline-devel
    else
        echo "无法确定包管理器，请手动安装 gcc make flex bison openssl-devel zlib-devel" >&2
    fi
    echo "编译依赖安装完成"
}

Install_Pgvector() {
    echo "正在安装pgvector扩展..."
    cd ${RUYI_TEMP_PATH}
    PGVECTOR_URL="http://download.lybbn.cn/ruyi/install/linux/pgsql/pgvector-0.8.2.tar.gz"
    wget -q -O pgvector-0.8.2.tar.gz ${PGVECTOR_URL}
    if [ "$?" != "0" ];then
        echo "pgvector下载失败，跳过pgvector安装"
        return 1
    fi
    tar -zxf pgvector-0.8.2.tar.gz
    cd pgvector-0.8.2
    make -j${cpu_core} PG_CONFIG=${PGSQL_INSTALL_PATH}/bin/pg_config
    if [ "$?" != "0" ];then
        echo "pgvector编译失败，跳过pgvector安装"
        rm -rf ${RUYI_TEMP_PATH}/pgvector-0.8.2 ${RUYI_TEMP_PATH}/pgvector-0.8.2.tar.gz
        return 1
    fi
    make install PG_CONFIG=${PGSQL_INSTALL_PATH}/bin/pg_config
    if [ "$?" != "0" ];then
        echo "pgvector安装失败，跳过pgvector安装"
        rm -rf ${RUYI_TEMP_PATH}/pgvector-0.8.2 ${RUYI_TEMP_PATH}/pgvector-0.8.2.tar.gz
        return 1
    fi
    rm -rf ${RUYI_TEMP_PATH}/pgvector-0.8.2 ${RUYI_TEMP_PATH}/pgvector-0.8.2.tar.gz
    echo "pgvector安装完成"
    return 0
}

Install_Soft() {
    if ! getent group postgres > /dev/null; then
        groupadd postgres
    fi
    if ! id -u postgres > /dev/null 2>&1; then
        useradd -g postgres -s /bin/bash -d ${PGSQL_INSTALL_PATH} postgres
    fi
    Install_Deps
    rm -rf ${PGSQL_INSTALL_PATH}
    cd ${RUYI_TEMP_PATH}
    tar -zxf postgresql-${pgsql_version}.tar.gz
    cd postgresql-${pgsql_version}
    echo "正在编译PostgreSQL..."
    ./configure --prefix=${PGSQL_INSTALL_PATH} --with-openssl --without-readline
    if [ "$?" != "0" ];then
        Return_Error "PostgreSQL configure配置失败，请检查依赖是否安装完整"
    fi
    make -j${cpu_core}
    if [ "$?" != "0" ];then
        Return_Error "PostgreSQL编译失败"
    fi
    make install
    if [ "$?" != "0" ];then
        Return_Error "PostgreSQL安装失败"
    fi
    echo "编译安装完成"
    cd contrib
    make -j${cpu_core}
    make install
    Install_Pgvector
    PGVECTOR_INSTALLED=$?
    echo "正在初始化数据库..."
    mkdir -p ${PGSQL_DATA_PATH}
    mkdir -p ${PGSQL_LOG_PATH}
    chown -R postgres:postgres ${PGSQL_INSTALL_PATH}
    su - postgres -c "${PGSQL_INSTALL_PATH}/bin/initdb -D ${PGSQL_DATA_PATH} -E UTF8 --locale=C"
    if [ "$?" != "0" ];then
        Return_Error "PostgreSQL数据库初始化失败"
    fi
    echo "正在配置PostgreSQL..."
    sed -i "s/#listen_addresses = 'localhost'/listen_addresses = '*'/" ${PGSQL_DATA_PATH}/postgresql.conf
    sed -i "s/#port = 5432/port = 5432/" ${PGSQL_DATA_PATH}/postgresql.conf
    sed -i "s/#max_connections = 100/max_connections = 100/" ${PGSQL_DATA_PATH}/postgresql.conf
    sed -i "s/#shared_buffers = 128MB/shared_buffers = 128MB/" ${PGSQL_DATA_PATH}/postgresql.conf
    sed -i "s/#dynamic_shared_memory_type = posix/dynamic_shared_memory_type = posix/" ${PGSQL_DATA_PATH}/postgresql.conf
    sed -i "s/#logging_collector = off/logging_collector = on/" ${PGSQL_DATA_PATH}/postgresql.conf
    sed -i "s|#log_directory = 'log'|log_directory = '${PGSQL_LOG_PATH}'|" ${PGSQL_DATA_PATH}/postgresql.conf
    sed -i "s/#log_filename = 'postgresql-%Y-%m-%d_%H%M%S.log'/log_filename = 'postgresql.log'/" ${PGSQL_DATA_PATH}/postgresql.conf
    echo "host all all 0.0.0.0/0 md5" >> ${PGSQL_DATA_PATH}/pg_hba.conf
    chown -R postgres:postgres ${PGSQL_INSTALL_PATH}
    Service_Add
    echo "正在启动PostgreSQL..."
    systemctl start postgresql
    sleep 2
    if [ "${PGVECTOR_INSTALLED}" = "0" ]; then
        echo "正在启用pgvector扩展..."
        su - postgres -c "${PGSQL_INSTALL_PATH}/bin/psql -p 5432 -c 'CREATE EXTENSION IF NOT EXISTS vector;'" 2>/dev/null
        if [ "$?" = "0" ]; then
            echo "pgvector扩展启用成功"
        else
            echo "pgvector扩展启用失败，可稍后手动执行 CREATE EXTENSION vector 启用"
        fi
    fi
    echo "PostgreSQL安装完成"
}

Uninstall_soft() {
    Service_Del
    userdel -r postgres 2>/dev/null
    groupdel postgres 2>/dev/null
    rm -rf ${PGSQL_INSTALL_PATH}
    rm -f /etc/systemd/system/postgresql.service
}

trap 'sync && echo 3 > /proc/sys/vm/drop_caches 2>/dev/null' EXIT

if [ "$action_type" == 'install' ];then
    if [ -z "${pgsql_version}" ]; then
        exit
    fi
	Install_Soft
elif [ "$action_type" == 'uninstall' ];then
	Uninstall_soft
fi
