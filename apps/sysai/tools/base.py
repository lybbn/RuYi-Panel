import inspect
import json
import functools
import logging
import threading
from typing import Dict, Any, Callable, List, Optional, get_type_hints, Union

_current_session = threading.local()

from apps.sysai.provider.base import ToolDefinition

logger = logging.getLogger(__name__)

_PARAM_ALIASES = {
    'query': {'keyword', 'keywords', 'q', 'search', 'search_term', 'search_query', 'keyword_query', 'search_keyword'},
    'max_results': {'limit', 'max', 'count', 'top_k', 'num_results', 'max_count', 'result_count', 'num'},
    'command': {'cmd', 'shell_command', 'shell_cmd', 'exec', 'cmd_line'},
    'path': {'file_path', 'filepath', 'dir', 'directory', 'file', 'folder', 'dir_path'},
    'name': {'title', 'label', 'identifier', 'id_name', 'app_name', 'service_name'},
    'content': {'text', 'body', 'data', 'value', 'message', 'input', 'input_text'},
    'url': {'uri', 'link', 'endpoint', 'address', 'host', 'domain'},
    'port': {'port_number', 'port_num', 'listen_port'},
    'username': {'user', 'user_name', 'login', 'account'},
    'password': {'pass', 'passwd', 'secret', 'credential', 'pwd'},
    'timeout': {'timeout_seconds', 'timeout_secs', 'wait_time', 'max_wait'},
    'site_id': {'website_id', 'web_id', 'domain_id'},
    'database_name': {'db_name', 'dbname', 'db'},
    'container_id': {'container', 'container_name', 'docker_id'},
    'image': {'image_name', 'docker_image', 'image_id'},
    'todos': {'tasks', 'items', 'task_list', 'todo_list'},
}


def _smart_truncate(content: str, max_chars: int) -> str:
    total = len(content)
    if total <= max_chars:
        return content

    stripped = content.strip()
    if stripped.startswith('{') or stripped.startswith('['):
        try:
            data = json.loads(stripped)
            compressed = _compress_json(data, max_chars)
            if compressed and len(compressed) <= max_chars:
                return compressed
        except (json.JSONDecodeError, ValueError):
            pass

    head_keep = int(max_chars * 0.7)
    tail_keep = int(max_chars * 0.25)
    separator = f'\n\n...[内容已截断，共{total}字符，保留前{head_keep}+后{tail_keep}字符]...\n\n'
    return content[:head_keep] + separator + content[-tail_keep:]


def _compress_json(data, max_chars: int) -> str:
    if isinstance(data, list):
        if not data:
            return '[]'
        item_keys = set()
        for item in data[:3]:
            if isinstance(item, dict):
                item_keys.update(item.keys())
        key_fields = _pick_key_fields(item_keys) if item_keys else set()

        if len(data) > 10:
            compact_items = []
            for item in data[:5]:
                compact_items.append(_slim_item(item, key_fields))
            compact_items.append(f'... 省略中间{len(data) - 8}项 ...')
            for item in data[-3:]:
                compact_items.append(_slim_item(item, key_fields))
            result = json.dumps(compact_items, ensure_ascii=False, default=str)
            if len(result) <= max_chars:
                return result

        compact_items = [_slim_item(item, key_fields) for item in data]
        result = json.dumps(compact_items, ensure_ascii=False, default=str)
        if len(result) <= max_chars:
            return result

        result = json.dumps(data, ensure_ascii=False, default=str, separators=(',', ':'))
        if len(result) <= max_chars:
            return result

    elif isinstance(data, dict):
        for array_key in ('data', 'list', 'items', 'results', 'rows', 'soft_list',
                          'entries', 'containers', 'websites', 'databases', 'records'):
            if array_key in data and isinstance(data[array_key], list):
                meta = {k: v for k, v in data.items() if k != array_key and not isinstance(v, list)}
                compressed_list = _compress_json(data[array_key], max_chars - 500)
                if compressed_list:
                    result = json.dumps({**meta, array_key: json.loads(compressed_list)},
                                        ensure_ascii=False, default=str)
                    if len(result) <= max_chars:
                        return result

        result = json.dumps(data, ensure_ascii=False, default=str, separators=(',', ':'))
        if len(result) <= max_chars:
            return result

    return None


_PRIORITY_FIELDS = {
    'name', 'title', 'id', 'status', 'state', 'installed', 'version',
    'port', 'host', 'ip', 'type', 'category', 'error', 'success',
    'message', 'running', 'healthy', 'site_id', 'db_type',
    'container_id', 'image', 'service_name', 'action',
}

_SKIP_FIELDS = {
    'description', 'desc', 'remark', 'detail', 'details', 'content',
    'raw_output', 'log', 'logs', 'metadata', 'extra', 'extensions',
    'versions', 'env', 'labels', 'mounts', 'networks',
}


def _pick_key_fields(all_keys: set) -> set:
    key_fields = set()
    for k in all_keys:
        if k in _PRIORITY_FIELDS:
            key_fields.add(k)
    if not key_fields:
        for k in all_keys:
            if k not in _SKIP_FIELDS and len(k) <= 20:
                key_fields.add(k)
                if len(key_fields) >= 6:
                    break
    return key_fields


def _slim_item(item, key_fields: set) -> Any:
    if not isinstance(item, dict):
        return item
    if not key_fields:
        return item
    slimmed = {}
    for k in key_fields:
        if k in item:
            v = item[k]
            if isinstance(v, str) and len(v) > 100:
                v = v[:100] + '...'
            slimmed[k] = v
    return slimmed if slimmed else item


def summarize_tool_result(tool_name: str, tool_content: str) -> str:
    if not tool_content or len(tool_content) < 200:
        return tool_content

    is_error = '<toolcall_status>error</toolcall_status>' in tool_content
    if is_error:
        error_match = None
        for tag in ('<toolcall_result>', '<toolcall_result>\n'):
            idx = tool_content.find(tag)
            if idx != -1:
                start = idx + len(tag)
                end = tool_content.find('</toolcall_result>', start)
                if end != -1:
                    error_match = tool_content[start:end].strip()[:200]
                    break
        if error_match:
            return f'[{tool_name}] 执行失败: {error_match}'
        return f'[{tool_name}] 执行失败'

    result_text = tool_content
    for tag in ('<toolcall_result>', '<toolcall_result>\n'):
        idx = tool_content.find(tag)
        if idx != -1:
            start = idx + len(tag)
            end = tool_content.find('</toolcall_result>', start)
            if end != -1:
                result_text = tool_content[start:end].strip()
                break

    try:
        data = json.loads(result_text)
        if isinstance(data, dict):
            if 'error' in data:
                return f'[{tool_name}] 失败: {str(data["error"])[:150]}'
            if 'soft_list' in data:
                total = data.get('total', len(data['soft_list']))
                installed = sum(1 for s in data['soft_list'] if s.get('installed'))
                return f'[{tool_name}] 应用列表: 共{total}个, 已安装{installed}个'
            if 'containers' in data:
                total = data.get('total', len(data['containers']))
                running = sum(1 for c in data['containers'] if 'running' in str(c.get('status', '')).lower() or 'up' in str(c.get('status', '')).lower())
                return f'[{tool_name}] 容器列表: 共{total}个, 运行中{running}个'
            if 'sites' in data or 'websites' in data:
                items = data.get('sites', data.get('websites', []))
                return f'[{tool_name}] 网站列表: 共{len(items)}个'
            if 'databases' in data or 'db_list' in data:
                items = data.get('databases', data.get('db_list', []))
                return f'[{tool_name}] 数据库列表: 共{len(items)}个'
            if 'output' in data:
                output = str(data['output'])
                lines = output.count('\n') + 1
                return f'[{tool_name}] 命令输出: {lines}行, {len(output)}字符'
            if 'content' in data and isinstance(data.get('content'), str):
                lines = data['content'].count('\n') + 1
                return f'[{tool_name}] 文件内容: {lines}行, {len(data["content"])}字符'
            if 'success' in data:
                msg = data.get('message', data.get('msg', ''))
                return f'[{tool_name}] {"成功" if data["success"] else "失败"}: {str(msg)[:100]}'
            if 'processes' in data:
                return f'[{tool_name}] 进程列表: {data.get("total", len(data["processes"]))}个'
            if 'entries' in data:
                return f'[{tool_name}] 目录内容: {data.get("total", len(data["entries"]))}项'
            if 'matches' in data:
                return f'[{tool_name}] 搜索结果: {data.get("count", len(data["matches"]))}条匹配'
            key_info = []
            for k in ('name', 'title', 'status', 'version', 'port', 'ip'):
                if k in data and data[k]:
                    key_info.append(f'{k}={data[k]}')
            if key_info:
                return f'[{tool_name}] {", ".join(key_info[:4])}'
        elif isinstance(data, list):
            return f'[{tool_name}] 列表结果: {len(data)}项'
    except (json.JSONDecodeError, ValueError):
        pass

    lines = result_text.count('\n') + 1
    return f'[{tool_name}] 结果: {lines}行, {len(result_text)}字符'


def _xml_response(tool_name: str, status: str, content: str, max_chars: int = 50000) -> str:
    content = _smart_truncate(content, max_chars)

    return (
        f'\n<tool>'
        f'\n<tool_name>{tool_name}</tool_name>'
        f'\n<toolcall_status>{status}</toolcall_status>'
        f'\n<toolcall_result>'
        f'\n{content}'
        f'\n</toolcall_result>'
        f'\n</tool>\n'
    )


class AIToolRegistry:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools = {}
            cls._instance._definitions = {}
            cls._instance._metadata = {}
            cls._instance._dangerous_tools = set()
            cls._instance._progress_callbacks = {}
        return cls._instance

    def set_progress_callback(self, callback, session_id: str = ''):
        if session_id:
            self._progress_callbacks[session_id] = callback

    def remove_progress_callback(self, session_id: str):
        self._progress_callbacks.pop(session_id, None)

    def emit_progress(self, tool_name: str, event_type: str, progress: int = 0, message: str = '', data: dict = None, session_id: str = ''):
        if not session_id:
            session_id = getattr(_current_session, 'session_id', '')
        callback = None
        if session_id and session_id in self._progress_callbacks:
            callback = self._progress_callbacks[session_id]
        elif self._progress_callbacks:
            callback = next(iter(self._progress_callbacks.values()))
        if callback:
            try:
                callback(event_type, tool_name, '', progress, message, data)
            except Exception:
                pass

    def register_tool(self, tool_id: Union[str, Callable, type] = None, **kwargs):
        category = kwargs.get('category', 'default')
        name_cn = kwargs.get('name_cn', '')
        risk_level = kwargs.get('risk_level', 'low')

        if tool_id is None and 'id' in kwargs:
            tool_id = kwargs['id']

        if inspect.isclass(tool_id):
            return self._register_class(tool_id, None, category, name_cn, risk_level)

        if callable(tool_id):
            return self._register_func(tool_id, None, category, name_cn, risk_level)

        def decorator(obj):
            if inspect.isclass(obj):
                return self._register_class(obj, tool_id, category, name_cn, risk_level)
            else:
                return self._register_func(obj, tool_id, category, name_cn, risk_level)
        return decorator

    def _register_class(self, clazz: type, tool_id: Optional[str], category: str, name_cn: str, risk_level: str):
        try:
            instance = clazz()
        except Exception as e:
            raise ValueError(f'Failed to instantiate tool class {clazz.__name__}: {e}')

        func = None
        if hasattr(instance, 'execute') and callable(instance.execute):
            func = instance.execute
        elif callable(instance):
            func = instance.__call__
        else:
            raise ValueError(f'Class {clazz.__name__} must implement execute method or be callable.')

        if not tool_id:
            tool_id = clazz.__name__

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        wrapper.__name__ = tool_id

        if not wrapper.__doc__:
            wrapper.__doc__ = inspect.getdoc(clazz)

        self._register_func(wrapper, tool_id, category, name_cn, risk_level)
        return clazz

    def _register_func(self, func: Callable, tool_id: Optional[str], category: str, name_cn: str, risk_level: str):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        name = func.__name__
        final_id = tool_id if tool_id else name

        self._tools[name] = func
        schema = self._generate_schema(func)
        self._definitions[name] = ToolDefinition(
            name=name,
            description=schema['function']['description'],
            parameters=schema['function']['parameters'],
        )

        self._metadata[name] = {
            'id': final_id,
            'name': name,
            'name_cn': name_cn,
            'category': category,
            'risk_level': risk_level,
            'description': schema['function']['description'],
        }

        if risk_level in ('high', 'dangerous'):
            self._dangerous_tools.add(name)

        return wrapper

    def register(self, name: str, description: str, parameters: Dict[str, Any],
                 func: Callable, is_dangerous: bool = False):
        self._tools[name] = func
        self._definitions[name] = ToolDefinition(
            name=name,
            description=description,
            parameters=parameters,
        )
        self._metadata[name] = {
            'id': name,
            'name': name,
            'name_cn': '',
            'category': 'default',
            'risk_level': 'high' if is_dangerous else 'low',
            'description': description,
        }
        if is_dangerous:
            self._dangerous_tools.add(name)

    def get_tool(self, name: str) -> Optional[Callable]:
        return self._tools.get(name)

    def get_definition(self, name: str) -> Optional[ToolDefinition]:
        return self._definitions.get(name)

    def get_metadata(self, name: str) -> Optional[Dict[str, Any]]:
        return self._metadata.get(name)

    def get_all_definitions(self) -> List[ToolDefinition]:
        return list(self._definitions.values())

    def get_enabled_definitions(self, enabled_names: List[str] = None) -> List[ToolDefinition]:
        if enabled_names is None:
            return self.get_all_definitions()
        return [self._definitions[n] for n in enabled_names if n in self._definitions]

    def get_openai_tools(self, enabled_ids: List[str] = None) -> List[Dict[str, Any]]:
        self._refresh_dynamic_docs()

        tools = []
        for name, defn in self._definitions.items():
            meta = self._metadata.get(name, {})
            if enabled_ids is not None:
                if meta.get('id', name) not in enabled_ids:
                    continue
            tools.append({
                'type': 'function',
                'function': {
                    'name': defn.name,
                    'description': defn.description,
                    'parameters': defn.parameters,
                }
            })
        return tools

    def _refresh_dynamic_docs(self):
        for name, func in self._tools.items():
            doc = inspect.getdoc(func)
            if doc and name in self._definitions:
                if self._definitions[name].description != doc:
                    self._definitions[name] = ToolDefinition(
                        name=name,
                        description=doc,
                        parameters=self._definitions[name].parameters,
                    )

    def all_tool_names(self) -> List[str]:
        return list(self._tools.keys())

    def get_openai_tools_by_toolsets(self, toolset_names: List[str]) -> List[Dict[str, Any]]:
        from apps.sysai.agent.toolsets import resolve_tools_by_toolsets
        tool_names = resolve_tools_by_toolsets(toolset_names)
        return self.get_openai_tools(enabled_ids=tool_names)

    def get_openai_tools_by_profile(self, profile_name: str) -> List[Dict[str, Any]]:
        from apps.sysai.agent.toolsets import get_profile_tools
        tool_names = get_profile_tools(profile_name)
        return self.get_openai_tools(enabled_ids=tool_names)

    def get_all_tools_info(self) -> List[Dict[str, Any]]:
        infos = []
        for name, meta in self._metadata.items():
            info = meta.copy()
            if info.get('name_cn'):
                info['display_name'] = info['name_cn']
            infos.append(info)
        return infos

    def _resolve_param_aliases(self, sig_params: Dict[str, Any], arguments: Dict[str, Any]) -> Dict[str, Any]:
        resolved = dict(arguments)
        sig_param_names = {p for p in sig_params if p not in ('self', 'cls')}
        extra_args = {k: v for k, v in resolved.items() if k not in sig_param_names}

        if not extra_args:
            return resolved

        for extra_name, extra_value in extra_args.items():
            for param_name, aliases in _PARAM_ALIASES.items():
                if param_name in sig_param_names and extra_name in aliases:
                    if param_name not in resolved:
                        resolved[param_name] = extra_value
                        logger.info(f'参数别名映射: {extra_name} -> {param_name}')
                    break
            else:
                for param_name in sig_param_names:
                    if param_name in resolved:
                        continue
                    param_aliases = _PARAM_ALIASES.get(param_name, set())
                    if extra_name in param_aliases:
                        resolved[param_name] = extra_value
                        logger.info(f'参数别名映射: {extra_name} -> {param_name}')
                        break
                    if extra_name.replace('_', '') == param_name.replace('_', ''):
                        resolved[param_name] = extra_value
                        logger.info(f'参数模糊映射: {extra_name} -> {param_name}')
                        break

        return resolved

    def execute(self, name: str, arguments: Dict[str, Any]) -> str:
        func = self.get_tool(name)
        if not func:
            return _xml_response(name, 'error', f'工具 {name} 不存在')
        try:
            session_id = arguments.get('session_id', '')
            _current_session.session_id = session_id
            target_func = func
            if not inspect.isfunction(func) and not inspect.ismethod(func):
                if hasattr(func, '__call__'):
                    target_func = func.__call__

            sig = inspect.signature(target_func)
            arguments = self._resolve_param_aliases(sig.parameters, arguments)

            valid_kwargs = {}
            missing_params = []
            for pname, param in sig.parameters.items():
                if pname in ('self', 'cls'):
                    continue
                if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                    continue
                if pname in arguments:
                    valid_kwargs[pname] = arguments[pname]
                elif param.default == inspect.Parameter.empty:
                    missing_params.append(pname)

            if missing_params:
                doc = inspect.getdoc(func) or ''
                param_descriptions = self._parse_args_from_docstring(doc)
                hints = []
                for mp in missing_params:
                    hint = f'"{mp}"'
                    if mp in param_descriptions:
                        hint += f'（{param_descriptions[mp]}）'
                    hints.append(hint)
                hint_text = '、'.join(hints)

                extra_args = {k: v for k, v in arguments.items() if k not in sig.parameters}
                extra_hint = ''
                if extra_args:
                    extra_names = ', '.join(f'"{k}"' for k in extra_args.keys())
                    extra_hint = f' 你提供的参数名{extra_names}不正确，'

                return _xml_response(name, 'error',
                    f'{extra_hint}缺少必需参数: {hint_text}。请使用正确的参数名重新调用此工具。')

            result = func(**valid_kwargs)
            if isinstance(result, str):
                if result.strip().startswith('<tool>'):
                    return result
                content = result
            else:
                content = json.dumps(result, ensure_ascii=False, default=str, indent=2)
            return _xml_response(name, 'done', content)
        except PermissionError:
            return _xml_response(name, 'error', f'权限不足，无法执行工具 {name}')
        except Exception as e:
            logger.error(f'工具执行失败 [{name}]: {e}', exc_info=True)
            return _xml_response(name, 'error', f'工具执行失败: {str(e)}')

    def is_dangerous(self, name: str) -> bool:
        return name in self._dangerous_tools

    def _generate_schema(self, func: Callable) -> Dict[str, Any]:
        target_func = func
        if not inspect.isfunction(func) and not inspect.ismethod(func):
            if hasattr(func, '__call__'):
                target_func = func.__call__

        sig = inspect.signature(target_func)
        doc = inspect.getdoc(func) or 'No description provided.'

        param_descriptions = self._parse_args_from_docstring(doc)

        parameters = {
            'type': 'object',
            'properties': {},
            'required': []
        }

        try:
            type_hints = get_type_hints(target_func)
        except Exception:
            type_hints = {}

        for pname, param in sig.parameters.items():
            if pname in ('self', 'cls'):
                continue
            if pname == 'session_id':
                continue
            if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                continue

            param_type = type_hints.get(pname, str)
            json_type = self._python_type_to_json_type(param_type)

            param_info = {'type': json_type}
            if pname in param_descriptions:
                param_info['description'] = param_descriptions[pname]
            if param.default != inspect.Parameter.empty:
                param_info['default'] = param.default

            parameters['properties'][pname] = param_info

            if param.default == inspect.Parameter.empty:
                parameters['required'].append(pname)

        return {
            'type': 'function',
            'function': {
                'name': func.__name__,
                'description': doc,
                'parameters': parameters
            }
        }

    def _parse_args_from_docstring(self, doc: str) -> Dict[str, str]:
        result = {}
        if not doc:
            return result
        in_args = False
        for line in doc.split('\n'):
            stripped = line.strip()
            if stripped.startswith('Args:'):
                in_args = True
                continue
            if in_args:
                if not stripped:
                    break
                if stripped.startswith('Returns:') or stripped.startswith('Raises:') or stripped.startswith('Example'):
                    break
                if ':' in stripped:
                    parts = stripped.split(':', 1)
                    param_name = parts[0].strip().rstrip(')')
                    for ch in ('(', ' '):
                        if ch in param_name:
                            param_name = param_name.split(ch)[0].strip()
                    result[param_name] = parts[1].strip()
        return result

    def _python_type_to_json_type(self, py_type) -> str:
        if py_type == int:
            return 'integer'
        elif py_type == float:
            return 'number'
        elif py_type == bool:
            return 'boolean'
        elif py_type == list or getattr(py_type, '__origin__', None) == list:
            return 'array'
        elif py_type == dict or getattr(py_type, '__origin__', None) == dict:
            return 'object'
        else:
            return 'string'


registry = AIToolRegistry()

register_tool = registry.register_tool
