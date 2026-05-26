import logging
import threading
from typing import Optional

logger = logging.getLogger(__name__)

_TITLE_PROMPT = (
    "根据以下对话的开头，生成一个简短的会话标题（3-10个字）。"
    "标题应概括对话的主要话题或意图。"
    "只返回标题文本，不要加引号、标点或前缀。"
)


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
        {"role": "user", "content": f"用户: {user_snippet}\n\nAI: {assistant_snippet}"},
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

        response_text = ''
        for chunk in model.chat_stream(messages, tools=None):
            if chunk.content:
                response_text += chunk.content
            if chunk.finish_reason:
                break

        title = response_text.strip().strip('"\'""''《》【】').strip()
        if title:
            title = title[:50]
            logger.info(f'会话标题生成成功: session={session_id}, title={title}')
            return title
        return None
    except Exception as e:
        logger.warning(f'会话标题生成失败: session={session_id}, error={e}')
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
