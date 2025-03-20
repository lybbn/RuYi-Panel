#!/bin/python
#coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2024-01-16
# +-------------------------------------------------------------------

# ------------------------------
# channels jwt token认证中间件
# ------------------------------
import base64
from channels.db import database_sync_to_async
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken
from apps.system.models import Users
from django.http.request import QueryDict
from django.contrib.auth.models import AnonymousUser
from django.conf import settings

class JWTChannelsAuthMiddleware:
    """
    @name channels jwt 认证中间件
    @author lybbn<2024-01-16>
    """
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        # 从查询参数或头部中提取 JWT token
        try:
            query_string = scope.get('query_string')
            query_args = QueryDict(query_string=query_string, encoding='utf-8')
            token = AccessToken(base64.b64decode(query_args.get('token',None)).decode('utf-8'))
        except:
            token = None

        # 获取用户对象
        user = await self.get_user(token)

        # 如果用户未登录，则拒绝 WebSocket 连接
        if not user.is_authenticated or settings.RUYI_DEMO:
            await send({
                "type": "websocket.close",
                "code": 403
            })
            return

        # 将用户对象添加到当前请求中
        scope['user'] = user

        # 执行其他中间件
        inner = self.inner(scope, receive, send)  # 将 receive 和 send 参数传递给下一个中间件
        return await inner

    @database_sync_to_async
    def get_user(self, token):
        # 如果 token 不存在，则返回匿名用户
        if not token or not token.payload.get('user_id'):
            return AnonymousUser()
        user_id = token.payload['user_id']
        try:
            user = Users.objects.get(id=user_id)
            return user
        except:
            return AnonymousUser()