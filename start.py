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
if os.name == "posix":
    from setproctitle import setproctitle
    setproctitle("RuYi-Panel")

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ruyi.settings')
django.setup()

import sys
import importlib
import datetime
import socket
from django.apps import apps
from django.conf import settings
from utils.common import GetPanelPort,isSSLEnable,GetPanelBindAddress,ReadFile,current_os
from daphne.server import Server as DaphneServer
from daphne.endpoints import build_endpoint_description_strings

from django.core.exceptions import ImproperlyConfigured
from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler

import logging
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

class Server(DaphneServer):
    def log_action(self, protocol, action, details):
        """
        Dispatches to any registered action logger, if there is one.
        """
        if self.action_logger:
            self.action_logger(protocol, action, details)

class AccessLogGenerator:
    """
    Object that implements the Daphne "action logger" internal interface in
    order to provide an access log in something resembling NCSA format.
    """

    def __init__(self, stream):
        self.stream = stream

    def __call__(self, protocol, action, details):
        """
        Called when an action happens; use it to generate log entries.
        """
        # HTTP requests
        if protocol == "http" and action == "complete":
            self.write_entry(
                host=details["client"],
                date=datetime.datetime.now(),
                request="%(method)s %(path)s" % details,
                status=details["status"],
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
    options = {}
    server_name = "ruyi"
    http_timeout = None
    application_close_timeout = 30 #应用超时时间
    websocket_timeout= 86400 #(websocket超时时间1天)
    ping_timeout = 40
    request_buffer_size = 8192 * 10
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
        ruyi_server.run()
        logger.info("ruyi exited")
    except KeyboardInterrupt:
        logger.info("ruyi shutdown")
        return

if __name__ == '__main__':
    main()