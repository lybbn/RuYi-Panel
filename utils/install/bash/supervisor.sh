#!/bin/bash
#go环境安装
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
export PATH
LANG=en_US.UTF-8

RUYI_TEMP_PATH="/ruyi/tmp"
SOFT_INSTALL_PATH=/ruyi/server/supervisor
SOFT_TMP_PATH=/ruyi/server/supervisor/tmp
BASE_BIN_PATH=/usr/local/ruyi/python/bin
CONFIG_PATH=/etc/rysupervisord.conf
DATA_CONFIG_BASH_PATH=/ruyi/server/ruyi/data/supervisor
action_type=$1
soft_version=$2
soft_file_name=$3
cpu_core=$(cat /proc/cpuinfo|grep processor|wc -l)

# 检查是否以 root 用户运行
if [ "$(id -u)" -ne 0 ]; then
    echo "请以 root 用户运行此脚本"
    exit 1
fi

Service_Add() {
	cat <<EOF > /etc/systemd/system/rysupervisord.service
[Unit]
Description=Supervisor RuYi Service
After=network.target

[Service]
Type=forking
KillMode=process
ExecStart=/usr/local/ruyi/python/bin/python3 /ruyi/server/supervisor/bin/supervisord -c ${CONFIG_PATH}
ExecReload=/usr/local/ruyi/python/bin/python3 /ruyi/server/supervisor/bin/supervisorctl -c ${CONFIG_PATH} reload
ExecStop=/usr/local/ruyi/python/bin/python3 /ruyi/server/supervisor/bin/supervisorctl -c ${CONFIG_PATH} shutdown
ExecStatus=/usr/local/ruyi/python/bin/python3 /ruyi/server/supervisor/bin/supervisorctl -c ${CONFIG_PATH} status
ExecRestart=/usr/local/ruyi/python/bin/python3 /ruyi/server/supervisor/bin/supervisorctl -c ${CONFIG_PATH} restart
User=root
Group=root
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable rysupervisord
}

Service_Del() {
    if [ -f "/etc/systemd/system/rysupervisord.service" ];then
        systemctl stop rysupervisord > /dev/null
        systemctl disable rysupervisord > /dev/null
        rm -rf /etc/systemd/system/rysupervisord.service > /dev/null
        rm -rf /etc/systemd/system/multi-user.target.wants/rysupervisord.service > /dev/null
        systemctl daemon-reload
        ps aux | grep '[s]upervisord' | awk '{print $2}' | xargs -r sudo kill -9 2>/dev/null
    fi
}

Write_Config() {
    mkdir -p ${SOFT_TMP_PATH}
	cat <<EOF > ${CONFIG_PATH}
; Sample supervisor config file.
;
; For more information on the config file, please see:
; http://supervisord.org/configuration.html

[unix_http_server]
file=${SOFT_TMP_PATH}/supervisor.sock   ; the path to the socket file
;chmod=0700                 ; socket file mode (default 0700)
;chown=nobody:nogroup       ; socket file uid:gid owner
;username=user              ; default is no username (open server)
;password=123               ; default is no password (open server)

;[inet_http_server]         ; inet (TCP) server disabled by default
;port=127.0.0.1:9001        ; ip_address:port specifier, *:port for all iface
;username=user              ; default is no username (open server)
;password=123               ; default is no password (open server)

[supervisord]
logfile=${SOFT_TMP_PATH}/supervisord.log ; main log file; default $CWD/supervisord.log
logfile_maxbytes=50MB        ; max main logfile bytes b4 rotation; default 50MB
logfile_backups=10           ; # of main logfile backups; 0 means none, default 10
loglevel=info                ; log level; default info; others: debug,warn,trace
pidfile=${SOFT_TMP_PATH}/supervisord.pid ; supervisord pidfile; default supervisord.pid
nodaemon=false               ; start in foreground if true; default false
silent=false                 ; no logs to stdout if true; default false
minfds=1024                  ; min. avail startup file descriptors; default 1024
minprocs=200                 ; min. avail process descriptors;default 200
;umask=022                   ; process file creation umask; default 022
;user=supervisord            ; setuid to this UNIX account at startup; recommended if root
;identifier=supervisor       ; supervisord identifier, default is 'supervisor'
;directory=/tmp              ; default is not to cd during start
;nocleanup=true              ; don't clean up tempfiles at start; default false
;childlogdir=/tmp            ; 'AUTO' child log dir, default $TEMP
;environment=KEY="value"     ; key value pairs to add to environment
;strip_ansi=false            ; strip ansi escape codes in logs; def. false

; The rpcinterface:supervisor section must remain in the config file for
; RPC (supervisorctl/web interface) to work.  Additional interfaces may be
; added by defining them in separate [rpcinterface:x] sections.

[rpcinterface:supervisor]
supervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface

; The supervisorctl section configures how supervisorctl will connect to
; supervisord.  configure it match the settings in either the unix_http_server
; or inet_http_server section.

[supervisorctl]
serverurl=unix://${SOFT_TMP_PATH}/supervisor.sock ; use a unix:// URL  for a unix socket
;serverurl=http://127.0.0.1:9001 ; use an http:// url to specify an inet socket
;username=chris              ; should be same as in [*_http_server] if set
;password=123                ; should be same as in [*_http_server] if set
;prompt=mysupervisor         ; cmd line prompt (default "supervisor")
;history_file=~/.sc_history  ; use readline history if available

; The sample program section below shows all possible program subsection values.
; Create one or more 'real' program: sections to be able to control them under
; supervisor.

;[program:theprogramname]
;command=/bin/cat              ; the program (relative uses PATH, can take args)
;process_name=%(program_name)s ; process_name expr (default %(program_name)s)
;numprocs=1                    ; number of processes copies to start (def 1)
;directory=/tmp                ; directory to cwd to before exec (def no cwd)
;umask=022                     ; umask for process (default None)
;priority=999                  ; the relative start priority (default 999)
;autostart=true                ; start at supervisord start (default: true)
;startsecs=1                   ; # of secs prog must stay up to be running (def. 1)
;startretries=3                ; max # of serial start failures when starting (default 3)
;autorestart=unexpected        ; when to restart if exited after running (def: unexpected)
;exitcodes=0                   ; 'expected' exit codes used with autorestart (default 0)
;stopsignal=QUIT               ; signal used to kill process (default TERM)
;stopwaitsecs=10               ; max num secs to wait b4 SIGKILL (default 10)
;stopasgroup=false             ; send stop signal to the UNIX process group (default false)
;killasgroup=false             ; SIGKILL the UNIX process group (def false)
;user=chrism                   ; setuid to this UNIX account to run the program
;redirect_stderr=true          ; redirect proc stderr to stdout (default false)
;stdout_logfile=/a/path        ; stdout log path, NONE for none; default AUTO
;stdout_logfile_maxbytes=1MB   ; max # logfile bytes b4 rotation (default 50MB)
;stdout_logfile_backups=10     ; # of stdout logfile backups (0 means none, default 10)
;stdout_capture_maxbytes=1MB   ; number of bytes in 'capturemode' (default 0)
;stdout_events_enabled=false   ; emit events on stdout writes (default false)
;stdout_syslog=false           ; send stdout to syslog with process name (default false)
;stderr_logfile=/a/path        ; stderr log path, NONE for none; default AUTO
;stderr_logfile_maxbytes=1MB   ; max # logfile bytes b4 rotation (default 50MB)
;stderr_logfile_backups=10     ; # of stderr logfile backups (0 means none, default 10)
;stderr_capture_maxbytes=1MB   ; number of bytes in 'capturemode' (default 0)
;stderr_events_enabled=false   ; emit events on stderr writes (default false)
;stderr_syslog=false           ; send stderr to syslog with process name (default false)
;environment=A="1",B="2"       ; process environment additions (def no adds)
;serverurl=AUTO                ; override serverurl computation (childutils)

; The sample eventlistener section below shows all possible eventlistener
; subsection values.  Create one or more 'real' eventlistener: sections to be
; able to handle event notifications sent by supervisord.

;[eventlistener:theeventlistenername]
;command=/bin/eventlistener    ; the program (relative uses PATH, can take args)
;process_name=%(program_name)s ; process_name expr (default %(program_name)s)
;numprocs=1                    ; number of processes copies to start (def 1)
;events=EVENT                  ; event notif. types to subscribe to (req'd)
;buffer_size=10                ; event buffer queue size (default 10)
;directory=/tmp                ; directory to cwd to before exec (def no cwd)
;umask=022                     ; umask for process (default None)
;priority=-1                   ; the relative start priority (default -1)
;autostart=true                ; start at supervisord start (default: true)
;startsecs=1                   ; # of secs prog must stay up to be running (def. 1)
;startretries=3                ; max # of serial start failures when starting (default 3)
;autorestart=unexpected        ; autorestart if exited after running (def: unexpected)
;exitcodes=0                   ; 'expected' exit codes used with autorestart (default 0)
;stopsignal=QUIT               ; signal used to kill process (default TERM)
;stopwaitsecs=10               ; max num secs to wait b4 SIGKILL (default 10)
;stopasgroup=false             ; send stop signal to the UNIX process group (default false)
;killasgroup=false             ; SIGKILL the UNIX process group (def false)
;user=chrism                   ; setuid to this UNIX account to run the program
;redirect_stderr=false         ; redirect_stderr=true is not allowed for eventlisteners
;stdout_logfile=/a/path        ; stdout log path, NONE for none; default AUTO
;stdout_logfile_maxbytes=1MB   ; max # logfile bytes b4 rotation (default 50MB)
;stdout_logfile_backups=10     ; # of stdout logfile backups (0 means none, default 10)
;stdout_events_enabled=false   ; emit events on stdout writes (default false)
;stdout_syslog=false           ; send stdout to syslog with process name (default false)
;stderr_logfile=/a/path        ; stderr log path, NONE for none; default AUTO
;stderr_logfile_maxbytes=1MB   ; max # logfile bytes b4 rotation (default 50MB)
;stderr_logfile_backups=10     ; # of stderr logfile backups (0 means none, default 10)
;stderr_events_enabled=false   ; emit events on stderr writes (default false)
;stderr_syslog=false           ; send stderr to syslog with process name (default false)
;environment=A="1",B="2"       ; process environment additions
;serverurl=AUTO                ; override serverurl computation (childutils)

; The sample group section below shows all possible group values.  Create one
; or more 'real' group: sections to create "heterogeneous" process groups.

;[group:thegroupname]
;programs=progname1,progname2  ; each refers to 'x' in [program:x] definitions
;priority=999                  ; the relative start priority (default 999)

; The [include] section can just contain the "files" setting.  This
; setting can list multiple files (separated by whitespace or
; newlines).  It can also contain wildcards.  The filenames are
; interpreted as relative to this file.  Included files *cannot*
; include files themselves.

[include]
files = ${DATA_CONFIG_BASH_PATH}/*.ini
EOF

}

Install_Soft() {
    echo "==================================================="
    echo "正在配置..."
    echo "==================================================="
    cd ${RUYI_TEMP_PATH}
    rm -rf ${SOFT_INSTALL_PATH}
    mkdir -p ${SOFT_INSTALL_PATH}/bin
    rypip install ${soft_file_name}
    Install_SRC_Path="rypip show supervisor 2>/dev/null | grep 'Location' | awk '{print $2}'"
    ln -sf ${BASE_BIN_PATH}/supervisord ${SOFT_INSTALL_PATH}/bin/supervisord
    ln -sf ${BASE_BIN_PATH}/supervisorctl ${SOFT_INSTALL_PATH}/bin/supervisorctl
    ln -sf ${BASE_BIN_PATH}/echo_supervisord_conf ${SOFT_INSTALL_PATH}/bin/echo_supervisord_conf
    ln -sf ${BASE_BIN_PATH}/pidproxy ${SOFT_INSTALL_PATH}/bin/pidproxy
    Write_Config
    echo "==================================================="
    echo "正安装服务..."
    Service_Add
    echo "==================================================="
    echo "正在检测是否安装成功..."
    echo "==================================================="
	if [ -z "$Install_SRC_Path" ];then
		rm -rf ${SOFT_INSTALL_PATH}
		echo "ERROR: Install supervisor fielded." "ERROR: 安装supervisor失败，请尝试重新安装！" 
        exit 1
	fi
    echo "supervisor 安装完成"
    echo "==================================================="
}

Uninstall_soft() {
    Service_Del
    rm -rf /ruyi/server/supervisor
    rypip uninstall supervisor -y
}

if [ "$action_type" == 'install' ];then
    if [ -z "${soft_version}" ] || [ -z "${soft_file_name}" ]; then
        exit 1
    fi
	Install_Soft
elif [ "$action_type" == 'uninstall' ];then
	Uninstall_soft
fi
