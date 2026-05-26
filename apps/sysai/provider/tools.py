from typing import Any, Dict
from apps.sysai.provider.constants import get_provider_class
from apps.sysai.provider.base import ModelConfig


def get_provider(provider_key: str, **kwargs) -> Any:
    provider_class = get_provider_class(provider_key)
    return provider_class(provider_key=provider_key, **kwargs)


def create_model(model_config: ModelConfig) -> Any:
    provider = get_provider(model_config.provider_key)
    return provider.create_model(model_config)


def get_model_from_config(
    provider_key: str,
    model_type: str,
    model_name: str,
    api_base: str = '',
    api_key: str = '',
    api_secret: str = '',
    api_version: str = '',
    max_tokens: int = 4096,
    temperature: float = 0.7,
    top_p: float = 1.0,
    **kwargs
) -> Any:
    model_config = ModelConfig(
        model_name=model_name,
        model_type=model_type,
        provider_key=provider_key,
        api_base=api_base,
        api_key=api_key,
        api_secret=api_secret,
        api_version=api_version,
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
        extra_params=kwargs
    )
    return create_model(model_config)


def get_model_from_db(model_instance, **kwargs) -> Any:
    extra = model_instance.extra_params or {}
    return get_model_from_config(
        provider_key=model_instance.provider,
        model_type=model_instance.model_type,
        model_name=model_instance.model_name,
        api_base=model_instance.api_base or '',
        api_key=model_instance.api_key or '',
        api_secret=model_instance.api_secret or '',
        api_version=model_instance.api_version or '',
        max_tokens=model_instance.max_tokens or 4096,
        temperature=model_instance.temperature if model_instance.temperature is not None else 0.7,
        top_p=model_instance.top_p if model_instance.top_p is not None else 1.0,
        **extra,
        **kwargs
    )


def validate_model_from_db(model_instance, raise_error=True) -> bool:
    model = get_model_from_db(model_instance)
    return model.is_valid()
