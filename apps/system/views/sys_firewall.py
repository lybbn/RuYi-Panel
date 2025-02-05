#!/bin/python
#coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2024-09-13
# +-------------------------------------------------------------------
# | EditDate: 2024-09-13
# +-------------------------------------------------------------------

# ------------------------------
# 系统防火墙
# ------------------------------

import re
from rest_framework.views import APIView
from utils.customView import CustomAPIView
from utils.jsonResponse import SuccessResponse,ErrorResponse,DetailResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from utils.pagination import CustomPagination
from utils.customView import CustomAPIView
from utils.common import get_parameter_dic,current_os,formatdatetime,RunCommand,ast_convert
from apps.syslogs.logutil import RuyiAddOpLog
from utils.server.system import system
from django.conf import settings

class RYSysFirewallView(CustomAPIView):
    """
    get:
    系统防火墙列表
    post:
    防火墙设置
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def get(self,request):
        is_windows = True  if current_os == "windows" else False
        reqData = get_parameter_dic(request)
        search = reqData.get("search","")
        action = reqData.get("action","")
        if action == "firewall_info":
            data = system.GetFirewallInfo()
            return DetailResponse(data=data)
        elif action in ["forwarding_rules"]:
            data = system.GetPortProxyRules({'search':search})
            return DetailResponse(data=data)

        if is_windows:
            if action in ["in_rules","out_rules"]:
                dir ='in' if action == "in_rules" else "out"
                status = reqData.get("status","")
                data = system.GetFirewallRules({'dir':dir,'search':search,'status':status})
                return DetailResponse(data=data)
        else:
            if action in ["port_rules"]:
                dir = reqData.get("dir","all")
                status = reqData.get("status","")
                data = system.GetFirewallRules({'dir':dir,'search':search,'status':status})
                return DetailResponse(data=data)
            return ErrorResponse(msg="类型错误")
        return ErrorResponse(msg="类型错误")

    def post(self, request):
        reqData = get_parameter_dic(request)
        action = reqData.get("action","")
        is_windows = True  if current_os == "windows" else False
        if action == "set_ping":
            status = reqData.get("status",True)
            isok,msg = system.SetFirewallPing(status=status)
            if isok:
                statusname = "开启"
                if not status:
                    statusname = "关闭"
                RuyiAddOpLog(request,msg="【安全】-【系统防火墙】-【禁止Ping】 => %s"%statusname,module="safe")
                return DetailResponse(msg="设置成功")
            else:
                return ErrorResponse(msg="设置失败")
        elif action == "set_status":
            status = reqData.get("status","")
            isok,msg = system.SetFirewallStatus(status=status)
            if isok:
                statusname = "开启"
                if status == "stop":
                    statusname = "关闭"
                RuyiAddOpLog(request,msg="【安全】-【系统防火墙】- %s防火墙"%statusname,module="safe")
                return DetailResponse(msg="设置成功")
            else:
                return ErrorResponse(msg="设置失败")
        elif action == "del_rule":
            if is_windows:
                name = reqData.get("name","")
                if not name:
                    return ErrorResponse(msg="参数错误")
                protocol = reqData.get("protocol","")
                localport = reqData.get("localport","")
                isok = system.DelFirewallRule(param={'name':name,'protocol':protocol,'localport':localport})
            else:
                protocol = reqData.get("protocol","")
                localport = reqData.get("port","")
                address = reqData.get("address","")
                handle = reqData.get("handle","")
                isok = system.DelFirewallRule(param={'address':address,'protocol':protocol,'localport':localport,'handle':handle})
            if isok:
                if is_windows:
                    rulenames = f"规则名：{name}"
                else:
                    rulenames = ""
                if protocol:
                    rulenames = rulenames + f" 协议：{protocol}"
                if localport:
                    rulenames = rulenames + f" 端口：{localport}"
                RuyiAddOpLog(request,msg="【安全】-【系统防火墙】- 删除规则 => %s"%rulenames,module="safe")
                return DetailResponse(msg="删除成功")
            else:
                return ErrorResponse(msg="删除失败")
        elif action == "add_rule":
            if is_windows:
                name = reqData.get("name","")
                if not name:
                    return ErrorResponse(msg="规则名不能为空")
                protocol = reqData.get("protocol","")
                direction = reqData.get("direction","")
                if protocol not in ['tcp','TCP','UDP','udp']:
                    return ErrorResponse(msg="协议类型错误")
                if direction not in ['in','out']:
                    return ErrorResponse(msg="方向类型错误")
                handle = reqData.get("handle","")
                if handle not in ['allow','block']:
                    return ErrorResponse(msg="策略类型错误")
                localport = reqData.get("localport","")
                rep = r"^(?:\d{1,5}(-\d{1,5})?(,\d{1,5}(-\d{1,5})?)*|\d{1,5}(,\d{1,5})*|\*)$"
                if not re.match(rep, localport):
                    return ErrorResponse(msg="端口格式错误")
                isok = system.AddFirewallRule(param={'name':name,'protocol':protocol,'localport':localport,'handle':handle,'direction':direction})
                if isok:
                    rulenames = f"规则名：{name}"
                    if protocol:
                        rulenames = rulenames + f" 协议：{protocol}"
                    if localport:
                        rulenames = rulenames + f" 端口：{localport}"
                    rulenames = rulenames + f' 方向：{direction} 策略：{action}'
                    RuyiAddOpLog(request,msg="【安全】-【系统防火墙】- 添加规则 => %s"%rulenames,module="safe")
                    return DetailResponse(msg="添加成功")
                else:
                    return ErrorResponse(msg="添加失败")
            else:
                protocol = reqData.get("protocol","")
                localport = reqData.get("port","")
                address = reqData.get("address","")
                handle = reqData.get("handle","")
                direction = reqData.get("direction","")
                if direction not in ['in','out']:
                    return ErrorResponse(msg="方向类型错误")
                isok = system.AddFirewallRule(param={'address':address,'protocol':protocol,'localport':localport,'handle':handle})
                if isok:
                    rulenames=""
                    if protocol:
                        rulenames = rulenames + f" 协议：{protocol}"
                    if localport:
                        rulenames = rulenames + f" 端口：{localport}"
                    rulenames = rulenames + f' 方向：{direction} 策略：{action}'
                    RuyiAddOpLog(request,msg="【安全】-【系统防火墙】- 添加规则 => %s"%rulenames,module="safe")
                    return DetailResponse(msg="添加成功")
                else:
                    return ErrorResponse(msg="添加失败")
        elif action == "edit_rule":
            if is_windows:
                name = reqData.get("name","")
                if not name:
                    return ErrorResponse(msg="规则名不能为空")
                handle = reqData.get("handle","")
                if handle not in ['allow','block']:
                    return ErrorResponse(msg="策略类型错误")
                localport = reqData.get("localport","")
                rep = r"^(?:\d{1,5}(-\d{1,5})?(,\d{1,5}(-\d{1,5})?)*|\d{1,5}(,\d{1,5})*|\*)$"
                if not re.match(rep, localport):
                    return ErrorResponse(msg="端口格式错误")
                isok = system.EditFirewallRule(param={'name':name,'localport':localport,'handle':handle})
                if isok:
                    rulenames = f"规则名：{name} 端口：{localport} 策略：{action}"
                    RuyiAddOpLog(request,msg="【安全】-【系统防火墙】- 修改规则 => %s"%rulenames,module="safe")
                    return DetailResponse(msg="编辑成功")
                else:
                    return ErrorResponse(msg="编辑失败")
            else:
                protocol = reqData.get("protocol","")
                localport = reqData.get("port","")
                address = reqData.get("address","")
                handle = reqData.get("handle","")
                oldData = ast_convert(reqData.get("oldData",{}))
                isok = system.EditFirewallRule(param={'oldData':oldData,'address':address,'protocol':protocol,'localport':localport,'handle':handle})
                if isok:
                    statusname = "允许"
                    if handle == "drop":
                        statusname = "拒绝"
                    rulenames = f"端口：{localport} 协议：{protocol} 策略：{statusname}"
                    RuyiAddOpLog(request,msg="【安全】-【系统防火墙】- 修改规则 => %s"%rulenames,module="safe")
                    return DetailResponse(msg="编辑成功")
                else:
                    return ErrorResponse(msg="编辑失败")
        elif action == "set_rule_status":
            name = reqData.get("name","")
            if not name:
                return ErrorResponse(msg="规则名不能为空")
            status = reqData.get("status",True)
            isok = system.SetFirewallRuleStatus(param={'name':name,'status':status})
            if isok:
                statusname = "启用"
                if not status:
                    statusname = "禁用"
                rulenames = f"规则名：{name} 状态：{statusname}"
                RuyiAddOpLog(request,msg="【安全】-【系统防火墙】- 修改规则状态 => %s"%rulenames,module="safe")
                return DetailResponse(msg="设置成功")
            else:
                return ErrorResponse(msg="设置失败")
        elif action == "set_rule_action":
            if is_windows:
                name = reqData.get("name","")
                if not name:
                    return ErrorResponse(msg="规则名不能为空")
                handle = reqData.get("handle","")
                if handle not in ['allow','block']:
                    return ErrorResponse(msg="策略类型错误")
                isok = system.SetFirewallRuleAction(param={'name':name,'handle':handle})
                if isok:
                    statusname = "允许"
                    if handle == "block":
                        statusname = "拒绝"
                    rulenames = f"规则名：{name} 策略：{statusname}"
                    RuyiAddOpLog(request,msg="【安全】-【系统防火墙】- 修改规则策略 => %s"%rulenames,module="safe")
                    return DetailResponse(msg="设置成功")
                else:
                    return ErrorResponse(msg="设置失败")
            else:
                protocol = reqData.get("protocol","")
                localport = reqData.get("port","")
                address = reqData.get("address","")
                handle = reqData.get("handle","")
                newhandle = reqData.get("newhandle","")
                isok = system.SetFirewallRuleAction(param={'address':address,'protocol':protocol,'localport':localport,'handle':handle,'newhandle':newhandle})
                if isok:
                    statusname = "允许"
                    if newhandle == "drop":
                        statusname = "拒绝"
                    rulenames = f"端口：{localport} 协议：{protocol} 策略：{statusname}"
                    RuyiAddOpLog(request,msg="【安全】-【系统防火墙】- 修改规则策略 => %s"%rulenames,module="safe")
                    return DetailResponse(msg="设置成功")
                else:
                    return ErrorResponse(msg="设置失败")
        
        elif action == "add_forwarding_rules":
            protocol = reqData.get("protocol","")
            localport = reqData.get("localport",0)
            remoteport = reqData.get("remoteport",0)
            remoteip = reqData.get("remoteip","")
            isok,msg = system.AddPortProxyRules(param=reqData)
            if not isok:
                return ErrorResponse(msg=msg)
            if is_windows:
                rulenames = f"源端口：{localport} 转发到 {remoteip}:{remoteport}"
            else:
                rulenames = f"协议：{protocol} 源端口：{localport} 转发到 {remoteip}:{remoteport}"
            RuyiAddOpLog(request,msg="【安全】-【系统防火墙】- 添加端口转发规则 => %s"%rulenames,module="safe")
            return DetailResponse(msg="设置成功")
        
        elif action == "del_forwarding_rules":
            protocol = reqData.get("protocol","")
            localport = reqData.get("localport",0)
            remoteport = reqData.get("remoteport",0)
            remoteip = reqData.get("remoteip","")
            isok,msg = system.DelPortProxyRules(param=reqData)
            if not isok:
                return ErrorResponse(msg=msg)
            if is_windows:
                rulenames = f"源端口：{localport} 转发到 {remoteip}:{remoteport}"
            else:
                rulenames = f"协议：{protocol} 源端口：{localport} 转发到 {remoteip}:{remoteport}"
            RuyiAddOpLog(request,msg="【安全】-【系统防火墙】- 删除端口转发规则 => %s"%rulenames,module="safe")
            return DetailResponse(msg="删除成功")
        
        return ErrorResponse(msg="类型错误")