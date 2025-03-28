#!/bin/bash
#mysql安装
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
export PATH
LANG=en_US.UTF-8

py_path="/usr/local/ruyi"
RUYI_TEMP_PATH="/ruyi/tmp"
CUSTOM_OPENSSL_PATH="/usr/local/ruyi/openssl"
OPENSSL_PATH="/usr/local/ruyi/openssl"
MYSQL_SETUP_PATH="/ruyi/server/mysql"
MYSQL_DATA_PATH="/ruyi/server/data"
DWITH_SSL=""

action_type=$1
mysql_version=$2
install_type=$3
#大版本
mysql_version_2=""

cpu_core=$(cat /proc/cpuinfo|grep processor|wc -l)
IsCentos7=$(cat /etc/redhat-release | grep ' 7.' | grep -iE 'centos')
IsCentos8=$(cat /etc/redhat-release | grep ' 8.' | grep -iE 'centos|Red Hat')
IsCentosStream8=$(cat /etc/redhat-release |grep -i "Centos Stream"|grep 8)
IsCentos9=$(cat /etc/redhat-release | grep ' 9.' | grep -iE 'centos|Red Hat')
IsCentosStream9=$(cat /etc/redhat-release |grep -i "Centos Stream"|grep 9)
IsAliYunOS=$(cat /etc/redhat-release |grep "Alibaba Cloud Linux release")
ARCH=$(uname -m)

if [ -z "${cpu_core}" ]; then
    cpu_core="1"
fi

MEM_G=$(free -m|grep Mem|awk '{printf("%.f",($2)/1024)}')
if [ "${cpu_core}" != "1" ] && [ "${MEM_G}" != "0" ];then
    if [ "${cpu_core}" -gt "${MEM_G}" ];then
        cpu_core="${MEM_G}"
    fi
else
    cpu_core="1"
fi

Return_Error() {
	echo '================================================='
	echo "$@" >&2
	exit 1
}

# 检查是否以 root 用户运行
if [ "$(id -u)" -ne 0 ]; then
    echo "请以 root 用户运行此脚本" >&2
    exit 1
fi

Install_Openssl() {
    echo "=============================================="
    echo "正在安装OpenSSL..."
    echo "=============================================="
    if [ -f ${py_path}/openssl/bin/openssl ];then
        echo "检测到OpenSSL版本符合要求，无需再安装"
        echo "=============================================="
	 	return
	fi
	opensslVersion="1.1.1w"
    mkdir -p ${py_path}/openssl
	cd ${py_path}
    # wget https://github.com/openssl/openssl/releases/download/OpenSSL_1_1_1w/openssl-${opensslVersion}.tar.gz
    wget https://download.lybbn.cn/ruyi/install/common/openssl-${opensslVersion}.tar.gz
	tar -zxf openssl-${opensslVersion}.tar.gz
    rm -f openssl-${opensslVersion}.tar.gz
	cd openssl-${opensslVersion}
    if [ "${IsAliYunOS}" ];then
        ./config --prefix=${py_path}/openssl --openssldir=${py_path}/openssl zlib-dynamic -Wl,-rpath,${py_path}/openssl/lib
        make -j${cpu_core}
        make install
    else
        ./config --prefix=${py_path}/openssl zlib-dynamic
        make -j${cpu_core}
        make install
        echo "$py_path/openssl/lib" >>/etc/ld.so.conf.d/ryopenssl111.conf

        # ln -s $py_path/openssl/lib64/libcrypto.so.3 /usr/lib64/libcrypto.so.3
        # ln -s $py_path/openssl/lib64/libssl.so.3 /usr/lib64/libssl.so.3
        # ln -s $py_path/openssl/bin/openssl /usr/bin/openssl

        ldconfig
        ldconfig /lib64
    fi
	cd ..
	rm -rf openssl-${opensslVersion}
    echo "=============================================="
    echo "OpenSSL $opensslVersion 安装完成"
    echo "=============================================="
}

#检测hosts文件
hostfileck=`cat /etc/hosts | grep 127.0.0.1 | grep localhost`
if [ "${hostfileck}" = '' ]; then
    echo "127.0.0.1  localhost" >> /etc/hosts
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

Install_rpcgen() {
    if [ ! -f "/usr/bin/rpcgen" ];then
        echo "====================================="
        echo "缺少rpcgen安装中..."
        echo "====================================="
        cd /tmp
        wget https://download.lybbn.cn/ruyi/install/linux/mysql/rpcsvc-proto-1.4.tar.gz
        tar -xvf rpcsvc-proto-1.4.tar.gz
        cd rpcsvc-proto-1.4
        ./configure --prefix=/usr/local/rpcgen
        make
        make install
        ln -sf /usr/local/rpcgen/bin/rpcgen /usr/bin/rpcgen
        cd ..
        rm -rf rpcsvc-proto*
    fi
}

Check_GCC() {
    if ! command -v gcc &> /dev/null; then
        echo -e "${YELLOW}GCC 未安装${NC}"
        return 1
    else
        local version_str=$(gcc --version | head -n1 | awk '{print $3}')
        echo "$version_str" | grep -oE '^[0-9]+'
    fi
}

Install_Package() {
    local package_name=$1

    # 检查是否传入了包名称
    if [[ -z "$package_name" ]]; then
        echo "错误：请提供要安装的包名称。"
        return 1
    fi

    # 检查包是否已经安装
    if command -v "$package_name" &> /dev/null; then
        echo "$package_name 已安装。"
    else
        echo "$package_name 未安装，正在安装..."
        # 根据不同的包管理器安装包
        if command -v apt-get &> /dev/null; then
            # 适用于基于 Debian/Ubuntu 的系统
            apt-get install -y "$package_name"
        elif command -v yum &> /dev/null; then
            # 适用于基于 CentOS/RHEL 的系统
            yum install -y "$package_name"
        elif command -v brew &> /dev/null; then
            # 适用于 macOS
            brew install "$package_name"
        else
            echo "无法确定包管理器，请手动安装 $package_name" >&2
            exit 1
        fi

        # 检查安装是否成功
        if command -v "$package_name" &> /dev/null; then
            echo "$package_name 安装完成。"
        else
            echo "$package_name 安装失败，请检查日志。"
            return 1
        fi
    fi
}

Install_MySQL_Binary() {
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
    case $ARCH in
        x86_64) ARCH_TYPE="x86_64" ;;
        aarch64) ARCH_TYPE="aarch64" ;;
        *) Return_Error "不支持的架构: $ARCH" ;;
    esac

    if [[ $ARCH_TYPE == "aarch64" ]]; then
        Return_Error "不支持的架构: $ARCH_TYPE，请选择源码编译安装！！！"
    fi

    echo "安装需要的依赖..."
    if [ -f "/usr/bin/yum" ];then
        yum install ncurses-compat-libs -y
        yum install libarchive -y
        yum install libuv openldap-devel -y
        yum install libtirpc libtirpc-devel -y
        yum install libaio -y
    elif [ -f "/usr/bin/apt-get" ];then
        apt-get install libncurses5 -y
        apt-get install patchelf -y > /dev/null
        apt-get install libtirpc-dev -y > /dev/null
        apt-get install libaio1 -y > /dev/null
    fi
    Install_rpcgen

    # 根据版本选择下载路径
    if [[ $mysql_version_2 == "5.7" ]]; then
        MYSQL_URL="https://mirrors.aliyun.com/mysql/MySQL-5.7/mysql-${mysql_version}-linux-glibc2.12-${ARCH_TYPE}.tar.gz"
        FILE_SUFFIX="tar.gz"
    elif [[ $mysql_version_2 == "8.0" ]]; then
        MYSQL_URL="https://mirrors.aliyun.com/mysql/MySQL-8.0/mysql-${mysql_version}-linux-glibc2.12-${ARCH_TYPE}.tar.xz"
        FILE_SUFFIX="tar.xz"
    else
        Return_Error "不支持的MySQL版本"
    fi

    echo "====================================="
    echo "正在下载MySQL二进制包..."
    echo "URL: ${MYSQL_URL}"
    echo "====================================="

    rm -rf ${MYSQL_SETUP_PATH}
    # 下载并解压
    cd /ruyi/server
    rm -rf mysql.tar.gz
    # wget ${MYSQL_URL} -O mysql.tar.gz --timeout=30 --tries=3
    curl -L ${MYSQL_URL} -o mysql.${FILE_SUFFIX} --max-time 2800
    if [ $? -ne 0 ]; then
        echo "MySQL 下载失败，请检查网络连接或 URL 是否正确。" >&2
        exit 1
    fi

    echo "下载完成，开始解压..."
    if [[ $FILE_SUFFIX == "tar.xz" ]]; then
        tar -xf mysql.${FILE_SUFFIX}
    else
        tar -zxf mysql.${FILE_SUFFIX}
    fi

    # 移动文件到安装目录
    echo "====================================="
    echo "正在安装MySQL..."
    echo "====================================="

    # if [[ $mysql_version_2 == "8.0" ]]; then
    #     mv mysql-${mysql_version}-linux-glibc2.*-${ARCH_TYPE}-minimal mysql
    # else
    #     mv mysql-${mysql_version}-linux-glibc2.*-${ARCH_TYPE} mysql
    # fi

    mv mysql-${mysql_version}-linux-glibc2.*-${ARCH_TYPE} mysql
    
    rm -f mysql.tar.*

    echo "正在配置mysql..."
    if [ -d "/ruyi/server/data" ]; then
        rm -rf /ruyi/server/data/*
    else
        mkdir -p /ruyi/server/data
    fi
    chown -R mysql:mysql /ruyi/server/data
    chgrp -R mysql /ruyi/server/mysql/.
    Service_Add
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

    Install_Openssl

    # 检查自定义 OpenSSL 路径是否存在
    if [ -d "$CUSTOM_OPENSSL_PATH" ]; then
        OPENSSL_PATH="$CUSTOM_OPENSSL_PATH"
        DWITH_SSL="-DWITH_SSL=${OPENSSL_PATH}"
    else
        OPENSSL_PATH=$(which openssl)  # 获取系统默认的 openssl 路径
        if [ -f "$OPENSSL_PATH" ]; then
            DWITH_SSL="-DWITH_SSL=system"
        fi
    fi

    if [ -z "${IsCentos7}" ] && [ -f "/usr/bin/yum" ];then
        echo "安装需要的依赖：libtirpc rpcgen"
        yum install libtirpc -y
        yum install libtirpc-devel -y
        yum install rpcgen -y
        yum install rpcbind -y
        yum install libtirpc-devel* -y
        yum install patchelf -y  > /dev/null
    elif [ -f "/usr/bin/apt-get" ];then
        apt-get cmake install libtirpc-dev -y
        apt-get install patchelf -y > /dev/null
    fi
    if [ "${IsAliYunOS}" ];then
        yum install bison libaio-devel libtirpc-devel -y
    fi
    if [ "${IsCentos9}" ] || [ "${IsCentosStream9}" ];then
        echo "安装libtirpc-devel"
        dnf --enablerepo=crb install libtirpc-devel -y
    fi

    Install_rpcgen
    rm -rf /ruyi/server/mysql
    mkdir /ruyi/server/mysql
    cd ${RUYI_TEMP_PATH}
    rm -rf mysql-$mysql_version
    tar -zxf mysql-boost-$mysql_version.tar.gz
    cd mysql-$mysql_version
    GCC_VERSION=$(gcc -v 2>&1|grep "gcc version"|awk '{print $3}')
    GCC_MAJOR_VERSION=$(echo $GCC_VERSION | cut -d '.' -f 1)
    GCC_MINOR_VERSION=$(echo $GCC_VERSION | cut -d '.' -f 2)
    CMAKE_VERSION=$(cmake --version|grep version|awk '{print $3}')
    echo -e 当前系统 gcc:${GCC_VERSION} cmake:${CMAKE_VERSION}
    if [[ $mysql_version_2 == "5.7" ]]; then
        Install_Package "cmake"
        echo "====================================="
        echo "开始编译"
        echo "====================================="
        # cmake -DCMAKE_INSTALL_PREFIX=${MYSQL_SETUP_PATH} -DWITHOUT_TESTS=ON -DCMAKE_BUILD_TYPE=Release -DMYSQL_UNIX_ADDR=/tmp/mysql.sock -DMYSQL_DATADIR=${MYSQL_DATA_PATH} -DMYSQL_USER=mysql -DSYSCONFDIR=/etc -DWITH_MYISAM_STORAGE_ENGINE=1 -DWITH_INNOBASE_STORAGE_ENGINE=1 -DWITH_PARTITION_STORAGE_ENGINE=1 -DWITH_FEDERATED_STORAGE_ENGINE=1 -DEXTRA_CHARSETS=all -DDEFAULT_CHARSET=utf8mb4 -DDEFAULT_COLLATION=utf8mb4_general_ci -DWITH_EMBEDDED_SERVER=1 -DENABLED_LOCAL_INFILE=1 -DWITH_BOOST=./boost -DWITH_SSL=${OPENSSL_PATH} -DWITH_TOKUDB=OFF
        cmake -DCMAKE_INSTALL_PREFIX=${MYSQL_SETUP_PATH} -DWITH_DEBUG=OFF  -DWITH_DOCS=OFF -DWITH_TESTS=OFF -DWITH_EXAMPLES=OFF -DWITHOUT_TESTS=ON -DCMAKE_BUILD_TYPE=Release -DMYSQL_UNIX_ADDR=/tmp/mysql.sock -DMYSQL_DATADIR=${MYSQL_DATA_PATH} -DMYSQL_USER=mysql -DSYSCONFDIR=/etc -DWITH_MYISAM_STORAGE_ENGINE=1 -DWITH_INNOBASE_STORAGE_ENGINE=1 -DWITH_PARTITION_STORAGE_ENGINE=1 -DWITH_FEDERATED_STORAGE_ENGINE=1 -DEXTRA_CHARSETS=all -DDEFAULT_CHARSET=utf8mb4 -DDEFAULT_COLLATION=utf8mb4_general_ci -DWITH_EMBEDDED_SERVER=1 -DENABLED_LOCAL_INFILE=1 -DWITH_BOOST=./boost ${DWITH_SSL} -DWITH_TOKUDB=OFF
    elif [[ $mysql_version_2 == "8.0" ]]; then
        mkdir rybuild
        cd rybuild
        cmakeCV="cmake"
        if [ -f "/usr/bin/yum" ]; then
            if [ "${IsCentos7}" ];then
                current_gcc_version=$(Check_GCC)
                required_gcc_version=11
                if [[ "$current_gcc_version" -ge "$required_gcc_version" ]]; then
                    echo "当前 GCC 版本: ${current_gcc_version} (已满足要求)"
                else
                    echo "当前 GCC 版本: ${current_gcc_version}，需额外安装gcc${required_gcc_version}"
                    if [ -f "/etc/yum.repos.d/CentOS-SCLo-scl-rh.repo" ];then
                        sed -i 's/mirrorlist/#mirrorlist/g' /etc/yum.repos.d/CentOS-SCLo-scl-rh.repo
                        sed -i 's|#\s*baseurl=http://mirror.centos.org|baseurl=http://mirrors.aliyun.com|g' /etc/yum.repos.d/CentOS-SCLo-scl-rh.repo
                        sed -i 's/mirrorlist/#mirrorlist/g' /etc/yum.repos.d/CentOS-SCLo-scl.repo
                        sed -i 's|#\s*baseurl=http://mirror.centos.org|baseurl=http://mirrors.aliyun.com|g' /etc/yum.repos.d/CentOS-SCLo-scl.repo
                    else
                        yum remove centos-release-scl centos-release-scl-rh -y
                        yum install centos-release-scl centos-release-scl-rh -y
                        sed -i 's/mirrorlist/#mirrorlist/g' /etc/yum.repos.d/CentOS-SCLo-scl-rh.repo
                        sed -i 's|#\s*baseurl=http://mirror.centos.org|baseurl=http://mirrors.aliyun.com|g' /etc/yum.repos.d/CentOS-SCLo-scl-rh.repo
                        sed -i 's/mirrorlist/#mirrorlist/g' /etc/yum.repos.d/CentOS-SCLo-scl.repo
                        sed -i 's|#\s*baseurl=http://mirror.centos.org|baseurl=http://mirrors.aliyun.com|g' /etc/yum.repos.d/CentOS-SCLo-scl.repo
                    fi
                    yum install devtoolset-11-gcc devtoolset-11-gcc-c++ -y
                    current_gcc_version=$required_gcc_version
                fi
                yum install patchelf -y
                yum install cmake3 -y
                yum install openldap-devel -y
                cmakeCV="cmake3"
                export CC=/opt/rh/devtoolset-$current_gcc_version/root/usr/bin/gcc
                export CXX=/opt/rh/devtoolset-$current_gcc_version/root/usr/bin/g++
            else
                export CC=/usr/bin/gcc
                export CXX=/usr/bin/g++
            fi
        fi
        ${cmakeCV} .. -DCMAKE_INSTALL_PREFIX=${MYSQL_SETUP_PATH} -DWITHOUT_TESTS=ON -DENABLE_DEBUG_SYNC=0 -DCMAKE_BUILD_TYPE=Release -DMYSQL_UNIX_ADDR=/tmp/mysql.sock -DMYSQL_DATADIR=${MYSQL_DATA_PATH} -DMYSQL_USER=mysql -DSYSCONFDIR=/etc -DWITH_MYISAM_STORAGE_ENGINE=1 -DWITH_INNOBASE_STORAGE_ENGINE=1 -DWITH_PARTITION_STORAGE_ENGINE=1 -DDEFAULT_CHARSET=utf8mb4 -DDEFAULT_COLLATION=utf8mb4_general_ci -DENABLED_LOCAL_INFILE=1 -DWITH_BOOST=../boost ${DWITH_SSL} -DWITH_TOKUDB=OFF -DWITH_ZLIB=bundled -DWITH_ROCKSDB=OFF -DWITH_COREDUMPER=OFF -DWITH_DEBUG=OFF
    else
        cmake -DCMAKE_INSTALL_PREFIX=${MYSQL_SETUP_PATH} -DMYSQL_UNIX_ADDR=/tmp/mysql.sock -DMYSQL_DATADIR=${MYSQL_DATA_PATH} -DMYSQL_USER=mysql -DWITH_ARIA_STORAGE_ENGINE=1 -DWITH_XTRADB_STORAGE_ENGINE=1 -DWITH_INNOBASE_STORAGE_ENGINE=1 -DWITH_PARTITION_STORAGE_ENGINE=1 -DWITH_MYISAM_STORAGE_ENGINE=1 -DWITH_FEDERATED_STORAGE_ENGINE=1 -DEXTRA_CHARSETS=all -DDEFAULT_CHARSET=utf8mb4 -DDEFAULT_COLLATION=utf8mb4_general_ci -DWITH_READLINE=1 -DWITH_EMBEDDED_SERVER=1 -DENABLED_LOCAL_INFILE=1 -DWITHOUT_TOKUDB=1
    fi
    if [ "$?" != "0" ] ;then
        Return_Error "cmake编译失败"
    fi
    echo "====================================="
    echo "正在安装..."
    echo "====================================="
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
        echo "参数错误" >&2
        exit 1
    fi
    if [[ $mysql_version == 5.7* ]]; then
        mysql_version_2="5.7"
    elif [[ $mysql_version == 8.0* ]]; then
        mysql_version_2="8.0"
    else
        echo "参数错误" >&2
        exit 1
    fi
    if [ "$install_type" == '2' ];then
        Install_MySQL_Binary
    else
        Install_Soft
    fi
elif [ "$action_type" == 'uninstall' ];then
	Uninstall_soft
fi
