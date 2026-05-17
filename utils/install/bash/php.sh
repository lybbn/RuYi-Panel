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

if [ "$(id -u)" -ne 0 ]; then
    echo "请以 root 用户运行此脚本" >&2
    exit 1
fi

if [ -z "${cpu_core}" ]; then
    cpu_core=1
fi

Service_Add() {
	cat <<EOF > /etc/systemd/system/php-fpm-${php_version}.service
[Unit]
Description=php-fpm ${php_version} RuYi Server
After=network.target

[Service]
Type=forking
PIDFile=${setup_path}/var/run/php-fpm.pid
ExecStart=${setup_path}/sbin/php-fpm --fpm-config ${setup_path}/etc/php-fpm.conf --pid ${setup_path}/var/run/php-fpm.pid
ExecReload=/bin/kill -USR2 \$MAINPID
ExecStop=/bin/kill -SIGQUIT \$MAINPID

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable php-fpm-${php_version}.service
}

Service_Del() {
    systemctl stop php-fpm-${php_version}.service 2>/dev/null
    systemctl disable php-fpm-${php_version}.service 2>/dev/null
    rm -f /etc/systemd/system/php-fpm-${php_version}.service
    rm -rf /etc/systemd/system/multi-user.target.wants/php-fpm-${php_version}.service
    systemctl daemon-reload
}

Install_Lib() {
    echo "安装系统依赖..."
    if [ -f "/usr/bin/yum" ]; then
        yum install -y gcc gcc-c++ make autoconf libtool re2c bison ccache \
            libxml2-devel sqlite-devel openssl-devel bzip2-devel libcurl-devel \
            libpng-devel libjpeg-devel freetype-devel libicu-devel oniguruma-devel \
            libsodium-devel libzip-devel gd-devel libxslt-devel
    elif [ -f "/usr/bin/apt-get" ]; then
        apt-get update
        apt-get install -y gcc g++ make autoconf libtool re2c bison \
            libxml2-dev libsqlite3-dev libssl-dev libbz2-dev libcurl4-openssl-dev \
            libpng-dev libjpeg-dev libfreetype6-dev libicu-dev oniguruma-dev \
            libsodium-dev libzip-dev libgd-dev libxslt1-dev pkg-config
    fi
}

Install_Openssl() {
    echo "=============================================="
    echo "正在检查OpenSSL..."
    echo "=============================================="
    local openssl_version
    openssl_version=$(openssl version 2>/dev/null | awk '{print $2}')
    local major
    local minor
    major=$(echo $openssl_version | cut -d '.' -f 1)
    minor=$(echo $openssl_version | cut -d '.' -f 2)
    if [ -f ${install_sys_path}/openssl/bin/openssl ] || [ "${minor:-0}" -ge 1 ]; then
        echo "检测到OpenSSL版本符合要求，无需再安装"
        echo "=============================================="
        return
    fi
    opensslVersion="1.1.1w"
    mkdir -p ${install_sys_path}/openssl
    cd ${install_sys_path}
    wget -q https://github.com/openssl/openssl/releases/download/OpenSSL_1_1_1w/openssl-${opensslVersion}.tar.gz
    tar -zxf openssl-${opensslVersion}.tar.gz
    rm -f openssl-${opensslVersion}.tar.gz
    cd openssl-${opensslVersion}
    ./config --prefix=${install_sys_path}/openssl zlib-dynamic
    make -j${cpu_core}
    make install
    echo "${install_sys_path}/openssl/lib" >> /etc/ld.so.conf.d/ryopenssl111.conf
    ldconfig
    cd ..
    rm -rf openssl-${opensslVersion}
    echo "=============================================="
    echo "OpenSSL $opensslVersion 安装完成"
    echo "=============================================="
}

Get_PHP_Major_Version() {
    echo "$php_version" | cut -d '.' -f 1
}

Get_PHP_Minor_Version() {
    echo "$php_version" | cut -d '.' -f 2
}

Build_PHP_7() {
    echo "==================================================="
    echo "正在配置 PHP ${php_version} (PHP7编译参数)..."
    echo "==================================================="
    soft_configure_str="--prefix=${setup_path} \
        --with-config-file-path=${setup_path} \
        --with-config-file-scan-dir=${setup_path}/lib/php/extensions \
        --with-curl \
        --with-freetype-dir \
        --with-gd \
        --with-gettext \
        --with-iconv-dir \
        --with-kerberos \
        --with-libdir=lib64 \
        --with-libxml-dir \
        --with-mysqli=mysqlnd \
        --with-openssl \
        --with-pcre-regex \
        --with-pdo-mysql=mysqlnd \
        --with-pdo-sqlite \
        --with-pear \
        --with-png-dir \
        --with-xmlrpc \
        --with-xsl \
        --with-zlib \
        --with-bz2 \
        --with-jpeg-dir \
        --enable-fpm \
        --enable-bcmath \
        --enable-libxml \
        --enable-inline-optimization \
        --enable-gd-native-ttf \
        --enable-mbregex \
        --enable-mbstring \
        --enable-opcache \
        --enable-pcntl \
        --enable-shmop \
        --enable-soap \
        --enable-sockets \
        --enable-sysvsem \
        --enable-xml \
        --enable-zip \
        --enable-intl \
        --enable-exif \
        --enable-fileinfo \
        --disable-rpath"
    echo "./configure ${soft_configure_str}"
    ./configure $soft_configure_str
}

Build_PHP_8() {
    echo "==================================================="
    echo "正在配置 PHP ${php_version} (PHP8编译参数)..."
    echo "==================================================="
    local with_openssl=""
    if [ -f "${install_sys_path}/openssl/bin/openssl" ]; then
        with_openssl="--with-openssl-dir=${install_sys_path}/openssl"
    fi
    soft_configure_str="--prefix=${setup_path} \
        --with-config-file-path=${setup_path} \
        --with-config-file-scan-dir=${setup_path}/lib/php/extensions \
        --with-curl \
        --with-freetype \
        --with-gettext \
        --with-iconv \
        --with-kerberos \
        --with-libdir=lib64 \
        --with-libxml \
        --with-mysqli=mysqlnd \
        --with-openssl \
        ${with_openssl} \
        --with-pdo-mysql=mysqlnd \
        --with-pdo-sqlite \
        --with-pear \
        --with-xsl \
        --with-zlib \
        --with-bz2 \
        --with-zip \
        --enable-fpm \
        --enable-bcmath \
        --enable-mbstring \
        --enable-opcache \
        --enable-pcntl \
        --enable-shmop \
        --enable-soap \
        --enable-sockets \
        --enable-sysvsem \
        --enable-xml \
        --enable-intl \
        --enable-exif \
        --enable-fileinfo \
        --enable-gd \
        --with-jpeg \
        --disable-rpath"
    echo "./configure ${soft_configure_str}"
    ./configure $soft_configure_str
}

Install_Soft() {
    Install_Lib
    Install_Openssl

    cd ${RUYI_TEMP_PATH}
    php_unzip_file_name=$(basename "$php_file_name" .tgz)
    if [ ! -d "$php_unzip_file_name" ]; then
        php_unzip_file_name=$(basename "$php_file_name" .tar.gz)
    fi

    echo "==================================================="
    echo "正在解压 ${php_file_name}..."
    echo "==================================================="
    rm -rf $php_unzip_file_name
    rm -rf php-src-$php_unzip_file_name
    tar -zxf $php_file_name

    if [ ! -d "$php_unzip_file_name" ] && [ -d "php-src-$php_unzip_file_name" ]; then
        mv php-src-$php_unzip_file_name $php_unzip_file_name
    fi

    if [ ! -d "$php_unzip_file_name" ]; then
        echo "ERROR: 解压失败，找不到源码目录" >&2
        exit 1
    fi

    rm -rf $setup_path > /dev/null 2>&1
    mkdir -p ${setup_path}

    echo "True" > ${setup_path}/disk.ry
    if [ ! -w ${setup_path}/disk.ry ]; then
        echo "ERROR: $setup_path 目录无法写入，请检查目录/用户/磁盘权限！" >&2
        exit 1
    fi

    cd ${php_unzip_file_name}

    local major_version
    major_version=$(Get_PHP_Major_Version)

    if [ "$major_version" -ge 8 ]; then
        Build_PHP_8
    else
        Build_PHP_7
    fi

    if [ $? -ne 0 ]; then
        echo "ERROR: configure 失败" >&2
        exit 1
    fi

    echo "==================================================="
    echo "正在编译..."
    echo "==================================================="
    make -j${cpu_core}
    if [ $? -ne 0 ]; then
        echo "ERROR: make 失败" >&2
        exit 1
    fi

    echo "==================================================="
    echo "正在安装..."
    echo "==================================================="
    make install
    if [ $? -ne 0 ]; then
        echo "ERROR: make install 失败" >&2
        exit 1
    fi

    if [ ! -e ${setup_path}/bin/php ]; then
        cd ..
        rm -rf ${php_unzip_file_name}
        echo "ERROR: 安装PHP失败，php可执行文件不存在" >&2
        exit 1
    fi

    mkdir -p ${setup_path}/var/run
    mkdir -p ${setup_path}/var/log
    mkdir -p ${setup_path}/tmp
    mkdir -p ${setup_path}/etc/php-fpm.d

    if [ -f ${setup_path}/etc/php-fpm.conf.default ]; then
        cp ${setup_path}/etc/php-fpm.conf.default ${setup_path}/etc/php-fpm.conf
    fi
    if [ -f ${setup_path}/etc/php-fpm.d/www.conf.default ]; then
        cp ${setup_path}/etc/php-fpm.d/www.conf.default ${setup_path}/etc/php-fpm.d/www.conf
    fi
    if [ -f ${setup_path}/lib/php.ini-production ]; then
        cp ${setup_path}/lib/php.ini-production ${setup_path}/lib/php.ini
    elif [ -f ${setup_path}/lib/php.ini-development ]; then
        cp ${setup_path}/lib/php.ini-development ${setup_path}/lib/php.ini
    fi

    Service_Add

    cd ..
    rm -rf ${php_unzip_file_name}
    echo "==================================================="
    echo "PHP ${php_version} 编译安装完成"
    echo "==================================================="
}

Uninstall_soft() {
    Service_Del
    rm -rf ${setup_path}
    echo "==================================================="
    echo "PHP ${php_version} 已卸载"
    echo "==================================================="
}

if [ "$action_type" == 'install' ]; then
    if [ -z "${php_version}" ] || [ -z "${php_file_name}" ]; then
        echo "参数错误" >&2
        exit 1
    fi
    Install_Soft
elif [ "$action_type" == 'uninstall' ]; then
    if [ -z "${php_version}" ]; then
        echo "参数错误" >&2
        exit 1
    fi
    Uninstall_soft
fi
