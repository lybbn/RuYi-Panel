#!/bin/bash
#mysql安装
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
export PATH
LANG=en_US.UTF-8

RUYI_TEMP_PATH="/ruyi/tmp"
OPENSSL_PATH="/usr/local/ruyi/openssl"
MYSQL_SETUP_PATH="/ruyi/server/mysql"
MYSQL_DATA_PATH="/ruyi/server/data"

action_type=$1
mysql_version=$2
#大版本
mysql_version_2=""

cpu_core=$(cat /proc/cpuinfo|grep processor|wc -l)
IsCentos7=$(cat /etc/redhat-release | grep ' 7.' | grep -iE 'centos')
IsCentos8=$(cat /etc/redhat-release | grep ' 8.' | grep -iE 'centos|Red Hat')
IsCentosStream8=$(cat /etc/redhat-release |grep -i "Centos Stream"|grep 8)

# 检查是否以 root 用户运行
if [ "$(id -u)" -ne 0 ]; then
    echo "请以 root 用户运行此脚本"
    exit 1
fi

#检测hosts文件
hostfileck=`cat /etc/hosts | grep 127.0.0.1 | grep localhost`
if [ "${hostfileck}" = '' ]; then
    echo "127.0.0.1  localhost  localhost.localdomain" >> /etc/hosts
fi

Service_Add() {
	cat <<EOF > /etc/systemd/system/mysql.service
[Unit]
Description=Mysql RuYi Server
After=network.target

[Service]
ExecStart=/ruyi/server/mysql/bin/mysqld --defaults-file=/etc/my.cnf
User=mysql
Group=mysql
Restart=no

[Install]
WantedBy=multi-user.target
EOF

    # 重新加载 systemd 配置
    systemctl daemon-reload
    systemctl enable mysql
}

Service_Del() {
    if [ -f "/etc/systemd/system/mysql.service" ];then
        systemctl stop mysql > /dev/null
        systemctl disable mysql > /dev/null
        rm -f /etc/systemd/system/mysql.service > /dev/null
        rm -rf /etc/systemd/system/multi-user.target.wants/mysql.service > /dev/null
        systemctl daemon-reload
    fi
}

Install_Soft() {
    [ -f "/etc/init.d/mysqld" ] && /etc/init.d/mysqld stop
    if [ -f "/etc/systemd/system/mysql.service" ];then
        systemctl stop mysql > /dev/null
    fi
    if ! getent group mysql > /dev/null; then
        groupadd mysql
    fi
    if ! id -u mysql > /dev/null 2>&1; then
        useradd -s /sbin/nologin -M -g mysql mysql
    fi
    if [ -z "${IsCentos7}" ] && [ -f "/usr/bin/yum" ];then
        yum install libtirpc libtirpc-devel -y
    fi
    rm -rf /ruyi/server/mysql
    mkdir /ruyi/server/mysql
    cd ${RUYI_TEMP_PATH}
    tar -zxf mysql-boost-$mysql_version.tar.gz
    cd mysql-$mysql_version
    if [[ $mysql_version_2 == "5.7" ]]; then
        cmake -DCMAKE_INSTALL_PREFIX=${MYSQL_SETUP_PATH} -DWITHOUT_TESTS=ON -DCMAKE_BUILD_TYPE=Release -DMYSQL_UNIX_ADDR=/tmp/mysql.sock -DMYSQL_DATADIR=${MYSQL_DATA_PATH} -DMYSQL_USER=mysql -DSYSCONFDIR=/etc -DWITH_MYISAM_STORAGE_ENGINE=1 -DWITH_INNOBASE_STORAGE_ENGINE=1 -DWITH_PARTITION_STORAGE_ENGINE=1 -DWITH_FEDERATED_STORAGE_ENGINE=1 -DEXTRA_CHARSETS=all -DDEFAULT_CHARSET=utf8mb4 -DDEFAULT_COLLATION=utf8mb4_general_ci -DWITH_EMBEDDED_SERVER=1 -DENABLED_LOCAL_INFILE=1 -DWITH_BOOST=./boost -DWITH_SSL=${OPENSSL_PATH}
    elif [[ $mysql_version_2 == "8.0" ]]; then
        mkdir rybuild
        cd rybuild
        cmakeCV="cmake"
        if [ -f "/usr/bin/yum" ]; then
            if [ "${IsCentos7}" ];then
                yum install centos-release-scl-rh openldap-devel patchelf -y
                local MIRROR_CHECK=$(cat /etc/yum.repos.d/CentOS-SCLo-scl-rh.repo|grep "[^#]mirror.centos.org")
                if [ "${MIRROR_CHECK}" ];then
                    sed -i 's/mirrorlist/#mirrorlist/g' /etc/yum.repos.d/CentOS-SCLo-scl-rh.repo
                    sed -i 's|#baseurl=http://mirror.centos.org|baseurl=http://vault.centos.org|g' /etc/yum.repos.d/CentOS-SCLo-scl-rh.repo
                fi
                yum install devtoolset-8-gcc devtoolset-8-gcc-c++ -y
                yum install cmake3 -y
                cmakeCV="cmake3"
                export CC=/opt/rh/devtoolset-8/root/usr/bin/gcc
                export CXX=/opt/rh/devtoolset-8/root/usr/bin/g++
            else
                export CC=/usr/bin/gcc
                export CXX=/usr/bin/g++
            fi
        fi
        ${cmakeCV} .. -DCMAKE_INSTALL_PREFIX=${MYSQL_SETUP_PATH} -DWITHOUT_TESTS=ON -DENABLE_DEBUG_SYNC=0 -DCMAKE_BUILD_TYPE=Release -DMYSQL_UNIX_ADDR=/tmp/mysql.sock -DMYSQL_DATADIR=${MYSQL_DATA_PATH} -DMYSQL_USER=mysql -DSYSCONFDIR=/etc -DWITH_MYISAM_STORAGE_ENGINE=1 -DWITH_INNOBASE_STORAGE_ENGINE=1 -DWITH_PARTITION_STORAGE_ENGINE=1 -DDEFAULT_CHARSET=utf8mb4 -DDEFAULT_COLLATION=utf8mb4_general_ci -DENABLED_LOCAL_INFILE=1 -DWITH_BOOST=../boost -DWITH_SSL=${OPENSSL_PATH} -DWITH_TOKUDB=OFF -DWITH_ZLIB=bundled -DWITH_ROCKSDB=OFF -DWITH_COREDUMPER=OFF -DWITH_DEBUG=OFF
    else
        cmake -DCMAKE_INSTALL_PREFIX=${MYSQL_SETUP_PATH} -DMYSQL_UNIX_ADDR=/tmp/mysql.sock -DMYSQL_DATADIR=${MYSQL_DATA_PATH} -DMYSQL_USER=mysql -DWITH_ARIA_STORAGE_ENGINE=1 -DWITH_XTRADB_STORAGE_ENGINE=1 -DWITH_INNOBASE_STORAGE_ENGINE=1 -DWITH_PARTITION_STORAGE_ENGINE=1 -DWITH_MYISAM_STORAGE_ENGINE=1 -DWITH_FEDERATED_STORAGE_ENGINE=1 -DEXTRA_CHARSETS=all -DDEFAULT_CHARSET=utf8mb4 -DDEFAULT_COLLATION=utf8mb4_general_ci -DWITH_READLINE=1 -DWITH_EMBEDDED_SERVER=1 -DENABLED_LOCAL_INFILE=1 -DWITHOUT_TOKUDB=1
    fi
    make -j${cpu_core}
    make install
    echo "正在配置mysql..."
    cd ${RUYI_TEMP_PATH}/
    if [ -d "/ruyi/server/data" ]; then
        rm -rf /ruyi/server/data/*
    else
        mkdir -p /ruyi/server/data
    fi
    chown -R mysql:mysql /ruyi/server/data
    chgrp -R mysql /ruyi/server/mysql/.
    rm -rf mysql-$mysql_version
    Service_Add
}

Uninstall_soft() {
    Service_Del
    rm -rf /ruyi/server/mysql
    rm -rf /etc/systemd/system/mysql.service > /dev/null
    rm -rf /etc/systemd/system/multi-user.target.wants/mysql.service > /dev/null
    rm -rf /etc/my.cnf
    rm -rf /etc/my.cnf.d > /dev/null
    rm -rf /ruyi/server/data
}

if [ "$action_type" == 'install' ];then
    if [ -z "${mysql_version}" ]; then
        exit
    fi
    if [[ $mysql_version == 5.7* ]]; then
        mysql_version_2="5.7"
    elif [[ $mysql_version == 8.0* ]]; then
        mysql_version_2="8.0"
    else
        exit
    fi
	Install_Soft
elif [ "$action_type" == 'uninstall' ];then
	Uninstall_soft
fi
