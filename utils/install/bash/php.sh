#!/bin/bash
#php环境安装
echo "当前PATH路径:$PATH"
LANG=en_US.UTF-8

RUYI_TEMP_PATH="/ruyi/tmp"

action_type=$1
php_version=$2
php_file_name=$3
cpu_core=$(cat /proc/cpuinfo|grep processor|wc -l)

if [ -z "${cpu_core}" ]; then
    cpu_core=1
fi

Get_Make_Jobs() {
    local mem_available_mb=$(free -m 2>/dev/null | grep Mem | awk '{print $7}')
    if [ -z "${mem_available_mb}" ] || [ "${mem_available_mb}" -le 0 ]; then
        mem_available_mb=$(free -m 2>/dev/null | grep Mem | awk '{print $4}')
    fi
    if [ -z "${mem_available_mb}" ] || [ "${mem_available_mb}" -le 0 ]; then
        mem_available_mb=512
    fi
    local mem_per_job=1024
    local max_jobs_by_mem=$((mem_available_mb / mem_per_job))
    if [ "${max_jobs_by_mem}" -le 0 ]; then
        max_jobs_by_mem=1
    fi
    local jobs=${cpu_core}
    if [ "${jobs}" -gt "${max_jobs_by_mem}" ]; then
        jobs=${max_jobs_by_mem}
    fi
    if [ "${jobs}" -gt 4 ]; then
        jobs=4
    fi
    if [ "${jobs}" -le 0 ]; then
        jobs=1
    fi
    echo "可用内存: ${mem_available_mb}MB, 编译并发数: ${jobs}" >&2
    echo ${jobs}
}

make_jobs=$(Get_Make_Jobs)
install_sys_path="/usr/local/ruyi"
OPENSSL_DIR=/usr/local/ruyi/openssl
Sqlite3_Env_Path=/usr/local/ruyi/sqlite3
WITH_SSL=""

setup_path=/ruyi/server/php/${php_version}

if [ "$(id -u)" -ne 0 ]; then
    echo "请以 root 用户运行此脚本" >&2
    exit 1
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

Ensure_Swap() {
    local mem_total_mb=$(free -m 2>/dev/null | grep Mem | awk '{print $2}')
    if [ -z "${mem_total_mb}" ] || [ "${mem_total_mb}" -le 0 ]; then
        mem_total_mb=1024
    fi
    local swap_total_mb=$(free -m 2>/dev/null | grep Swap | awk '{print $2}')
    if [ -z "${swap_total_mb}" ]; then
        swap_total_mb=0
    fi
    local total_mb=$((mem_total_mb + swap_total_mb))
    if [ "${total_mb}" -lt 4096 ]; then
        local need_swap=$((4096 - total_mb))
        if [ "${need_swap}" -lt 1024 ]; then
            need_swap=1024
        fi
        local swap_file="/ruyi/swapfile"
        if [ -f "${swap_file}" ]; then
            local existing_swap_size=$(du -m "${swap_file}" 2>/dev/null | awk '{print $1}')
            if [ "${existing_swap_size}" -ge 1024 ]; then
                echo "检测到已有swap文件 ${swap_file} (${existing_swap_size}MB)，跳过创建"
                return
            fi
        fi
        echo "系统内存+Swap仅 ${total_mb}MB，正在创建 ${need_swap}MB swap文件以防止编译OOM..."
        dd if=/dev/zero of=${swap_file} bs=1M count=${need_swap} status=progress
        chmod 600 ${swap_file}
        mkswap ${swap_file}
        swapon ${swap_file}
        echo "${swap_file} swap文件已启用"
    else
        echo "系统内存+Swap共 ${total_mb}MB，满足编译需求"
    fi
}

Install_Lib() {
    echo "安装系统依赖..."
    export DEBIAN_FRONTEND=noninteractive
    if [ -f "/usr/bin/yum" ]; then
        yum install -y gcc gcc-c++ make autoconf automake libtool re2c bison ccache \
            libxml2-devel sqlite-devel openssl-devel bzip2-devel libcurl-devel \
            libpng-devel libjpeg-devel freetype-devel libicu-devel oniguruma-devel \
            libsodium-devel libzip-devel gd-devel libxslt-devel krb5-devel
    elif [ -f "/usr/bin/apt-get" ]; then
        apt-get update -y
        apt-get install -y gcc g++ make autoconf automake libtool re2c bison \
            libxml2-dev libsqlite3-dev libssl-dev libbz2-dev libcurl4-openssl-dev \
            libpng-dev libjpeg-dev libfreetype6-dev libicu-dev \
            libsodium-dev libzip-dev libgd-dev libxslt1-dev pkg-config \
            libkrb5-dev
        apt-get install -y libonig-dev || apt-get install -y oniguruma-dev || echo "WARNING: oniguruma-dev/libonig-dev 安装失败，mbstring扩展可能不可用"
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

    local need_custom_openssl=0
    local php_major
    php_major=$(Get_PHP_Major_Version)
    if [ "${php_major}" -lt 8 ] && [ "${major:-0}" -ge 3 ]; then
        need_custom_openssl=1
        echo "检测到系统OpenSSL版本为 ${openssl_version}，PHP7不兼容OpenSSL 3.0+，需要安装OpenSSL 1.1.1"
    fi

    if [ -f ${install_sys_path}/openssl/bin/openssl ] && [ "${need_custom_openssl}" -eq 0 ]; then
        echo "检测到自定义OpenSSL已安装，无需再安装"
        echo "=============================================="
        return
    fi

    if [ "${need_custom_openssl}" -eq 0 ] && [ "${major:-0}" -ge 1 ] && [ "${minor:-0}" -ge 1 ]; then
        echo "检测到系统OpenSSL版本 ${openssl_version} 符合要求，无需再安装"
        echo "=============================================="
        return
    fi

    opensslVersion="1.1.1w"
    if [ -f ${install_sys_path}/openssl/bin/openssl ]; then
        local custom_ver=$(${install_sys_path}/openssl/bin/openssl version 2>/dev/null | awk '{print $2}')
        if [ -n "${custom_ver}" ]; then
            echo "检测到已安装自定义OpenSSL ${custom_ver}，无需重新安装"
            echo "=============================================="
            return
        fi
    fi
    echo "正在安装OpenSSL ${opensslVersion}..."
    mkdir -p ${install_sys_path}/openssl
    cd ${install_sys_path}
    wget -q https://github.com/openssl/openssl/releases/download/OpenSSL_1_1_1w/openssl-${opensslVersion}.tar.gz
    if [ $? -ne 0 ]; then
        echo "GitHub下载失败，尝试从php.net镜像下载..."
        wget -q https://www.php.net/distributions/openssl-${opensslVersion}.tar.gz || \
        wget -q https://mirrors.huaweicloud.com/openssl/source/openssl-${opensslVersion}.tar.gz || \
        curl -sL -o openssl-${opensslVersion}.tar.gz https://github.com/openssl/openssl/releases/download/OpenSSL_1_1_1w/openssl-${opensslVersion}.tar.gz
    fi
    if [ ! -f openssl-${opensslVersion}.tar.gz ]; then
        echo "ERROR: OpenSSL下载失败，请检查网络连接" >&2
        exit 1
    fi
    tar -zxf openssl-${opensslVersion}.tar.gz
    rm -f openssl-${opensslVersion}.tar.gz
    cd openssl-${opensslVersion}
    ./config --prefix=${install_sys_path}/openssl zlib-dynamic
    make -j${make_jobs}
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

    local minor_version=$(Get_PHP_Minor_Version)

    local gd_config=""
    if [ "${minor_version}" -ge 4 ]; then
        gd_config="--enable-gd --with-freetype --with-jpeg"
    else
        gd_config="--with-gd --with-freetype-dir=/usr --with-jpeg-dir=/usr"
    fi

    local zip_config="--with-zip"
    local iconv_config="--with-iconv"

    local with_openssl=""
    local openssl_env=""
    if [ -f "${install_sys_path}/openssl/bin/openssl" ]; then
        with_openssl="--with-openssl=${install_sys_path}/openssl"
        openssl_env="PKG_CONFIG_PATH=${install_sys_path}/openssl/lib/pkgconfig:\$PKG_CONFIG_PATH"
        echo "检测到自定义OpenSSL，使用路径: ${install_sys_path}/openssl"
    else
        with_openssl="--with-openssl"
    fi

    local lib_dir="lib64"
    if [ -f "/usr/bin/apt-get" ]; then
        lib_dir="lib"
    fi

    local with_pear="--with-pear"
    if [ "${minor_version}" -lt 4 ]; then
        with_pear="--with-pear"
    fi

    local with_xmlrpc="--with-xmlrpc"
    if [ "${minor_version}" -ge 4 ]; then
        with_xmlrpc=""
    fi

    soft_configure_str="--prefix=${setup_path} \
        --with-config-file-path=${setup_path}/lib \
        --with-config-file-scan-dir=${setup_path}/lib/php/extensions \
        --with-curl \
        ${gd_config} \
        --with-gettext \
        ${iconv_config} \
        --with-kerberos \
        --with-libdir=${lib_dir} \
        --with-libxml \
        --with-mysqli=mysqlnd \
        ${with_openssl} \
        --with-pdo-mysql=mysqlnd \
        --with-pdo-sqlite \
        ${with_pear} \
        ${with_xmlrpc} \
        --with-xsl \
        --with-zlib \
        --with-bz2 \
        --enable-fpm \
        --enable-bcmath \
        --enable-inline-optimization \
        --enable-mbregex \
        --enable-mbstring \
        --enable-opcache \
        --enable-pcntl \
        --enable-shmop \
        --enable-soap \
        --enable-sockets \
        --enable-sysvsem \
        --enable-xml \
        ${zip_config} \
        --enable-intl \
        --enable-exif \
        --enable-fileinfo \
        --disable-rpath"
    echo "./configure ${soft_configure_str}"
    if [ -n "${openssl_env}" ]; then
        export PKG_CONFIG_PATH="${install_sys_path}/openssl/lib/pkgconfig:${PKG_CONFIG_PATH}"
        export LDFLAGS="-L${install_sys_path}/openssl/lib -Wl,-rpath,${install_sys_path}/openssl/lib"
        export CPPFLAGS="-I${install_sys_path}/openssl/include"
    fi
    ./configure $soft_configure_str
}

Build_PHP_8() {
    echo "==================================================="
    echo "正在配置 PHP ${php_version} (PHP8编译参数)..."
    echo "==================================================="
    local with_openssl=""
    if [ -f "${install_sys_path}/openssl/bin/openssl" ]; then
        with_openssl="--with-openssl=${install_sys_path}/openssl"
        echo "检测到自定义OpenSSL，使用路径: ${install_sys_path}/openssl"
    else
        with_openssl="--with-openssl"
    fi
    local lib_dir="lib64"
    if [ -f "/usr/bin/apt-get" ]; then
        lib_dir="lib"
    fi
    soft_configure_str="--prefix=${setup_path} \
        --with-config-file-path=${setup_path}/lib \
        --with-config-file-scan-dir=${setup_path}/lib/php/extensions \
        --with-curl \
        --with-freetype \
        --with-gettext \
        --with-iconv \
        --with-kerberos \
        --with-libdir=${lib_dir} \
        --with-libxml \
        --with-mysqli=mysqlnd \
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
    if [ -f "${install_sys_path}/openssl/bin/openssl" ]; then
        export PKG_CONFIG_PATH="${install_sys_path}/openssl/lib/pkgconfig:${PKG_CONFIG_PATH}"
        export LDFLAGS="-L${install_sys_path}/openssl/lib -Wl,-rpath,${install_sys_path}/openssl/lib"
        export CPPFLAGS="-I${install_sys_path}/openssl/include"
    fi
    ./configure $soft_configure_str
}

Install_Soft() {
    Install_Lib
    Install_Openssl
    Ensure_Swap

    mkdir -p ${RUYI_TEMP_PATH}
    cd ${RUYI_TEMP_PATH} || { echo "ERROR: 无法进入临时目录 ${RUYI_TEMP_PATH}" >&2; exit 1; }
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
    if [ $? -ne 0 ] || [ ! -d "." ]; then
        echo "ERROR: 无法进入源码目录 ${php_unzip_file_name}" >&2
        echo "当前目录: $(pwd)" >&2
        echo "目录内容: $(ls -la)" >&2
        exit 1
    fi
    echo "已进入源码目录: $(pwd)"

    if [ ! -f "./configure" ]; then
        echo "未找到configure脚本，正在通过buildconf生成..."
        if [ -f "./buildconf" ]; then
            ./buildconf --force
            if [ $? -ne 0 ]; then
                echo "ERROR: buildconf 执行失败" >&2
                exit 1
            fi
        else
            echo "ERROR: 源码目录中未找到configure和buildconf，请检查源码包是否完整" >&2
            exit 1
        fi
    fi

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
    make -j${make_jobs}
    if [ $? -ne 0 ]; then
        echo "首次编译失败，正在清理并降低并发数重试..."
        make clean 2>/dev/null
        local retry_jobs=1
        if [ "${make_jobs}" -gt 2 ]; then
            retry_jobs=$((make_jobs / 2))
        fi
        echo "重试编译，并发数: ${retry_jobs}"
        make -j${retry_jobs}
        if [ $? -ne 0 ]; then
            echo "ERROR: make 失败" >&2
            exit 1
        fi
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
    if [ ! -f ${setup_path}/etc/php-fpm.conf ]; then
        cat >${setup_path}/etc/php-fpm.conf<<EOF
[global]
pid = ${setup_path}/var/run/php-fpm.pid
error_log = ${setup_path}/var/log/php-fpm.log
log_level = notice

include = ${setup_path}/etc/php-fpm.d/*.conf
EOF
    fi
    if [ -f ${setup_path}/etc/php-fpm.d/www.conf.default ]; then
        cp ${setup_path}/etc/php-fpm.d/www.conf.default ${setup_path}/etc/php-fpm.d/www.conf
    fi
    if [ ! -f ${setup_path}/etc/php-fpm.d/www.conf ]; then
        id www >/dev/null 2>&1 || useradd -r -s /sbin/nologin www 2>/dev/null
        local fpm_user="www"
        id www >/dev/null 2>&1 || fpm_user="nobody"
        local pm_type="dynamic"
        local mem_total=$(free -m 2>/dev/null | grep Mem | awk '{print $2}')
        if [ -n "${mem_total}" ] && [ "${mem_total}" -le 2200 ]; then
            pm_type="ondemand"
        fi
        cat >${setup_path}/etc/php-fpm.d/www.conf<<EOF
[www]
user = ${fpm_user}
group = ${fpm_user}
listen = ${setup_path}/tmp/php-cgi.sock
listen.backlog = 8192
listen.allowed_clients = 127.0.0.1
listen.owner = ${fpm_user}
listen.group = ${fpm_user}
listen.mode = 0660
pm = ${pm_type}
pm.max_children = 30
pm.start_servers = 5
pm.min_spare_servers = 5
pm.max_spare_servers = 10
pm.max_requests = 1000
request_terminate_timeout = 100
request_slowlog_timeout = 30
slowlog = ${setup_path}/var/log/slow.log
EOF
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

# 释放Linux文件系统缓存（page cache）
trap 'sync && echo 3 > /proc/sys/vm/drop_caches 2>/dev/null' EXIT

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
