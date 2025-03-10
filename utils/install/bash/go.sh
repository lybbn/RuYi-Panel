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

Install_Soft() {
    echo "==================================================="
    echo "正在配置..."
    echo "==================================================="
    cd ${RUYI_TEMP_PATH}
    tar -zxf $go_file_name
    go_unzip_file_name="go"
    # go_unzip_file_name=$(basename "$go_file_name" .tar.gz)
    go_path=/ruyi/server/go/${go_version}
    rm -rf $go_path
	mv ${go_unzip_file_name} ${go_path}
    echo "==================================================="
    echo "正在检测是否安装成功..."
    echo "==================================================="
	if [ ! -e ${go_path}/bin/go ];then
		rm -rf ${go_path}
		echo "ERROR: Install go fielded." "ERROR: 安装go环境失败，请尝试重新安装！" 
        exit 1
	fi
    echo "==================================================="
    echo "Go $go_version 安装完成"
    echo "==================================================="
}

Uninstall_soft() {
    rm -rf /ruyi/server/go/${go_version}
}

if [ "$action_type" == 'install' ];then
    if [ -z "${go_version}" ] || [ -z "${go_file_name}" ]; then
        exit 1
    fi
	Install_Soft
elif [ "$action_type" == 'uninstall' ];then
    if [ -z "${go_version}" ];then
        exit 1
    fi
	Uninstall_soft
fi
