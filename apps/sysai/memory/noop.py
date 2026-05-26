from typing import List, Dict, Any
from apps.sysai.memory.base import BaseMemoryStore


class NoOpMemoryStore(BaseMemoryStore):

    def add(self, session_id: str, text: str, metadata: Dict[str, Any] = None) -> bool:
        return False

    def search(self, session_id: str, query: str, top_k: int = 5, threshold: float = 0.3) -> List[Dict[str, Any]]:
        return []

    def search_by_text(self, session_id: str, text: str, top_k: int = 5, threshold: float = 0.3) -> List[Dict[str, Any]]:
        return []

    def delete_session(self, session_id: str) -> bool:
        return True

    def is_available(self) -> bool:
        return False
