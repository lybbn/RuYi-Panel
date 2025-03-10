#!/bin/bash
#go环境安装
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
export PATH
LANG=en_US.UTF-8

RUYI_TEMP_PATH="/ruyi/tmp"

action_type=$1
go_version=$2
go_file_name=$3
cpu_core=$(cat /proc/cpuinfo|grep processor|wc -l)

# 检查是否以 root 用户运行
if [ "$(id -u)" -ne 0 ]; then
    echo "请以 root 用户运行此脚本"
    exit 1
fi

OS=$(uname -s | tr '[:upper:]' '[:lower:]')  # 转换为小写
ARCH=$(uname -m)  # 获取架构

Install_Soft() {
    echo "==================================================="
    echo "OS: $OS, Architecture: $ARCH"
    echo "==================================================="
    if [[ "$OS" == "linux" && "$ARCH" == "x86_64" ]]; then
        go_file_name=go$go_version.linux-amd64.tar.gz
    elif [[ "$OS" == "linux" && "$ARCH" == "aarch64" ]]; then
        go_file_name=go$go_version.linux-arm64.tar.gz
    else
        echo "不支持的平台: $OS $ARCH" >&2
        exit 1
    fi
    go_file_name_url="https://mirrors.aliyun.com/golang/${go_file_name}"
    rm -rf ${RUYI_TEMP_PATH}/go*
    echo "下载地址：${go_file_name_url}"
    cd ${RUYI_TEMP_PATH}
    wget -q $go_file_name_url

    echo "==================================================="
    echo "正在解压：$go_file_name"
    echo "==================================================="
    tar -zxf $go_file_name
    if [ $? -eq 0 ] ; then
        echo "解压成功"
    else
        echo "解压失败 x" >&2
        exit 1
    fi
    go_unzip_file_name="go"
    # go_unzip_file_name=$(basename "$go_file_name" .tar.gz)
    go_path=/ruyi/server/go/${go_version}
    rm -rf $go_path
    mkdir -p ${go_path}
	mv ${go_unzip_file_name}/* ${go_path}/
    rm -rf ${go_unzip_file_name}
    echo "==================================================="
    echo "正在检测是否安装成功..."
    echo "==================================================="
	if [ ! -e ${go_path}/bin/go ];then
		# rm -rf ${go_path}
        # 其中 >&2 用于重定向错误到stderr ，让subprocess.Popen捕获
		echo "ERROR: Install go fielded . 安装go环境失败，请尝试重新安装！" >&2
        exit 1
	fi
    echo "==================================================="
    echo "Go $go_version 安装完成"
    echo "==================================================="
    rm -rf $RUYI_TEMP_PATH/go*
    exit 0
}

Uninstall_soft() {
    rm -rf /ruyi/server/go/${go_version}
}

if [ "$action_type" == 'install' ];then
    if [ -z "${go_version}" ] || [ -z "${go_file_name}" ]; then
        echo "参数错误" >&2
        exit 1
    fi
	Install_Soft
elif [ "$action_type" == 'uninstall' ];then
    if [ -z "${go_version}" ];then
        echo "参数错误" >&2
        exit 1
    fi
	Uninstall_soft
fi
