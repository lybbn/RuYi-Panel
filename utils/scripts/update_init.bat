@echo off
:: ruyi面板更新后操作执行工具v0.1 - Windows版本
:: author lybbn
setlocal enabledelayedexpansion

set DEFAULT_PYTHON=python
set DEFAULT_PIP=pip
set DEFAULT_PAENL_PATH=

for %%A in ("%~dp0\..\..") do set "DEFAULT_PAENL_PATH=%%~fA"

set "PANEL_PATH=%~1"
if "!PANEL_PATH!"=="" ( 
    set "PANEL_PATH=%DEFAULT_PAENL_PATH%" 
)

set "PYTHON_DIR=%~2"
if "!PYTHON_DIR!"=="" ( 
    set "PYTHON_EXE=%DEFAULT_PYTHON%" 
    set "PIP_EXE=%DEFAULT_PIP%" 
) else (
    set "PYTHON_EXE=%PYTHON_DIR%\python.exe"
    set "PIP_EXE=%PYTHON_DIR%\Scripts\pip.exe"
)

echo 正在升级pip...
%PYTHON_EXE% -m pip install --upgrade pip

echo 正在安装依赖包...
%PIP_EXE% install -r "%PANEL_PATH%\requirements.txt" -i https://mirrors.aliyun.com/pypi/simple/

echo 正在同步数据库...
cd /d "%PANEL_PATH%"
%PYTHON_EXE% manage.py syncdb

echo 操作完成！

endlocal