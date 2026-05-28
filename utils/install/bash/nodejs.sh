#!/bin/bash
#nodejs环境安装
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
export PATH
LANG=en_US.UTF-8

RUYI_TEMP_PATH="/ruyi/tmp"

action_type=$1
nodejs_version=$2
nodejs_file_name=$3

nodejs_unzip_dir=""

cleanup_temp() {
    if [ -n "$nodejs_unzip_dir" ] && [ -d "$nodejs_unzip_dir" ]; then
        rm -rf "$nodejs_unzip_dir"
    fi
    rm -rf ${RUYI_TEMP_PATH}/node-v*
    sync && echo 3 > /proc/sys/vm/drop_caches 2>/dev/null
}
trap cleanup_temp EXIT

if [ "$(id -u)" -ne 0 ]; then
    echo "请以 root 用户运行此脚本"
    exit 1
fi

OS=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m)

Install_Soft() {
    echo "==================================================="
    echo "OS: $OS, Architecture: $ARCH"
    echo "==================================================="
    if [[ "$OS" == "linux" && "$ARCH" == "x86_64" ]]; then
        nodejs_file_name=node-v${nodejs_version}-linux-x64.tar.xz
    elif [[ "$OS" == "linux" && "$ARCH" == "aarch64" ]]; then
        nodejs_file_name=node-v${nodejs_version}-linux-arm64.tar.xz
    else
        echo "不支持的平台: $OS $ARCH" >&2
        exit 1
    fi
    nodejs_file_name_url="https://mirrors.aliyun.com/nodejs-release/v${nodejs_version}/${nodejs_file_name}"
    rm -rf ${RUYI_TEMP_PATH}/node-v*
    echo "下载地址：${nodejs_file_name_url}"
    cd ${RUYI_TEMP_PATH}
    wget -q $nodejs_file_name_url

    echo "==================================================="
    echo "正在解压：$nodejs_file_name"
    echo "==================================================="
    tar -xJf $nodejs_file_name
    if [ $? -eq 0 ] ; then
        echo "解压成功"
    else
        echo "解压失败 x" >&2
        exit 1
    fi
    nodejs_unzip_file_name="node-v${nodejs_version}-linux-$( [ "$ARCH" == "x86_64" ] && echo "x64" || echo "arm64" )"
    nodejs_unzip_dir="${RUYI_TEMP_PATH}/${nodejs_unzip_file_name}"
    nodejs_path=/ruyi/server/nodejs/${nodejs_version}
    rm -rf $nodejs_path
    mkdir -p ${nodejs_path}
    mv ${nodejs_unzip_file_name}/* ${nodejs_path}/
    rm -rf ${nodejs_unzip_file_name}
    echo "==================================================="
    echo "正在检测是否安装成功..."
    echo "==================================================="
    if [ ! -e ${nodejs_path}/bin/node ];then
        echo "ERROR: Install nodejs fielded . 安装Node.js环境失败，请尝试重新安装！" >&2
        exit 1
    fi
    echo "==================================================="
    echo "Node.js $nodejs_version 安装完成"
    echo "==================================================="
    rm -rf $RUYI_TEMP_PATH/node-v*
    exit 0
}

Uninstall_soft() {
    rm -rf /ruyi/server/nodejs/${nodejs_version}
}

if [ "$action_type" == 'install' ];then
    if [ -z "${nodejs_version}" ] || [ -z "${nodejs_file_name}" ]; then
        echo "参数错误" >&2
        exit 1
    fi
    Install_Soft
elif [ "$action_type" == 'uninstall' ];then
    if [ -z "${nodejs_version}" ];then
        echo "参数错误" >&2
        exit 1
    fi
    Uninstall_soft
fi
