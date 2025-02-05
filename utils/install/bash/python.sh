#!/bin/bash
#python环境安装
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
export PATH
LANG=en_US.UTF-8

RUYI_TEMP_PATH="/ruyi/tmp"

action_type=$1
python_version=$2
python_file_name=$3
cpu_core=$(cat /proc/cpuinfo|grep processor|wc -l)
install_sys_path="/usr/local/ruyi"
OPENSSL_DIR=/usr/local/ruyi/openssl
Sqlite3_Env_Path=/usr/local/ruyi/sqlite3
WITH_SSL=""

# 检查是否以 root 用户运行
if [ "$(id -u)" -ne 0 ]; then
    echo "请以 root 用户运行此脚本" >&2
    exit 1
fi

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
    cd ${RUYI_TEMP_PATH}
    tar -zxf $python_file_name
    python_unzip_file_name=$(basename "$python_file_name" .tgz)
    py_path=/ruyi/server/python/${python_version}
    rm -rf $py_path > /dev/null 2>&1
	mkdir -p ${py_path}
	echo "True" > ${py_path}/disk.ry
	if [ ! -w ${py_path}/disk.ry ];then
		echo "ERROR: Install python fielded." "ERROR: $py_path 目录无法写入，请检查目录/用户/磁盘权限！" >&2
        exit 1
	fi
	cd ${python_unzip_file_name}
    echo "==================================================="
    echo "正在配置..."
    echo "==================================================="
	if [ ${python_version:2:2} -ge 10 ]; then
        if [ -f ${OPENSSL_DIR}/bin/openssl ];then
            echo "检测到OpenSSL版本符合要求，无需再安装"
            echo "=============================================="
            WITH_SSL="--with-openssl=${OPENSSL_DIR} --with-openssl-rpath=auto"
		elif command -v openssl >/dev/null 2>&1; then
            local openssl_version
            openssl_version=$(openssl version | awk '{print $2}' | grep -o '[0-9]\+\.[0-9]\+\.[0-9]\+')
            target_version="1.1.1"
            if [[ "$(echo -e "$openssl_version\n$target_version" | sort -V | head -n1)" == "$target_version" ]]; then
                echo "当前OpenSSL为${openssl_version}，符合要求"
                WITH_SSL=""
            else
                echo "当前OpenSSL为${openssl_version}，不符合要求，尝试安装指定版本OpenSSL"
                Install_Openssl
                WITH_SSL="--with-openssl=${OPENSSL_DIR} --with-openssl-rpath=auto"
            fi
            
        else
            echo  "检测到OpenSSL未安装，正在安装支持Python${python_version}版本的openssl"
            Install_Openssl
        fi

        if [ ${python_version:2:2} -ge 12 ]; then
            ./configure --prefix=${py_path} ${WITH_SSL} --without-pgo
        else
            ./configure --prefix=${py_path} ${WITH_SSL} --with-sqlite3=${Sqlite3_Env_Path}
        fi

	else
        ./configure --prefix=${py_path} --with-sqlite3=${Sqlite3_Env_Path}
    fi
    cd ${RUYI_TEMP_PATH}
    cd ${python_unzip_file_name}
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
    rm -rf /ruyi/server/python/${python_version}
}

if [ "$action_type" == 'install' ];then
    if [ -z "${python_version}" ] || [ -z "${python_file_name}" ]; then
        echo "参数错误" >&2
        exit 1
    fi
	Install_Soft
elif [ "$action_type" == 'uninstall' ];then
    if [ -z "${python_version}" ];then
        echo "参数错误" >&2
        exit 1
    fi
	Uninstall_soft
fi
