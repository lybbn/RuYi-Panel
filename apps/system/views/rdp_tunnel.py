#!/bin/python
#coding: utf-8

import asyncio
import codecs
import logging
import uuid
from collections import deque

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings
from django.http.request import QueryDict

from apps.system.models import TerminalServer

logger = logging.getLogger(__name__)


class GuacamoleProtocolError(Exception):
    """Raised when the guacd protocol stream is malformed."""


class GuacamoleInstructionCodec:
    """Incrementally parses and encodes Guacamole instructions."""

    def __init__(self):
        self.buffer = ""
        self.decoder = codecs.getincrementaldecoder("utf-8")()

    @staticmethod
    def encode_instruction(opcode="", *args):
        parts = [opcode, *args]
        encoded = []
        for value in parts:
            text = "" if value is None else str(value)
            encoded.append(f"{len(text)}.{text}")
        return ",".join(encoded) + ";"

    def feed_bytes(self, data):
        text = self.decoder.decode(data)
        return self.feed_text(text)

    def feed_text(self, text):
        if text:
            self.buffer += text

        instructions = []
        while True:
            parsed = self._parse_one()
            if parsed is None:
                break
            instructions.append(parsed)
        return instructions

    def _parse_one(self):
        if not self.buffer:
            return None

        pos = 0
        elements = []

        while True:
            dot = self.buffer.find(".", pos)
            if dot == -1:
                return None

            length_text = self.buffer[pos:dot]
            if not length_text.isdigit():
                raise GuacamoleProtocolError("Invalid Guacamole element length.")

            value_length = int(length_text)
            value_start = dot + 1
            value_end = value_start + value_length

            if len(self.buffer) <= value_end:
                return None

            value = self.buffer[value_start:value_end]
            terminator = self.buffer[value_end]
            if terminator not in ",;":
                raise GuacamoleProtocolError("Invalid Guacamole instruction terminator.")

            elements.append(value)
            pos = value_end + 1

            if terminator == ";":
                instruction = self.buffer[:pos]
                self.buffer = self.buffer[pos:]
                return instruction, elements


class WebRDPConsumerAsync(AsyncWebsocketConsumer):
    """
    Thin Guacamole tunnel that proxies browser RDP sessions to guacd.
    """

    async def connect(self):
        requested_subprotocols = self.scope.get("subprotocols", [])
        subprotocol = "guacamole" if "guacamole" in requested_subprotocols else None
        await self.accept(subprotocol=subprotocol)

        self.active = False
        self.terminal_id = None
        self.terminal_info = None
        self.width = 1280
        self.height = 720
        self.dpi = 96
        self.timezone = ""
        self.guacd_reader = None
        self.guacd_writer = None
        self.guacd_parser = GuacamoleInstructionCodec()
        self.browser_parser = GuacamoleInstructionCodec()
        self.pending_instructions = deque()
        self.relay_task = None
        self.connection_uuid = str(uuid.uuid4())

        try:
            self._load_query_params()
            self.terminal_info = await self.get_terminal_info()
            if not self.terminal_info:
                raise GuacamoleProtocolError("未找到目标连接配置。")
            if self.terminal_info.connect_protocol != "rdp":
                raise GuacamoleProtocolError("当前连接不是 RDP 协议。")

            self.guacd_reader, self.guacd_writer = await asyncio.wait_for(
                asyncio.open_connection(settings.RUYI_GUACD_HOST, settings.RUYI_GUACD_PORT),
                timeout=10,
            )

            await self.send(text_data=GuacamoleInstructionCodec.encode_instruction("", self.connection_uuid))
            await self.perform_handshake()
            self.active = True
            self.relay_task = asyncio.create_task(self.relay_guacd_output())
        except Exception as exc:
            logger.exception("Failed to open RDP session: %s", exc)
            await self.send_error(self.format_open_error(exc))
            await self.close()

    def _load_query_params(self):
        query_string = self.scope.get("query_string", b"")
        connect_args = QueryDict(query_string=query_string, encoding="utf-8")
        self.terminal_id = connect_args.get("id")
        self.width = self._safe_int(connect_args.get("width"), 1280)
        self.height = self._safe_int(connect_args.get("height"), 720)
        self.dpi = self._safe_int(connect_args.get("dpi"), 96)
        self.timezone = connect_args.get("timezone", "")

    async def disconnect(self, close_code):
        self.active = False
        if self.relay_task:
            self.relay_task.cancel()
            self.relay_task = None

        if self.guacd_writer:
            try:
                self.guacd_writer.close()
                await self.guacd_writer.wait_closed()
            except Exception:
                pass
            self.guacd_writer = None

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data or not self.guacd_writer:
            return

        try:
            instructions = self.browser_parser.feed_text(text_data)
            for instruction, elements in instructions:
                opcode = elements[0] if elements else ""
                arguments = elements[1:]

                if opcode == "":
                    await self.handle_internal_message(arguments)
                    continue

                self.guacd_writer.write(instruction.encode("utf-8"))
            await self.guacd_writer.drain()
        except Exception as exc:
            logger.exception("Failed to process browser Guacamole instruction: %s", exc)
            await self.send_error("RDP 连接数据转发失败")
            await self.close()

    async def handle_internal_message(self, arguments):
        if not arguments:
            return

        if arguments[0] == "ping":
            await self.send(
                text_data=GuacamoleInstructionCodec.encode_instruction("", *arguments)
            )

    async def perform_handshake(self):
        await self.send_guacd_instruction("select", "rdp")
        _raw_args_instruction, args_elements = await self.read_guacd_instruction()

        opcode = args_elements[0] if args_elements else ""
        if opcode == "error":
            raise GuacamoleProtocolError(args_elements[1] if len(args_elements) > 1 else "guacd 返回错误")
        if opcode != "args":
            raise GuacamoleProtocolError("guacd 握手失败，未收到 args 指令")

        protocol_args = list(args_elements[1:])
        protocol_version = ""
        if protocol_args and protocol_args[0].startswith("VERSION_"):
            protocol_version = protocol_args.pop(0)

        await self.send_guacd_instruction("size", self.width, self.height, self.dpi)
        await self.send_guacd_instruction("audio")
        await self.send_guacd_instruction("video")
        await self.send_guacd_instruction("image", "image/png", "image/jpeg")
        if self.timezone:
            await self.send_guacd_instruction("timezone", self.timezone)

        connect_values = []
        if protocol_version:
            connect_values.append(protocol_version)
        for name in protocol_args:
            connect_values.append(self.get_rdp_parameter(name))

        await self.send_guacd_instruction("connect", *connect_values)

        first_instruction, first_elements = await self.read_guacd_instruction()
        first_opcode = first_elements[0] if first_elements else ""
        if first_opcode == "error":
            reason = first_elements[1] if len(first_elements) > 1 else "RDP 连接失败"
            raise GuacamoleProtocolError(reason)

        await self.send(text_data=first_instruction)

    async def relay_guacd_output(self):
        try:
            while self.active:
                data = await self.guacd_reader.read(8192)
                if not data:
                    break

                for instruction, _elements in self.guacd_parser.feed_bytes(data):
                    await self.send(text_data=instruction)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("guacd relay failed: %s", exc)
            if self.active:
                await self.send_error("RDP 连接已中断")
        finally:
            if self.active:
                await self.close()

    async def read_guacd_instruction(self):
        if self.pending_instructions:
            return self.pending_instructions.popleft()

        while True:
            data = await self.guacd_reader.read(8192)
            if not data:
                raise GuacamoleProtocolError("guacd 连接已关闭。")

            instructions = self.guacd_parser.feed_bytes(data)
            if instructions:
                self.pending_instructions.extend(instructions[1:])
                return instructions[0]

    async def send_guacd_instruction(self, opcode="", *args):
        if not self.guacd_writer:
            raise GuacamoleProtocolError("guacd 连接未建立。")

        payload = GuacamoleInstructionCodec.encode_instruction(opcode, *args)
        self.guacd_writer.write(payload.encode("utf-8"))
        await self.guacd_writer.drain()

    def get_rdp_parameter(self, name):
        if not self.terminal_info:
            return ""

        security = self.terminal_info.rdp_security or "any"
        mapping = {
            "hostname": self.terminal_info.host,
            "port": str(self.terminal_info.port or 3389),
            "username": self.terminal_info.username or "",
            "password": self.terminal_info.password or "",
            "domain": self.terminal_info.rdp_domain or "",
            "security": security,
            "ignore-cert": "true" if self.terminal_info.rdp_ignore_cert else "false",
            "resize-method": "display-update",
            "color-depth": str(self.terminal_info.rdp_color_depth or 32),
            "width": str(self.width),
            "height": str(self.height),
            "dpi": str(self.dpi),
            "timezone": self.timezone or "",
            "client-name": "Ruyi Panel",
            "enable-wallpaper": "false",
            "enable-theming": "false",
            "enable-full-window-drag": "false",
            "enable-desktop-composition": "false",
            "enable-font-smoothing": "true",
            "enable-drive": "false",
            "disable-copy": "false",
            "disable-paste": "false",
            "read-only": "false",
        }
        return mapping.get(name, "")

    async def send_error(self, reason):
        try:
            await self.send(
                text_data=GuacamoleInstructionCodec.encode_instruction("error", reason, 0x0200)
            )
        except Exception:
            pass

    @staticmethod
    def format_open_error(exc):
        if isinstance(exc, TimeoutError):
            return "无法连接 guacd，请先在容器应用中安装并启动 guacd"
        if isinstance(exc, OSError) and not isinstance(exc, GuacamoleProtocolError):
            return "无法连接 guacd，请先在容器应用中安装并启动 guacd"
        return str(exc) or "RDP 连接失败"

    @staticmethod
    def _safe_int(value, default):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @database_sync_to_async
    def get_terminal_info(self):
        if not self.terminal_id:
            return None
        return TerminalServer.objects.filter(id=self.terminal_id).first()
