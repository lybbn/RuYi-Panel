#!/bin/bash
#ruyi 面板更新/修复工具v0.1
#场景：面板文件错误异常导致启动失败等问题
#author lybbn
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
export PATH
LANG=en_US.UTF-8
PANEL_PATH="/ruyi/server/ruyi"

RY_PACKAGE_URL="http://download.lybbn.cn/ruyi/install/linux/ruyi.zip"

if [ $(whoami) != "root" ];then
    echo "请使用root权限执行本启动命令！"
    exit 1
fi

echo "正在下载并解压如意面板包文件..."
cd /tmp
rm -rf ruyi.zip
wget -T 20 $RY_PACKAGE_URL
if [ $? -eq 0 ]; then
    echo "下载成功"
else
    echo "获取面板包失败，请稍后操作或联系如意面板询问情况"
	exit 1;
fi
unzip -o ruyi.zip > /dev/null
rm -rf ruyi.zip

echo "正在备份面板..."

cp -a $PANEL_PATH /ruyi/tmp/ruyi

echo "正在修复/更新面板..."
rm -rf $PANEL_PATH/web/dist
cp -rf /tmp/ruyi/* $PANEL_PATH/

if [ $? -eq 0 ]; then
    rm -rf /ruyi/tmp/ruyi
    echo "操作已完成"
else
    echo "执行失败，正在回滚..."
    cp -rf /ruyi/tmp/ruyi/* $PANEL_PATH/
    exit 1
fi



