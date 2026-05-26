import json
import re
import uuid
import logging
from typing import Any, Dict, List, Generator, Optional
from openai import OpenAI
import httpx
from apps.sysai.provider.base import (
    BaseAIProvider, BaseLLMModel, BaseEmbeddingModel, ModelConfig, ModelType,
    ChatMessage, ChatResponse, ToolDefinition
)

logger = logging.getLogger(__name__)

_TOOL_FALLBACK_RULES = """### 工具调用规则（必须遵守 - 当前模型不支持Function Calling）
1. **使用JSON格式调用工具**：由于当前模型不支持Function Calling，你必须使用以下JSON格式调用工具，直接在回复文本中输出：
{{"name": "工具名", "arguments": {{参数对象}}}}
2. **格式要求**：
   - 直接输出JSON，不要用代码块包裹
   - 不要在JSON前后添加额外说明文字
   - 确保JSON格式正确，可以被解析
3. **严格使用工具定义中的参数名**：每个工具的参数名在工具定义中已明确指定，调用时必须使用完全相同的参数名，不要自创参数名。
4. **一次只调用一个工具**：每次只输出一个工具调用的JSON，等待结果后再决定下一步。
5. **工具结果处理**：工具执行结果会通过tool消息返回，不要在文本中重复工具结果。
6. 如果工具调用失败，根据错误信息调整参数后重试，不要放弃。

可用工具列表：
{tool_list}"""

_FC_RULES_PATTERN = re.compile(
    r'###\s*工具调用规则.*?(?=###|\Z)',
    re.DOTALL,
)


def _is_tool_choice_error(error: Exception) -> bool:
    error_str = str(error).lower()
    return any(kw in error_str for kw in (
        'auto tool choice', 'tool-call-parser',
        'enable-auto-tool-choice', 'tool call parser',
        'tool_choice is not supported',
    ))


class OpenAIModel(BaseLLMModel):

    def __init__(self, model_config: ModelConfig):
        super().__init__(model_config)
        timeout = httpx.Timeout(connect=10.0, read=300.0, write=30.0, pool=10.0)
        self.client = OpenAI(
            api_key=model_config.api_key,
            base_url=model_config.api_base or None,
            timeout=timeout,
            max_retries=1,
        )
        self._supports_tools: Optional[bool] = None
        self._tool_fallback_warning: Optional[str] = None

    def _build_messages(self, messages) -> List[Dict]:
        result = []
        for msg in messages:
            if isinstance(msg, dict):
                item = {'role': msg.get('role', 'user'), 'content': msg.get('content', '')}
                if msg.get('tool_calls'):
                    item['tool_calls'] = msg['tool_calls']
                if msg.get('tool_call_id'):
                    item['tool_call_id'] = msg['tool_call_id']
                if msg.get('name'):
                    item['name'] = msg['name']
                if msg.get('reasoning_content'):
                    item['reasoning_content'] = msg['reasoning_content']
            else:
                item = {'role': msg.role, 'content': msg.content}
                if msg.tool_calls:
                    item['tool_calls'] = msg.tool_calls
                if msg.tool_call_id:
                    item['tool_call_id'] = msg.tool_call_id
                if msg.name:
                    item['name'] = msg.name
                if getattr(msg, 'reasoning_content', None):
                    item['reasoning_content'] = msg.reasoning_content
            result.append(item)
        return result

    def _build_tools(self, tools) -> List[Dict]:
        if not tools:
            return None
        result = []
        for tool in tools:
            if isinstance(tool, dict):
                result.append(tool)
            else:
                result.append({
                    'type': 'function',
                    'function': {
                        'name': tool.name,
                        'description': tool.description,
                        'parameters': tool.parameters,
                    }
                })
        return result

    def _inject_tools_to_messages(self, messages: List[Dict], tools: List[Dict]) -> List[Dict]:
        if not tools:
            return messages

        tool_lines = []
        for tool in tools:
            func = tool.get('function', {})
            name = func.get('name', '')
            desc = func.get('description', '')
            params = func.get('parameters', {})
            tool_lines.append(f"- {name}: {desc}\n  参数Schema: {json.dumps(params, ensure_ascii=False)}")

        fallback_rules = _TOOL_FALLBACK_RULES.format(tool_list='\n'.join(tool_lines))

        result = list(messages)
        if result and result[0].get('role') == 'system':
            content = result[0]['content']
            if _FC_RULES_PATTERN.search(content):
                content = _FC_RULES_PATTERN.sub(lambda m: fallback_rules, content)
                result[0] = {**result[0], 'content': content}
            else:
                result[0] = {**result[0], 'content': content + '\n\n' + fallback_rules}
        else:
            result.insert(0, {'role': 'system', 'content': fallback_rules.strip()})

        return result

    def chat(self, messages: List[ChatMessage], tools: List[ToolDefinition] = None,
             stream: bool = False, **kwargs) -> Any:
        params = {
            'model': self.model_config.model_name,
            'messages': self._build_messages(messages),
            'max_tokens': kwargs.get('max_tokens', self.model_config.max_tokens),
            'temperature': kwargs.get('temperature', self.model_config.temperature),
            'top_p': kwargs.get('top_p', self.model_config.top_p),
            'stream': stream,
        }
        if stream:
            params['stream_options'] = {'include_usage': True}
        built_tools = self._build_tools(tools)

        if built_tools and self._supports_tools is False:
            params['messages'] = self._inject_tools_to_messages(params['messages'], built_tools)
            built_tools = None

        if built_tools:
            params['tools'] = built_tools

        try:
            response = self.client.chat.completions.create(**params)
            if built_tools:
                self._supports_tools = True
            return response
        except Exception as e:
            if 'stream_options' in str(e).lower() and stream:
                params.pop('stream_options', None)
                try:
                    response = self.client.chat.completions.create(**params)
                    if built_tools:
                        self._supports_tools = True
                    return response
                except Exception as e2:
                    e = e2

            if built_tools and _is_tool_choice_error(e):
                logger.warning(f'当前模型不支持原生tool calling, 降级为文本工具模式: {e}')
                self._supports_tools = False
                self._tool_fallback_warning = (
                    f'当前模型不支持原生工具调用(Function Calling)，已自动降级为文本工具模式。'
                    f'服务端返回错误: {str(e)}'
                )
                params.pop('tools', None)
                params['messages'] = self._inject_tools_to_messages(params['messages'], built_tools)
                return self.client.chat.completions.create(**params)

            raise

    def chat_stream(self, messages: List[ChatMessage], tools: List[ToolDefinition] = None,
                    **kwargs) -> Generator[ChatResponse, None, None]:
        response = self.chat(messages, tools, stream=True, **kwargs)

        content_buffer = ''
        reasoning_buffer = ''
        tool_calls_buffer: Dict[int, Dict] = {}
        tc_id_to_idx: Dict[str, int] = {}

        for chunk in response:
            if not chunk.choices:
                if hasattr(chunk, 'usage') and chunk.usage:
                    yield ChatResponse(
                        content='',
                        reasoning_content='',
                        finish_reason='',
                        usage={
                            'total_tokens': getattr(chunk.usage, 'total_tokens', 0) or 0,
                            'prompt_tokens': getattr(chunk.usage, 'prompt_tokens', 0) or 0,
                            'completion_tokens': getattr(chunk.usage, 'completion_tokens', 0) or 0,
                        },
                    )
                continue

            delta = chunk.choices[0].delta
            finish_reason = chunk.choices[0].finish_reason

            if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                reasoning_buffer += delta.reasoning_content
                yield ChatResponse(
                    content='',
                    reasoning_content=delta.reasoning_content,
                    finish_reason=finish_reason or '',
                )

            if delta.content:
                content_buffer += delta.content
                yield ChatResponse(
                    content=delta.content,
                    reasoning_content='',
                    finish_reason=finish_reason or '',
                )

            if delta.tool_calls:
                for tc in delta.tool_calls:
                    tc_id = tc.id or ''
                    tc_index = tc.index if tc.index is not None else 0

                    if tc_id and tc_id in tc_id_to_idx:
                        target_idx = tc_id_to_idx[tc_id]
                    elif tc_index not in tool_calls_buffer:
                        target_idx = tc_index
                        if tc_id:
                            tc_id_to_idx[tc_id] = target_idx
                    elif tc_id and tool_calls_buffer[tc_index].get('id') == tc_id:
                        target_idx = tc_index
                    elif not tc_id and tc_index in tool_calls_buffer:
                        target_idx = tc_index
                    else:
                        target_idx = max(tool_calls_buffer.keys()) + 1 if tool_calls_buffer else 0
                        if tc_id:
                            tc_id_to_idx[tc_id] = target_idx

                    if target_idx not in tool_calls_buffer:
                        tool_calls_buffer[target_idx] = {
                            'id': tc_id or f'call_auto_{target_idx}_{uuid.uuid4().hex[:8]}',
                            'index': target_idx,
                            'type': 'function',
                            'function': {'name': '', 'arguments': ''}
                        }

                    if tc_id and not tool_calls_buffer[target_idx]['id']:
                        tool_calls_buffer[target_idx]['id'] = tc_id

                    if tc.function:
                        if tc.function.name:
                            tool_calls_buffer[target_idx]['function']['name'] += tc.function.name
                        if tc.function.arguments:
                            tool_calls_buffer[target_idx]['function']['arguments'] += tc.function.arguments

            if finish_reason:
                if tool_calls_buffer:
                    tool_calls_list = [tool_calls_buffer[i] for i in sorted(tool_calls_buffer.keys())]
                    yield ChatResponse(
                        content=content_buffer,
                        reasoning_content=reasoning_buffer,
                        tool_calls=tool_calls_list,
                        finish_reason=finish_reason,
                    )
                else:
                    yield ChatResponse(
                        content=content_buffer,
                        reasoning_content=reasoning_buffer,
                        finish_reason=finish_reason,
                    )

    def is_valid(self) -> bool:
        try:
            test_msg = [ChatMessage(role='user', content='hi')]
            self.chat(test_msg, max_tokens=5)
            return True
        except Exception as e:
            logger.warning(f'OpenAI模型验证失败: {e}')
            return False


class OpenAIEmbeddingModel(BaseEmbeddingModel):

    def __init__(self, model_config: ModelConfig):
        super().__init__(model_config)
        timeout = httpx.Timeout(connect=10.0, read=60.0, write=30.0, pool=10.0)
        self.client = OpenAI(
            api_key=model_config.api_key,
            base_url=model_config.api_base or None,
            timeout=timeout,
            max_retries=1,
        )

    def embed(self, text: str) -> Optional[List[float]]:
        try:
            text = text.replace('\n', ' ')
            response = self.client.embeddings.create(
                input=[text],
                model=self.model_config.model_name,
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f'Embedding失败: {e}')
            return None

    def embed_batch(self, texts: List[str]) -> Optional[List[List[float]]]:
        try:
            cleaned = [t.replace('\n', ' ') for t in texts]
            response = self.client.embeddings.create(
                input=cleaned,
                model=self.model_config.model_name,
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            logger.error(f'批量Embedding失败: {e}')
            return None

    def is_valid(self) -> bool:
        try:
            result = self.embed('test')
            return result is not None
        except Exception as e:
            logger.warning(f'Embedding模型验证失败: {e}')
            return False


class OpenAIProvider(BaseAIProvider):

    def get_supported_types(self) -> List[ModelType]:
        return [ModelType.LLM, ModelType.EMBEDDING, ModelType.TTS, ModelType.STT]

    def create_model(self, model_config: ModelConfig) -> Any:
        if model_config.model_type == 'LLM':
            return OpenAIModel(model_config)
        elif model_config.model_type == 'EMBEDDING':
            return OpenAIEmbeddingModel(model_config)
        raise ValueError(f'不支持的模型类型: {model_config.model_type}')

    def validate_credentials(self, api_key: str, api_base: str = '', **kwargs) -> bool:
        try:
            client = OpenAI(api_key=api_key, base_url=api_base or None)
            client.models.list()
            return True
        except Exception:
            return False
