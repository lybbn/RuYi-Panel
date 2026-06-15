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
# 项目启动
# ------------------------------

import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

if os.name == "posix":
    try:
        from setproctitle import setproctitle
        setproctitle("RuYi-Panel")
    except Exception:
        pass

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ruyi.settings')
django.setup()

import sys
import importlib
import datetime
import signal
from django.apps import apps
from django.conf import settings
from utils.common import GetPanelPort,isSSLEnable,GetPanelBindAddress,current_os,initWindowsEnv
from daphne.server import Server as DaphneServer
from daphne.endpoints import build_endpoint_description_strings
from daphne.http_protocol import WebRequest, HTTPFactory

from django.core.exceptions import ImproperlyConfigured
from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler
from twisted.internet import reactor

import logging
import time as _time
logger = logging.getLogger("django.channels.server")

def get_default_application():
    """
    Gets the default application, set in the ASGI_APPLICATION setting.
    """
    try:
        path, name = settings.ASGI_APPLICATION.rsplit(".", 1)
    except (ValueError, AttributeError):
        raise ImproperlyConfigured("Cannot find ASGI_APPLICATION setting.")
    try:
        module = importlib.import_module(path)
    except ImportError:
        raise ImproperlyConfigured("Cannot import ASGI_APPLICATION module %r" % path)
    try:
        value = getattr(module, name)
    except AttributeError:
        raise ImproperlyConfigured(
            f"Cannot find {name!r} in ASGI_APPLICATION module {path}"
        )
    return value

def get_application(options):
    """
    Returns the static files serving application wrapping the default application,
    if static files should be served. Otherwise just returns the default
    handler.
    """
    staticfiles_installed = apps.is_installed("django.contrib.staticfiles")
    use_static_handler = options.get("use_static_handler", staticfiles_installed)
    insecure_serving = options.get("insecure_serving", False)
    if use_static_handler and (settings.DEBUG or insecure_serving):
        return ASGIStaticFilesHandler(get_default_application())
    else:
        return get_default_application()

class RuyiWebRequest(WebRequest):
    """
    自定义WebRequest，将http_timeout从总超时改为空闲超时。
    原版Daphne的check_timeouts使用duration()（请求总时间）判断超时，
    导致SSE长连接即使持续发送heartbeat也会被强制断开。
    修改后：响应已开始时，从最后一次发送数据的时间算起，SSE有heartbeat不会超时。
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_body_time = None

    def handle_reply(self, message):
        """重写handle_reply，在发送响应体时更新_last_body_time"""
        result = super().handle_reply(message)
        # 每次发送响应体时更新时间戳
        if message.get("type") == "http.response.body":
            self._last_body_time = _time.time()
        elif message.get("type") == "http.response.start":
            self._last_body_time = _time.time()
        return result

    def check_timeouts(self):
        if self.server.http_timeout:
            if self._response_started and self._last_body_time is not None:
                # 响应已开始发送数据，使用空闲超时
                idle_time = _time.time() - self._last_body_time
                if idle_time > self.server.http_timeout:
                    logger.warning("Application timed out while sending response (idle %.0fs)", idle_time)
                    self.finish()
            else:
                # 响应未开始，使用总超时
                if self.duration() > self.server.http_timeout:
                    self.basic_error(
                        503,
                        b"Service Unavailable",
                        "Application failed to respond within time limit.",
                    )


class RuyiHTTPFactory(HTTPFactory):
    """使用自定义的RuyiWebRequest替代默认的WebRequest"""

    def buildProtocol(self, addr):
        try:
            protocol = super().buildProtocol(addr)
            protocol.requestFactory = RuyiWebRequest
            return protocol
        except Exception:
            logger.error("Cannot build protocol: %s" % __import__('traceback').format_exc())
            raise


class Server(DaphneServer):
    def log_action(self, protocol, action, details):
        """
        Dispatches to any registered action logger, if there is one.
        """
        if self.action_logger:
            self.action_logger(protocol, action, details)

    def run(self):
        """重写run，使用RuyiHTTPFactory替代默认HTTPFactory"""
        # 以下代码来自DaphneServer.run()，仅替换HTTPFactory为RuyiHTTPFactory
        from daphne.ws_protocol import WebSocketFactory
        from twisted.logger import globalLogBeginner, STDLibLogObserver
        from twisted.web import http

        self.connections = {}
        self.http_factory = RuyiHTTPFactory(self)
        self.ws_factory = WebSocketFactory(self, server=self.server_name)
        self.ws_factory.setProtocolOptions(
            autoPingTimeout=self.ping_timeout,
            allowNullOrigin=True,
            openHandshakeTimeout=self.websocket_handshake_timeout,
        )
        if self.verbosity <= 1:
            globalLogBeginner.beginLoggingTo(
                [lambda _: None], redirectStandardIO=False, discardBuffer=True
            )
        else:
            globalLogBeginner.beginLoggingTo([STDLibLogObserver(__name__)])

        if http.H2_ENABLED:
            logger.info("HTTP/2 support enabled")
        else:
            logger.info("HTTP/2 support not enabled")

        reactor.callLater(1, self.application_checker)
        reactor.callLater(2, self.timeout_checker)

        from twisted.internet.endpoints import serverFromString
        for socket_description in self.endpoints:
            logger.info("Configuring endpoint %s", socket_description)
            ep = serverFromString(reactor, str(socket_description))
            listener = ep.listen(self.http_factory)
            listener.addCallback(self.listen_success)
            listener.addErrback(self.listen_error)
            self.listeners.append(listener)

        import asyncio
        asyncio.set_event_loop(reactor._asyncioEventloop)

        if self.ready_callable:
            self.ready_callable()

        reactor.run(installSignalHandlers=self.signal_handlers)

class AccessLogGenerator:
    """
    Object that implements the Daphne "action logger" internal interface in
    order to provide an access log in something resembling NCSA format.
    1. 减少日志写入频率，只记录重要事件
    2. 跳过静态资源日志，减少 I/O
    """

    def __init__(self, stream):
        self.stream = stream
        # 静态资源扩展名，不记录这些请求的日志
        self.static_extensions = {
            '.ico', '.png', '.jpg', '.jpeg', '.gif', '.svg',
            '.css', '.js', '.woff', '.woff2', '.ttf', '.eot',
            '.map', '.json', '.xml', '.txt'
        }

    def __call__(self, protocol, action, details):
        """
        只记录重要的 HTTP 请求，跳过静态资源
        """
        # HTTP requests
        if protocol == "http" and action == "complete":
            path = details.get("path", "")
            # 跳过静态资源请求，减少日志 I/O
            if not any(path.lower().endswith(ext) for ext in self.static_extensions):
                # 只记录状态码>=400 或重要的请求
                status = details.get("status", 200)
                if status >= 400 or not path.startswith(('/static/', '/media/')):
                    self.write_entry(
                        host=details["client"],
                        date=datetime.datetime.now(),
                        request="%(method)s %(path)s" % details,
                        status=status,
                        length=details["size"],
                    )
        # Websocket requests
        elif protocol == "websocket" and action == "connecting":
            self.write_entry(
                host=details["client"],
                date=datetime.datetime.now(),
                request="WSCONNECTING %(path)s" % details,
            )
        elif protocol == "websocket" and action == "rejected":
            self.write_entry(
                host=details["client"],
                date=datetime.datetime.now(),
                request="WSREJECT %(path)s" % details,
            )
        elif protocol == "websocket" and action == "connected":
            self.write_entry(
                host=details["client"],
                date=datetime.datetime.now(),
                request="WSCONNECT %(path)s" % details,
            )
        elif protocol == "websocket" and action == "disconnected":
            self.write_entry(
                host=details["client"],
                date=datetime.datetime.now(),
                request="WSDISCONNECT %(path)s" % details,
            )

    def write_entry(
        self, host, date, request, status=None, length=None, ident=None, user=None
    ):
        """
        Writes an NCSA-style entry to the log file (some liberty is taken with
        what the entries are for non-HTTP)
        """
        self.stream.write(
            '[%s] %s "%s" %s %s\n'
            % (
                date.strftime("%Y-%m-%d %H:%M:%S"),
                host,
                request,
                status or "-",
                length or "-",
            )
        )

def ready_callable():
    """
    @name 启动后回调
    @author lybbn<2024-01-13>
    """
    quit_command = "CTRL-BREAK" if sys.platform == "win32" else "CONTROL-C"
    sys.stdout.write("Quit the server with %s.\n"%quit_command)
    if sys.platform == "win32":
        import threading
        def _run_startpost():
            try:
                from django.core.management import call_command
                call_command('startpost')
            except Exception as e:
                logger.error(f"Windows开机自启执行startpost失败: {e}")
        t = threading.Thread(target=_run_startpost, daemon=True)
        t.start()

def main():
    """
    @name 启动项目
    @author lybbn<2024-01-13>
    """
    LOG_PATH_FILE = os.path.join(settings.BASE_DIR,"logs",'ry_access.log')
    access_log_stream = open(LOG_PATH_FILE, "a", 1)
    HOST = GetPanelBindAddress()
    PORT = GetPanelPort()
    privateKeyFile = settings.RUYI_PRIVATEKEY_PATH_FILE
    certKeyFile = settings.RUYI_CERTKEY_PATH_FILE
    is_ssl = False
    if isSSLEnable() and os.path.exists(privateKeyFile) and os.path.exists(certKeyFile):
        is_ssl = True
    endpoints = build_endpoint_description_strings(host=HOST, port=PORT)
    if is_ssl:
        privateKeyFile = os.path.relpath(privateKeyFile, settings.BASE_DIR).replace("\\","/") if current_os == "windows" else privateKeyFile
        certKeyFile = os.path.relpath(certKeyFile, settings.BASE_DIR).replace("\\","/") if current_os == "windows" else certKeyFile
        endpoints = ['ssl:%d:privateKey=%s:certKey=%s:interface=%s'%(PORT,privateKeyFile,certKeyFile,HOST)]
    
    initWindowsEnv()
    
    options = {}
    server_name = "ruyi"
    http_timeout = 300  # HTTP空闲超时时间5分钟（响应开始后按空闲时间计算，SSE有heartbeat不会超时）
    application_close_timeout = 30 #应用超时时间
    websocket_timeout= 86400  # WebSocket 超时时间，默认1天
    ping_timeout = 40
    request_buffer_size = 8192 * 5
    websocket_handshake_timeout = 10

    try:
        ruyi_server = Server(
            application=get_application(options),
            endpoints=endpoints,
            signal_handlers=True,
            action_logger= AccessLogGenerator(access_log_stream) if access_log_stream else None,
            http_timeout=http_timeout,
            root_path=getattr(settings, "FORCE_SCRIPT_NAME", "") or "",
            request_buffer_size=request_buffer_size,
            websocket_timeout=websocket_timeout,
            ping_timeout=ping_timeout,
            websocket_handshake_timeout=websocket_handshake_timeout,
            application_close_timeout = application_close_timeout,
            # proxy_forwarded_address_header="X-Forwarded-For",
            # proxy_forwarded_port_header="X-Forwarded-Port",
            # proxy_forwarded_proto_header="X-Forwarded-Proto",
            server_name = server_name,
            verbosity=1,
            ready_callable=ready_callable
        )

        def handle_exit_signal(signum,frame):
            """处理退出信号"""
            if signum == 2:
                signum = "Ctrl+C"
            elif signum == 15:
                signum = "Kill"
            logger.info(f"收到信号 {signum}，正在关闭ruyi server...")
            if ruyi_server and reactor.running:
                ruyi_server.stop()
            logger.info("ruyi exited")
            os._exit(0)

        # 注册信号处理函数
        signal.signal(signal.SIGINT, handle_exit_signal)
        signal.signal(signal.SIGTERM,handle_exit_signal)
        
        ruyi_server.run()
        logger.info("ruyi exited")
    except KeyboardInterrupt:
        logger.info("ruyi shutdown")
        os._exit(0)
    except Exception as e:
        logger.error(f"服务器运行出错: {e}")
        os._exit(1)
if __name__ == '__main__':
    main()