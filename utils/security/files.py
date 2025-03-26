#!/bin/python
#coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2024-01-03
# +-------------------------------------------------------------------

# ------------------------------
# 文件/目录操作
# ------------------------------

import re
import wget
import os
import shutil
import datetime
import mimetypes
import requests
from natsort import natsorted, ns
from utils.server.system import system
from utils.security.no_delete_list import check_no_delete,check_in_black_list
from utils.common import ast_convert,GetTmpPath,WriteFile,RunCommand,current_os
from itertools import chain
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

def get_file_name_from_url(url):
    """
    @name 使用 os.path.basename() 函数获取 URL 中的文件名
    @author lybbn<2024-02-22>
    """
    file_name = os.path.basename(url)
    return file_name

def select_github_mirror():
    """
    选择可用的 github 镜像源
    返回第一个可用的镜像 URL 或 None
    """
    MIRROR_GITHUB_LIST = [
        "https://ghfast.top",
        "https://github.moeyy.xyz",
        "https://ghproxy.cfd"
    ]
    
    for mirror in MIRROR_GITHUB_LIST:
        try:
            response = requests.get(mirror, timeout=5)
            if response.status_code == 200:
                return mirror
        except requests.RequestException as e:
            continue

    return None

def get_github_quick_downloadurl(url):
    baseurl = select_github_mirror()
    if not baseurl:
        return None
    return f"${baseurl}/{url}"

def download_url_file(url, save_path="",process=False,log_path=None,chunk_size=8192):
    """
    @name 下载网络文件
    @save_path 下载本地路径名称（包含文件名），为空则默认存储在tmp中
    @author lybbn<2024-02-22>
    @process 是否显示进度
    @log_path 记录日志路径(包含文件名),process True时有效
    """
    try:
        if not save_path:
            save_directory = GetTmpPath()
            if not os.path.exists(save_directory):
                os.makedirs(save_directory)
            filename = get_file_name_from_url(url)
            save_path = os.path.join(save_directory, filename)
        else:
            save_directory = os.path.dirname(save_path)
            if not os.path.exists(save_directory):
                os.makedirs(save_directory)

        buffered_logs = []
        # headers = {}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0 ruyi",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
            "Accept-Encoding":"gzip, deflate, br, zstd",
            "Sec-Ch-Ua":'"Chromium";v="134", "Not:A-Brand";v="24", "Microsoft Edge";v="134"',
            "Sec-Ch-Ua-Mobile":"?0"
        }
        downloaded_size = 0
        if os.path.exists(save_path):
            downloaded_size = os.path.getsize(save_path)
            headers['Range'] = 'bytes={}-'.format(downloaded_size)
        r = requests.get(url, headers=headers, stream=True)
        total_size = int(r.headers.get('content-length', 0))
        if total_size == 0:
            WriteFile(log_path, f"检测到已下载的文件，已跳过\n", mode='a', write=True)
            return True,"下载成功"
        with open(save_path, 'ab') as f:
            for chunk in r.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    if process:
                        downloaded_size += len(chunk)
                        # 计算进度百分比
                        progress = (downloaded_size / total_size) * 100
                        if progress> 100:progress=100
                        logs = f'Downloaded {downloaded_size} of {total_size} bytes ({progress:.2f}%)\n'
                        buffered_logs.append(logs)
                        # 仅当缓存达到一定大小时才写入日志
                        if len(buffered_logs) >= 10:
                            WriteFile(log_path, buffered_logs[-1], mode='a', write=True)
                            buffered_logs.clear()
            # 写入剩余的日志
            if buffered_logs:
                WriteFile(log_path, buffered_logs[-1], mode='a', write=True)
        return True,"下载成功"
    except:
        return False,"网络文件错误"

def download_url_file_wget(url, save_path="", process=False, log_path=None,chunk_size=32768):
    """
    @name 下载网络文件wget
    @save_path 下载本地路径名称（包含文件名），为空则默认存储在tmp中
    @author lybbn<2024-02-22>
    @process 是否显示进度
    @log_path 记录日志路径(包含文件名), process True时有效
    """
    try:
        if not save_path:
            save_directory = GetTmpPath()
            if not os.path.exists(save_directory):
                os.makedirs(save_directory)
            filename = get_file_name_from_url(url)
            save_path = os.path.join(save_directory, filename)
        else:
            save_directory = os.path.dirname(save_path)
            if not os.path.exists(save_directory):
                os.makedirs(save_directory)

        # 如果文件已存在，跳过下载
        if os.path.exists(save_path):
            WriteFile(log_path, f"检测到已下载的文件，已跳过\n", mode='a', write=True)
            return True, "下载成功"
        buffered_logs = []

        # 使用 wget 下载文件
        def log_progress(current, total, width=80):
            if process:
                progress = (current / total) * 100
                if progress> 100:progress=100

                logs = f'Downloaded {current} of {total} bytes ({progress:.2f}%)\n'
                buffered_logs.append(logs)
                # 仅当缓存达到一定大小时才写入日志
                if len(buffered_logs) >= 10:
                    WriteFile(log_path, buffered_logs[-1], mode='a', write=True)
                    buffered_logs.clear()

        # 下载文件
        wget.download(url, out=save_path, bar=log_progress if process else None)

        # 写入剩余的日志
        if buffered_logs:
            WriteFile(log_path, buffered_logs[-1], mode='a', write=True)

        return True, "下载成功"
    except Exception as e:
        WriteFile(log_path, f"下载失败: {str(e)}\n", mode='a', write=True)
        return False, f"网络文件错误: {str(e)}"

def _download_chunk(url, start_byte, end_byte, save_path, chunk_id, max_retries=3, headers=None,process=True, log_path=None, failed_flag=None):
    """
    下载文件的指定部分
    """
    headers = headers or {}
    headers['Range'] = f'bytes={start_byte}-{end_byte}'
    retries = 0

    while retries < max_retries:
        if failed_flag and failed_flag.is_set():  # 检查是否已失败
            WriteFile(log_path, f"分块 {chunk_id} 下载已终止\n", mode='a', write=True)
            return False
        try:
            with requests.Session() as session:
                response = session.get(url, headers=headers, stream=True, timeout=10)
                response.raise_for_status()
                chunk_path = f"{save_path}.part{chunk_id}"
                buffered_logs = []
                downloaded_size = 0  # 已下载的字节数
                total_size = end_byte - start_byte + 1  # 当前分块的总大小
                with open(chunk_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded_size += len(chunk)  # 更新已下载的字节数
                            # 写入当前分块的下载进度
                            if process and log_path:
                                progress = (downloaded_size / total_size) * 100  # 计算下载进度百分比
                                if progress> 100:progress=100
                                logs = f'分块 {chunk_id} 下载进度: {progress:.2f}%\n'
                                buffered_logs.append(logs)
                                # 仅当缓存达到一定大小时才写入日志
                                if len(buffered_logs) >= 10:
                                    WriteFile(log_path, buffered_logs[-1], mode='a', write=True)
                                    buffered_logs.clear()
                                WriteFile(log_path, f"", mode='a', write=True)
                            if failed_flag and failed_flag.is_set():  # 检查是否已失败
                                WriteFile(log_path, f"分块 {chunk_id} 下载已终止\n", mode='a', write=True)
                                return False
                    # 写入剩余的日志
                    if buffered_logs:
                        WriteFile(log_path, buffered_logs[-1], mode='a', write=True)
                WriteFile(log_path, f"分块 {chunk_id} 下载成功\n", mode='a', write=True)
                # 记录进度
                if process and log_path:
                    downloaded_size = end_byte - start_byte + 1
                    with open(log_path, 'a') as log_file:
                        WriteFile(log_path, f"分块 {chunk_id} 下载完成，大小: {downloaded_size} 字节\n", mode='a', write=True)
                return True
        except Exception as e:
            retries += 1
            WriteFile(log_path, f"下载分块 {chunk_id} 失败，重试 {retries}/{max_retries}: {e}\n", mode='a', write=True)
    WriteFile(log_path, f"下载分块 {chunk_id} 失败，已达到最大重试次数\n", mode='a', write=True)
    if failed_flag:
        failed_flag.set()  # 设置失败标志
    return False

def _merge_chunks(save_path, num_chunks,log_path=None):
    """
    合并所有下载的分块
    """
    try:
        with open(save_path, 'wb') as final_file:
            for i in range(num_chunks):
                chunk_path = f"{save_path}.part{i}"
                with open(chunk_path, 'rb') as chunk_file:
                    final_file.write(chunk_file.read())
                os.remove(chunk_path)  # 删除临时分块文件
                WriteFile(log_path, f"分块 {i} 已合并\n", mode='a', write=True)
        WriteFile(log_path, f"所有分块已合并\n", mode='a', write=True)
        return True
    except Exception as e:
        WriteFile(log_path, f"合并分块失败: {e}\n", mode='a', write=True)
        return False

def _cleanup_temp_files(save_path, num_chunks, log_path=None):
    """
    清理临时分块文件
    """
    for i in range(num_chunks):
        chunk_file = f"{save_path}.part{i}"
        if os.path.exists(chunk_file):
            try:
                os.remove(chunk_file)
                WriteFile(log_path, f"已清理临时文件: {chunk_file}\n", mode='a', write=True)
            except Exception as e:
                WriteFile(log_path, f"清理临时文件 {chunk_file} 失败: {e}\n", mode='a', write=True)

def download_url_file_m(url, save_path="", process=False, log_path=None, num_threads=4, max_retries=3):
    """
    @name 多线程下载网络文件
    @param url: 下载链接
    @param save_path: 本地保存路径（包含文件名）
    @param process: 是否显示进度
    @param log_path: 日志文件路径
    @param num_threads: 下载线程数
    @param max_retries: 最大重试次数
    @author lybbn<2025-03-22>
    """
    try:
        if not save_path:
            save_directory = GetTmpPath()
            if not os.path.exists(save_directory):
                os.makedirs(save_directory)
            filename = get_file_name_from_url(url)
            save_path = os.path.join(save_directory, filename)
        else:
            save_directory = os.path.dirname(save_path)
            if not os.path.exists(save_directory):
                os.makedirs(save_directory)

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0 ruyi",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
            "Accept-Encoding":"gzip, deflate, br, zstd",
            "Sec-Ch-Ua":'"Chromium";v="134", "Not:A-Brand";v="24", "Microsoft Edge";v="134"',
            "Sec-Ch-Ua-Mobile":"?0"
        }

        # 获取文件总大小
        response = requests.head(url,headers=headers)
        total_size = int(response.headers.get('content-length', 0))
        if total_size == 0:
            WriteFile(log_path, "无法获取文件大小，无法进行多线程下载\n", mode='a', write=True)
            return False, "无法获取文件大小"
        
        if os.path.exists(save_path):
            locla_total_size = os.path.getsize(save_path)
            if total_size == locla_total_size:
                WriteFile(log_path, f"检测到已下载的历史文件，已跳过下载，使用本地文件\n", mode='a', write=True)
                return True,"下载成功"

        # 计算每个线程下载的字节范围
        chunk_size = total_size // num_threads
        ranges = [(i * chunk_size, (i + 1) * chunk_size - 1) for i in range(num_threads)]
        ranges[-1] = (ranges[-1][0], total_size - 1)  # 最后一个线程下载剩余部分

        # 共享状态：用于标记是否下载失败
        failed_flag = threading.Event()

        # 使用线程池下载
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = []
            for i, (start_byte, end_byte) in enumerate(ranges):
                futures.append(executor.submit(_download_chunk, url, start_byte, end_byte, save_path, i, max_retries,headers,process,log_path, failed_flag))

            # 检查所有分块是否下载成功
            for future in as_completed(futures):
                if not future.result():
                    WriteFile(log_path, "部分分块下载失败，终止下载\n", mode='a', write=True)
                    failed_flag.set()  # 设置失败标志
                    executor.shutdown(wait=False)  # 立即关闭线程池
                    _cleanup_temp_files(save_path, num_threads,log_path=log_path)  # 清理临时文件
                    return False, "部分分块下载失败"

        # 合并分块
        if not _merge_chunks(save_path, num_threads,log_path=log_path):
            _cleanup_temp_files(save_path, num_threads,log_path=log_path)  # 清理临时文件
            return False, "合并分块失败"

        WriteFile(log_path, "下载成功\n", mode='a', write=True)
        return True, "下载成功"
    except Exception as e:
        WriteFile(log_path, f"下载失败: {e}\n", mode='a', write=True)
        _cleanup_temp_files(save_path, num_threads,log_path=log_path)  # 清理临时文件
        return False, f"下载失败: {e}"

def get_file_extension(file_path):
    """
    @name 获取文件后缀扩展
    @author lybbn<2024-02-22>
    """
    _, extension = os.path.splitext(file_path)
    return extension

def detect_file_type(file_path):
    """
    @name 检测文件类型
    @author lybbn<2024-02-22>
    """
    file_type, _ = mimetypes.guess_type(file_path)
    return file_type

def auto_detect_file_language(file_path):
    """
    @name 智能检测文件所属语言
    @author lybbn<2024-03-08>
    """
    ext = get_file_extension(file_path)
    if ext in ['.readme','.md']:
        return "markdown"
    elif ext in ['.sh']:
        return "shell"
    elif ext in ['.lua']:
        return "lua"
    elif ext in ['.rb']:
        return "ruby"
    elif ext in ['.js','.ts']:
        return "javascript"
    elif ext in ['.html','htm']:
        return "html"
    elif ext in ['.css','.scss','.sass','.less']:
        return "css"
    elif ext in ['.json']:
        return "json"
    elif ext in ['.py']:
        return "python"
    elif ext in ['.yaml','.yml']:
        return "yaml"
    elif ext in ['.conf','.ini']:
        if 'nginx' in file_path:
            return "nginx"
        return "properties"
    elif ext in ['.vue']:
        return "vue"
    elif ext in ['.php']:
        return "php"
    elif ext in ['.java']:
        return "java"
    elif ext in ['.go']:
        return "go"
    elif ext in ['.sql']:
        return "sql"
    elif ext in ['.xml']:
        return "xml"
    else:
        return "log"
def list_dirs(dst_path):
    """
    列出指定目录下文件\目录名
    返回指定目录下文件+目录名的列表
    """
    if not os.path.exists(dst_path):
        return []
    data = []
    for f in os.listdir(dst_path):
        data.append(f)
    return data

def get_size(file_path):
    """
    @name 获取文件大小
    @author lybbn<2024-02-22>
    """
    return os.path.getsize(file_path)

def is_link(file_path):
    """
    @name 是否软链接
    @author lybbn<2024-02-22>
    """
    return os.path.islink(file_path)

def get_directory_size(dst_path):
    """
    @name 计算指定目录大小
    @author lybbn<2024-02-22>
    """
    if current_os == "windows":
        total_size = 0
        for path, dirs, files in os.walk(dst_path):
            for file in files:
                if not os.path.exists(file): continue
                if os.path.islink(file): continue
                file_path = os.path.join(path, file)
                total_size += os.path.getsize(file_path)
        return total_size
    else:
        result,err,returncode = RunCommand(f"du -sh {dst_path}",returncode=True)
        if returncode == 0:
            size = result.split()[0]
            return re.sub(r'(\d+)([a-zA-Z])', r'\1 \2', size)+"B"
        else:
            return "0 B"

def get_path_files_nums(path):
    """
    @name 获取指定目录文件数量
    @author lybbn<2024-02-22>
    """
    if os.path.isfile(path):
        return 1
    if not os.path.exists(path):
        return 0
    i = 0
    for name in os.listdir(path):
        i += 1
    return i

def get_filename_ext(filename):
    """
    @name 获取文件扩展名
    @author lybbn<2024-02-22>
    """
    tmpList = filename.split('.')
    return tmpList[-1]

def windows_path_replace(path,is_windows = True):
    """
    @name 把path中的\\ sep替换成 /
    @author lybbn<2024-02-22>
    """
    if is_windows:
        path = path.replace("\\", "/")
    return path

def list_files_in_directory(dst_path,sort="name",is_reverse=False,is_windows=False,search=None,containSub=False,isDir=False):
    """
    @name 列出指定目录下文件\目录名列表，包含文件\目录属性（大小、路径、权限、所属者）
    目录size大小默认不计算为0
    owner所属者为空可能为文件/目录无权限查看或被占用等
    @author lybbn<2024-02-22>
    @param sort 排序
    @param is_reverse True 降序(desc) 、False 升序(asc)
    @param search 搜索名称
    @param containSub 搜索内容是否包含所有子目录
    @param isDir 是否只列出目录
    """
    def get_file_info(entry):
        """获取文件信息的内部函数"""
        file_info = entry.stat()
        modified_time = datetime.datetime.fromtimestamp(file_info.st_mtime)
        formatted_time = modified_time.strftime("%Y-%m-%d %H:%M:%S")
        gid = file_info.st_gid
        group_name = "" if is_windows else system.GetGroupidName(entry.path, gid)
        
        return {
            "name": entry.name,
            "type": "file" if entry.is_file() else "dir",
            "path": windows_path_replace(entry.path, is_windows=is_windows),
            "size": file_info.st_size if entry.is_file() else None,
            "permissions": oct(file_info.st_mode)[-3:],
            "owner_uid": file_info.st_uid,
            "owner": system.GetUidName(entry.path, file_info.st_uid),
            "gid": gid,
            "group": group_name,
            "modified": formatted_time
        }

    def process_entry(entry):
        """处理单个目录项"""
        if search and search.lower() not in entry.name.lower():
            return None
        if isDir and entry.is_file():
            return None
        return get_file_info(entry)

    # 处理Windows磁盘根目录情况
    if is_windows and not dst_path:
        disk_paths = system().GetDiskInfo()
        datainfo = {
            'data':[],
            'file_nums':0,
            'dir_nums':0,
            'total_nums':0
        }
        for d in disk_paths:
            if search and d['path'].lower().find(search) == -1:
                continue
            datainfo['data'].append({
                "name": d['path'].lower(),
                "type": "pan",
                "path": windows_path_replace(d['path'].lower(), is_windows=is_windows),
                "size": d['size'][0],
                "permissions": "",
                "owner_uid": None,
                "owner": "",
                "modified": ""
            })
        datainfo['total_nums'] = len(disk_paths)
        return datainfo

    # 检查路径有效性
    if not os.path.exists(dst_path):
        return {
            'data': [],
            'file_nums': 0,
            'dir_nums': 0,
            'total_nums': 0
        }
    if not os.path.isdir(dst_path):
        raise ValueError("错误：非目录")

    # 处理不包含子目录的情况
    if not containSub:
        dirData = []
        fileData = []
        for entry in os.scandir(dst_path):
            item = process_entry(entry)
            if item:
                if item["type"] == "dir":
                    dirData.append(item)
                else:
                    fileData.append(item)

        # 对目录和文件分别排序
        if sort == "name":
            dirData = natsorted(dirData, key=lambda x: x["name"], alg=ns.PATH, reverse=is_reverse)
            fileData = natsorted(fileData, key=lambda x: x["name"], alg=ns.PATH, reverse=is_reverse)
        elif sort == "modified":
            dirData = sorted(dirData, key=lambda x: x["modified"], reverse=is_reverse)
            fileData = sorted(fileData, key=lambda x: x["modified"], reverse=is_reverse)
        elif sort == "size":
            dirData = sorted(dirData, key=lambda x: x["size"] if x["size"] is not None else 0, reverse=is_reverse)
            fileData = sorted(fileData, key=lambda x: x["size"] if x["size"] is not None else 0, reverse=is_reverse)

        data = dirData + fileData
    else:
        # 处理包含子目录的情况
        data = []
        count_limit = 0
        max_limit = 3000
        for root, dirs, files in os.walk(dst_path):
            if count_limit >= max_limit:
                break
            for entry in chain((os.path.join(root, f) for f in files), 
                             (os.path.join(root, d) for d in dirs)):
                if count_limit >= max_limit:
                    break
                info = process_entry(os.DirEntry(entry))
                if info:
                    data.append(info)
                    count_limit += 1

        # 对结果进行排序
        if sort == "name":
            data = natsorted(data, key=lambda x: x["name"], alg=ns.PATH, reverse=is_reverse)
        elif sort == "modified":
            data = sorted(data, key=lambda x: x["modified"], reverse=is_reverse)
        elif sort == "size":
            data = sorted(data, key=lambda x: x["size"] if x["size"] is not None else 0, reverse=is_reverse)

    # 统计文件数量
    file_nums = sum(1 for item in data if item["type"] == "file")
    dir_nums = sum(1 for item in data if item["type"] == "dir")

    return {
        'data': data,
        'file_nums': file_nums,
        'dir_nums': dir_nums,
        'total_nums': file_nums + dir_nums
    }
def list_files_in_directory_old(dst_path,sort="name",is_reverse=False,is_windows=False,search=None,containSub=False,isDir=False):
    """
    @name 列出指定目录下文件\目录名列表，包含文件\目录属性（大小、路径、权限、所属者）
    目录size大小默认不计算为0
    owner所属者为空可能为文件/目录无权限查看或被占用等
    @author lybbn<2024-02-22>
    @param sort 排序
    @param is_reverse True 降序(desc) 、False 升序(asc)
    @param search 搜索名称
    @param containSub 搜索内容是否包含所有子目录
    @param isDir 是否只列出目录
    """
    is_dir_first = True#是否把目录放在前面
    if is_windows:
        if not dst_path:
            disk_paths = system().GetDiskInfo()
            datainfo = {
                'data':[],
                'file_nums':0,
                'dir_nums':0,
                'total_nums':0
            }
            for d in disk_paths:
                if search:
                    if d['path'].lower().find(search) == -1:
                        continue
                datainfo['data'].append({"name":d['path'].lower(),"type":"pan","path":windows_path_replace(d['path'].lower(),is_windows=is_windows),"size":d['size'][0],"permissions":"","owner_uid":None,"owner":"","modified":""})
            datainfo['total_nums'] = len(disk_paths)
            return datainfo
    if not os.path.exists(dst_path):
        return {
            'data':[],
            'file_nums':0,
            'dir_nums':0,
            'total_nums':0
        }
    if not os.path.isdir(dst_path):
        raise ValueError("错误：非目录")
    data = []
    dirData = []
    fileData = []
    file_nums = 0
    dir_nums = 0
    if not containSub:
        for entry in os.scandir(dst_path):
            if entry.is_file():
                if isDir:
                    continue
                if search:
                    if entry.name.lower().find(search) == -1:
                        continue
                file_nums = file_nums + 1
                file_info = entry.stat()
                modified_time = datetime.datetime.fromtimestamp(file_info.st_mtime)
                formatted_time = modified_time.strftime("%Y-%m-%d %H:%M:%S")
                gid=file_info.st_gid
                group_name=""
                if not is_windows:
                    group_name = system.GetGroupidName(entry.path,gid)
                tempData = {"name":entry.name,"type":"file","path":windows_path_replace(entry.path,is_windows=is_windows),"size":file_info.st_size,"permissions":oct(file_info.st_mode)[-3:],"owner_uid":file_info.st_uid,"owner":system.GetUidName(entry.path,file_info.st_uid),"gid":gid,"group":group_name,"modified":formatted_time}
                data.append(tempData)
                if is_dir_first:
                    fileData.append(tempData)
            elif entry.is_dir():
                if search:
                    if entry.name.lower().find(search) == -1:
                        continue
                dir_nums = dir_nums + 1
                dir_info = entry.stat()
                modified_time = datetime.datetime.fromtimestamp(dir_info.st_mtime)
                formatted_time = modified_time.strftime("%Y-%m-%d %H:%M:%S")
                gid=dir_info.st_gid
                group_name=""
                if not is_windows:
                    group_name = system.GetGroupidName(entry.path,gid)
                tempData = {"name":entry.name,"type":"dir","path":windows_path_replace(entry.path,is_windows=is_windows),"size":None,"permissions":oct(dir_info.st_mode)[-3:],"owner_uid":dir_info.st_uid,"owner":system.GetUidName(entry.path,dir_info.st_uid),"gid":gid,"group":group_name,"modified":formatted_time}
                data.append(tempData)
                if is_dir_first:
                    dirData.append(tempData)
    else:
        count_limit = 0
        max_limit = 3000
        for root, dirs, files in os.walk(dst_path):
            if count_limit >= max_limit:
                break
            # 在当前目录下搜索文件
            for file in files:
                if count_limit >= max_limit:
                    break
                if search:
                    if file.lower().find(search) == -1:
                        continue
                file_nums = file_nums + 1
                file_path = os.path.join(root, file)
                file_info = os.stat(file_path)
                modified_time = datetime.datetime.fromtimestamp(file_info.st_mtime)
                formatted_time = modified_time.strftime("%Y-%m-%d %H:%M:%S")
                tempData = {"name":file,"type":"file","path":windows_path_replace(file_path,is_windows=is_windows),"size":file_info.st_size,"permissions":oct(file_info.st_mode)[-3:],"owner_uid":file_info.st_uid,"owner":system.GetUidName(file_path,file_info.st_uid),"modified":formatted_time}
                data.append(tempData)
                if is_dir_first:
                    fileData.append(tempData)
                count_limit += 1
            # 在当前目录下搜索目录
            for dir in dirs:
                if count_limit >= max_limit:
                    break
                if search:
                    if dir.lower().find(search) == -1:
                        continue
                dir_nums = dir_nums + 1
                dir_path = os.path.join(root, dir)
                dir_info = os.stat(dir_path)
                modified_time = datetime.datetime.fromtimestamp(dir_info.st_mtime)
                formatted_time = modified_time.strftime("%Y-%m-%d %H:%M:%S")
                tempData = {"name":dir,"type":"dir","path":windows_path_replace(dir_path,is_windows=is_windows),"size":None,"permissions":oct(dir_info.st_mode)[-3:],"owner_uid":dir_info.st_uid,"owner":system.GetUidName(dir_path,dir_info.st_uid),"modified":formatted_time}
                data.append(tempData)
                if is_dir_first:
                    dirData.append(tempData)
                count_limit += 1
    if is_dir_first:
        data = []
        temp_dir_date1 = dirData[:4000]
        temp_dir_date2 = natsorted(temp_dir_date1,key=lambda x: x.get("name", ""), alg=ns.PATH, reverse=is_reverse)
        temp_dir_data = temp_dir_date2 + dirData[4000:]
        temp_file_date1 = fileData[:4000]
        temp_file_date2 = natsorted(temp_file_date1,key=lambda x: x.get("name", ""), alg=ns.PATH, reverse=is_reverse)
        temp_file_data = temp_file_date2 + fileData[4000:]
        data.extend(temp_dir_data)
        data.extend(temp_file_data)

    # if sort == "name":
    #     # 根据 sort 参数对结果进行排序,海量文件可能导致排序缓慢，因此限制排序前4000个
    #     temp_date1 = data[:4000]
    #     temp_date2 = natsorted(temp_date1,key=lambda x: x.get("name", ""), alg=ns.PATH, reverse=is_reverse)
    #     data = temp_date2 + data[4000:]
    if sort == "modified":
        # 根据 sort 参数对结果进行排序,海量文件可能导致排序缓慢，因此限制排序前4000个
        temp_date1 = data[:4000]
        temp_date2 = sorted(temp_date1, key=lambda x: x["modified"], reverse=is_reverse)
        data = temp_date2 + data[4000:]
    elif sort == "size":
        # 根据 sort 参数对结果进行排序,海量文件可能导致排序缓慢，因此限制排序前4000个
        temp_date1 = data[:4000]
        temp_date2 = sorted(temp_date1, key=lambda x: x["size"] if x["size"] is not None else 0, reverse=is_reverse)
        data = temp_date2 + data[4000:]
    
    data_info = {
        'data':data,
        'file_nums':file_nums,
        'dir_nums':dir_nums,
        'total_nums':file_nums+dir_nums
    }
    return data_info

def get_filedir_attribute(path,is_windows=False):
    """
    @name 获取文件/目录属性
    @author lybbn<2024-02-22>
    """
    if not path:
        return None
    if os.path.isfile(path):
        name = os.path.basename(path)
        file_info = os.stat(path)
        modified_time = datetime.datetime.fromtimestamp(file_info.st_mtime)
        formatted_time = modified_time.strftime("%Y-%m-%d %H:%M:%S")
        access_time = datetime.datetime.fromtimestamp(file_info.st_atime)
        formatted_at = access_time.strftime("%Y-%m-%d %H:%M:%S")
        return {"name":name,"type":"file","is_link":is_link(path),"path":windows_path_replace(path,is_windows=is_windows),"size":file_info.st_size,"permissions":oct(file_info.st_mode)[-3:],"owner_uid":file_info.st_uid,"owner":system.GetUidName(path,file_info.st_uid),"gid":file_info.st_gid,"group":system.GetGroupidName(path,file_info.st_gid),"modified":formatted_time,"access_at":formatted_at}
    elif os.path.isdir(path):
        name = os.path.basename(path)
        dir_info = os.stat(path)
        modified_time = datetime.datetime.fromtimestamp(dir_info.st_mtime)
        formatted_time = modified_time.strftime("%Y-%m-%d %H:%M:%S")
        access_time = datetime.datetime.fromtimestamp(dir_info.st_atime)
        formatted_at = access_time.strftime("%Y-%m-%d %H:%M:%S")
        return {"name":name,"type":"dir","is_link":is_link(path),"path":windows_path_replace(path,is_windows=is_windows),"size":get_directory_size(path),"permissions":oct(dir_info.st_mode)[-3:],"owner_uid":dir_info.st_uid,"owner":system.GetUidName(path,dir_info.st_uid),"gid":dir_info.st_gid,"group":system.GetGroupidName(path,dir_info.st_gid),"modified":formatted_time,"access_at":formatted_at}
    return None

def create_file(path,is_windows=False):
    """
    @name 创建文件
    @author lybbn<2024-02-22>
    """
    #去除干扰
    filename = os.path.basename(path).strip()
    filepath = os.path.dirname(path).strip()
    if not filename:
        raise ValueError("请填写文件名")
    if not is_windows:
        path = os.path.join(filepath, filename)
    else:
        filepath = filepath.replace("//", "/").replace("/", "\\")
        path = os.path.join(filepath, filename)
    if path[-1] == '.':
        raise ValueError("文件名不能以'.'点结尾")
    if len(filename)>100 or len(filename) < 1:
        raise ValueError("长度在1到100个字符之间")
    black_list = ['\\','/', '&', '*', '|', ';', '"', "'", '<', '>']
    for black in black_list:
        if black in filename:
            raise ValueError("文件名不能包含指定特殊字符")
    if os.path.exists(path):
        return ValueError("该文件已存在")
    if not os.path.exists(filepath):
        os.makedirs(filepath)
    # 创建空文件
    open(path, 'w+').close()

def create_dir(path,is_windows=False):
    """
    @name 创建目录
    @author lybbn<2024-02-22>
    """
    path = path.replace("//", "/")
    if path[-1] == '.':
        raise ValueError("目录名不能以'.'点结尾")
    dirname = os.path.basename(path)
    if len(dirname)>100 or len(dirname) < 1:
        raise ValueError("长度在1到100个字符之间")
    black_list = ['\\','/', '&', '*', '|', ';', '"', "'", '<', '>']
    for black in black_list:
        if black in dirname:
            raise ValueError("文件名不能包含指定特殊字符")
    if os.path.exists(path):
        return ValueError("该目录已存在")
    os.makedirs(path)

def delete_dir(path,is_windows=False):
    """
    @name 删除目录
    @author lybbn<2024-02-22>
    """
    if not os.path.exists(path) and not os.path.islink(path):
        raise ValueError("目录不存在")
    
    #检查哪些目录不能被删除
    check_no_delete(path,is_windows)

    if os.path.islink(path):
        os.remove(path)
    else:
        shutil.rmtree(path)

def delete_file(path,is_windows=False):
    """
    @name 删除文件
    @author lybbn<2024-02-22>
    """
    if not os.path.exists(path) and not os.path.islink(path):
        raise ValueError("文件不存在")
    
    #检查哪些目录不能被删除
    check_no_delete(path,is_windows)
    
    os.remove(path)

def rename_file(sPath,dPath,is_windows=False):
    """
    @name 重命名文件或目录
    @author lybbn<2024-02-22>
    @params sPath 源路径
    @params dPath 新路径
    """
    if sPath == dPath:
        return ValueError("源目标名称相同，已忽略")
    dPath = dPath.replace("//", "/")
    sPath = sPath.replace('//', '/')
    if dPath[-1] == '.':
        raise ValueError("不能以'.'点结尾")
    if not os.path.exists(sPath):
        raise ValueError("源文件/目录不存在")
    if os.path.exists(dPath):
        raise ValueError("目标存在相同名称")
    if dPath[-1] == '/':
       dPath = dPath[:-1]
    
    #安全检查
    if check_in_black_list(dPath,is_windows):
        raise ValueError("与系统内置冲突，请更换名称")

    os.rename(sPath, dPath)

def copy_file(sPath,dPath,is_windows=False):
    """
    @name 复制文件
    @author lybbn<2024-02-22>
    @params sPath 源路径
    @params dPath 新路径
    """
    # if sPath == dPath:
    #     raise ValueError("源目标相同，已忽略")
    dPath = dPath.replace("//", "/")
    sPath = sPath.replace('//', '/')
    if dPath[-1] == '.':
        raise ValueError("不能以'.'点结尾")
    if not os.path.exists(sPath):
        raise ValueError("源文件不存在")
    # if os.path.exists(dPath):
    #     raise ValueError("目标存在相同名称")

    shutil.copyfile(sPath, dPath)

def copy_dir(sPath,dPath,is_windows=False,cover=False):
    """
    @name 复制目录
    @author lybbn<2024-02-22>
    @params sPath 源路径
    @params dPath 新路径
    """
    if sPath == dPath:
        raise ValueError("源和目标相同，已忽略")
    dPath = dPath.replace("//", "/")
    sPath = sPath.replace('//', '/')
    if dPath[-1] == '.':
        raise ValueError("不能以'.'点结尾")
    if not os.path.exists(sPath):
        raise ValueError("源目录不存在")
    if cover and os.path.exists(dPath):
        shutil.rmtree(dPath)
    # if os.path.exists(dPath):
    #     raise ValueError("目标存在相同名称")
    # if not os.path.exists(dPath):
    #     os.makedirs(dPath)
    shutil.copytree(sPath, dPath)

def move_file(sPath,dPath,is_windows=False,cover=False):
    """
    @name 移动文件/目录
    @author lybbn<2024-02-22>
    @params sPath 源路径
    @params dPath 新路径
    """
    if sPath == dPath:
        raise ValueError("源和目标相同，已忽略")
    dPath = dPath.replace("//", "/")
    sPath = sPath.replace('//', '/')
    if dPath[-1] == '.':
        raise ValueError("不能以'.'点结尾")
    if dPath[-1] == '/':
       dPath = dPath[:-1]
    if not os.path.exists(sPath):
        raise ValueError("源目录不存在")
    #安全检查
    if check_in_black_list(dPath,is_windows):
        raise ValueError("与系统内置冲突，请更换名称")
    is_dir = os.path.isdir(sPath)
    if cover and os.path.exists(dPath):
        if is_dir:
            shutil.rmtree(dPath)
        else:
            os.remove(dPath)

    shutil.move(sPath, dPath)
    
def batch_operate(param,is_windows=False):
    """
    @name 批量操作（移动、复制、压缩、权限、删除）
    @author lybbn<2024-02-22>
    @params param 请求参数
    """
    type = param.get('type',None)
    if type in ['copy','move']:
        confirm = param.get('confirm',False)
        skip_list = ast_convert(param.get('skipList',[]))#需要跳过覆盖的文件列表
        dPath = param.get('path',"")
        sPath = ast_convert(param.get('spath',[]))
        if not dPath or not sPath:
            return False,"参数错误",4000,None
        dPath = dPath.replace('//', '/')
        # if dPath[-1] == '/':
        #     dPath = dPath[:-1]
        conflict_list = []
        if not confirm:#初次先检查有冲突则返回确认
            for d in sPath:
                if d[-1] == '.':
                    raise ValueError("%s不能以'.'点结尾"%d)
                if d[-1] == '/':
                    d = d[:-1]
                dfile = dPath + '/' + os.path.basename(d)
                if os.path.exists(dfile):
                    conflict_list.append({
                        'path':d,
                        'name':os.path.basename(d)
                    })
            if conflict_list:
                return False,"文件冲突",4050,conflict_list
        
        if skip_list:
            for s in skip_list:
                if s['path'] in sPath:
                    sPath.remove(s)

        if type == 'copy':
            for sf in sPath:
                dfile = dPath + '/' + os.path.basename(sf)
                if os.path.commonpath([dfile, sf]) == sf:
                    return False,'从{}复制到{}有包含关系，请更换目标目录！'.format(sf, dfile),4000,None
            for sf in sPath:
                dfile = dPath + '/' + os.path.basename(sf)
                if os.path.isdir(sf):
                    shutil.copytree(sf, dfile)
                else:
                    shutil.copyfile(sf, dfile)
            return True,"批量复制成功",2000,None
        else:
            for sf in sPath:
                dfile = dPath + '/' + os.path.basename(sf)
                move_file(sPath=sf,dPath=dfile,is_windows=is_windows,cover=True)
            return True,"批量剪切成功",2000,None
    elif type == 'zip':
        dPath = param.get('path',"")
        sPath = ast_convert(param.get('spath',[]))
        zip_type = param.get('zip_type',"")
        if not dPath or not sPath:
            return False,"参数错误",4000,None
        if not zip_type in ["tar","zip"]:
            return False,"不支持的压缩格式",4000,None
        dPath = dPath.replace('//', '/')
        # if dPath[-1] == '/':
        #     dPath = dPath[:-1]
        from apps.systask.tasks import func_zip
        func_zip(zip_filename=dPath,items=sPath,zip_type=zip_type)
        return True,"压缩成功",2000,None
    elif type == 'unzip':
        dPath = param.get('path',"")
        sPath = param.get('spath',"")
        zip_type = param.get('zip_type',"")
        if not dPath or not sPath:
            return False,"参数错误",4000,None
        dPath = dPath.replace('//', '/')
        from apps.systask.tasks import func_unzip
        func_unzip(zip_filename=sPath,extract_path=dPath)
        return True,"解压成功",2000,None
    elif type == 'pms':
        pass
    elif type == 'del':
        sPath = ast_convert(param.get('spath',[]))
        for sf in sPath:
            if os.path.isdir(sf):
                delete_dir(path=sf,is_windows=is_windows)
            else:
                delete_file(path=sf,is_windows=is_windows)
        return True,"批量删除成功",2000,None
    else:
        return False,"类型错误",4000,None
