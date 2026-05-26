import logging
import re
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ErrorClassification:
    category: str
    recoverable: bool
    strategy: str
    message: str
    retry_after: float = 0.0


def classify_api_error(error: Exception) -> ErrorClassification:
    error_str = str(error).lower()
    error_type = type(error).__name__.lower()

    if _is_context_overflow(error_str, error_type):
        return ErrorClassification(
            category='context_overflow',
            recoverable=True,
            strategy='compress_and_retry',
            message='上下文长度超限，将自动压缩后重试',
        )

    if _is_rate_limit(error_str, error_type):
        retry_after = _extract_retry_after(str(error))
        return ErrorClassification(
            category='rate_limit',
            recoverable=True,
            strategy='backoff_retry',
            message=f'API请求频率超限，{retry_after}秒后重试',
            retry_after=retry_after,
        )

    if _is_auth_error(error_str, error_type):
        return ErrorClassification(
            category='auth',
            recoverable=False,
            strategy='notify_user',
            message='API认证失败，请检查API Key配置',
        )

    if _is_billing_error(error_str, error_type):
        return ErrorClassification(
            category='billing',
            recoverable=False,
            strategy='notify_user',
            message='API余额不足或计费异常，请检查账户',
        )

    if _is_timeout(error_str, error_type):
        return ErrorClassification(
            category='timeout',
            recoverable=True,
            strategy='retry_once',
            message='API请求超时，将重试一次',
            retry_after=2.0,
        )

    if _is_server_error(error_str, error_type):
        return ErrorClassification(
            category='server_error',
            recoverable=True,
            strategy='backoff_retry',
            message='API服务端错误，稍后重试',
            retry_after=5.0,
        )

    if _is_connection_error(error_str, error_type):
        return ErrorClassification(
            category='connection',
            recoverable=True,
            strategy='retry_once',
            message='网络连接异常，将重试一次',
            retry_after=3.0,
        )

    if _is_model_not_found(error_str, error_type):
        return ErrorClassification(
            category='model_not_found',
            recoverable=False,
            strategy='notify_user',
            message='模型不存在或不可用，请检查模型配置',
        )

    return ErrorClassification(
        category='unknown',
        recoverable=False,
        strategy='notify_user',
        message=f'API调用异常: {str(error)[:200]}',
    )


def should_retry_after_error(
    error: Exception,
    attempt: int,
    max_retries: int = 2,
) -> Optional[float]:
    if attempt >= max_retries:
        return None

    classification = classify_api_error(error)
    if not classification.recoverable:
        return None

    if classification.strategy == 'compress_and_retry':
        return 0.0

    if classification.strategy in ('backoff_retry', 'retry_once'):
        base = classification.retry_after or 2.0
        return min(base * (2 ** attempt), 30.0)

    return None


_CONTEXT_OVERFLOW_PATTERNS = [
    r'context.length',
    r'maximum.context',
    r'token.limit',
    r'too.many.tokens',
    r'exceeds.the.maximum',
    r'reduce.the.length',
    r'context.window',
    r'max_tokens',
    r'input.is.too.long',
    r'requested.*tokens.*exceed',
]

_RATE_LIMIT_PATTERNS = [
    r'rate.limit',
    r'too.many.requests',
    r'requests.per.minute',
    r'rpm.limit',
    r'throttl',
    r'429',
]

_AUTH_PATTERNS = [
    r'invalid.api.key',
    r'authentication.failed',
    r'invalid.x.api.key',
    r'incorrect.api.key',
    r'unauthorized',
    r'401',
    r'permission.denied',
    r'access.denied',
]

_BILLING_PATTERNS = [
    r'billing',
    r'quota.exceeded',
    r'insufficient.quota',
    r'plan.limit',
    r'credit',
    r'balance',
    r'402',
]

_TIMEOUT_PATTERNS = [
    r'timeout',
    r'timed.out',
    r'time.out',
    r'deadline.exceeded',
]

_SERVER_ERROR_PATTERNS = [
    r'500',
    r'502',
    r'503',
    r'504',
    r'internal.server.error',
    r'bad.gateway',
    r'service.unavailable',
    r'gateway.timeout',
    r'server.error',
    r'overloaded',
]

_CONNECTION_PATTERNS = [
    r'connection.error',
    r'connection.refused',
    r'connection.reset',
    r'connection.aborted',
    r'network.error',
    r'econnrefused',
    r'econnreset',
    r'ename.resolution',
    r'dns',
    r'socket.error',
]

_MODEL_NOT_FOUND_PATTERNS = [
    r'model.not.found',
    r'model.does.not.exist',
    r'invalid.model',
    r'model.unavailable',
    r'not.found',
]


def _match_patterns(text: str, patterns: list) -> bool:
    for pattern in patterns:
        if re.search(pattern, text):
            return True
    return False


def _is_context_overflow(text: str, error_type: str) -> bool:
    return _match_patterns(text, _CONTEXT_OVERFLOW_PATTERNS)


def _is_rate_limit(text: str, error_type: str) -> bool:
    return _match_patterns(text, _RATE_LIMIT_PATTERNS)


def _is_auth_error(text: str, error_type: str) -> bool:
    return _match_patterns(text, _AUTH_PATTERNS)


def _is_billing_error(text: str, error_type: str) -> bool:
    return _match_patterns(text, _BILLING_PATTERNS)


def _is_timeout(text: str, error_type: str) -> bool:
    return _match_patterns(text, _TIMEOUT_PATTERNS) or 'timeout' in error_type


def _is_server_error(text: str, error_type: str) -> bool:
    return _match_patterns(text, _SERVER_ERROR_PATTERNS)


def _is_connection_error(text: str, error_type: str) -> bool:
    return _match_patterns(text, _CONNECTION_PATTERNS) or 'connection' in error_type


def _is_model_not_found(text: str, error_type: str) -> bool:
    return _match_patterns(text, _MODEL_NOT_FOUND_PATTERNS)


def _extract_retry_after(error_str: str) -> float:
    match = re.search(r'retry.?after[:\s]*(\d+(?:\.\d+)?)', error_str, re.IGNORECASE)
    if match:
        return float(match.group(1))
    return 5.0
