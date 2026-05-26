from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Generator
from dataclasses import dataclass, field
from enum import Enum


class ModelType(Enum):
    LLM = "LLM"
    EMBEDDING = "EMBEDDING"
    TTS = "TTS"
    STT = "STT"
    IMAGE = "IMAGE"


@dataclass
class ModelConfig:
    model_name: str
    model_type: str
    provider_key: str
    api_base: str = ''
    api_key: str = ''
    api_secret: str = ''
    api_version: str = ''
    max_tokens: int = 4096
    temperature: float = 0.7
    top_p: float = 1.0
    extra_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatMessage:
    role: str
    content: str
    tool_calls: Optional[List[Dict]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: Dict[str, Any]


@dataclass
class ChatResponse:
    content: str = ''
    reasoning_content: str = ''
    tool_calls: List[Dict] = field(default_factory=list)
    finish_reason: str = ''
    usage: Dict[str, int] = field(default_factory=dict)


class BaseAIProvider(ABC):

    def __init__(self, provider_key: str, **kwargs):
        self.provider_key = provider_key
        self.config = kwargs

    @abstractmethod
    def get_supported_types(self) -> List[ModelType]:
        pass

    @abstractmethod
    def create_model(self, model_config: ModelConfig) -> Any:
        pass

    @abstractmethod
    def validate_credentials(self, api_key: str, api_base: str = '', **kwargs) -> bool:
        pass

    def is_type_supported(self, model_type: ModelType) -> bool:
        return model_type in self.get_supported_types()


class BaseLLMModel(ABC):

    def __init__(self, model_config: ModelConfig):
        self.model_config = model_config

    @abstractmethod
    def chat(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        stream: bool = False,
        **kwargs
    ) -> Any:
        pass

    @abstractmethod
    def chat_stream(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        **kwargs
    ) -> Generator[ChatResponse, None, None]:
        pass

    @abstractmethod
    def is_valid(self) -> bool:
        pass

    def get_model_info(self) -> Dict[str, Any]:
        return {
            'model_type': self.model_config.model_type,
            'model_name': self.model_config.model_name,
            'provider_key': self.model_config.provider_key,
        }


class BaseEmbeddingModel(ABC):

    def __init__(self, model_config: ModelConfig):
        self.model_config = model_config

    @abstractmethod
    def embed(self, text: str) -> Optional[List[float]]:
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> Optional[List[List[float]]]:
        pass

    @abstractmethod
    def is_valid(self) -> bool:
        pass
