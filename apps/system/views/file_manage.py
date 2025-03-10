#!/bin/python
#coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2024-02-29
# +-------------------------------------------------------------------
# | EditDate: 2024-02-29
# +-------------------------------------------------------------------

# ------------------------------
# 文件管理
# ------------------------------
import os,re
import time
from math import ceil
from rest_framework.views import APIView
from utils.customView import CustomAPIView
from utils.jsonResponse import SuccessResponse,ErrorResponse,DetailResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from utils.common import get_parameter_dic,GetWebRootPath,md5,WriteFile,ast_convert,GetBackupPath,RunCommand
from utils.security.files import list_files_in_directory,get_directory_size,delete_file,delete_dir,create_file,create_dir,rename_file,copy_file,copy_dir,move_file
from utils.security.files import get_filedir_attribute,batch_operate,get_filename_ext,auto_detect_file_language
from utils.security.no_delete_list import check_in_black_list
import platform
from django.http import FileResponse,StreamingHttpResponse
from django.utils.encoding import escape_uri_path
import mimetypes
from utils.streamingmedia_response import stream_video
from django.conf import settings
from utils.security.security_path import ResponseNginx404
from apps.syslogs.logutil import RuyiAddOpLog
from apps.sysbak.models import RuyiBackup

def get_type_name(type):
    c_type_name = ""
    if type == "copy":
        c_type_name = "复制"
    elif type == "move":
        c_type_name = "移动"
    elif type == "zip":
        c_type_name = "压缩"
    elif type == "unzip":
        c_type_name = "解压"
    return c_type_name

class RYFileManageView(CustomAPIView):
    """
    get:
    文件管理
    post:
    文件管理
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        reqData = get_parameter_dic(request)
        action = reqData.get("action","")
        is_windows = True if platform.system() == 'Windows' else False

        #路径处理
        path = reqData.get("path",GetWebRootPath())
        if path == "default":
            path = GetWebRootPath()
        if not path:#根目录
            if is_windows:
                path = ""
            else:
                path = "/"
        if is_windows:#windows 路径处理
            path = path.replace("\\", "/")

        #接口逻辑处理
        if action == "list_dir":
            containSub = reqData.get("containSub",False)
            isDir = reqData.get("isDir",False)#只显示目录
            search = reqData.get("search","")
            if search:
                search = search.strip().lower()
            order = reqData.get("order","")
            sort = reqData.get("sort","name")
            is_reverse = True if (order and order == "desc") else False
            data_info = list_files_in_directory(dst_path=path,sort=sort,is_windows=is_windows,is_reverse=is_reverse,search=search,containSub=containSub,isDir=isDir)
            data_dirs = data_info.get('data',[])
            page = int(reqData.get("page",1))
            limit = int(reqData.get("limit",100))
            #一次最大条数限制
            limit = 3000 if limit > 3000 else limit
            total_nums = data_info['total_nums']
            file_nums = data_info['file_nums']
            dir_nums = data_info['dir_nums']
            total_pages = ceil(total_nums / limit)
            if page > total_pages:
                page = total_pages
            page = 1 if page<1 else page
            # 根据分页参数对结果进行切片
            start_idx = (page - 1) * limit
            end_idx = start_idx + limit
            paginated_data = data_dirs[start_idx:end_idx]
            if not is_windows:
                # directory, filename = os.path.split(path)
                if path == "/":
                    directory_dict_list = []
                else:
                    directory_list = path.split(os.path.sep)
                    directory_dict_list = [{'name': directory_list[i-1], 'url': os.sep.join(directory_list[:i])} for i in range(1,len(directory_list)+1)]
            else:
                # 去掉盘符部分
                drive_name = path.split(':')[0]
                if drive_name:
                    drive_name.lower()
                try:
                    path_without_drive =path.split(':')[1] if drive_name else None
                except:
                    return ErrorResponse(msg="路径错误：%s"%path)
                # 按斜杠分割路径
                if not path_without_drive or path_without_drive == "/":
                    directory_list = []
                    directory_dict_list = []
                else:
                    directory_list = path_without_drive.strip('/').strip('\\').split('/')
                    # 获取每个名称的路径
                    path_list = ['/'.join(directory_list[:i+1]) for i in range(len(directory_list))]
                    directory_dict_list = [{'name': name, 'url': drive_name+":/"+path_list[i]} for i, name in enumerate(directory_list)]
                if drive_name:
                    directory_dict_list.insert(0, {'name':drive_name+"盘",'url':drive_name+":/"})
                else:
                    directory_dict_list.insert(0, {'name':drive_name,'url':""})
            data = {
                'data':paginated_data,
                'path':path,
                'paths':directory_dict_list,
                'file_nums':file_nums,
                'dir_nums':dir_nums,
                'is_windows':is_windows
            }
            return SuccessResponse(data=data,total=total_nums,page=page,limit=limit)
        elif action == "get_filedir_attribute":
            data = get_filedir_attribute(path,is_windows=is_windows)
            if not data:
                return ErrorResponse(msg="目标不存在/或不支持查看")
            return DetailResponse(data=data)
        elif action == "calc_size":
            size = get_directory_size(path)
            data = {"size":size}
            return DetailResponse(data=data)
        elif action == "batch_operate":
            reqData['path'] = path
            c_type = reqData.get('type',None)
            c_type_name = get_type_name(c_type)
            isok,msg,code,data = batch_operate(param=reqData,is_windows=is_windows)
            new_msg = "【文件管理】-【批量】-【%s】-【%s】-从[%s]到[%s]"%(c_type_name,msg,ast_convert(reqData.get('spath',[])),path)
            if c_type == "del":
                new_msg = "【文件管理】-【批量】-【删除】-【%s】- %s"%(msg,ast_convert(reqData.get('spath',[])))
            RuyiAddOpLog(request,msg=new_msg,module="filemg",status=isok)
            if not isok:
                return ErrorResponse(code=code,msg=msg,data=data)
            return DetailResponse(msg=msg,data=data)
        elif action == "create_file":
            filename = reqData.get("filename","")
            if not filename:
                return ErrorResponse(msg="请填写文件名")
            path = path+"/"+filename
            create_file(path=path,is_windows=is_windows)
            RuyiAddOpLog(request,msg="【文件管理】-【创建文件】%s"%path,module="filemg")
            return DetailResponse(msg="创建成功")
        elif action == "create_dir":
            dirname = reqData.get("dirname","")
            if not dirname:
                return ErrorResponse(msg="请填写目录名")
            path = path+"/"+dirname
            create_dir(path=path,is_windows=is_windows)
            RuyiAddOpLog(request,msg="【文件管理】-【创建目录】%s"%path,module="filemg")
            return DetailResponse(msg="创建成功")
        elif action == "delete_file":
            delete_file(path=path,is_windows=is_windows)
            RuyiAddOpLog(request,msg="【文件管理】-【删除文件】%s"%path,module="filemg")
            return DetailResponse(msg="删除成功")
        elif action == "delete_dir":
            delete_dir(path=path,is_windows=is_windows)
            RuyiAddOpLog(request,msg="【文件管理】-【删除目录】%s"%path,module="filemg")
            return DetailResponse(msg="删除成功")
        elif action == "rename_file":
            sname = reqData.get("sname","")
            dname = reqData.get("dname","")
            if not sname or not dname:
                return ErrorResponse(msg="参数错误")
            sPath = path+"/"+sname
            dPath = path+"/"+dname
            rename_file(sPath=sPath,dPath=dPath,is_windows=is_windows)
            RuyiAddOpLog(request,msg="【文件管理】-【重命名】源：%s，目标：%s"%(sPath,dPath),module="filemg")
            return DetailResponse(msg="重命名成功")
        elif action == "copy_file":
            spath = reqData.get("spath","")
            name = reqData.get("name","")
            cover = reqData.get("cover",False)
            if not spath or not name:
                return ErrorResponse(msg="参数错误")
            dPath = path+"/"+name
            if not cover:
                if os.path.exists(dPath):
                    return ErrorResponse(code=4050,msg="目标存在相同文件")
            copy_file(sPath=spath,dPath=dPath,is_windows=is_windows)
            RuyiAddOpLog(request,msg="【文件管理】-【复制文件】源：%s，目标：%s"%(sPath,dPath),module="filemg")
            return DetailResponse(msg="复制成功")
        elif action == "copy_dir":
            spath = reqData.get("spath","")
            name = reqData.get("name","")
            cover = reqData.get("cover",False)
            if not spath or not name:
                return ErrorResponse(msg="参数错误")
            dPath = path+"/"+name
            if not cover:
                if os.path.exists(dPath):
                    return ErrorResponse(code=4050,msg="目标存在相同目录")
            copy_dir(sPath=spath,dPath=dPath,is_windows=is_windows,cover=cover)
            RuyiAddOpLog(request,msg="【文件管理】-【复制目录】源：%s，目标：%s"%(sPath,dPath),module="filemg")
            return DetailResponse(msg="复制成功")
        elif action == "move_file":
            spath = reqData.get("spath","")
            name = reqData.get("name","")
            cover = reqData.get("cover",False)
            if not spath or not name:
                return ErrorResponse(msg="参数错误")
            dPath = path+"/"+name
            if not cover:
                if os.path.exists(dPath):
                    return ErrorResponse(code=4050,msg="目标存在相同目录/文件")
            move_file(sPath=spath,dPath=dPath,is_windows=is_windows,cover=cover)
            RuyiAddOpLog(request,msg="【文件管理】-【移动】源：%s，目标：%s"%(spath,dPath),module="filemg")
            return DetailResponse(msg="移动成功")
        elif action == "read_file_body":
            ext = get_filename_ext(path)
            if ext in ['msi','psd','dll','sys','gz', 'zip', 'rar','7z', 'bz2', 'exe', 'db','sqlite','sqlite3','.mdb', 'pdf', 'doc', 'xls', 'docx', 'xlsx', 'ppt','pptx','mp4','flv','avi', 'png', 'gif', 'jpg', 'jpeg', 'bmp', 'icon', 'ico', 'pyc','class', 'so', 'pyd']:
                return ErrorResponse(msg="该文件不支持在线编辑")
            if not os.path.exists(path):
                return ErrorResponse(msg="该文件不存在")
            size = os.path.getsize(path)
            if size>3145728:#大于3M不建议在线编辑
                return ErrorResponse(msg="文件过大，不支持在线编辑")
            content = ""
            encoding = "utf-8"
            try:
                with open(path, 'r', encoding="utf-8", errors='ignore') as file:
                    content = file.read()
            except PermissionError as e:
                return ErrorResponse(msg="文件被占用，暂无法打开")
            except OSError as e:
                return ErrorResponse(msg="操作系统错误，暂无法打开")
            except:
                try:
                    with open(path, 'r', encoding="GBK", errors='ignore') as file:
                        content = file.read()
                    encoding = "GBK"
                except PermissionError as e:
                    return ErrorResponse(msg="文件被占用，暂无法打开")
                except OSError as e:
                    return ErrorResponse(msg="操作系统错误，暂无法打开")
                except Exception as e:
                    return ErrorResponse(msg="文件编码不兼容")
            data = {
                'st_mtime':str(int(os.stat(path).st_mtime)),
                'content':content,
                'size':size,
                'encoding':encoding,
                'language':auto_detect_file_language(path)
            }
            return DetailResponse(data=data,msg="获取成功")
        elif action == "save_file_body":
            content = reqData.get("content",None)
            st_mtime = reqData.get("st_mtime",None)
            force = reqData.get("force",False)
            if not force and st_mtime and not st_mtime == str(int(os.stat(path).st_mtime)):
                return ErrorResponse(code=4050,msg="在线文件可能发生变动，是否继续保存")
            WriteFile(path,content)
            RuyiAddOpLog(request,msg="【文件管理】-【修改文件】%s"%(path),module="filemg")
            return DetailResponse({'st_mtime':str(int(os.stat(path).st_mtime))},msg="保存成功")
        elif action == "set_file_access":
            user = reqData.get("user",None)
            group = reqData.get("group",None)
            access = reqData.get("access",False)
            issub = reqData.get("issub",True)
            if not user or not group:return ErrorResponse(msg="所属组/者不能为空")
            if not os.path.exists(path):
                return ErrorResponse(msg="路径不存在")
            numeric_pattern = re.compile(r'^[0-7]{3}$')
            if not numeric_pattern.match(str(access)):return ErrorResponse(msg="权限格式错误")
            if is_windows:
                return ErrorResponse(msg="windows目前还不支持此功能")
            if check_in_black_list(path=path,is_windows=is_windows):
                return ErrorResponse(msg="该目录不能设置权限")
            issub_str ="-R" if issub else ""
            command = f"chmod {issub_str} {access} {path}"
            res,err = RunCommand(command)
            if err:
                return ErrorResponse(msg=err)
            command1 = f"chown {issub_str} {user}:{group} {path}"
            res1,err1 =RunCommand(command1)
            if err1:
                return ErrorResponse(msg=err1)
            RuyiAddOpLog(request,msg=f"【文件管理】-【修改权限】{path} => 子目录:{issub} 权限:{access} {user}:{group}",module="filemg")
            return DetailResponse({'st_mtime':str(int(os.stat(path).st_mtime))},msg="设置成功")
        data = {}
        return DetailResponse(data=data)

class RYGetFileDownloadView(CustomAPIView):
    """
    get:
    根据文件token进行文件下载
    """
    permission_classes = []
    authentication_classes = []

    def get(self, request):
        reqData = get_parameter_dic(request)
        filename = reqData.get("filename",None)
        token = reqData.get("token",None)
        expires = reqData.get("expires",0)
        isok,msg = validate_file_token(filename=filename,expires=expires,token=token)
        if not isok:
            return ResponseNginx404()
        if not filename:
            return ErrorResponse(msg="参数错误")
        if not os.path.exists(filename):
            return ErrorResponse(msg="文件不存在")
        if not os.path.isfile(filename):
            return ErrorResponse(msg="参数错误")
        file_size = os.path.getsize(filename)
        content_type, encoding = mimetypes.guess_type(filename)
        content_type = content_type or 'application/octet-stream'
        response = StreamingHttpResponse(open(filename, 'rb'), content_type=content_type)
        response['Content-Disposition'] = f'attachment;filename="{escape_uri_path(os.path.basename(filename))}"'
        response['Content-Length'] = file_size
        RuyiAddOpLog(request,msg="【下载文件】%s"%(filename),module="filemg")
        return response

class RYFileDownloadView(CustomAPIView):
    """
    post:
    文件下载
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def post(self, request):
        reqData = get_parameter_dic(request)
        filename = reqData.get("filename",None)
        if not filename:
            return ErrorResponse(msg="参数错误")
        if not os.path.exists(filename):
            return ErrorResponse(msg="文件不存在")
        if not os.path.isfile(filename):
            return ErrorResponse(msg="参数错误")
        file_size = os.path.getsize(filename)
        response = FileResponse(open(filename, 'rb'))
        response['content_type'] = "application/octet-stream"
        response['Content-Disposition'] = f'attachment;filename="{escape_uri_path(os.path.basename(filename))}"'
        # response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response['Content-Length'] = file_size  # 设置文件大小
        RuyiAddOpLog(request,msg="【下载文件】%s"%(filename),module="filemg")
        return response


def generate_file_token(filename,expire=None):
    secret_key = settings.SECRET_KEY
    if not expire:
        expire = 43200
    expire_time = int(time.time()) + expire  # 设置过期时间
    # 生成安全签名 token
    signature = md5(f"{filename}-{expire_time}-{secret_key}")
    return {
        'token':signature,
        'expires':expire_time,
        'filename':filename
    }

def validate_file_token(filename,expires,token):
    expires = int(expires)
    current_time = int(time.time())
    secret_key = settings.SECRET_KEY
    # 校验安全签名 token
    expected_signature = md5(f"{filename}-{expires}-{secret_key}")
    if token == expected_signature:
        if current_time <= expires:
            return True,"ok"
        else:
            return False,"token已过期"
    else:
        return False,"无效的token"

class RYFileTokenView(CustomAPIView):
    """
    post:
    获取文件访问token
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        reqData = get_parameter_dic(request)
        filename = reqData.get("filename",None)
        if not filename:
            return ErrorResponse(msg="参数错误")
        if not os.path.exists(filename):
            return ErrorResponse(msg="文件不存在")
        data = generate_file_token(filename=filename)
        return DetailResponse(data=data)

class RYFileMediaView(CustomAPIView):
    """
    get:
    媒体文件
    """
    permission_classes = []
    authentication_classes = []

    def get(self, request):
        reqData = get_parameter_dic(request)
        filename = reqData.get("filename",None)
        token = reqData.get("token",None)
        expires = reqData.get("expires",0)
        isok,msg = validate_file_token(filename=filename,expires=expires,token=token)
        if not isok:
            return ResponseNginx404()
        if not filename:
            return ErrorResponse(msg="参数错误")
        if not os.path.exists(filename):
            return ErrorResponse(msg="文件不存在")
        if not os.path.isfile(filename):
            return ErrorResponse(msg="参数错误")
        content_type, encoding = mimetypes.guess_type(filename)
        content_type = content_type or 'application/octet-stream'
        if content_type in ['video/mp4','video/ogg', 'video/flv', 'video/avi', 'video/wmv', 'video/rmvb','audio/mp3','audio/x-m4a','audio/mpeg','audio/ogg']:
            response = stream_video(request, filename)#支持视频流媒体播放
            return response
        return ErrorResponse(msg="限制只能媒体文件")
    
class RYFileUploadView(CustomAPIView):
    """
    post:
    文件上传(支持分片断点续传)
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        reqData = get_parameter_dic(request)
        file = request.FILES.get('lyfile',None)
        filechunk_name = reqData.get('lyfilechunk',None)
        path = reqData.get("path",None)
        if not path:
            return ErrorResponse(msg="参数错误")
        is_backup_database_path = False
        if path[-1] == '/':
            path = path[:-1]
        if path == "backup_datebase_path":
            path = GetBackupPath()+"/database"
            is_backup_database_path = True
        if file:
            save_path = path+"/"+file.name
            if path and not os.path.exists(path):
                os.makedirs(path)
            with open(save_path, 'wb+') as destination:
                for ck in file.chunks():
                    destination.write(ck)
            if is_backup_database_path:
                RuyiBackup.objects.create(type=1,name=file.name,filename=os.path.abspath(save_path),size=file.size)
            RuyiAddOpLog(request,msg="【上传文件】%s"%(save_path),module="filemg")
            return DetailResponse(data=None,msg="上传成功")
        elif filechunk_name:
            chunk = reqData.get('chunk')
            chunkIndex = int(reqData.get('chunkIndex',0))
            chunkCount = int(reqData.get('chunkCount',0))
            if not chunkCount:
                return ErrorResponse(msg="参数错误") 
            if path and not os.path.exists(path):
                os.makedirs(path)
            # 保存文件分片
            with open(f'{path}/{filechunk_name}.part{chunkIndex}', 'wb') as destination:
                for content in chunk.chunks():
                    destination.write(content)

            # 如果所有分片上传完毕，合并文件
            if chunkIndex == chunkCount - 1:
                with open(f'{path}/{filechunk_name}', 'ab') as final_destination:
                    for i in range(chunkCount):
                        with open(f'{path}/{filechunk_name}.part{i}', 'rb') as part_file:
                            final_destination.write(part_file.read())
                        os.remove(f'{path}/{filechunk_name}.part{i}')  # 删除临时分片文件
                if is_backup_database_path:
                    RuyiBackup.objects.create(type=1,name=file.name,filename=os.path.abspath(save_path),size=file.size)
                RuyiAddOpLog(request,msg="【分片上传文件】【分片%s】%s"%(chunkIndex,f'{path}/{filechunk_name}'),module="filemg")
                return DetailResponse(data=None,msg="上传成功")
            RuyiAddOpLog(request,msg="【分片上传文件】【分片%s】%s"%(chunkIndex,f'{path}/{filechunk_name}'),module="filemg")
            return DetailResponse(data=None,msg=f'分片{chunkIndex}上传成功')
        else:
            return ErrorResponse(msg="参数错误")