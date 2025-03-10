#!/bin/python
#coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2025-02-17
# +-------------------------------------------------------------------
# | EditDate: 2025-02-17
# +-------------------------------------------------------------------

# ------------------------------
# docker 仓库管理
# ------------------------------
from apps.sysdocker.models import RyDockerRepo
from utils.customView import CustomAPIView
from utils.pagination import CustomPagination
from utils.viewset import CustomModelViewSet
from utils.serializers import CustomModelSerializer
from utils.common import get_parameter_dic
from utils.jsonResponse import ErrorResponse,DetailResponse,SuccessResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from utils.ruyiclass.dockerClass import DockerClient
from apps.syslogs.logutil import RuyiAddOpLog

class RyDockerRepoSimpleSerializer(CustomModelSerializer):
    """
    容器仓库 简化序列化器
    """

    class Meta:
        model = RyDockerRepo
        fields = ["id","name","url","is_auth"]
        read_only_fields = ["id"]

class RyDockerRepoSerializer(CustomModelSerializer):
    """
    容器仓库 序列化器
    """

    class Meta:
        model = RyDockerRepo
        fields = "__all__"
        read_only_fields = ["id"]

class RyDockerRepoCreateUpdateServerSerializer(CustomModelSerializer):
    """
    容器仓库 序列化器
    """

    class Meta:
        model = RyDockerRepo
        fields = "__all__"
        read_only_fields = ["id"]

class RyDockerRepoViewSet(CustomModelViewSet):
    """
    容器仓库接口
    """
    queryset = RyDockerRepo.objects.all().order_by('-create_at')
    serializer_class = RyDockerRepoSerializer
    create_serializer_class = RyDockerRepoCreateUpdateServerSerializer
    update_serializer_class = RyDockerRepoCreateUpdateServerSerializer
    search_fields = ('name','url')
    
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        is_simple = get_parameter_dic(request).get("is_simple","")
        if page is not None:
            if is_simple:
                serializer = RyDockerRepoSimpleSerializer(page, many=True, request=request)
            else:
                serializer = self.get_serializer(page, many=True, request=request)
            tmp_data = serializer.data
            return self.get_paginated_response(tmp_data)
        else:  
            return SuccessResponse(data=[], msg="获取成功")

    def create(self, request, *args, **kwargs):
        reqData = get_parameter_dic(request)
        name = reqData.get("name","")
        is_auth = reqData.get("is_auth",False)
        username = reqData.get("username","")
        password = reqData.get("password","")
        protocol = reqData.get("protocol","")
        url = reqData.get("url","")
        dockcli=None
        if is_auth:
            dockcli = DockerClient()
            if not username or not password:
                return ErrorResponse(msg="请提供仓库账号密码")
            res1,msg1 = dockcli.login_test(protocol+"://"+url, username, password)
            if not res1:return ErrorResponse(msg=msg1)
        if protocol not in ["http","https"]:return ErrorResponse(msg="协议错误")
        extra_msg=""
        serializer = self.get_serializer(data=reqData, request=request)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        if protocol == "http":
            extra_msg="-但需重启docker生效"
            if not dockcli:dockcli = DockerClient()
            dockcli.add_insecure_registries({'url':url})
        RuyiAddOpLog(request,msg="【容器】-【仓库】=>【新增】=>%s"%name,module="dockermg")
        return DetailResponse(data=serializer.data, msg=f"新增成功{extra_msg}")
    
    def update(self, request, *args, **kwargs):
        return ErrorResponse(msg="接口禁用")
    
    def destroy(self, request, *args, **kwargs):
        instance_list = self.get_object_list()
        for sql_ins in instance_list:
            name = sql_ins.name
            if str(sql_ins.id) == '1':
                return ErrorResponse(msg=f"【{name}】官方库禁止删除")
            sql_ins.delete()
            RuyiAddOpLog(request,msg="【容器】-【仓库】=>【删除】=>%s "%name,module="dockermg")
        return DetailResponse(data=[], msg="删除成功")