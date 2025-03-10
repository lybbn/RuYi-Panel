"""
ASGI config for ruyi project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.1/howto/deployment/asgi/
"""

import os
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

#application = get_asgi_application()

application = ProtocolTypeRouter({
    "http": get_asgi_application(),# 也可以不需要此项，普通的HTTP请求不需要我们手动在这里添加，框架会自动加载
    "websocket": JWTChannelsAuthMiddleware(
        AuthMiddlewareStack(
            # 多个url合并一起使用，多个子路由列表相加:a+b
            URLRouter(
                websocket_urlpatterns
            )
        )
    ),
})
