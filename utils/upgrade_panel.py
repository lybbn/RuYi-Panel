#!/bin/python
#coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2025-01-26
# +-------------------------------------------------------------------

# ------------------------------
# 更新面板 v1.0.0
# ------------------------------

import os
import hashlib
import requests
from utils.common import ProgramRootPath,GetTmpPath,GetLogsPath,GetPanelPath,GetInstallPath,DeleteDir,DeleteFile,RunCommand,current_os,WriteFile,GetPythonPath
import zipfile
import time
import shutil

ruyi_panel_path = GetPanelPath()
ruyi_install_parent_path = GetInstallPath()
tmp_save_file = GetTmpPath()+'/ruyi.zip'
tmp_new_panel_dir = GetTmpPath()+"/ruyi"
bak_panel_dir = ruyi_install_parent_path+f'/ruyi_bak_{int(time.time())}'
tmp_updatelog_file = GetLogsPath()+'/ruyi_updatepanel.log'
web_pack_xd_path = "/web/dist/static"
web_pack_path = ruyi_panel_path+web_pack_xd_path

def print_log(msg):
    """
    @name 打印并记录日志
    """
    print(msg)
    WriteFile(tmp_updatelog_file, f"{msg}\n", mode='a')
    

def get_file_list(dpath, f_list,root_dir):
    """
    @name 递归获取目录所有文件列表(去除主目录路径root_dir)
    """
    if not os.path.exists(dpath):
        return
    files = os.listdir(dpath)
    for f in files:
        if current_os == "windows":
            f = f.replace('\\','/').lstrip('\\').lstrip('/')
        else:
            f = f.replace('//','').lstrip('/')
        if os.path.isdir(dpath + '/' + f):
            get_file_list(dpath + '/' + f, f_list,root_dir)
        else:
            sfile = (dpath + '/' + f).replace(root_dir,'')
            f_list.append(sfile)

def func_unzip(zip_filename,extract_path):
    """
    @name 解压
    @author lybbn<2024-03-07>
    @param zip_filename 压缩文件名（含路径）
    @param extract_path 需要解压的目标目录
    """
    _, ext = os.path.splitext(zip_filename)
    if ext == '.zip':
        with zipfile.ZipFile(zip_filename, 'r') as zipf:
            zipf.extractall(extract_path)
    else:
        raise ValueError("不支持的文件格式")
    if not os.path.exists(extract_path):
        return False
    return True

def get_file_name_from_url(url):
    """
    @name 使用 os.path.basename() 函数获取 URL 中的文件名
    @author lybbn<2024-02-22>
    """
    file_name = os.path.basename(url)
    return file_name

def download_url_file(url, save_path="",chunk_size=8192):
    """
    @name 下载网络文件
    @save_path 下载本地路径名称（包含文件名），为空则默认存储在tmp中
    @author lybbn<2024-02-22>
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
        headers = {}
        downloaded_size = 0
        if os.path.exists(save_path):
            downloaded_size = os.path.getsize(save_path)
            headers['Range'] = 'bytes={}-'.format(downloaded_size)
        r = requests.get(url, headers=headers, stream=True)
        total_size = int(r.headers.get('content-length', 0))
        if total_size == 0:
            return True,"下载成功"
        with open(save_path, 'ab') as f:
            for chunk in r.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
        return True,"下载成功"
    except:
        return False,"网络文件错误"

def DeleteDirGlob(path_pattern):
    """
    @name 模糊路径删除 如：'/ruyi/tmp/ruyi_bak_*'
    """
    import glob
    directories_to_delete = glob.glob(path_pattern)
    for dir_path in directories_to_delete:
        if os.path.isdir(dir_path):  # 确保是目录
            shutil.rmtree(dir_path)

def clear_update_tmp_files():
    """
    @name 清除更新过程产生的临时文件/目录
    """
    DeleteFile(tmp_save_file,empty_tips=False)
    DeleteDir(tmp_new_panel_dir)
    DeleteDir(bak_panel_dir)
    old_bak_panel_dir_pattern = ruyi_install_parent_path+'/ruyi_bak_*'
    DeleteDirGlob(old_bak_panel_dir_pattern)
    
def last_update_op():
    """
    @name 最终更新操作
    """
    if current_os == "windows":
        RunCommand(f'{ruyi_panel_path}/utils/scripts/update_init.bat {ruyi_panel_path} {GetPythonPath()}')
    else:
        RunCommand(f'bash {ruyi_panel_path}/utils/scripts/update_init.sh')

def get_file_hash(file_path, hash_algorithm="sha256"):
    hash_func = hashlib.new(hash_algorithm)
    with open(file_path, "rb") as f:
        # 以块读取文件，避免内存溢出
        while chunk := f.read(4096):
            hash_func.update(chunk)
    # 返回文件的哈希值（以十六进制格式）
    return hash_func.hexdigest()

def check_hash(f_list,src_dir,dst_dir):
    """
    @name 校验文件hash
    """
    result = []

    for f in f_list:
        f = f.lstrip('/')

        sfile = '{}/{}'.format(src_dir,f).replace('//','/')
        if not os.path.exists(sfile):
            continue
        dfile = '{}/{}'.format(dst_dir,f).replace('//','/')
        if not os.path.exists(dfile):
            print_log(f'文件 {dfile} 更新失败...x')
            result.append(sfile)
            continue

        def check_file_hash(sfile,dfile):
            sf_hash = get_file_hash(sfile)
            df_hash = get_file_hash(dfile)

            if df_hash != sf_hash:
                return False
            return True

        if not check_file_hash(sfile,dfile):
            print_log(f'文件 {dfile} 更新失败...x')
            result.append(f)
    return result

def update_copy_dir_files(f_list ,src_dir,dst_dir):
    """
    @name 更新面板文件
    @param f_list 需要拷贝的文件列表（不包含根目录）-- 新包文件列表
    @param src_dir 源目录
    @param dst_dir 目标目录
    """
    try:
        dst_dir = dst_dir.rstrip('/')
        if not os.path.exists(dst_dir):
            os.makedirs(dst_dir)

        i = 0
        src_percent = 0
        totalnums = len(f_list)
        for f in f_list:
            try:
                #calc进度
                i += 1
                src_percent  = int(i / totalnums * 100)
                if f.startswith("/data/") or f.startswith("/logs/"):#个人数据不备份，也不更新
                    continue
                print_log(f'正在更新： {i}/{totalnums}  .......................  {src_percent} %  {f}')

                #copy文件
                if f == '/': continue
                sfile = f'{src_dir.rstrip('/')}{f}'
                if not os.path.exists(sfile):
                    continue
                dfile = f'{dst_dir}{f}'
                d_root_dir = os.path.dirname(dfile)
                if not os.path.exists(d_root_dir): 
                    os.makedirs(d_root_dir)

                if os.path.isfile(sfile):
                    shutil.copyfile(sfile,dfile)
            except Exception as e:
                print_log(f'文件{dfile}，异常错误：{str(e)}')
                pass
        if totalnums == i:
            return True
    except:
        pass

    return False

def bakcup_copy_dir_files(f_list,old_web_list,src_dir,dst_dir):
    """
    @name 备份面板(只备份新包文件将要更新的文件和web目录)
    @param f_list 需要拷贝的文件列表（不包含根目录）-- 新包文件列表
    @param old_web_list 备份web包的static里的文件列表(如：/web/dist/static/123.js)
    @param src_dir 源目录
    @param dst_dir 目标目录
    """
    try:
        dst_dir = dst_dir.rstrip('/')
        if not os.path.exists(dst_dir):
            os.makedirs(dst_dir)
        
        new_f_list = []
        for nf in f_list:
            if nf.startswith(web_pack_xd_path):
                continue
            new_f_list.append(nf)
        
        new_f_list = new_f_list + old_web_list
        
        i = 0
        src_percent = 0
        totalnums = len(new_f_list)
        for f in new_f_list:
            try:
                #calc进度
                i += 1
                src_percent  = int(i / totalnums * 100)
                if f.startswith("/data/") or f.startswith("/logs/"):#个人数据不备份，也不更新
                    continue
                sfile = f'{src_dir.rstrip('/')}{f}'
                print_log(f'备份面板文件： {i}/{totalnums}  .......................  {src_percent} %  {sfile}')

                #copy文件
                if f == '/': continue
                if not os.path.exists(sfile):
                    continue
                
                dfile = f'{dst_dir}{f}'
                d_root_dir = os.path.dirname(dfile)
                if not os.path.exists(d_root_dir): 
                    os.makedirs(d_root_dir)

                if os.path.isfile(sfile):
                    shutil.copyfile(sfile,dfile)
            except Exception as e:
                print_log(f'文件{sfile}，异常错误：{str(e)}')
                pass
        if totalnums == i:
            return True
    except Exception as e:
        print_log(f'备份异常：{str(e)}')

    return False


def rollback_copy_dir_files(f_list,old_web_list,src_dir,dst_dir):
    """
    @name 回滚面板(只回滚新包文件将要更新的文件和web目录)
    @param f_list 需要拷贝的文件列表（不包含根目录）-- 新包文件列表
    @param old_web_list 备份web包的static里的文件列表(如：/web/dist/static/123.js)
    @param src_dir 源目录
    @param dst_dir 目标目录
    """
    try:
        dst_dir = dst_dir.rstrip('/')
        if not os.path.exists(dst_dir):
            os.makedirs(dst_dir)
            
        new_f_list = []
        for nf in f_list:
            if nf.startswith(web_pack_xd_path):
                continue
            new_f_list.append(nf)
        
        new_f_list = new_f_list + old_web_list

        i = 0
        src_percent = 0
        totalnums = len(new_f_list)
        for f in new_f_list:
            try:
                #calc进度
                i += 1
                src_percent  = int(i / totalnums * 100)
                if f.startswith("/data/") or f.startswith("/logs/"):#个人数据不备份，也不更新，也不回滚
                    continue
                print_log(f'回滚 {i}/{totalnums}  .......................  {src_percent} %  {f}')

                #copy文件
                if f == '/': continue
                sfile = f'{src_dir.rstrip('/')}{f}'
                if not os.path.exists(sfile):
                    continue
                dfile = f'{dst_dir}{f}'
                d_root_dir = os.path.dirname(dfile)
                if not os.path.exists(d_root_dir): 
                    os.makedirs(d_root_dir)

                if os.path.isfile(sfile):
                    shutil.copyfile(sfile,dfile)
            except Exception as e:
                print_log(f'文件{dfile}，异常错误：{str(e)}')
                pass
        if totalnums == i:
            return True
    except:
        pass

    return False

def update_ruyi_panel():
    """
    @name 更新面板
    @author lybbn
    """
    local_dev_files=["README_AUTHOR.md","create_package.py"]
    zs_program_path = ProgramRootPath()
    for ldf in local_dev_files:
        if os.path.exists(f"{ruyi_panel_path}/{ldf}") or os.path.exists(f"{zs_program_path}/{ldf}"):
            print("本地开发模式，禁止此操作！！！")
            return False,"本地开发模式"
    clear_update_tmp_files()
    DeleteFile(tmp_updatelog_file,empty_tips=False)
    base_url = "https://download.lybbn.cn/ruyi/install"
    if current_os == "windows":
        up_url = '/windows/ruyi.zip'
    else:
        up_url = "/linux/ruyi.zip"
    download_url = base_url+up_url
    print_log('正在下载面板文件【ruyi.zip】...')
    dl_ok,err = download_url_file(download_url,save_path=tmp_save_file)
    if dl_ok and os.path.exists(tmp_save_file):
        print_log('正在解压面板文件【ruyi.zip】...')
        if func_unzip(zip_filename=tmp_save_file,extract_path=tmp_new_panel_dir):
            file_list = []
            new_s_dir = tmp_new_panel_dir+"/ruyi"
            get_file_list(tmp_new_panel_dir,file_list,new_s_dir)
            
            old_web_static_list = []
            get_file_list(web_pack_path,old_web_static_list,ruyi_panel_path)
            
            print_log('正在备份面板...')
            if bakcup_copy_dir_files(file_list,old_web_static_list,ruyi_panel_path, bak_panel_dir):
                def update_panel_files(f_list,src_dir,retry_nums = 1):
                    if update_copy_dir_files(f_list,src_dir,ruyi_panel_path):
                        print_log('正在校验面板文件完整性...')
                        res = check_hash(f_list,src_dir,ruyi_panel_path)
                        if not res:
                            print_log('SUCCESS：面板更新成功！！！')
                            return True,"更新成功"
                        else:
                            if retry_nums < 3:
                                print_log(f'正在第【{retry_nums + 1}】次重试更新面板，尝试解除文件占用...')
                                for f in res:
                                    dsc_file = '{}/{}'.format(ruyi_panel_path,f).replace('//','/')
                                    if not current_os == "windows":
                                        RunCommand(f'chattr -a -i {dsc_file}')
                                    else:
                                        pass
                                return update_panel_files(res,src_dir,retry_nums + 1)
                            else:
                                for f in res:
                                    dsc_file = '{}/{}'.format(ruyi_panel_path,f).replace('//','/')
                                    print_log(dsc_file)
                                print_log(f'ERROR：校验失败，有【{len(res)}】个文件无法更新，正在回滚操作。')
                    return False,"更新失败"
                #删掉web包，避免无用文件过多堆积
                DeleteDir(web_pack_path)
                udok,err= update_panel_files(file_list,new_s_dir)
                if not udok:
                    #恢复备份
                    DeleteDir(web_pack_path)
                    rollback_copy_dir_files(file_list,old_web_static_list,bak_panel_dir,ruyi_panel_path)
                    print_log('操作失败，已回滚此次操作...')
                else:
                    clear_update_tmp_files()
                    last_update_op()
                    return True,err
            else:
                err="备份失败"
        else:
            err="解压失败"
    clear_update_tmp_files()
    return False,err

if __name__ == '__main__':
    update_ruyi_panel()