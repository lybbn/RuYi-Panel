#!/usr/bin/python
#coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2025-06-02
# +-------------------------------------------------------------------
# | EditDate: 2025-06-02
# +-------------------------------------------------------------------

# ------------------------------
# docker 容器编排管理
# ------------------------------
import os
from utils.customView import CustomAPIView
from utils.common import get_parameter_dic
from utils.jsonResponse import ErrorResponse, DetailResponse, SuccessResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from apps.syslogs.logutil import RuyiAddOpLog
from utils.ruyiclass.dockerInclude.ry_dk_compose import RyDockerCompose


class RYDockerComposeListManageView(CustomAPIView):
    """
    get:
    获取容器编排列表
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        reqData = get_parameter_dic(request)
        search = reqData.get("search", "")
        compose = RyDockerCompose()
        if not compose.is_docker_running():
            return ErrorResponse(msg="Docker服务未运行")
        data = compose.get_compose_list()
        if search:
            data = [d for d in data if search.lower() in d['name'].lower()]
        total = len(data)
        page = int(reqData.get("page", 1))
        limit = int(reqData.get("limit", 10))
        start = (page - 1) * limit
        end = start + limit
        paginated = data[start:end]
        return SuccessResponse(data=paginated, total=total, page=page, limit=limit)


class RYDockerComposeManageView(CustomAPIView):
    """
    post:
    容器编排操作
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        reqData = get_parameter_dic(request)
        action = reqData.get("action", "")
        compose = RyDockerCompose()

        if not compose.is_docker_running():
            return ErrorResponse(msg="Docker服务未运行")

        if action == "add":
            name = reqData.get("name", "")
            yml_content = reqData.get("yml_content", "")
            env_content = reqData.get("env_content", "")
            isok, msg = compose.create_compose(name, yml_content, env_content)
            if not isok:
                return ErrorResponse(msg=msg)
            RuyiAddOpLog(request, msg=f"【容器编排】=> 创建：{name}", module="dockermg")
            return DetailResponse(data=msg, msg="创建成功")

        elif action == "up":
            name = reqData.get("name", "")
            config_path = reqData.get("config_path", "")
            isok, msg = compose.up_compose(config_path)
            if not isok:
                return ErrorResponse(msg=msg)
            RuyiAddOpLog(request, msg=f"【容器编排】=> 启动：{name}", module="dockermg")
            return DetailResponse(msg=msg)

        elif action == "start":
            name = reqData.get("name", "")
            config_path = reqData.get("config_path", "")
            isok, msg = compose.start_compose(config_path)
            if not isok:
                return ErrorResponse(msg=msg)
            RuyiAddOpLog(request, msg=f"【容器编排】=> 启动：{name}", module="dockermg")
            return DetailResponse(msg=msg)

        elif action == "stop":
            name = reqData.get("name", "")
            config_path = reqData.get("config_path", "")
            isok, msg = compose.stop_compose(config_path)
            if not isok:
                return ErrorResponse(msg=msg)
            RuyiAddOpLog(request, msg=f"【容器编排】=> 停止：{name}", module="dockermg")
            return DetailResponse(msg=msg)

        elif action == "restart":
            name = reqData.get("name", "")
            config_path = reqData.get("config_path", "")
            isok, msg = compose.restart_compose(config_path)
            if not isok:
                return ErrorResponse(msg=msg)
            RuyiAddOpLog(request, msg=f"【容器编排】=> 重启：{name}", module="dockermg")
            return DetailResponse(msg=msg)

        elif action == "down":
            name = reqData.get("name", "")
            config_path = reqData.get("config_path", "")
            isok, msg = compose.down_compose(config_path)
            if not isok:
                return ErrorResponse(msg=msg)
            RuyiAddOpLog(request, msg=f"【容器编排】=> 停止并删除容器：{name}", module="dockermg")
            return DetailResponse(msg=msg)

        elif action == "remove":
            name = reqData.get("name", "")
            config_path = reqData.get("config_path", "")
            isok, msg = compose.remove_compose(name, config_path)
            if not isok:
                return ErrorResponse(msg=msg)
            RuyiAddOpLog(request, msg=f"【容器编排】=> 删除：{name}", module="dockermg")
            return DetailResponse(msg=msg)

        elif action == "rebuild":
            name = reqData.get("name", "")
            config_path = reqData.get("config_path", "")
            isok, msg = compose.rebuild_compose(config_path)
            if not isok:
                return ErrorResponse(msg=msg)
            RuyiAddOpLog(request, msg=f"【容器编排】=> 重建：{name}", module="dockermg")
            return DetailResponse(msg=msg)

        elif action == "pull":
            name = reqData.get("name", "")
            config_path = reqData.get("config_path", "")
            isok, msg = compose.pull_compose(config_path)
            if not isok:
                return ErrorResponse(msg=msg)
            RuyiAddOpLog(request, msg=f"【容器编排】=> 更新镜像：{name}", module="dockermg")
            return DetailResponse(msg=msg)

        elif action == "update_yml":
            name = reqData.get("name", "")
            config_path = reqData.get("config_path", "")
            yml_content = reqData.get("yml_content", "")
            isok, msg = compose.update_compose_yml(config_path, yml_content)
            if not isok:
                return ErrorResponse(msg=msg)
            RuyiAddOpLog(request, msg=f"【容器编排】=> 更新配置：{name}", module="dockermg")
            return DetailResponse(msg=msg)

        elif action == "update_env":
            name = reqData.get("name", "")
            env_path = reqData.get("env_path", "")
            env_content = reqData.get("env_content", "")
            isok, msg = compose.update_compose_env(env_path, env_content)
            if not isok:
                return ErrorResponse(msg=msg)
            RuyiAddOpLog(request, msg=f"【容器编排】=> 更新环境变量：{name}", module="dockermg")
            return DetailResponse(msg=msg)

        elif action == "logs":
            name = reqData.get("name", "")
            config_path = reqData.get("config_path", "")
            tail = reqData.get("tail", 200)
            isok, msg = compose.get_compose_logs(config_path, tail=int(tail))
            if not isok:
                return ErrorResponse(msg=msg)
            return DetailResponse(data={"logs": msg})

        elif action == "detail":
            name = reqData.get("name", "")
            isok, data = compose.get_compose_detail(name)
            if not isok:
                return ErrorResponse(msg=data)
            return DetailResponse(data=data)

        return ErrorResponse(msg="无效的操作类型")
