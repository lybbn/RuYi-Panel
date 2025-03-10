#!/bin/bash
#mysql安装
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
export PATH
LANG=en_US.UTF-8

RUYI_TEMP_PATH="/ruyi/tmp"
OPENSSL_PATH="/usr/local/ruyi/openssl"
NGINX_SETUP_PATH="/ruyi/server/nginx"

action_type=$1
nginx_version=$2
#大版本
nginx_version_2=$3
jemallocLD=""

cpu_core=$(cat /proc/cpuinfo|grep processor|wc -l)

# 检查是否以 root 用户运行
if [ "$(id -u)" -ne 0 ]; then
    echo "请以 root 用户运行此脚本"
    exit 1
fi

Service_Add() {
	cat <<EOF > /etc/systemd/system/nginx.service
[Unit]
Description=Nginx RuYi Server
After=network.target

[Service]
Type=forking
PIDFile=/ruyi/server/nginx/logs/nginx.pid
ExecStart=/ruyi/server/nginx/sbin/nginx
ExecReload=/ruyi/server/nginx/sbin/nginx -s reload
ExecStop=/ruyi/server/nginx/sbin/nginx -s quit
User=root
Group=root
Restart=no
PrivateTmp=True

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable nginx
}

Return_Error() {
	echo '=================================================';
	printf '\033[1;31;40m%b\033[0m\n' "$@";
	exit 1;
}

Service_Del() {
    if [ -f "/etc/systemd/system/nginx.service" ];then
        systemctl stop nginx > /dev/null
        systemctl disable nginx > /dev/null
        rm -f /etc/systemd/system/nginx.service > /dev/null
        rm -rf /etc/systemd/system/multi-user.target.wants/nginx.service > /dev/null
        systemctl daemon-reload
    fi
}

Install_lib() {
    if [[ -f /etc/os-release ]]; then
        local os_info
        os_info=$(< /etc/os-release)
        local ID
        ID=$(echo "$os_info" | grep "^ID=" | cut -d'=' -f2 | tr -d '"')
        case $ID in
            ubuntu|debian)
                LIBCURL_VER=$(dpkg -l | grep libx11-6 | awk '{print $3}')
                if [ "${LIBCURL_VER}" == "2:1.6.9-2ubuntu1.3" ]; then
                    apt-get remove libx11* -y
                    apt-get install libpcre3-dev ruby zlib1g zlib1g.dev libx11-6 libx11-dev libx11-data -y
                fi
                Packs="gcc g++ libgd3 libgd-dev libevent-dev libncurses5-dev libreadline-dev uuid-dev"
                apt-get install ${Packs} -y
                ;;
            centos|fedora|rhel)
                Packs="gcc gcc-c++ gd-devel curl pcre pcre-devel zlib zlib-devel curl-devel libtermcap-devel ncurses-devel libevent-devel readline-devel libuuid-devel"
                yum install ${Packs} -y
                ;;
            arch)
                Return_Error "不支持的系统OS: $ID"
                ;;
            opensuse)
                Return_Error "不支持的系统OS: $ID"
                ;;
            *)
                Return_Error "不支持的系统OS: $ID"
                ;;
        esac
        echo "依赖包安装完成."
    else
        Return_Error "无法检测当前系统OS"
    fi
}

Install_Jemalloc() {
    cd /tmp
    if [ ! -f '/usr/local/lib/libjemalloc.so' ]; then
        wget https://github.com/jemalloc/jemalloc/releases/download/5.2.1/jemalloc-5.2.1.tar.bz2
        tar -xjf jemalloc-5.2.1.tar.bz2
        cd jemalloc-5.2.1
        ./configure
        make -j${cpu_core}
        make install
        ldconfig
        cd ..
        rm -rf jemalloc*
    fi
}

Install_Soft() {
    [ -f "/etc/init.d/nginx" ] && /etc/init.d/nginx stop
    if [ -f "/etc/systemd/system/nginx.service" ];then
        systemctl stop nginx > /dev/null
    fi
    if ! getent group www > /dev/null; then
        groupadd www
    fi
    if ! id -u www > /dev/null 2>&1; then
        useradd -s /sbin/nologin -g www www
    fi
    Install_lib
    Install_Jemalloc
    if [ -f "/usr/local/lib/libjemalloc.so" ] && [ -z "${ARM_CHECK}" ]; then
        jemallocLD="--with-ld-opt="-ljemalloc""
    fi
    ENABLE_HTTP2="--with-http_v2_module --with-stream --with-stream_ssl_module --with-stream_ssl_preread_module"
    rm -rf /ruyi/server/nginx
    mkdir /ruyi/server/nginx
    cd ${RUYI_TEMP_PATH}
    ENABLE_LUA=""
    if [ "${nginx_version_2}" == "openresty" ]; then
        ENABLE_LUA="--with-luajit"
        mv openresty-$nginx_version.tar.gz nginx-$nginx_version.tar.gz
    fi

    tar -zxf nginx-$nginx_version.tar.gz

    if [ "${nginx_version_2}" == "openresty" ]; then
        mv openresty-$nginx_version nginx-$nginx_version
    fi

    cd nginx-$nginx_version
    mkdir module3lib
    cd module3lib/

    if [ "${nginx_version_2}" == "openresty" ]; then
        withPcre=""
    else
        pcre_version="10.44"
        wget https://github.com/PCRE2Project/pcre2/releases/download/pcre2-${pcre_version}/pcre2-${pcre_version}.tar.gz
        tar zxf pcre2-$pcre_version.tar.gz
        rm -rf pcre2-$pcre_version.tar.gz
        withPcre="--with-pcre=${RUYI_TEMP_PATH}/nginx-$nginx_version/module3lib/pcre2-${pcre_version}"
    fi

    opensslVersion="1.1.1w"
    wget https://github.com/openssl/openssl/releases/download/OpenSSL_1_1_1w/openssl-${opensslVersion}.tar.gz
	tar -zxf openssl-${opensslVersion}.tar.gz
    mv openssl-${opensslVersion} openssl
    rm -rf openssl-${opensslVersion}.tar.gz

    if [ "${nginx_version_2}" == "openresty" ]; then
        NGX_CHACHE_PURGE=""
    else
        wget -O ngx_cache_purge-2.3.tar.gz https://github.com/FRiCKLE/ngx_cache_purge/archive/refs/tags/2.3.tar.gz
        tar -zxf ngx_cache_purge-2.3.tar.gz
        mv ngx_cache_purge-2.3 ngx_cache_purge
        rm -rf ngx_cache_purge-2.3.tar.gz
        NGX_CHACHE_PURGE="--add-module=${RUYI_TEMP_PATH}/nginx-$nginx_version/module3lib/ngx_cache_purge"
    fi
    
    cd ..
    #
    ./configure --user=www --group=www --prefix=${NGINX_SETUP_PATH} ${NGX_CHACHE_PURGE} ${ENABLE_LUA} ${withPcre}  --with-openssl=${RUYI_TEMP_PATH}/nginx-$nginx_version/module3lib/openssl ${ENABLE_HTTP2} --with-http_stub_status_module --with-http_ssl_module --with-http_image_filter_module --with-http_gzip_static_module --with-http_gunzip_module --with-http_sub_module --with-http_flv_module --with-http_addition_module --with-http_realip_module --with-http_mp4_module --with-ld-opt="-Wl,-E" --with-cc-opt="-Wno-error" ${jemallocLD}
    if [ $? -ne 0 ]; then
        cd ..
        rm -rf nginx-$nginx_version
        Return_Error "配置失败，退出安装"
    fi
    echo "==================================================="
    echo "正在编译..."
    echo "==================================================="
    make -j${cpu_core}
    if [ $? -ne 0 ]; then
        cd ..
        rm -rf nginx-$nginx_version
        Return_Error "编译失败，退出安装"
    fi
    echo "==================================================="
    echo "正在安装..."
    echo "==================================================="
    make install

    if [ "${nginx_version_2}" == "openresty" ]; then
        ln -sf /ruyi/server/nginx/nginx/html /ruyi/server/nginx/html
        ln -sf /ruyi/server/nginx/nginx/conf /ruyi/server/nginx/conf
        ln -sf /ruyi/server/nginx/nginx/logs /ruyi/server/nginx/logs
        ln -sf /ruyi/server/nginx/nginx/sbin /ruyi/server/nginx/sbin
    fi
    
    mkdir -p /ruyi/server/nginx/temp/proxy_cache_dir
    chown -R www:www /ruyi/server/nginx/temp
    chmod 755 /ruyi/server/nginx/temp
    echo "==================================================="
    echo "正在配置nginx..."
    echo "==================================================="
    cd ${RUYI_TEMP_PATH}/
    rm -rf nginx-$nginx_version
    rm -rf nginx-$nginx_version.tar.gz
    Service_Add
}

Uninstall_soft() {
    Service_Del
    rm -rf /ruyi/server/nginx
    rm -rf /etc/systemd/system/nginx.service > /dev/null
    rm -rf /etc/systemd/system/multi-user.target.wants/nginx.service > /dev/null
}

if [ "$action_type" == 'install' ];then
    if [ -z "${nginx_version}" ]; then
        exit
    fi
    if [ -z "${nginx_version_2}" ]; then
        exit
    fi
	Install_Soft
elif [ "$action_type" == 'uninstall' ];then
	Uninstall_soft
fi
