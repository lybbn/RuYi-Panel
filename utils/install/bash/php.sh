#!/bin/bash
#php环境安装
echo "当前PATH路径:$PATH"
LANG=en_US.UTF-8

RUYI_TEMP_PATH="/ruyi/tmp"

action_type=$1
php_version=$2
php_file_name=$3
cpu_core=$(cat /proc/cpuinfo|grep processor|wc -l)
install_sys_path="/usr/local/ruyi"
OPENSSL_DIR=/usr/local/ruyi/openssl
Sqlite3_Env_Path=/usr/local/ruyi/sqlite3
WITH_SSL=""

setup_path=/ruyi/server/php/${php_version}

# 检查是否以 root 用户运行
if [ "$(id -u)" -ne 0 ]; then
    echo "请以 root 用户运行此脚本" >&2
    exit 1
fi

if [ -z "${cpu_core}" ]; then
    cpu_core=1
fi

# # 获取内存大小（以 GB 为单位）
# MEM_G=$(free -m | awk '/Mem/ {printf("%.f", \$2 / 1024)}')

# # 如果 CPU 核心数和内存大小都有效
# if [ "$cpu_core" -gt 1 ] && [ "$MEM_G" -gt 0 ]; then
#     # 根据 CPU 核心数和内存大小，选择较小的值
#     cpu_core=$((cpu_core > MEM_G ? MEM_G : cpu_core))
# else
#     # 如果 CPU 核心数小于等于 1 或内存为 0，设置 CPU 核心数为 1
#     cpu_core=1
# fi

Service_Add() {
	cat <<EOF > /etc/systemd/system/php-fpm-${php_version}.service
[Unit]
Description=php-fpm ${php_version} RuYi Server
After=network.target

[Service]
Type=forking
PIDFile=${setup_path}/var/run/php-fpm.pid
ExecStart=${setup_path}/sbin/php-fpm --daemonize --fpm-config ${setup_path}/etc/php-fpm.conf --pid ${setup_path}/var/run/php-fpm.pidonf
ExecReload=/bin/kill -USR2 \$MAINPID

[Install]
WantedBy=multi-user.target
EOF

    # 重新加载 systemd 配置
    systemctl daemon-reload
    systemctl enable php-fpm-${php_version}.service
}

Service_Del() {
	# 停止 Redis 服务
    systemctl stop php-fpm-${php_version}.service

    # 禁用 Redis 服务
    systemctl disable php-fpm-${php_version}.service

    # 删除 Redis 服务文件
    rm -f /etc/systemd/system/php-fpm-${php_version}.service
    rm -rf /etc/systemd/system/multi-user.target.wants/php-fpm-${php_version}.service

    # 重新加载 systemd 配置
    systemctl daemon-reload
}

Install_Lib() {
    echo "安装系统依赖..."
    if [ -f "/usr/bin/yum" ];then
        yum install -y gcc gcc-c++ libsodium-devel re2c bison autoconf make libtool ccache libxml2-devel sqlite-devel openssl-devel gd-devel
    elif [ -f "/usr/bin/apt-get" ];then
        apt-get install -y gcc gcc-c++ pkg-config build-essential autoconf bison re2c libxml2-dev libsqlite3-dev libcurl4-openssl-dev libsodium-dev
    fi
}

Install_Openssl() {
    echo "=============================================="
    echo "正在安装OpenSSL..."
    echo "=============================================="
    local openssl_version
    openssl_version=$(openssl version | awk '{print $2}')
    # 提取主要和次要版本号
    local major
    local minor
    major=$(echo $openssl_version | cut -d '.' -f 1)
    minor=$(echo $openssl_version | cut -d '.' -f 2)
    if [ -f ${install_sys_path}/openssl/bin/openssl ] || [ $minor -ge 1 ];then
        echo "检测到OpenSSL版本符合要求，无需再安装"
        echo "=============================================="
	 	return
	fi
	opensslVersion="1.1.1w"
    mkdir -p ${install_sys_path}/openssl
	cd ${install_sys_path}
    wget https://github.com/openssl/openssl/releases/download/OpenSSL_1_1_1w/openssl-${opensslVersion}.tar.gz
	tar -zxf openssl-${opensslVersion}.tar.gz
    rm -f openssl-${opensslVersion}.tar.gz
	cd openssl-${opensslVersion}
    if [ "${IsAliYunOS}" ];then
        ./config --prefix=${py_path}/openssl --openssldir=${py_path}/openssl zlib-dynamic -Wl,-rpath,${py_path}/openssl/lib
        make -j${cpu_core}
        make install
    else
        ./config --prefix=${install_sys_path}/openssl zlib-dynamic
        make -j${cpu_core}
        make install
        echo "$install_sys_path/openssl/lib" >>/etc/ld.so.conf.d/ryopenssl111.conf
        ldconfig
        ldconfig /lib64
    fi
	cd ..
	rm -rf openssl-${opensslVersion}
    echo "=============================================="
    echo "OpenSSL $opensslVersion 安装完成"
    echo "=============================================="
}

Install_Openssl34() {
    echo "=============================================="
    echo "正在安装OpenSSL..."
    echo "=============================================="
    local openssl_version
    openssl_version=$(openssl version | awk '{print $2}')
    # 提取主要和次要版本号
    local major
    local minor
    major=$(echo $openssl_version | cut -d '.' -f 1)
    minor=$(echo $openssl_version | cut -d '.' -f 2)
    if [ -f ${install_sys_path}/openssl34/bin/openssl ] || [ $minor -ge 1 ];then
        echo "检测到OpenSSL版本符合要求，无需再安装"
        echo "=============================================="
	 	return
	fi
	opensslVersion="3.4.0"
    mkdir -p ${install_sys_path}/openssl34
	cd ${install_sys_path}
    wget  https://github.com/openssl/openssl/releases/download/openssl-3.4.0/openssl-${opensslVersion}.tar.gz
	tar -zxf openssl-${opensslVersion}.tar.gz
    rm -f openssl-${opensslVersion}.tar.gz
	cd openssl-${opensslVersion}
	./config --prefix=${install_sys_path}/openssl34 zlib shared
	make -j${cpu_core}
	make install
    echo "$install_sys_path/openssl34/lib64" >>/etc/ld.so.conf.d/ryopenssl34.conf
	ldconfig
    ldconfig /lib64
	cd ..
	rm -rf openssl-${opensslVersion}
    echo "=============================================="
    echo "OpenSSL $opensslVersion 安装完成"
    echo "=============================================="
}

Install_Soft() {
    # current_swappiness=$(sysctl -n vm.swappiness)
    # if [ -n "$current_swappiness" ]; then
    #     echo "当前的 vm.swappiness 值为：$current_swappiness"
        
    #     echo "临时设置 vm.swappiness=0"
    #     sysctl -w vm.swappiness=0

    #     trap "echo '恢复原来的 vm.swappiness 值';sysctl -w vm.swappiness=$current_swappiness" EXIT SIGTERM SIGINT
    # fi
    Install_Lib
    cd ${RUYI_TEMP_PATH}
    php_unzip_file_name=$(basename "$php_file_name" .tgz)
    rm -rf $php_unzip_file_name
    tar -zxf $php_file_name
    
    rm -rf $setup_path > /dev/null 2>&1
    
	mkdir -p ${setup_path}
	echo "True" > ${setup_path}/disk.ry
	if [ ! -w ${setup_path}/disk.ry ];then
		echo "ERROR: Install php fielded." "ERROR: $setup_path 目录无法写入，请检查目录/用户/磁盘权限！" >&2
        exit 1
	fi
	cd ${php_unzip_file_name}
    echo "==================================================="
    echo "正在配置..."
    echo "==================================================="
    soft_configure_str="--prefix=${setup_path} --with-config-file-path=${setup_path} --with-curl --with-freetype-dir --with-gd --with-gettext --with-iconv-dir --with-kerberos --with-libdir=lib64 --with-libxml-dir --with-mysqli --with-openssl --with-pcre-regex --with-pdo-mysql --with-pdo-sqlite --with-pear --with-png-dir --with-xmlrpc --with-xsl --with-zlib --with-mcrypt --enable-fpm --enable-bcmath --enable-libxml --enable-inline-optimization --enable-gd-native-ttf --enable-mbregex --enable-mbstring --enable-opcache --enable-pcntl --enable-shmop --enable-soap --enable-sockets --enable-sysvsem --enable-xml --enable-zip"
    echo "当前工作目录：$(pwd) ，开始执行configure..."
    echo "./configure ${soft_configure_str}"
    ./configure $soft_configure_str
    echo "==================================================="
    echo "正在编译..."
    echo "==================================================="
	make -j${cpu_core}
    echo "==================================================="
    echo "正在安装..."
    echo "==================================================="
	make install
	if [ ! -e ${py_path}/bin/python3 ];then
		rm -rf ${python_unzip_file_name}
		echo "ERROR: Install python fielded." "ERROR: 安装python环境失败，请尝试重新安装！" >&2
        exit 1
	fi
    cd ..
    rm -rf ${python_unzip_file_name}
    echo "==================================================="
    echo "Python $python_version 安装完成"
    echo "==================================================="
}

Uninstall_soft() {
    rm -rf ${setup_path}
    Service_Del
}

if [ "$action_type" == 'install' ];then
    if [ -z "${php_version}" ] || [ -z "${python_file_name}" ]; then
        echo "参数错误" >&2
        exit 1
    fi
	Install_Soft
elif [ "$action_type" == 'uninstall' ];then
    if [ -z "${php_version}" ];then
        echo "参数错误" >&2
        exit 1
    fi
	Uninstall_soft
fi
