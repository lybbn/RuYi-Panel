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
install_type=$4  #1=编译安装 2=快速安装（二进制）
jemallocLD=""

IsCentos7=""
IsCentos8=""
if [ -f /etc/redhat-release ]; then
    IsCentos7=$(cat /etc/redhat-release | grep ' 7.' | grep -iE 'centos')
    IsCentos8=$(cat /etc/redhat-release | grep ' 8.' | grep -iE 'centos|Red Hat')
fi

cpu_core=$(cat /proc/cpuinfo|grep processor|wc -l)
ARCH=$(uname -m)

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
        wget -c -O lua-${LUA_VERSION}.tar.gz http://download.lybbn.cn/ruyi/install/linux/nginx/lua-${LUA_VERSION}.tar.gz
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
    wget -c -O LuaJIT-2.1-20240815.zip http://download.lybbn.cn/ruyi/install/linux/nginx/LuaJIT-2.1-20240815.zip
    unzip -q -o LuaJIT-2.1-20240815.zip
    cd LuaJIT-2.1-20240815
    make -j${cpu_core}
    make install
    cd .. 
    rm -rf LuaJIT-2.1-20240815*
    export LUAJIT_LIB=/usr/local/lib
    export LUAJIT_INC=/usr/local/include/${LUAJIT_INC_PATH}
    if [ ! -d /usr/local/lib64 ]; then
        mkdir -p /usr/local/lib64
    fi
    rm -rf /usr/local/lib64/libluajit-5.1.so.2
    ln -sf /usr/local/lib/libluajit-5.1.so.2 /usr/local/lib64/libluajit-5.1.so.2
    LOCAL_LD_SO_CHECK1=$(cat /etc/ld.so.conf|grep /usr/local/lib)
    LOCAL_LD_SO_CHECK2=$(cat /etc/ld.so.conf.d/local.conf 2>/dev/null|grep /usr/local/lib)
    if [ -z "${LOCAL_LD_SO_CHECK1}" ] && [ -z "${LOCAL_LD_SO_CHECK2}" ];then
        echo "/usr/local/lib" >>/etc/ld.so.conf
    fi
    ldconfig
}

Install_Lua_cjson() {
    if [ ! -f /usr/local/lib/lua/5.1/cjson.so ]; then
        wget -c -O lua-cjson-2.1.0.9.zip http://download.lybbn.cn/ruyi/install/linux/nginx/lua-cjson-2.1.0.9.zip
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
    wget -c -O lua-nginx-module-${LuaNginxModuleVersion}.zip http://download.lybbn.cn/ruyi/install/linux/nginx/lua-nginx-module-${LuaNginxModuleVersion}.zip
    unzip -q -o lua-nginx-module-${LuaNginxModuleVersion}.zip
    mv lua-nginx-module-${LuaNginxModuleVersion} lua_nginx_module
    chmod +x lua_nginx_module/config
    rm -f lua-nginx-module-${LuaNginxModuleVersion}.zip

    NgxDevelKitVersion="0.3.3"
    wget -c -O ngx_devel_kit-${NgxDevelKitVersion}.zip http://download.lybbn.cn/ruyi/install/linux/nginx/ngx_devel_kit-${NgxDevelKitVersion}.zip
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
        wget http://download.lybbn.cn/ruyi/install/linux/nginx/jemalloc-${Jemalloc_Version}.tar.bz2
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

Install_Nginx_Binary() {
    echo "==================================================="
    echo "正在快速安装${nginx_version_2}-${nginx_version}"
    echo "==================================================="
    [ -f "/etc/init.d/nginx" ] && /etc/init.d/nginx stop
    if [ -f "/etc/systemd/system/nginx.service" ];then
        systemctl stop nginx > /dev/null
    fi
    # 停止已有的nginx/openresty进程
    if pgrep -x "nginx" > /dev/null; then
        pkill -9 nginx 2>/dev/null || true
        sleep 1
    fi

    if ! getent group www > /dev/null; then
        groupadd www
    fi
    if ! id -u www > /dev/null 2>&1; then
        useradd -s /sbin/nologin -g www www
    fi

    # 清理旧安装
    rm -rf ${NGINX_SETUP_PATH}

    # 通过包管理器从官方仓库安装，复制到 NGINX_SETUP_PATH 后卸载系统包
    if [ "${nginx_version_2}" == "openresty" ]; then
        echo "====================================="
        echo "通过包管理器安装 OpenResty..."
        echo "====================================="
        if [ -f "/usr/bin/apt-get" ];then
            export DEBIAN_FRONTEND=noninteractive
            # 安装依赖（wget、lsb-release 等）
            apt-get install -y --no-install-recommends wget gnupg ca-certificates lsb-release > /dev/null 2>&1
            # 确定仓库 URL 和 codename（支持回退到稳定版本）
            local repo_url=""
            local codename=$(lsb_release -sc 2>/dev/null || echo "")
            if [ -f /etc/debian_version ] && [ ! -f /etc/lsb-release ]; then
                # 纯 Debian 系统
                [ -z "${codename}" ] && codename="bookworm"
                repo_url="http://openresty.org/package/debian"
            else
                # Ubuntu 系统
                [ -z "${codename}" ] && codename="jammy"
                repo_url="http://openresty.org/package/ubuntu"
            fi
            # 写入仓库配置并验证可用性，不可用则回退到稳定版本
            # 使用 trusted=yes 因为 OpenResty GPG 密钥使用 SHA1，新版 Debian/Ubuntu 已拒绝 SHA1 签名
            local fallback_codenames=""
            if echo "${repo_url}" | grep -q "debian"; then
                fallback_codenames="bookworm bullseye"
            else
                fallback_codenames="jammy focal noble"
            fi
            echo "deb [trusted=yes] ${repo_url} ${codename} openresty" > /etc/apt/sources.list.d/openresty.list
            echo "[更新] 正在更新 ${codename} 仓库..."
            apt-get update -y 2>&1 | tail -3
            # 检查仓库是否可用（404 表示 codename 不被支持）
            if ! apt-cache policy openresty 2>/dev/null | grep -q "openresty"; then
                echo "[提示] OpenResty 仓库不支持 ${codename}，尝试回退..."
                local fallback_ok=0
                for fb in ${fallback_codenames}; do
                    if [ "${fb}" == "${codename}" ]; then continue; fi
                    rm -f /etc/apt/sources.list.d/openresty.list
                    echo "deb [trusted=yes] ${repo_url} ${fb} openresty" > /etc/apt/sources.list.d/openresty.list
                    echo "[尝试] 使用 ${fb} 仓库..."
                    apt-get update -y 2>&1 | tail -3
                    if apt-cache policy openresty 2>/dev/null | grep -q "openresty"; then
                        echo "[成功] 已回退到 ${fb} 仓库"
                        fallback_ok=1
                        break
                    fi
                done
                if [ ${fallback_ok} -eq 0 ]; then
                    echo "[警告] 所有仓库尝试失败，检查网络连接..."
                    cat /etc/apt/sources.list.d/openresty.list 2>/dev/null || echo "[错误] 仓库配置文件不存在"
                fi
            fi
            # 尝试安装指定版本，失败则安装最新版
            local install_output=""
            if [ -n "${nginx_version}" ] && [ "${nginx_version}" != "0.0.0" ]; then
                local pkg_version=$(echo "${nginx_version}" | sed 's/-/./g')
                install_output=$(apt-get install -y --allow-unauthenticated openresty=${pkg_version}* 2>&1) || \
                install_output=$(apt-get install -y --allow-unauthenticated openresty 2>&1)
            else
                install_output=$(apt-get install -y --allow-unauthenticated openresty 2>&1)
            fi
            if [ $? -ne 0 ]; then
                echo "[错误] apt-get install 输出:"
                echo "${install_output}" | tail -10
                Return_Error "OpenResty 安装失败: ${install_output##*$'\n'}"
            fi
        elif [ -f "/usr/bin/yum" ];then
            if [ ! -f /etc/yum.repos.d/openresty.repo ]; then
                yum install -y yum-utils > /dev/null 2>&1
                local os_ver=$(rpm -q --qf "%{VERSION}" $(rpm -qf /etc/redhat-release 2>/dev/null || echo "centos-release") 2>/dev/null | cut -d. -f1)
                cat > /etc/yum.repos.d/openresty.repo <<YUMEOF
[openresty]
name=Official OpenResty Open Source Repository for CentOS
baseurl=https://openresty.org/package/centos/${os_ver}/\$basearch
skip_if_unavailable=True
gpgcheck=1
repo_gpgcheck=0
gpgkey=https://openresty.org/package/pubkey.gpg
enabled=1
enabled_metadata=1
YUMEOF
            fi
            # 尝试安装指定版本，失败则安装最新版
            if [ -n "${nginx_version}" ] && [ "${nginx_version}" != "0.0.0" ]; then
                local pkg_version=$(echo "${nginx_version}" | sed 's/-/./g')
                yum install -y openresty-${pkg_version} > /dev/null 2>&1 || \
                yum install -y openresty > /dev/null 2>&1
            else
                yum install -y openresty > /dev/null 2>&1
            fi
            if [ $? -ne 0 ]; then
                Return_Error "OpenResty 安装失败，请检查网络连接"
            fi
        else
            Return_Error "不支持的包管理器，无法快速安装"
        fi
        # OpenResty 通过包管理器安装到 /usr/local/openresty
        local or_install_path="/usr/local/openresty"
        if [ ! -d "${or_install_path}" ]; then
            Return_Error "OpenResty 安装目录不存在: ${or_install_path}"
        fi
        # 通过符号链接映射到如意面板标准路径（无需复制，包管理器可正常升级）
        # OpenResty 目录结构: /usr/local/openresty/nginx/{sbin,conf,logs,html}
        # 面板期望结构: /ruyi/server/nginx/{sbin,conf,logs,html}
        mkdir -p ${NGINX_SETUP_PATH}
        ln -sf ${or_install_path}/nginx/sbin ${NGINX_SETUP_PATH}/sbin
        ln -sf ${or_install_path}/nginx/conf ${NGINX_SETUP_PATH}/conf
        ln -sf ${or_install_path}/nginx/logs ${NGINX_SETUP_PATH}/logs
        ln -sf ${or_install_path}/nginx/html ${NGINX_SETUP_PATH}/html
        ln -sf ${or_install_path}/luajit ${NGINX_SETUP_PATH}/luajit
        ln -sf ${or_install_path}/bin ${NGINX_SETUP_PATH}/bin
        # pod目录不一定存在，仅在存在时创建链接
        [ -d "${or_install_path}/pod" ] && ln -sf ${or_install_path}/pod ${NGINX_SETUP_PATH}/pod
        # OpenResty 内置 LuaJIT，设置库路径供 lua-cjson 编译使用
        if [ -f "${or_install_path}/luajit/lib/libluajit-5.1.so.2" ]; then
            ln -sf ${or_install_path}/luajit/lib/libluajit-5.1.so.2 /usr/local/lib/libluajit-5.1.so.2
            ln -sf ${or_install_path}/luajit/lib/libluajit-5.1.so.2 /usr/local/lib64/libluajit-5.1.so.2
            export LUAJIT_LIB=${or_install_path}/luajit/lib
            export LUAJIT_INC=${or_install_path}/luajit/include/luajit-2.1
            ldconfig
        fi
        # 安装 lua-cjson（WAF功能依赖）
        Install_Lua_cjson
        local installed_ver=$(${NGINX_SETUP_PATH}/sbin/nginx -v 2>&1 | grep -oP '[\d.]+' | head -1)
        echo "OpenResty ${installed_ver} 安装完成（支持 WAF/Lua），路径: ${NGINX_SETUP_PATH}"
    else
        echo "====================================="
        echo "通过包管理器安装 Nginx..."
        echo "====================================="
        if [ -f "/usr/bin/apt-get" ];then
            export DEBIAN_FRONTEND=noninteractive
            # 安装依赖
            apt-get install -y --no-install-recommends wget gnupg ca-certificates lsb-release > /dev/null 2>&1
            # 确定仓库 URL 和 codename（支持回退到稳定版本）
            local repo_url=""
            local codename=$(lsb_release -sc 2>/dev/null || echo "")
            if [ -f /etc/debian_version ] && [ ! -f /etc/lsb-release ]; then
                [ -z "${codename}" ] && codename="bookworm"
                repo_url="https://nginx.org/packages/mainline/debian"
            else
                [ -z "${codename}" ] && codename="jammy"
                repo_url="https://nginx.org/packages/mainline/ubuntu"
            fi
            # 写入仓库配置并验证可用性（使用 trusted=yes 避免 GPG SHA1 签名问题）
            local fallback_codenames=""
            if echo "${repo_url}" | grep -q "debian"; then
                fallback_codenames="bookworm bullseye"
            else
                fallback_codenames="jammy focal noble"
            fi
            echo "deb [trusted=yes] ${repo_url} ${codename} nginx" > /etc/apt/sources.list.d/nginx.list
            echo "[更新] 正在更新 ${codename} 仓库..."
            apt-get update -y 2>&1 | tail -3
            if ! apt-cache policy nginx 2>/dev/null | grep -q "nginx"; then
                echo "[提示] Nginx 仓库不支持 ${codename}，尝试回退..."
                local fallback_ok=0
                for fb in ${fallback_codenames}; do
                    if [ "${fb}" == "${codename}" ]; then continue; fi
                    rm -f /etc/apt/sources.list.d/nginx.list
                    echo "deb [trusted=yes] ${repo_url} ${fb} nginx" > /etc/apt/sources.list.d/nginx.list
                    echo "[尝试] 使用 ${fb} 仓库..."
                    apt-get update -y 2>&1 | tail -3
                    if apt-cache policy nginx 2>/dev/null | grep -q "nginx"; then
                        echo "[成功] 已回退到 ${fb} 仓库"
                        fallback_ok=1
                        break
                    fi
                done
                if [ ${fallback_ok} -eq 0 ]; then
                    echo "[警告] 所有仓库尝试失败，检查网络连接..."
                    cat /etc/apt/sources.list.d/nginx.list 2>/dev/null || echo "[错误] 仓库配置文件不存在"
                fi
            fi
            # 尝试安装指定版本，失败则安装最新版
            local install_output=""
            if [ -n "${nginx_version}" ] && [ "${nginx_version}" != "0.0.0" ]; then
                install_output=$(apt-get install -y --allow-unauthenticated nginx=${nginx_version}* 2>&1) || \
                install_output=$(apt-get install -y --allow-unauthenticated nginx 2>&1)
            else
                install_output=$(apt-get install -y --allow-unauthenticated nginx 2>&1)
            fi
            if [ $? -ne 0 ]; then
                echo "[错误] apt-get install 输出:"
                echo "${install_output}" | tail -10
                Return_Error "Nginx 安装失败: ${install_output##*$'\n'}"
            fi
        elif [ -f "/usr/bin/yum" ];then
            if [ ! -f /etc/yum.repos.d/nginx.repo ]; then
                local os_ver=$(rpm -q --qf "%{VERSION}" $(rpm -qf /etc/redhat-release 2>/dev/null || echo "centos-release") 2>/dev/null | cut -d. -f1)
                cat > /etc/yum.repos.d/nginx.repo <<YUMEOF
[nginx-mainline]
name=nginx mainline repo
baseurl=http://nginx.org/packages/mainline/centos/${os_ver}/\$basearch/
gpgcheck=1
enabled=1
gpgkey=https://nginx.org/keys/nginx_signing.key
module_hotfixes=true
YUMEOF
            fi
            # 尝试安装指定版本，失败则安装最新版
            if [ -n "${nginx_version}" ] && [ "${nginx_version}" != "0.0.0" ]; then
                yum install -y nginx-${nginx_version} > /dev/null 2>&1 || \
                yum install -y nginx > /dev/null 2>&1
            else
                yum install -y nginx > /dev/null 2>&1
            fi
            if [ $? -ne 0 ]; then
                Return_Error "Nginx 安装失败，请检查网络连接"
            fi
        else
            Return_Error "不支持的包管理器，无法快速安装"
        fi
        # Nginx 包管理器安装到分散路径，通过符号链接映射到 NGINX_SETUP_PATH
        # 注意：标准 Nginx 包不包含 lua-nginx-module，不支持 WAF/Lua 功能
        # 如需 WAF 功能，请选择 OpenResty 或使用编译安装方式
        echo "[提示] 标准 Nginx 快速安装不支持 WAF/Lua，如需 WAF 请选择 OpenResty"
        # 通过符号链接映射到如意面板标准路径（无需复制，包管理器可正常升级）
        # conf -> /etc/nginx, logs -> /var/log/nginx, html -> /usr/share/nginx/html
        # nginx.conf 中的路径无需修改，符号链接已正确映射
        mkdir -p ${NGINX_SETUP_PATH}
        mkdir -p ${NGINX_SETUP_PATH}/sbin
        ln -sf /usr/sbin/nginx ${NGINX_SETUP_PATH}/sbin/nginx
        ln -sf /etc/nginx ${NGINX_SETUP_PATH}/conf
        ln -sf /var/log/nginx ${NGINX_SETUP_PATH}/logs
        ln -sf /usr/share/nginx/html ${NGINX_SETUP_PATH}/html
        local installed_ver=$(${NGINX_SETUP_PATH}/sbin/nginx -v 2>&1 | grep -oP '[\d.]+' | head -1)
        echo "Nginx ${installed_ver} 安装完成（不支持 WAF/Lua），路径: ${NGINX_SETUP_PATH}"
    fi

    # 确保sbin/nginx可执行
    if [ -f "${NGINX_SETUP_PATH}/sbin/nginx" ]; then
        chmod +x ${NGINX_SETUP_PATH}/sbin/nginx
    fi

    mkdir -p ${NGINX_SETUP_PATH}/temp/proxy_cache_dir
    chown -R www:www ${NGINX_SETUP_PATH}/temp
    chmod 755 ${NGINX_SETUP_PATH}/temp
    echo "==================================================="
    echo "正在配置${nginx_version_2}..."
    echo "==================================================="
    Service_Add
    ldconfig
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
        echo "==================================================="
        echo "开始下载pcre2 for openresty..."
        echo "==================================================="
        pcre_version="10.44"
        wget http://download.lybbn.cn/ruyi/install/linux/nginx/pcre2-${pcre_version}.tar.gz
        tar zxf pcre2-$pcre_version.tar.gz
        rm -rf pcre2-$pcre_version.tar.gz
        echo "==================================================="
        echo "开始编译pcre2..."
        echo "==================================================="
        cd pcre2-$pcre_version
        ./configure
        make -j${cpu_core}
        make install
        cd ..
        withPcre="--with-pcre=${RUYI_TEMP_PATH}/nginx-$nginx_version/module3lib/pcre2-${pcre_version}"
    else
        echo "==================================================="
        echo "开始下载pcre2..."
        echo "==================================================="
        pcre_version="10.44"
        wget http://download.lybbn.cn/ruyi/install/linux/nginx/pcre2-${pcre_version}.tar.gz
        tar zxf pcre2-$pcre_version.tar.gz
        rm -rf pcre2-$pcre_version.tar.gz
        echo "==================================================="
        echo "开始编译pcre2..."
        echo "==================================================="
        cd pcre2-$pcre_version
        ./configure
        make -j${cpu_core}
        cd ..
        withPcre="--with-pcre=${RUYI_TEMP_PATH}/nginx-$nginx_version/module3lib/pcre2-${pcre_version}"
    fi

    echo "==================================================="
    echo "开始下载openssl..."
    echo "==================================================="
    opensslVersion="1.1.1w"
    #wget https://github.com/openssl/openssl/releases/download/OpenSSL_1_1_1w/openssl-${opensslVersion}.tar.gz
    wget http://download.lybbn.cn/ruyi/install/linux/nginx/openssl-${opensslVersion}.tar.gz
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
        wget http://download.lybbn.cn/ruyi/install/linux/nginx/ngx_cache_purge-2.3.tar.gz
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
        wget -c -O lua-resty-core-0.1.30.zip http://download.lybbn.cn/ruyi/install/linux/nginx/lua-resty-core-0.1.30.zip
        unzip -q lua-resty-core-0.1.30.zip
        cd lua-resty-core-0.1.30
        make install LUA_LIB_DIR=${NGINX_SETUP_PATH}/lib/lua
        cd ..
        rm -rf lua-resty-core-0.1.30*

        wget -c -O lua-resty-lrucache-0.15.zip http://download.lybbn.cn/ruyi/install/linux/nginx/lua-resty-lrucache-0.15.zip
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

# 释放Linux文件系统缓存（page cache）
trap 'sync && echo 3 > /proc/sys/vm/drop_caches 2>/dev/null' EXIT

if [ "$action_type" == 'install' ];then
    if [ -z "${nginx_version}" ]; then
        echo "参数错误" >&2
        exit 1
    fi
    if [ -z "${nginx_version_2}" ]; then
        echo "参数错误" >&2
        exit 1
    fi
    if [ "$install_type" == '2' ];then
        Install_Nginx_Binary
    else
        Install_Soft
    fi
elif [ "$action_type" == 'uninstall' ];then
	Uninstall_soft
fi
