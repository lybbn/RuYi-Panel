"""
ASGI config for ruyi project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.1/howto/deployment/asgi/
"""

import os
import logging
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ruyi.settings')
django.setup()

from apps.systask.tasks import start_scheduler
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from apps.system.ws_routing import websocket_urlpatterns
from utils.channelsMiddleware import JWTChannelsAuthMiddleware

from django.core.asgi import get_asgi_application

start_scheduler()

# 获取日志记录器
logger = logging.getLogger(__name__)

##application = get_asgi_application()

# application = ProtocolTypeRouter({
#     "http": get_asgi_application(),# 也可以不需要此项，普通的HTTP请求不需要我们手动在这里添加，框架会自动加载
#     "websocket": JWTChannelsAuthMiddleware(
#         AuthMiddlewareStack(
#             # 多个url合并一起使用，多个子路由列表相加:a+b
#             URLRouter(
#                 websocket_urlpatterns
#             )
#         )
#     ),
# })

class ErrorHandlingMiddleware:
    """
    全局异常处理中间件，区分HTTP和WebSocket协议进行错误响应
    """
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        try:
            await self.app(scope, receive, send)
        except Exception as e:
            logger.exception("ASGI application error occurred")
            if scope['type'] == 'http':
                await self.handle_http_error(send, e)
            elif scope['type'] == 'websocket':
                await self.handle_websocket_error(send, e)
            else:
                # 其他协议类型不处理，直接抛出
                raise

    async def handle_http_error(self, send, error):
        """
        处理HTTP协议错误响应
        """
        error_page = """
        <html>
            <head><title>500 Internal Server Error</title></head>
            <body>
                <h1>500 Internal Server Error</h1>
                <p>Please try again later.</p>
            </body>
        </html>
        """
        try:
            # 发送500错误响应
            await send({
                "type": "http.response.start",
                "status": 500,
                "headers": [(b"content-type", b"text/html; charset=utf-8")],
            })
            await send({
                "type": "http.response.body",
                "body": error_page.encode("utf-8"),
                "more_body": False,
            })
        except Exception as send_error:
            logger.error(f"Failed to send error response: {send_error}")

    async def handle_websocket_error(self, send, error):
        """
        处理WebSocket协议错误响应
        """
        try:
            # 发送关闭帧（状态码1011表示服务器内部错误）
            await send({
                "type": "websocket.close",
                "code": 1011,
                "reason": str(error)[:125]  # 原因字符串最多125字节
            })
        except Exception as send_error:
            logger.error(f"Failed to send websocket close frame: {send_error}")

# 构建基础ASGI应用
base_application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": JWTChannelsAuthMiddleware(
        AuthMiddlewareStack(
            URLRouter(
                websocket_urlpatterns
            )
        )
    ),
})

# 添加全局异常处理中间件
application = ErrorHandlingMiddleware(base_application)
