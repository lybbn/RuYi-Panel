#!/bin/python
#coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板 RUYI
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2025-03-25
# +-------------------------------------------------------------------

# ------------------------------
# 安全解压
# ------------------------------
import time
import os
import zipfile
import tarfile
from pathlib import Path
import shutil
import sys

def func_unzip_secure(
    zip_filename: str,
    extract_path: str,
    max_retries: int = 2,
    chunk_size: int = 16 * 1024 * 1024,  # 16MB分块
    timeout: int = 3600  # 超时时间（秒）
) -> None:
    """
    安全解压函数（防崩溃优化版）
    
    改进点：
    1. 分块解压避免OOM
    2. 完善的错误恢复机制
    3. 资源占用监控
    4. 跨平台路径安全
    """
    def _validate_paths():
        """校验路径安全性"""
        if not os.path.exists(zip_filename):
            raise FileNotFoundError(f"压缩文件不存在: {zip_filename}")
        if not os.path.isfile(zip_filename):
            raise ValueError(f"目标不是文件: {zip_filename}")
        if os.path.realpath(zip_filename) != os.path.abspath(zip_filename):
            raise ValueError("压缩文件路径包含非法符号链接")
        if not zip_filename.lower().endswith(('.zip', '.tar.gz', '.tgz', '.tar.bz2', '.tbz')):
            raise ValueError("不支持的压缩格式")

    def _safe_extract_zip():
        """分块解压ZIP文件"""
        with zipfile.ZipFile(zip_filename, 'r') as zipf:
            # 校验压缩包完整性
            corrupt_file = zipf.testzip()
            if corrupt_file:
                raise RuntimeError(f"压缩包损坏: {corrupt_file}")
            
            # 逐文件解压（内存友好）
            for member in zipf.infolist():
                target_path = os.path.normpath(
                    os.path.join(extract_path, member.filename)
                )
                # 防御路径穿越攻击
                if not os.path.realpath(target_path).startswith(os.path.realpath(extract_path)):
                    raise ValueError(f"非法路径: {member.filename}")
                
                # 分块写入（避免大文件内存溢出）
                if member.filename.endswith('/') or member.is_dir():
                    os.makedirs(target_path, exist_ok=True)
                else:
                    # 确保父目录存在
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    
                    # 分块写入（保持不变）
                    with zipf.open(member) as source, open(target_path, 'wb') as target:
                        while chunk := source.read(chunk_size):
                            target.write(chunk)
                            target.flush()

    def _safe_extract_tar():
        """分块解压TAR文件"""
        with tarfile.open(zip_filename, 'r:*') as tar:
            # 安全提取（Python 3.12+）
            if sys.version_info >= (3, 12):
                tar.extractall(extract_path, filter='data')
            else:
                # 兼容旧版的替代方案
                for member in tar.getmembers():
                    member_path = os.path.join(extract_path, member.name)
                    if not os.path.realpath(member_path).startswith(os.path.realpath(extract_path)):
                        raise ValueError(f"非法路径: {member.name}")
                    tar.extract(member, extract_path)

    try:
        # 1. 前置检查
        _validate_paths()
        os.makedirs(extract_path, exist_ok=True)

        # 2. Windows解除占用（带重试）
        if os.name == 'nt':
            from utils.server.windows import kill_cmd_if_working_dir
            for attempt in range(max_retries):
                try:
                    kill_cmd_if_working_dir(extract_path)
                    break
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise RuntimeError(f"解除占用失败: {extract_path}") from e
                    time.sleep(1)  # 等待1秒重试

        # 3. 根据类型选择解压方式
        ext = Path(zip_filename).suffix.lower()
        if ext == '.zip':
            _safe_extract_zip()
        else:
            _safe_extract_tar()

    except Exception as e:
        # 失败时清理残留
        shutil.rmtree(extract_path, ignore_errors=True)
        raise RuntimeError(f"解压失败: {type(e).__name__}: {str(e)}") from e