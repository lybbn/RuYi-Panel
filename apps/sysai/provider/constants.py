import logging
from typing import Dict, Type
from apps.sysai.provider.base import BaseAIProvider

logger = logging.getLogger(__name__)

PROVIDER_MAPPING: Dict[str, Type[BaseAIProvider]] = {}


def _init_providers():
    global PROVIDER_MAPPING
    if PROVIDER_MAPPING:
        return

    try:
        from apps.sysai.provider.providers.openai_provider.openai_provider import OpenAIProvider
        PROVIDER_MAPPING['openai'] = OpenAIProvider
        PROVIDER_MAPPING['azure'] = OpenAIProvider
        PROVIDER_MAPPING['custom'] = OpenAIProvider
    except ImportError as e:
        logger.warning(f'OpenAI Provider 加载失败: {e}')

    try:
        from apps.sysai.provider.providers.deepseek_provider.deepseek_provider import DeepSeekProvider
        PROVIDER_MAPPING['deepseek'] = DeepSeekProvider
    except ImportError as e:
        logger.warning(f'DeepSeek Provider 加载失败: {e}')

    try:
        from apps.sysai.provider.providers.ollama_provider.ollama_provider import OllamaProvider
        PROVIDER_MAPPING['ollama'] = OllamaProvider
    except ImportError as e:
        logger.warning(f'Ollama Provider 加载失败: {e}')

    try:
        from apps.sysai.provider.providers.longcat_provider.longcat_provider import LongcatProvider
        PROVIDER_MAPPING['longcat'] = LongcatProvider
    except ImportError as e:
        logger.warning(f'Longcat Provider 加载失败: {e}')

    try:
        from apps.sysai.provider.providers.vllm_provider.vllm_provider import VLLMProvider
        PROVIDER_MAPPING['vllm'] = VLLMProvider
    except ImportError as e:
        logger.warning(f'vLLM Provider 加载失败: {e}')

    try:
        from apps.sysai.provider.providers.openrouter_provider.openrouter_provider import OpenRouterProvider
        PROVIDER_MAPPING['openrouter'] = OpenRouterProvider
    except ImportError as e:
        logger.warning(f'OpenRouter Provider 加载失败: {e}')


def get_provider_class(provider_key: str) -> Type[BaseAIProvider]:
    _init_providers()
    provider_key = provider_key.lower()
    if provider_key not in PROVIDER_MAPPING:
        raise ValueError(f'未找到Provider: {provider_key}，请确保已安装相应的依赖包')
    return PROVIDER_MAPPING[provider_key]


def list_providers() -> Dict[str, str]:
    _init_providers()
    return {key: PROVIDER_MAPPING[key].__name__ for key in PROVIDER_MAPPING}
