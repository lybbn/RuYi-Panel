import logging
import re
import threading
from typing import List, Dict, Any, Optional

from apps.sysai.models import AIChatMessage, AIChatSession, AICompactionLog
from apps.sysai.provider.base import ChatMessage

logger = logging.getLogger(__name__)


class ContextCompressor:
    def __init__(self, config: dict):
        self.enabled = config.get('enable_context_compress', True)
        self.threshold = config.get('context_compress_threshold', 10000)
        self.preserve_rounds = config.get('compress_preserve_rounds', 5)
        self.enable_flush = config.get('enable_memory_flush', True)
        self.max_tool_result_chars = config.get('max_tool_result_chars', 6000)

    def should_compress(self, messages: list) -> bool:
        if not self.enabled:
            return False
        total_chars = sum(len(m.get('content', '') or '') for m in messages)
        return total_chars >= self.threshold

    def compress(self, session: AIChatSession, messages: list, llm_model) -> dict:
        if not self.enabled:
            return {'compacted': False, 'reason': 'disabled'}

        user_assistant_msgs = [
            m for m in messages if m.get('role') in ('user', 'assistant') and m.get('content')
        ]
        if len(user_assistant_msgs) < self.preserve_rounds * 2 + 2:
            return {'compacted': False, 'reason': 'too_few_messages'}

        split_point = max(0, len(user_assistant_msgs) - self.preserve_rounds * 2)
        old_msgs = user_assistant_msgs[:split_point]
        recent_msgs = user_assistant_msgs[split_point:]

        if not old_msgs:
            return {'compacted': False, 'reason': 'no_old_messages'}

        flushed_count = 0
        if self.enable_flush:
            flushed_count = self._flush_facts(session, old_msgs, llm_model)

        summary = self._generate_summary(old_msgs, llm_model)
        if not summary:
            return {'compacted': False, 'reason': 'summary_failed'}

        old_ids = [m.get('id') for m in old_msgs if m.get('id')]
        old_tool_call_ids = set()
        for m in old_msgs:
            if m.get('role') == 'assistant' and m.get('tool_calls'):
                for tc in m['tool_calls']:
                    if tc.get('id'):
                        old_tool_call_ids.add(tc['id'])

        tokens_before = sum(len(m.get('content', '') or '') for m in messages)

        if old_ids:
            AIChatMessage.objects.filter(session=session, id__in=old_ids).delete()

        if old_tool_call_ids:
            AIChatMessage.objects.filter(
                session=session, role='tool', tool_call_id__in=old_tool_call_ids
            ).delete()

        orphan_tool_msgs = AIChatMessage.objects.filter(
            session=session, role='tool'
        ).exclude(
            tool_call_id=''
        )
        active_assistant_tool_ids = set()
        for asm in AIChatMessage.objects.filter(session=session, role='assistant'):
            if asm.tool_calls:
                for tc in asm.tool_calls:
                    if tc.get('id'):
                        active_assistant_tool_ids.add(tc['id'])
        orphan_ids = [
            tm.id for tm in orphan_tool_msgs
            if tm.tool_call_id not in active_assistant_tool_ids
        ]
        if orphan_ids:
            AIChatMessage.objects.filter(id__in=orphan_ids).delete()

        AIChatMessage.objects.create(
            session=session,
            role='system',
            content=f'[历史对话摘要]: {summary}',
        )

        tokens_after = sum(
            len(m.content or '')
            for m in AIChatMessage.objects.filter(session=session)
        )

        AICompactionLog.objects.create(
            session=session,
            summary=summary[:2000],
            compacted_count=len(old_ids),
            flushed_facts=flushed_count,
            tokens_before=tokens_before,
            tokens_after=tokens_after,
        )

        session.message_count = AIChatMessage.objects.filter(session=session).count()
        session.save()

        self._async_vectorize(session.id, old_msgs, summary)

        return {
            'compacted': True,
            'summary': summary,
            'flushed': flushed_count,
            'compacted_count': len(old_ids),
            'tokens_before': tokens_before,
            'tokens_after': tokens_after,
        }

    def _flush_facts(self, session: AIChatSession, old_msgs: list, llm_model) -> int:
        assistant_msgs = [m for m in old_msgs if m.get('role') == 'assistant' and m.get('content')]
        if not assistant_msgs:
            return 0

        facts = []
        for msg in assistant_msgs[-10:]:
            content = msg.get('content', '')
            if not content or len(content) < 20:
                continue
            try:
                prompt = (
                    '从以下AI回复中提取关键事实信息，每条一行，格式为"- 事实内容"。'
                    '只提取客观事实、操作结果、配置信息等，忽略问候和解释性内容。'
                    '如果没有关键事实，返回空。\n\n'
                    f'AI回复:\n{content[:1500]}'
                )
                chunks = []
                for chunk in llm_model.chat_stream(
                    [ChatMessage(role='user', content=prompt)],
                    tools=None,
                ):
                    if chunk.content:
                        chunks.append(chunk.content)
                result = ''.join(chunks).strip()
                if result and result != '无':
                    facts.append(result)
            except Exception as e:
                logger.warning(f'Flush事实失败: {e}')
                continue

        if facts:
            combined = '\n'.join(facts)
            if len(combined) > 3000:
                combined = combined[:3000]
            AIChatMessage.objects.create(
                session=session,
                role='system',
                content=f'[记忆事实]:\n{combined}',
            )

        return len(facts)

    def _generate_summary(self, old_msgs: list, llm_model) -> str:
        dialogue_text = ''
        for msg in old_msgs:
            role = msg.get('role', '')
            content = msg.get('content', '')
            if not content:
                continue
            if role == 'user':
                dialogue_text += f'用户: {content[:300]}\n'
            elif role == 'assistant':
                dialogue_text += f'AI: {content[:300]}\n'

        if not dialogue_text.strip():
            return ''

        if len(dialogue_text) > 4000:
            dialogue_text = dialogue_text[:4000] + '\n...(内容已截断)'

        prompt = (
            '请用简洁的语言总结以下对话的核心要点，保留：\n'
            '1. 用户的关键需求和问题\n'
            '2. AI执行的关键操作和结果\n'
            '3. 重要的配置信息和参数\n'
            '4. 未解决的问题\n\n'
            '忽略问候、重复内容和无关细节。\n\n'
            f'对话内容:\n{dialogue_text}'
        )

        try:
            chunks = []
            for chunk in llm_model.chat_stream(
                [ChatMessage(role='user', content=prompt)],
                tools=None,
            ):
                if chunk.content:
                    chunks.append(chunk.content)
            return ''.join(chunks).strip()
        except Exception as e:
            logger.error(f'生成摘要失败: {e}', exc_info=True)
            return ''

    @staticmethod
    def prune_tool_results(messages: list, max_chars: int = 6000) -> list:
        pruned = []
        msg_count = len(messages)
        for idx, msg in enumerate(messages):
            if msg.get('role') == 'tool' and len(msg.get('content', '')) > max_chars:
                content = msg['content']
                is_old = idx < msg_count - 6
                msg = dict(msg)
                if is_old:
                    try:
                        from apps.sysai.tools.base import summarize_tool_result
                        tool_name = msg.get('tool_name', msg.get('name', ''))
                        if not tool_name:
                            for prev in reversed(messages[:idx]):
                                if prev.get('role') == 'assistant' and prev.get('tool_calls'):
                                    for tc in prev['tool_calls']:
                                        if tc.get('id') == msg.get('tool_call_id'):
                                            tool_name = tc.get('function', {}).get('name', '')
                                            break
                                    if tool_name:
                                        break
                        if tool_name:
                            summary = summarize_tool_result(tool_name, content)
                            if summary and len(summary) < len(content):
                                msg['content'] = f'[历史工具结果摘要] {summary}'
                                pruned.append(msg)
                                continue
                    except Exception:
                        pass
                try:
                    from apps.sysai.tools.base import _smart_truncate
                    msg['content'] = _smart_truncate(content, max_chars)
                except Exception:
                    head = content[:int(max_chars * 0.7)]
                    tail = content[-int(max_chars * 0.25):]
                    total = len(content)
                    msg['content'] = f'{head}\n\n...[工具结果已裁剪，原始{total}字符]...\n\n{tail}'
            pruned.append(msg)
        return pruned

    def _async_vectorize(self, session_id: str, old_msgs: list, summary: str):
        if not self.enable_flush:
            return

        def _do_vectorize():
            try:
                from apps.sysai.memory.embedding import EmbeddingProvider
                from apps.sysai.memory.local_store import LocalVectorMemoryStore

                sys_config = {}
                try:
                    from apps.sysai.models import AIModel
                    config_obj = AIModel.objects_all.filter(name='__sys_config__').first()
                    if config_obj and config_obj.extra_params:
                        sys_config = config_obj.extra_params
                except Exception:
                    pass

                if not sys_config.get('enable_memory', True):
                    return

                embedding_provider = EmbeddingProvider(sys_config)
                store = LocalVectorMemoryStore(embedding_provider)

                if not store.is_available():
                    return

                if summary:
                    store.add(
                        session_id,
                        summary,
                        metadata={'source': 'compaction', 'type': 'summary'}
                    )

                for msg in old_msgs:
                    role = msg.get('role', '')
                    content = msg.get('content', '')
                    if not content or role not in ('user', 'assistant'):
                        continue
                    if role == 'assistant' and len(content) > 50:
                        store.add(
                            session_id,
                            content[:500],
                            metadata={'source': 'memory', 'type': 'assistant_reply'}
                        )

            except Exception as e:
                logger.warning(f'异步向量化失败: {e}')

        t = threading.Thread(target=_do_vectorize, daemon=True)
        t.start()
