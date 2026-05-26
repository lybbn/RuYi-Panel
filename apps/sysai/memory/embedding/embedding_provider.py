import logging
from typing import Optional, List

import numpy as np

from apps.sysai.models import AIModel

logger = logging.getLogger(__name__)


class EmbeddingProvider:

    def __init__(self, config: dict = None):
        self._config = config or {}
        self._model = None
        self._model_name = ''
        self._initialized = False

    def _initialize(self):
        if self._initialized:
            return

        self._initialized = True

        embedding_model_id = self._config.get('embedding_model_id')
        if embedding_model_id:
            model_obj = AIModel.objects.filter(id=embedding_model_id, is_enabled=True, model_type='EMBEDDING').first()
            if model_obj:
                try:
                    from apps.sysai.provider.tools import get_model_from_db
                    self._model = get_model_from_db(model_obj)
                    self._model_name = model_obj.model_name
                    if self._model and self._model.is_valid():
                        logger.info(f'Embedding模型初始化成功: {self._model_name}')
                        return
                except Exception as e:
                    logger.warning(f'指定Embedding模型初始化失败: {e}')

        embedding_models = AIModel.objects.filter(is_enabled=True, model_type='EMBEDDING')
        for model_obj in embedding_models:
            try:
                from apps.sysai.provider.tools import get_model_from_db
                model = get_model_from_db(model_obj)
                if model and model.is_valid():
                    self._model = model
                    self._model_name = model_obj.model_name
                    logger.info(f'Embedding模型自动选择: {self._model_name}')
                    return
            except Exception as e:
                logger.warning(f'Embedding模型 {model_obj.model_name} 初始化失败: {e}')
                continue

        logger.info('未找到可用的Embedding模型，记忆功能将降级为NoOp')

    def embed(self, text: str) -> Optional[np.ndarray]:
        self._initialize()

        if not self._model:
            return None

        try:
            result = self._model.embed(text)
            if result is not None:
                return np.array(result, dtype=np.float32)
            return None
        except Exception as e:
            logger.error(f'Embedding失败: {e}', exc_info=True)
            return None

    def embed_batch(self, texts: List[str]) -> Optional[List[np.ndarray]]:
        self._initialize()

        if not self._model:
            return None

        try:
            results = []
            for text in texts:
                vec = self.embed(text)
                if vec is not None:
                    results.append(vec)
            return results if results else None
        except Exception as e:
            logger.error(f'批量Embedding失败: {e}', exc_info=True)
            return None

    def is_available(self) -> bool:
        self._initialize()
        return self._model is not None

    def get_model_name(self) -> str:
        return self._model_name
