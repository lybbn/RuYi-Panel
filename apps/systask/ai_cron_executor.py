#!/bin/python
#coding: utf-8

"""
AI定时任务执行引擎
1. AI Agent 执行模式 - AI自主分析并完成任务
2. 结果自动投递 - 任务执行完自动推送到通知渠道
3. 静默机制 - AI返回[SILENT]时不投递通知
4. 任务链 - 从上游任务获取上下文
5. 超时处理 - 防止AI执行无限挂起
"""

import json
import logging
import platform
import threading
import time
import uuid
from datetime import datetime
from typing import Optional, Tuple

logger = logging.getLogger('apscheduler.scheduler')

SILENT_MARKER = '[SILENT]'


def _get_cron_task_logger(job_id):
    from apps.systask.tasklogger import tasklogger
    return tasklogger(job_id)


def _build_ai_system_prompt(task_name: str, context_str: str = '') -> str:
    current_os = platform.system()
    if current_os == 'Windows':
        os_instruction = (
            '当前服务器为 **Windows** 系统。\n'
            '- 必须使用Windows命令（dir、tasklist、netstat、sc、powershell等），禁止使用Linux命令\n'
            '- 如需执行复杂操作，优先使用PowerShell命令\n'
            '- 路径分隔符使用反斜杠\\，如C:\\Users\\...\n'
        )
    elif current_os == 'Linux':
        os_instruction = (
            '当前服务器为 **Linux** 系统。\n'
            '- 使用标准Linux命令，注意不同发行版的包管理器差异（apt/yum/dnf）\n'
        )
    else:
        os_instruction = f'当前服务器为 **{current_os}** 系统。\n'

    base = (
        '你是如意面板的AI定时任务执行引擎。你正在自动执行一个定时任务，没有用户在线交互。\n\n'
        f'### 平台信息\n{os_instruction}\n'
        '### 执行规则\n'
        '1. 根据任务提示词自主完成操作，使用工具获取信息并执行\n'
        '2. 执行完毕后，给出简洁的执行结果摘要\n'
        '3. 如果检查结果一切正常、无需报告，请在回复开头写 [SILENT]，系统将跳过通知\n'
        '4. 如果发现异常或需要关注的问题，详细描述情况，系统会自动通知管理员\n'
        '5. 禁止执行危险操作（如 rm -rf /、格式化磁盘、del /s /q C:\\ 等）\n'
        '6. 优先使用面板工具（如 panel_shop_*、crontab_* 等），而非系统命令\n\n'
    )
    if context_str:
        base += f'### 上游任务上下文\n{context_str}\n\n'
    return base


def _get_context_from_upstream(context_from_id: str) -> str:
    if not context_from_id:
        return ''
    try:
        from apps.systask.models import CrontabTask
        upstream = CrontabTask.objects.filter(id=context_from_id).first()
        if not upstream:
            return f'[上游任务ID {context_from_id} 不存在]'
        if not upstream.ai_last_result:
            return f'[上游任务 "{upstream.name}" 暂无执行结果]'
        return f'上游任务 "{upstream.name}" 的最近执行结果：\n{upstream.ai_last_result[:3000]}'
    except Exception as e:
        logger.error(f'获取上游任务上下文失败: {e}')
        return ''


def _deliver_result(task_name: str, content: str, deliver_channels: str, job_id: str = ''):
    if not deliver_channels or deliver_channels == 'none':
        logger.info(f'AI任务 "{task_name}" 投递渠道为none，跳过投递')
        return

    from apps.sysalert.notify import AlertNotifier
    from apps.sysalert.models import AlertNotifyConfig

    channels = [ch.strip() for ch in deliver_channels.split(',') if ch.strip()]
    title = f'如意面板 - AI定时任务: {task_name}'

    for channel in channels:
        try:
            if channel == 'all':
                configs = AlertNotifyConfig.objects.filter(is_enabled=True)
                for cfg in configs:
                    success, msg = AlertNotifier.send(cfg, title, content)
                    status = '成功' if success else '失败'
                    logger.info(f'AI任务 "{task_name}" 投递到 {cfg.channel_type}({cfg.name}): {status} - {msg}')
            else:
                configs = AlertNotifyConfig.objects.filter(channel_type=channel, is_enabled=True)
                if not configs.exists():
                    logger.warning(f'AI任务 "{task_name}" 未找到启用的 {channel} 通知渠道')
                    continue
                for cfg in configs:
                    success, msg = AlertNotifier.send(cfg, title, content)
                    status = '成功' if success else '失败'
                    logger.info(f'AI任务 "{task_name}" 投递到 {channel}({cfg.name}): {status} - {msg}')
        except Exception as e:
            logger.error(f'AI任务 "{task_name}" 投递到 {channel} 失败: {e}')


def _run_ai_agent(prompt: str, system_prompt: str, timeout: int = 300) -> Tuple[bool, str, str]:
    success = False
    output = ''
    error = ''

    try:
        from apps.sysai.agent.core import Agent
        from apps.sysai.provider.tools import get_model_from_db
        from apps.sysai.models import AIModel
        from apps.sysai.tools.base import AIToolRegistry

        model = AIModel.objects.filter(is_enabled=True, is_default=True).first()
        if not model:
            model = AIModel.objects.filter(is_enabled=True).first()
        if not model:
            return False, '', 'AI模型未配置，无法执行AI定时任务，请先在AI设置中配置模型'

        ai_model = get_model_from_db(model)

        session_id = f'cron_{uuid.uuid4().hex[:12]}'
        tool_registry = AIToolRegistry()

        agent = Agent(
            session_id=session_id,
            model=ai_model,
            config={
                'max_tool_iterations': 15,
                'require_command_confirm': False,
                'enable_memory': False,
                'temperature': 0.3,
            },
            tool_registry=tool_registry,
        )
        agent.system_prompt = system_prompt

        result_content = ''
        result_event = threading.Event()
        result_lock = threading.Lock()

        def on_chunk(chunk):
            nonlocal result_content
            if chunk.get('type') == 'content':
                with result_lock:
                    result_content += chunk.get('content', '')
            elif chunk.get('type') == 'stop':
                result_event.set()
            elif chunk.get('type') == 'error':
                result_event.set()

        agent.set_progress_callback(lambda *args, **kwargs: None)

        def _run_chat():
            nonlocal result_content, success, error
            try:
                for chunk in agent.chat(prompt):
                    chunk_type = chunk.get('type', '')
                    if chunk_type == 'content':
                        with result_lock:
                            result_content += chunk.get('content', '')
                    elif chunk_type == 'stop':
                        full_resp = chunk.get('full_response', '')
                        if full_resp and not result_content.strip():
                            with result_lock:
                                result_content = full_resp
                        break
                    elif chunk_type == 'error':
                        error = chunk.get('content', 'AI执行出错')
                        break
                success = True
            except Exception as e:
                error = str(e)
                logger.error(f'AI Agent执行异常: {e}')
            finally:
                result_event.set()

        chat_thread = threading.Thread(target=_run_chat, daemon=True)
        chat_thread.start()

        if not result_event.wait(timeout=timeout):
            agent.stop()
            chat_thread.join(timeout=10)
            error = f'AI执行超时({timeout}秒)'
            return False, result_content[:5000], error

        chat_thread.join(timeout=5)

        with result_lock:
            output = result_content[:10000]

        if not output and not error:
            error = 'AI执行完成但未产生有效输出'
            success = False

    except ImportError as e:
        error = f'AI模块未安装: {e}'
        logger.error(error)
    except Exception as e:
        error = f'AI Agent执行失败: {e}'
        logger.error(error, exc_info=True)

    return success, output, error


def run_ai_cron_task(task_obj: dict, job_id: str) -> None:
    task_name = task_obj.get('name', '未知任务')
    ai_prompt = task_obj.get('ai_prompt', '')
    ai_deliver = task_obj.get('ai_deliver', 'none')
    ai_silent = task_obj.get('ai_silent', False)
    ai_context_from = task_obj.get('ai_context_from', '')
    ai_timeout = int(task_obj.get('ai_timeout', 300))

    taskloggers = _get_cron_task_logger(job_id)
    taskloggers.info(f'------------------------【{task_name}】AI任务开始------------------------')

    if not ai_prompt:
        taskloggers.info(f'【{task_name}】AI任务提示词为空，跳过执行')
        return

    context_str = _get_context_from_upstream(ai_context_from)
    system_prompt = _build_ai_system_prompt(task_name, context_str)

    if context_str:
        taskloggers.info(f'【{task_name}】已加载上游任务上下文')

    taskloggers.info(f'【{task_name}】AI Agent开始执行，超时设置: {ai_timeout}秒')

    success, output, error = _run_ai_agent(ai_prompt, system_prompt, timeout=ai_timeout)

    from apps.systask.models import CrontabTask
    cron_task = CrontabTask.objects.filter(job_id=job_id).first()

    if success:
        taskloggers.info(f'【{task_name}】AI执行成功')
        taskloggers.info(f'【{task_name}】执行结果:\n{output[:3000]}')

        if cron_task:
            cron_task.ai_last_result = output[:10000]
            cron_task.save(update_fields=['ai_last_result', 'update_at'])

        should_deliver = True
        if ai_silent and output.strip().upper().startswith(SILENT_MARKER):
            taskloggers.info(f'【{task_name}】AI返回[SILENT]，静默模式跳过通知')
            should_deliver = False

        if should_deliver and ai_deliver != 'none':
            deliver_content = output
            if ai_silent and SILENT_MARKER in deliver_content:
                deliver_content = deliver_content.replace(SILENT_MARKER, '').strip()
            taskloggers.info(f'【{task_name}】开始投递结果到: {ai_deliver}')
            _deliver_result(task_name, deliver_content, ai_deliver, job_id)
    else:
        error_msg = error or '未知错误'
        taskloggers.info(f'【{task_name}】AI执行失败: {error_msg}')

        if cron_task:
            cron_task.ai_last_result = f'[失败] {error_msg}'
            cron_task.save(update_fields=['ai_last_result', 'update_at'])

        if ai_deliver != 'none':
            fail_content = f'AI定时任务 "{task_name}" 执行失败:\n{error_msg}'
            _deliver_result(task_name, fail_content, ai_deliver, job_id)

    taskloggers.info(f'------------------------【{task_name}】AI任务结束------------------------')
