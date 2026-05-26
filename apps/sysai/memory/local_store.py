import hashlib
import logging
from typing import List, Dict, Any, Optional

import numpy as np

from apps.sysai.memory.base import BaseMemoryStore
from apps.sysai.models import AIEmbedding, AIChatSession

logger = logging.getLogger(__name__)


class LocalVectorMemoryStore(BaseMemoryStore):

    def __init__(self, embedding_provider=None):
        self._embedding_provider = embedding_provider

    def _compute_hash(self, text: str) -> str:
        return hashlib.sha256(text.encode('utf-8')).hexdigest()

    def _serialize_vector(self, vector: np.ndarray) -> bytes:
        return vector.astype(np.float32).tobytes()

    def _deserialize_vector(self, data: bytes) -> np.ndarray:
        return np.frombuffer(data, dtype=np.float32)

    def add(self, session_id: str, text: str, metadata: Dict[str, Any] = None) -> bool:
        if not self._embedding_provider or not self._embedding_provider.is_available():
            return False

        try:
            session = AIChatSession.objects.filter(id=session_id).first()
            if not session:
                return False

            content_hash = self._compute_hash(text)

            if AIEmbedding.objects.filter(session=session, content_hash=content_hash).exists():
                return True

            vector = self._embedding_provider.embed(text)
            if vector is None:
                return False

            embedding_bytes = self._serialize_vector(vector)

            AIEmbedding.objects.create(
                session=session,
                content_text=text[:2000],
                embedding=embedding_bytes,
                embedding_model=self._embedding_provider.get_model_name(),
                source=metadata.get('source', 'memory') if metadata else 'memory',
                content_hash=content_hash,
                metadata=metadata or {},
            )
            return True
        except Exception as e:
            logger.error(f'添加向量记忆失败: {e}', exc_info=True)
            return False

    def search(self, session_id: str, query: str, top_k: int = 5, threshold: float = 0.3) -> List[Dict[str, Any]]:
        if not self._embedding_provider or not self._embedding_provider.is_available():
            return []

        try:
            query_vector = self._embedding_provider.embed(query)
            if query_vector is None:
                return []

            session = AIChatSession.objects.filter(id=session_id).first()
            if not session:
                return []

            embeddings = AIEmbedding.objects.filter(session=session).only(
                'id', 'content_text', 'embedding', 'source', 'metadata', 'create_at'
            )

            if not embeddings.exists():
                return []

            candidates = []
            for emb in embeddings:
                try:
                    stored_vector = self._deserialize_vector(emb.embedding)
                    similarity = float(np.dot(query_vector, stored_vector) / (
                        np.linalg.norm(query_vector) * np.linalg.norm(stored_vector) + 1e-9
                    ))
                    if similarity >= threshold:
                        candidates.append({
                            'id': str(emb.id),
                            'text': emb.content_text,
                            'score': similarity,
                            'source': emb.source,
                            'metadata': emb.metadata or {},
                            'create_at': emb.create_at.isoformat() if emb.create_at else '',
                        })
                except Exception:
                    continue

            candidates.sort(key=lambda x: x['score'], reverse=True)
            return candidates[:top_k]
        except Exception as e:
            logger.error(f'搜索向量记忆失败: {e}', exc_info=True)
            return []

    def search_by_text(self, session_id: str, text: str, top_k: int = 5, threshold: float = 0.3) -> List[Dict[str, Any]]:
        return self.search(session_id, text, top_k=top_k, threshold=threshold)

    def delete_session(self, session_id: str) -> bool:
        try:
            session = AIChatSession.objects.filter(id=session_id).first()
            if session:
                AIEmbedding.objects.filter(session=session).delete()
            return True
        except Exception as e:
            logger.error(f'删除会话向量记忆失败: {e}', exc_info=True)
            return False

    def is_available(self) -> bool:
        return self._embedding_provider is not None and self._embedding_provider.is_available()
