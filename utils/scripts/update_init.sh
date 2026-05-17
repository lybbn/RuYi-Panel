#!/bin/bash
#ruyi 面板更新后操作执行工具v0.1
#author lybbn
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
export PATH
LANG=en_US.UTF-8
PANEL_PATH="/ruyi/server/ruyi"

#修复部分linux中\r换行报错
sed -i 's/\r//' ${PANEL_PATH}/ruyi-cmd.sh
chmod +x ${PANEL_PATH}/ruyi-cmd.sh
rm -f /usr/local/bin/ruyi-cmd
echo '#!/bin/bash' > /usr/local/bin/ruyi-cmd
echo "sed -i 's/\r//' ${PANEL_PATH}/ruyi-cmd.sh" >> /usr/local/bin/ruyi-cmd
echo "${PANEL_PATH}/ruyi-cmd.sh \"\$@\"" >> /usr/local/bin/ruyi-cmd
chmod +x /usr/local/bin/ruyi-cmd

rypython -m pip install --upgrade pip

#安装requirements.txt
rypip install -r ${PANEL_PATH}/requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

#同步数据
cd ${PANEL_PATH}
rypython manage.py syncdb
#升级初始化数据
rypython manage.py upgrade_init
