@echo off
setlocal
chcp 65001 > nul

if not "%~1"=="" (
    taskkill /F /PID %1
    timeout /t 2
)

REM 检查是否以管理员权限运行,如果没有,则请求提升权限
set "original_dir=%~dp0"
>nul 2>&1 "%SYSTEMROOT%\system32\cacls.exe" "%SYSTEMROOT%\system32\config\system"
if '%errorlevel%' NEQ '0' (
    echo 正在请求管理员权限...
    goto UACPrompt
) else ( 
    goto gotAdmin 
)

:UACPrompt
    set "VBSFile=%temp%\ruyigetadmin.vbs"
    echo Set UAC = CreateObject^("Shell.Application"^) > "%VBSFile%"
    echo UAC.ShellExecute "%~f0", "", "", "runas", 1 >> "%VBSFile%"
    cscript /nologo "%VBSFile%"
    del "%VBSFile%"
    exit /b

:gotAdmin
    goto startRuyi
    
:startRuyi
    echo 切换到目录: "%original_dir%"
    cd /d %original_dir%
    set SERVICE_NAME=RuyiService
    sc query "%SERVICE_NAME%" > nul 2>&1
    if %ERRORLEVEL% NEQ 0 (
        echo 服务 "%SERVICE_NAME%" 未安装.
        echo 正在安装服务...
        python service.py --startup auto install
    )
    echo 正在启动服务...
    python service.py restart
    timeout /t 1 /nobreak > nul
    sc query "%SERVICE_NAME%" | findstr /C:"RUNNING" > nul
    if %ERRORLEVEL% == 0 (
        echo 如意面板启动成功
    ) else (
        echo 如意面板启动失败!!!
    )
endlocal