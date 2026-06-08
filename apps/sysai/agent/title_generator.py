import logging
import re
import threading
from typing import Optional

logger = logging.getLogger(__name__)

_TITLE_PROMPT = (
    "根据用户的消息，生成一个简短准确的会话标题（3-10个字）。\n"
    "要求：\n"
    "1. 标题应概括用户消息的核心话题或意图\n"
    "2. 只返回标题文本，不要重复、不要加引号、标点或前缀\n"
    "3. 不要输出多余的解释"
)

_THINKING_DISABLED_V1 = {"thinking": {"type": "disabled"}}
_THINKING_DISABLED_V2 = {"enable_thinking": False}

_PROVIDER_THINKING_MAP = {
    'openai': _THINKING_DISABLED_V1,
    'deepseek': _THINKING_DISABLED_V1,
    'zhipu': _THINKING_DISABLED_V1,
    'openrouter': _THINKING_DISABLED_V1,
    'azure': _THINKING_DISABLED_V1,
    'baidu': _THINKING_DISABLED_V1,
    'alibaba': _THINKING_DISABLED_V2,
    'longcat': _THINKING_DISABLED_V1,
    'vllm': _THINKING_DISABLED_V1,
    'custom': _THINKING_DISABLED_V1,
}

_MODEL_NAME_THINKING_MAP = {
    'qwen': _THINKING_DISABLED_V2,
    'minimax': _THINKING_DISABLED_V2,
}


def _get_disable_thinking_body(model) -> dict:
    if model is None:
        return _THINKING_DISABLED_V1
    provider_key = ''
    model_name = ''
    if hasattr(model, 'model_config'):
        provider_key = getattr(model.model_config, 'provider_key', '') or ''
        model_name = getattr(model.model_config, 'model_name', '') or ''
    if provider_key:
        body = _PROVIDER_THINKING_MAP.get(provider_key.lower())
        if body is not None:
            return body
    if model_name:
        name_lower = model_name.lower()
        for keyword, body in _MODEL_NAME_THINKING_MAP.items():
            if keyword in name_lower:
                return body
    return _THINKING_DISABLED_V1


def _dedup_title(title: str) -> str:
    if not title or len(title) < 4:
        return title
    half = len(title) // 2
    for seg_len in range(half, 2, -1):
        first = title[:seg_len]
        second = title[seg_len:seg_len * 2]
        if first == second:
            return first
    return title


def generate_title(
    user_message: str,
    assistant_response: str,
    session_id: str = '',
    model=None,
) -> Optional[str]:
    user_snippet = user_message[:500] if user_message else ""
    assistant_snippet = assistant_response[:500] if assistant_response else ""

    if not user_snippet:
        return None

    messages = [
        {"role": "system", "content": _TITLE_PROMPT},
        {"role": "user", "content": user_snippet},
    ]

    try:
        if model is None:
            from apps.sysai.provider.tools import get_model_from_db
            model = get_model_from_db(None)
        elif not hasattr(model, 'chat_stream'):
            from apps.sysai.provider.tools import get_model_from_db
            model = get_model_from_db(model)

        if model is None:
            return None

        disable_thinking = _get_disable_thinking_body(model)
        response_text = ''
        for chunk in model.chat_stream(messages, tools=None, max_tokens=100, extra_body=disable_thinking):
            if chunk.content:
                response_text += chunk.content
            if chunk.finish_reason:
                break

        title = response_text.strip().strip('"\'""''《》【】').strip()
        title = re.sub(r'<[^>]+>', '', title).strip()
        title = _dedup_title(title)
        if title:
            title = title[:30]
            logger.info(f'会话标题生成成功: session={session_id}, title={title}')
            return title
        return None
    except Exception as e:
        logger.warning(f'标题生成失败: session={session_id}, error={e}')
        return None


def generate_title_async(
    user_message: str,
    assistant_response: str,
    session_id: str,
    model=None,
    callback=None,
):
    def _worker():
        title = generate_title(user_message, assistant_response, session_id, model)
        if title and callback:
            try:
                callback(session_id, title)
            except Exception as e:
                logger.warning(f'标题回调失败: session={session_id}, error={e}')

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return t
