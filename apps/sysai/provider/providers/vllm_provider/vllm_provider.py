import logging
from typing import Any
from apps.sysai.provider.base import ModelConfig
from apps.sysai.provider.providers.openai_provider.openai_provider import (
    OpenAIModel, OpenAIEmbeddingModel, OpenAIProvider
)

logger = logging.getLogger(__name__)


class VLLMModel(OpenAIModel):
    pass


class VLLMProvider(OpenAIProvider):

    def create_model(self, model_config: ModelConfig) -> Any:
        if model_config.model_type == 'LLM':
            return VLLMModel(model_config)
        elif model_config.model_type == 'EMBEDDING':
            return OpenAIEmbeddingModel(model_config)
        raise ValueError(f'不支持的模型类型: {model_config.model_type}')
