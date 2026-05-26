import os
import json
import logging
import platform
import subprocess
import threading
import time
import uuid
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
TEMPLATE_CONFIG_PATH = os.path.join(_BASE_DIR, 'template', 'agent', 'mcp_config.json')
DATA_CONFIG_PATH = os.path.join(_BASE_DIR, 'data', 'agent', 'mcp_config.json')


class MCPToolDefinition:
    def __init__(self, name: str, description: str, parameters: Dict[str, Any], server_name: str):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.server_name = server_name

    def to_openai_tool(self) -> Dict[str, Any]:
        return {
            'type': 'function',
            'function': {
                'name': self.name,
                'description': self.description,
                'parameters': self.parameters,
            }
        }


class MCPServerConfig:
    def __init__(self, name: str, transport: str, enabled: bool = True, **kwargs):
        self.name = name
        self.transport = transport
        self.enabled = enabled
        self.command = kwargs.get('command', '')
        self.url = kwargs.get('url', '')
        self.args = kwargs.get('args', [])
        self.env = kwargs.get('env', {})
        self.auth = kwargs.get('auth', {})
        self.extra = kwargs

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MCPServerConfig':
        return cls(
            name=data.get('name', ''),
            transport=data.get('transport', 'stdio'),
            enabled=data.get('enabled', True),
            command=data.get('command', ''),
            url=data.get('url', ''),
            args=data.get('args', []),
            env=data.get('env', {}),
            auth=data.get('auth', {}),
            **{k: v for k, v in data.items() if k not in ('name', 'transport', 'enabled', 'command', 'url', 'args', 'env', 'auth')}
        )

    def to_dict(self) -> Dict[str, Any]:
        d = {
            'name': self.name,
            'transport': self.transport,
            'enabled': self.enabled,
            'command': self.command,
            'url': self.url,
            'auth': self.auth,
        }
        if self.args:
            d['args'] = self.args
        if self.env:
            d['env'] = self.env
        return d


class StdioTransport:
    def __init__(self, command: str, args: List[str] = None, env: Dict[str, str] = None):
        self.command = command
        self.args = args or []
        self.env = env or {}
        self._process: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        self._request_id = 0

    def start(self) -> bool:
        try:
            if platform.system() == 'Windows':
                cmd_parts = self.command.split()
            else:
                import shlex
                cmd_parts = shlex.split(self.command)
            if self.args:
                cmd_parts.extend(self.args)

            proc_env = os.environ.copy()
            proc_env.update(self.env)

            self._process = subprocess.Popen(
                cmd_parts,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=proc_env,
                bufsize=0,
            )

            self._send_initialize()
            return True
        except Exception as e:
            logger.error(f'StdioTransport 启动失败 [{self.command}]: {e}')
            return False

    def stop(self):
        if self._process:
            try:
                self._send_notification('notifications/cancelled', {})
            except Exception:
                pass
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
            self._process = None

    def is_alive(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def send_request(self, method: str, params: Dict[str, Any] = None, timeout: float = 30) -> Optional[Dict[str, Any]]:
        if not self.is_alive():
            return None

        with self._lock:
            self._request_id += 1
            request_id = self._request_id

        message = {
            'jsonrpc': '2.0',
            'id': request_id,
            'method': method,
        }
        if params is not None:
            message['params'] = params

        return self._send_and_receive(message, timeout)

    def _send_notification(self, method: str, params: Dict[str, Any] = None):
        message = {
            'jsonrpc': '2.0',
            'method': method,
        }
        if params:
            message['params'] = params

        try:
            self._write_message(message)
        except Exception as e:
            logger.error(f'发送通知失败: {e}')

    def _send_initialize(self) -> Optional[Dict[str, Any]]:
        result = self.send_request('initialize', {
            'protocolVersion': '2024-11-05',
            'capabilities': {},
            'clientInfo': {
                'name': 'ruyi-panel',
                'version': '1.0.0',
            },
        }, timeout=10)

        if result:
            self._send_notification('notifications/initialized', {})

        return result

    def _write_message(self, message: Dict[str, Any]):
        if not self._process or not self._process.stdin:
            raise ConnectionError('Process not running')

        content = json.dumps(message, ensure_ascii=False)
        header = f'Content-Length: {len(content.encode("utf-8"))}\r\n\r\n'
        self._process.stdin.write(header.encode('utf-8'))
        self._process.stdin.write(content.encode('utf-8'))
        self._process.stdin.flush()

    def _read_message(self, timeout: float = 30) -> Optional[Dict[str, Any]]:
        if not self._process or not self._process.stdout:
            return None

        stdout = self._process.stdout

        old_timeout = stdout.timeout if hasattr(stdout, 'timeout') else None
        if hasattr(stdout, 'timeout'):
            stdout.timeout = timeout

        try:
            headers = {}
            while True:
                line = stdout.readline()
                if not line:
                    return None
                line = line.decode('utf-8', errors='replace').strip()
                if not line:
                    break
                if ':' in line:
                    key, value = line.split(':', 1)
                    headers[key.strip().lower()] = value.strip()

            content_length = int(headers.get('content-length', 0))
            if content_length <= 0:
                return None

            body = stdout.read(content_length)
            if not body:
                return None

            return json.loads(body.decode('utf-8', errors='replace'))
        except Exception as e:
            logger.error(f'读取MCP消息失败: {e}')
            return None
        finally:
            if hasattr(stdout, 'timeout') and old_timeout is not None:
                stdout.timeout = old_timeout

    def _send_and_receive(self, message: Dict[str, Any], timeout: float = 30) -> Optional[Dict[str, Any]]:
        try:
            self._write_message(message)
            request_id = message.get('id')

            start_time = time.time()
            while time.time() - start_time < timeout:
                response = self._read_message(timeout=timeout - (time.time() - start_time))
                if response is None:
                    return None

                if response.get('id') == request_id:
                    if 'error' in response:
                        error = response['error']
                        logger.error(f'MCP请求错误: {error}')
                        return {'error': error}
                    return response.get('result')

            logger.error(f'MCP请求超时: method={message.get("method")}')
            return None
        except Exception as e:
            logger.error(f'MCP通信失败: {e}')
            return None


class HttpTransport:
    def __init__(self, url: str, auth: Dict[str, str] = None):
        self.url = url.rstrip('/')
        self.auth = auth or {}
        self._session = None
        self._request_id = 0
        self._lock = threading.Lock()

    def start(self) -> bool:
        try:
            self._ensure_session()
            self._send_initialize()
            return True
        except Exception as e:
            logger.error(f'HttpTransport 连接失败 [{self.url}]: {e}')
            return False

    def stop(self):
        if self._session:
            try:
                self._session.close()
            except Exception:
                pass
            self._session = None

    def is_alive(self) -> bool:
        return self._session is not None

    def _ensure_session(self):
        if self._session is None:
            import requests
            self._session = requests.Session()
            if self.auth:
                if 'token' in self.auth:
                    self._session.headers['Authorization'] = f'Bearer {self.auth["token"]}'
                elif 'api_key' in self.auth:
                    self._session.headers['X-API-Key'] = self.auth['api_key']

    def send_request(self, method: str, params: Dict[str, Any] = None, timeout: float = 30) -> Optional[Dict[str, Any]]:
        if not self._session:
            return None

        with self._lock:
            self._request_id += 1
            request_id = self._request_id

        message = {
            'jsonrpc': '2.0',
            'id': request_id,
            'method': method,
        }
        if params is not None:
            message['params'] = params

        try:
            self._ensure_session()
            resp = self._session.post(
                self.url,
                json=message,
                timeout=timeout,
                headers={'Content-Type': 'application/json'},
            )
            resp.raise_for_status()
            data = resp.json()

            if 'error' in data:
                logger.error(f'MCP HTTP请求错误: {data["error"]}')
                return {'error': data['error']}

            return data.get('result')
        except Exception as e:
            logger.error(f'MCP HTTP请求失败 [{method}]: {e}')
            return None

    def _send_initialize(self) -> Optional[Dict[str, Any]]:
        return self.send_request('initialize', {
            'protocolVersion': '2024-11-05',
            'capabilities': {},
            'clientInfo': {
                'name': 'ruyi-panel',
                'version': '1.0.0',
            },
        }, timeout=10)


class SseTransport:
    def __init__(self, url: str, auth: Dict[str, str] = None):
        self.sse_url = url.rstrip('/')
        self.auth = auth or {}
        self._session = None
        self._message_endpoint = None
        self._request_id = 0
        self._lock = threading.Lock()
        self._sse_thread = None
        self._running = False
        self._pending: Dict[int, Dict[str, Any]] = {}
        self._pending_lock = threading.Lock()
        self._pending_event = threading.Condition()

    def start(self) -> bool:
        try:
            import requests
            self._session = requests.Session()
            if self.auth:
                if 'token' in self.auth:
                    self._session.headers['Authorization'] = f'Bearer {self.auth["token"]}'
                elif 'api_key' in self.auth:
                    self._session.headers['X-API-Key'] = self.auth['api_key']

            self._running = True
            self._sse_thread = threading.Thread(target=self._sse_listener, daemon=True)
            self._sse_thread.start()

            for _ in range(50):
                if self._message_endpoint is not None:
                    break
                time.sleep(0.1)

            if self._message_endpoint is None:
                logger.error(f'SseTransport 连接失败: 未获取到消息端点 [{self.sse_url}]')
                self.stop()
                return False

            self._send_initialize()
            return True
        except Exception as e:
            logger.error(f'SseTransport 启动失败 [{self.sse_url}]: {e}')
            return False

    def stop(self):
        self._running = False
        if self._session:
            try:
                self._session.close()
            except Exception:
                pass
            self._session = None
        self._message_endpoint = None

    def is_alive(self) -> bool:
        return self._session is not None and self._message_endpoint is not None

    def _sse_listener(self):
        try:
            resp = self._session.get(self.sse_url, stream=True, timeout=60, headers={'Accept': 'text/event-stream'})
            resp.raise_for_status()

            event_type = None
            data_buffer = []

            for line in resp.iter_lines(decode_unicode=True):
                if not self._running:
                    break

                if line is None:
                    continue

                if line.startswith('event:'):
                    event_type = line[6:].strip()
                elif line.startswith('data:'):
                    data_buffer.append(line[5:].strip())
                elif line == '':
                    if event_type and data_buffer:
                        data_str = '\n'.join(data_buffer)
                        self._handle_sse_event(event_type, data_str)
                    event_type = None
                    data_buffer = []
        except Exception as e:
            if self._running:
                logger.error(f'SSE监听异常: {e}')
            self._message_endpoint = None

    def _handle_sse_event(self, event_type: str, data: str):
        if event_type == 'endpoint':
            base_url = self.sse_url.rsplit('/sse', 1)[0]
            if data.startswith('/'):
                self._message_endpoint = base_url + data
            elif data.startswith('http'):
                self._message_endpoint = data
            else:
                self._message_endpoint = base_url + '/' + data
            logger.info(f'SSE消息端点: {self._message_endpoint}')
        elif event_type == 'message':
            try:
                message = json.loads(data)
                msg_id = message.get('id')
                if msg_id is not None:
                    with self._pending_lock:
                        self._pending[msg_id] = message
                    with self._pending_event:
                        self._pending_event.notify_all()
            except json.JSONDecodeError:
                logger.warning(f'SSE消息解析失败: {data[:100]}')

    def send_request(self, method: str, params: Dict[str, Any] = None, timeout: float = 30) -> Optional[Dict[str, Any]]:
        if not self._message_endpoint:
            return None

        with self._lock:
            self._request_id += 1
            request_id = self._request_id

        message = {
            'jsonrpc': '2.0',
            'id': request_id,
            'method': method,
        }
        if params is not None:
            message['params'] = params

        try:
            resp = self._session.post(
                self._message_endpoint,
                json=message,
                timeout=timeout,
                headers={'Content-Type': 'application/json'},
            )
            resp.raise_for_status()

            start_time = time.time()
            while time.time() - start_time < timeout:
                with self._pending_lock:
                    if request_id in self._pending:
                        response = self._pending.pop(request_id)
                        break
                with self._pending_event:
                    self._pending_event.wait(timeout=min(1.0, timeout - (time.time() - start_time)))
            else:
                logger.error(f'SSE请求超时: method={method}')
                return None

            if 'error' in response:
                logger.error(f'SSE请求错误: {response["error"]}')
                return {'error': response['error']}

            return response.get('result')
        except Exception as e:
            logger.error(f'SSE请求失败 [{method}]: {e}')
            return None

    def _send_initialize(self) -> Optional[Dict[str, Any]]:
        return self.send_request('initialize', {
            'protocolVersion': '2024-11-05',
            'capabilities': {},
            'clientInfo': {
                'name': 'ruyi-panel',
                'version': '1.0.0',
            },
        }, timeout=10)


class MCPClientManager:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._servers: Dict[str, MCPServerConfig] = {}
        self._tools: Dict[str, MCPToolDefinition] = {}
        self._connected: Dict[str, bool] = {}
        self._transports: Dict[str, Any] = {}
        self._connect_failed: Dict[str, float] = {}
        self._loaded = False

    def _ensure_loaded(self):
        if not self._loaded:
            self._load_config()
            self._loaded = True

    def _load_config(self):
        config = self._read_merged_config()

        for server_data in config.get('servers', []):
            server_config = MCPServerConfig.from_dict(server_data)
            if server_config.enabled:
                self._servers[server_config.name] = server_config

    def _read_merged_config(self) -> Dict[str, Any]:
        template_config = self._read_json_file(TEMPLATE_CONFIG_PATH)
        data_config = self._read_json_file(DATA_CONFIG_PATH)

        if not template_config and not data_config:
            return {'servers': []}

        if not data_config:
            return template_config or {'servers': []}

        if not template_config:
            return data_config

        template_servers = {s['name']: s for s in template_config.get('servers', []) if 'name' in s}
        data_servers = {s['name']: s for s in data_config.get('servers', []) if 'name' in s}

        merged = {}
        merged.update(template_servers)
        merged.update(data_servers)

        return {'servers': list(merged.values())}

    @staticmethod
    def _read_json_file(path: str) -> Optional[Dict[str, Any]]:
        if not os.path.exists(path):
            return None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f'读取MCP配置失败 [{path}]: {e}')
            return None

    def save_config(self, servers: List[Dict[str, Any]]):
        config = {'servers': servers}
        os.makedirs(os.path.dirname(DATA_CONFIG_PATH), exist_ok=True)
        try:
            with open(DATA_CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            logger.info(f'MCP配置已保存到 {DATA_CONFIG_PATH}')
        except Exception as e:
            logger.error(f'保存MCP配置失败: {e}')

    def add_server(self, server_data: Dict[str, Any]) -> bool:
        name = server_data.get('name', '')
        if not name:
            return False

        self._ensure_loaded()

        self._servers[name] = MCPServerConfig.from_dict(server_data)

        current_list = [cfg.to_dict() for cfg in self._servers.values()]
        self.save_config(current_list)
        return True

    def remove_server(self, server_name: str) -> bool:
        self._ensure_loaded()

        if server_name not in self._servers:
            return False

        self._disconnect_server(server_name)

        del self._servers[server_name]
        self._connected.pop(server_name, None)

        tools_to_remove = [n for n, t in self._tools.items() if t.server_name == server_name]
        for n in tools_to_remove:
            del self._tools[n]

        current_list = [cfg.to_dict() for cfg in self._servers.values()]
        self.save_config(current_list)
        return True

    def connect_server(self, server_name: str) -> bool:
        server = self._servers.get(server_name)
        if not server:
            logger.warning(f'MCP Server [{server_name}] 不存在')
            return False

        try:
            if server.transport == 'stdio':
                success = self._connect_stdio(server)
            elif server.transport == 'http':
                success = self._connect_http(server)
            elif server.transport == 'sse':
                success = self._connect_sse(server)
            else:
                logger.warning(f'不支持的传输类型: {server.transport}')
                return False

            if success:
                self._discover_tools(server)
                self._connected[server_name] = True
                self._connect_failed.pop(server_name, None)
                logger.info(f'MCP Server [{server_name}] 连接成功，发现 {sum(1 for t in self._tools.values() if t.server_name == server_name)} 个工具')
            else:
                self._connected[server_name] = False
                self._connect_failed[server_name] = time.time()

            return success
        except Exception as e:
            logger.error(f'MCP Server [{server_name}] 连接失败: {e}')
            self._connected[server_name] = False
            self._connect_failed[server_name] = time.time()
            return False

    def _connect_stdio(self, server: MCPServerConfig) -> bool:
        transport = StdioTransport(
            command=server.command,
            args=server.args,
            env=server.env,
        )
        if transport.start():
            self._transports[server.name] = transport
            return True
        return False

    def _connect_http(self, server: MCPServerConfig) -> bool:
        transport = HttpTransport(
            url=server.url,
            auth=server.auth,
        )
        if transport.start():
            self._transports[server.name] = transport
            return True
        return False

    def _connect_sse(self, server: MCPServerConfig) -> bool:
        transport = SseTransport(
            url=server.url,
            auth=server.auth,
        )
        if transport.start():
            self._transports[server.name] = transport
            return True
        return False

    def _disconnect_server(self, server_name: str):
        transport = self._transports.pop(server_name, None)
        if transport:
            try:
                transport.stop()
            except Exception as e:
                logger.warning(f'断开MCP Server [{server_name}] 失败: {e}')

    def _discover_tools(self, server: MCPServerConfig):
        transport = self._transports.get(server.name)
        if not transport:
            return

        result = transport.send_request('tools/list', {}, timeout=15)
        if not result:
            logger.warning(f'MCP Server [{server.name}] 工具发现返回空')
            return

        tools_data = result.get('tools', [])
        for tool_data in tools_data:
            tool_name = tool_data.get('name', '')
            if not tool_name:
                continue

            description = tool_data.get('description', '')
            input_schema = tool_data.get('inputSchema', {
                'type': 'object',
                'properties': {},
            })

            mcp_tool_name = f'mcp_{server.name}__{tool_name}'

            self._tools[mcp_tool_name] = MCPToolDefinition(
                name=mcp_tool_name,
                description=f'[MCP:{server.name}] {description}',
                parameters=input_schema,
                server_name=server.name,
            )

            logger.debug(f'MCP工具发现: {mcp_tool_name} from {server.name}')

    def discover_all_tools(self, lazy=True) -> List[MCPToolDefinition]:
        self._ensure_loaded()

        for server_name, server in self._servers.items():
            if server_name not in self._connected:
                if lazy and self._connect_failed.get(server_name):
                    continue
                self.connect_server(server_name)

        return list(self._tools.values())

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        tool_def = self._tools.get(tool_name)
        if not tool_def:
            return json.dumps({'error': f'MCP工具 {tool_name} 不存在'}, ensure_ascii=False)

        server_name = tool_def.server_name
        transport = self._transports.get(server_name)
        if not transport or not transport.is_alive():
            self._connected[server_name] = False
            return json.dumps({'error': f'MCP Server [{server_name}] 未连接'}, ensure_ascii=False)

        original_tool_name = tool_name
        if tool_name.startswith(f'mcp_{server_name}__'):
            original_tool_name = tool_name[len(f'mcp_{server_name}__'):]

        result = transport.send_request('tools/call', {
            'name': original_tool_name,
            'arguments': arguments,
        }, timeout=60)

        if result is None:
            return json.dumps({'error': f'MCP工具调用超时: {tool_name}'}, ensure_ascii=False)

        if isinstance(result, dict) and 'error' in result:
            return json.dumps({'error': result['error']}, ensure_ascii=False)

        content_parts = []
        for item in result.get('content', []):
            item_type = item.get('type', 'text')
            if item_type == 'text':
                content_parts.append(item.get('text', ''))
            elif item_type == 'image':
                content_parts.append(f'[Image: {item.get("mimeType", "unknown")}]')
            elif item_type == 'resource':
                resource = item.get('resource', {})
                content_parts.append(f'[Resource: {resource.get("uri", "")}]')

        if content_parts:
            return '\n'.join(content_parts)

        return json.dumps(result, ensure_ascii=False, default=str)

    def get_openai_tools(self) -> List[Dict[str, Any]]:
        return [tool.to_openai_tool() for tool in self.discover_all_tools()]

    def get_server_status(self) -> List[Dict[str, Any]]:
        self._ensure_loaded()
        result = []
        for name, config in self._servers.items():
            transport = self._transports.get(name)
            is_alive = transport.is_alive() if transport else False
            connected = self._connected.get(name, False) and is_alive
            if not is_alive and self._connected.get(name, False):
                self._connected[name] = False

            result.append({
                'name': name,
                'transport': config.transport,
                'connected': connected,
                'tools_count': sum(1 for t in self._tools.values() if t.server_name == name),
            })
        return result

    def reload(self):
        for name in list(self._transports.keys()):
            self._disconnect_server(name)

        self._loaded = False
        self._servers.clear()
        self._tools.clear()
        self._connected.clear()
        self._connect_failed.clear()


mcp_client_manager = MCPClientManager.get_instance()
