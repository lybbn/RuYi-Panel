#!/bin/bash
#nginx安装
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

IsCentos7=$(cat /etc/redhat-release | grep ' 7.' | grep -iE 'centos')
IsCentos8=$(cat /etc/redhat-release | grep ' 8.' | grep -iE 'centos|Red Hat')

cpu_core=$(cat /proc/cpuinfo|grep processor|wc -l)

# 检查是否以 root 用户运行
if [ "$(id -u)" -ne 0 ]; then
    echo "请以 root 用户运行此脚本" >&2
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
	echo '================================================='
	echo "$@" >&2
	exit 1
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
                apt-get install libgd-dev -y
                ;;
            centos|fedora|rhel|alinux)
                Packs="gcc gcc-c++ curl pcre pcre-devel zlib zlib-devel curl-devel ncurses-devel libevent-devel readline-devel libuuid-devel"
                yum install ${Packs} -y
                #单独安装，如果不存在则不影响上面库安装
                yum install jemalloc -y
                yum install libtermcap-devel -y
                yum install gd gd-devel -y
                yum install gd-devel* -y
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

Get_platform() {
    local os_name
    os_name=$(uname -s 2>/dev/null)

    if [[ -z "$os_name" ]]; then
        echo "unknown"
        return 1
    fi

    case "$os_name" in
        Linux)       echo "linux" ;;
        FreeBSD)     echo "freebsd" ;;
        *BSD*)       echo "bsd" ;;
        Darwin)      echo "macosx" ;;
        CYGWIN*|MINGW*|MSYS*) echo "mingw" ;;
        AIX)         echo "aix" ;;
        SunOS)       echo "solaris" ;;
        *)           echo "unknown"
    esac
}

Install_Lua() {
    if [ ! -f /usr/local/bin/lua ]; then
        #5.4.7不兼容，使用老版本5.1.5
        LUA_VERSION="5.1.5"
        wget -c -O lua-${LUA_VERSION}.tar.gz https://download.lybbn.cn/ruyi/install/linux/nginx/lua-${LUA_VERSION}.tar.gz
        tar zxf lua-${LUA_VERSION}.tar.gz
        cd lua-${LUA_VERSION}
        #5.4.7版本使用make all test
        local platform=$(Get_platform)
        if [ "${platform}" = "unknown" ];then
            platform="linux"
        fi
        make ${platform}
        make install
        cd ..
        rm -rf lua-${LUA_VERSION}*
    fi
}

Install_LuaJIT() {
    LUAJIT_INC_PATH="luajit-2.1"
    wget -c -O LuaJIT-2.1-20240815.zip https://download.lybbn.cn/ruyi/install/linux/nginx/LuaJIT-2.1-20240815.zip
    unzip -q -o LuaJIT-2.1-20240815.zip
    cd LuaJIT-2.1-20240815
    make -j${cpu_core}
    make install
    cd .. 
    rm -rf LuaJIT-2.1-20240815*
    export LUAJIT_LIB=/usr/local/lib
    export LUAJIT_INC=/usr/local/include/${LUAJIT_INC_PATH}
    rm -rf /usr/local/lib64/libluajit-5.1.so.2
    ln -sf /usr/local/lib/libluajit-5.1.so.2 /usr/local/lib64/libluajit-5.1.so.2
    LOCAL_LD_SO_CHECK1=$(cat /etc/ld.so.conf|grep /usr/local/lib)
    LOCAL_LD_SO_CHECK2=$(cat cat /etc/ld.so.conf.d/local.conf|grep /usr/local/lib)
    if [ -z "${LOCAL_LD_SO_CHECK1}" ] && [ -z "${LOCAL_LD_SO_CHECK2}" ];then
        echo "/usr/local/lib" >>/etc/ld.so.conf
    fi
    ldconfig
}

Install_Lua_cjson() {
    if [ ! -f /usr/local/lib/lua/5.1/cjson.so ]; then
        wget -c -O lua-cjson-2.1.0.9.zip https://download.lybbn.cn/ruyi/install/linux/nginx/lua-cjson-2.1.0.9.zip
        unzip -q -o lua-cjson-2.1.0.9.zip
        cd lua-cjson-2.1.0.9
        make
        make install
        cd ..
        rm -rf lua-cjson-2.1.0.9*
    fi
}

WAF_LIB_ENABLE=""

Download_WAF_Lib() {
    #版本要与其他匹配，不能乱升级，否则启动nginx报错 failed to load the 'resty.core' module
    LuaNginxModuleVersion="0.10.27"
    wget -c -O lua-nginx-module-${LuaNginxModuleVersion}.zip https://download.lybbn.cn/ruyi/install/linux/nginx/lua-nginx-module-${LuaNginxModuleVersion}.zip
    unzip -q -o lua-nginx-module-${LuaNginxModuleVersion}.zip
    mv lua-nginx-module-${LuaNginxModuleVersion} lua_nginx_module
    chmod +x lua_nginx_module/config
    rm -f lua-nginx-module-${LuaNginxModuleVersion}.zip

    NgxDevelKitVersion="0.3.3"
    wget -c -O ngx_devel_kit-${NgxDevelKitVersion}.zip https://download.lybbn.cn/ruyi/install/linux/nginx/ngx_devel_kit-${NgxDevelKitVersion}.zip
    unzip -q -o ngx_devel_kit-${NgxDevelKitVersion}.zip
    mv ngx_devel_kit-${NgxDevelKitVersion} ngx_devel_kit
    rm -f ngx_devel_kit-${NgxDevelKitVersion}.zip

    WAF_LIB_ENABLE="--add-module=${RUYI_TEMP_PATH}/nginx-$nginx_version/module3lib/ngx_devel_kit --add-module=${RUYI_TEMP_PATH}/nginx-$nginx_version/module3lib/lua_nginx_module"
}

Install_Jemalloc() {
    cd /tmp
    if [ ! -f '/usr/local/lib/libjemalloc.so' ]; then
        echo "==================================================="
        echo "正在安装jemalloc..."
        echo "==================================================="
        if [ "${IsCentos8}" ] || [ "${IsCentos7}" ];then
            Jemalloc_Version="5.2.1"
        else
            Jemalloc_Version="5.3.0"
        fi
        # wget https://github.com/jemalloc/jemalloc/releases/download/5.2.1/jemalloc-5.2.1.tar.bz2
        wget https://download.lybbn.cn/ruyi/install/linux/nginx/jemalloc-${Jemalloc_Version}.tar.bz2
        tar -xjf jemalloc-${Jemalloc_Version}.tar.bz2
        cd jemalloc-${Jemalloc_Version}
        ./configure
        make -j${cpu_core}
        make install
        echo '/usr/local/lib' > /etc/ld.so.conf.d/local.conf
        ldconfig
        cd ..
        rm -rf jemalloc*
    fi
}

Install_Soft() {
    echo "==================================================="
    echo "正在安装nginx-$nginx_version"
    echo "==================================================="
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
    Install_Lua
    Install_Jemalloc
    Install_LuaJIT
    Install_Lua_cjson
    if [ -f "/usr/local/lib/libjemalloc.so" ]; then
        jemallocLD="--with-ld-opt="-ljemalloc""
    fi
    
    ENABLE_HTTP2="--with-http_v2_module --with-stream --with-stream_ssl_module --with-stream_ssl_preread_module"
    ENABLE_HTTP3="--with-http_v3_module"

    rm -rf /ruyi/server/nginx
    mkdir /ruyi/server/nginx
    cd ${RUYI_TEMP_PATH}
    ENABLE_LUA=""
    if [ "${nginx_version_2}" == "openresty" ]; then
        ENABLE_LUA="--with-luajit"
        mv openresty-$nginx_version.tar.gz nginx-$nginx_version.tar.gz
    fi
    echo "==================================================="
    echo "开始解压nginx..."
    echo "==================================================="
    rm -rf nginx-$nginx_version
    tar -zxf nginx-$nginx_version.tar.gz
    if [ "${nginx_version_2}" == "openresty" ]; then
        mv openresty-$nginx_version nginx-$nginx_version
    fi

    cd nginx-$nginx_version
    mkdir module3lib
    cd module3lib/

    if [ "${nginx_version_2}" == "openresty" ]; then
        echo "==================================================="
        echo "openresty无需下载LUA环境Lib"
        echo "==================================================="
    else
        echo "==================================================="
        echo "开始下载LUA环境Lib..."
        echo "==================================================="
        Download_WAF_Lib
    fi
    

    if [ "${nginx_version_2}" == "openresty" ]; then
        withPcre=""
    else
        echo "==================================================="
        echo "开始下载pcre2..."
        echo "==================================================="
        pcre_version="10.44"
        # wget https://github.com/PCRE2Project/pcre2/releases/download/pcre2-${pcre_version}/pcre2-${pcre_version}.tar.gz
        wget https://download.lybbn.cn/ruyi/install/linux/nginx/pcre2-${pcre_version}.tar.gz
        tar zxf pcre2-$pcre_version.tar.gz
        rm -rf pcre2-$pcre_version.tar.gz
        withPcre="--with-pcre=${RUYI_TEMP_PATH}/nginx-$nginx_version/module3lib/pcre2-${pcre_version}"
    fi

    echo "==================================================="
    echo "开始下载openssl..."
    echo "==================================================="
    opensslVersion="1.1.1w"
    #wget https://github.com/openssl/openssl/releases/download/OpenSSL_1_1_1w/openssl-${opensslVersion}.tar.gz
    wget https://download.lybbn.cn/ruyi/install/linux/nginx/openssl-${opensslVersion}.tar.gz
	tar -zxf openssl-${opensslVersion}.tar.gz
    mv openssl-${opensslVersion} openssl
    rm -rf openssl-${opensslVersion}.tar.gz

    if [ "${nginx_version_2}" == "openresty" ]; then
        NGX_CHACHE_PURGE=""
    else
        # wget -O ngx_cache_purge-2.3.tar.gz https://github.com/FRiCKLE/ngx_cache_purge/archive/refs/tags/2.3.tar.gz
        echo "==================================================="
        echo "开始下载ngx_cache_purge..."
        echo "==================================================="
        wget https://download.lybbn.cn/ruyi/install/linux/nginx/ngx_cache_purge-2.3.tar.gz
        tar -zxf ngx_cache_purge-2.3.tar.gz
        mv ngx_cache_purge-2.3 ngx_cache_purge
        rm -rf ngx_cache_purge-2.3.tar.gz
        NGX_CHACHE_PURGE="--add-module=${RUYI_TEMP_PATH}/nginx-$nginx_version/module3lib/ngx_cache_purge"
    fi
    
    cd ${RUYI_TEMP_PATH}/nginx-$nginx_version

    echo "==================================================="
    echo "开始配置configure..."
    echo "==================================================="
    export LUAJIT_LIB=/usr/local/lib
    export LUAJIT_INC=/usr/local/include/${LUAJIT_INC_PATH}
    # export LD_LIBRARY_PATH=/usr/local/lib/:$LD_LIBRARY_PATH
    ./configure --user=www --group=www --prefix=${NGINX_SETUP_PATH} ${NGX_CHACHE_PURGE} ${ENABLE_LUA} ${withPcre} ${WAF_LIB_ENABLE} --with-openssl=${RUYI_TEMP_PATH}/nginx-$nginx_version/module3lib/openssl ${ENABLE_HTTP2} --with-http_stub_status_module --with-http_ssl_module --with-http_image_filter_module --with-http_gzip_static_module --with-http_gunzip_module --with-http_sub_module --with-http_flv_module --with-http_addition_module --with-http_realip_module --with-http_mp4_module --with-ld-opt="-Wl,-E" --with-cc-opt="-Wno-error" ${jemallocLD} ${ENABLE_HTTP3}
    if [ $? -ne 0 ]; then
        cd ..
        # rm -rf nginx-$nginx_version
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
        echo "==================================================="
        echo "跳过额外lua依赖库安装"
        echo "==================================================="
    else
        echo "==================================================="
        echo "开始安装LUA额外依赖库..."
        echo "==================================================="
        wget -c -O lua-resty-core-0.1.30.zip https://download.lybbn.cn/ruyi/install/linux/nginx/lua-resty-core-0.1.30.zip
        unzip -q lua-resty-core-0.1.30.zip
        cd lua-resty-core-0.1.30
        make install LUA_LIB_DIR=${NGINX_SETUP_PATH}/lib/lua
        cd ..
        rm -rf lua-resty-core-0.1.30*

        wget -c -O lua-resty-lrucache-0.15.zip https://download.lybbn.cn/ruyi/install/linux/nginx/lua-resty-lrucache-0.15.zip
        unzip -q lua-resty-lrucache-0.15.zip
        cd lua-resty-lrucache-0.15
        make install LUA_LIB_DIR=${NGINX_SETUP_PATH}/lib/lua
        cd ..
        rm -rf lua-resty-lrucache-0.15*
    fi

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
        echo "参数错误" >&2
        exit 1
    fi
    if [ -z "${nginx_version_2}" ]; then
        echo "参数错误" >&2
        exit 1
    fi
	Install_Soft
elif [ "$action_type" == 'uninstall' ];then
	Uninstall_soft
fi
