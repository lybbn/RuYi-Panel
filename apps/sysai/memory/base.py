from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class BaseMemoryStore(ABC):

    @abstractmethod
    def add(self, session_id: str, text: str, metadata: Dict[str, Any] = None) -> bool:
        pass

    @abstractmethod
    def search(self, session_id: str, query: str, top_k: int = 5, threshold: float = 0.3) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def search_by_text(self, session_id: str, text: str, top_k: int = 5, threshold: float = 0.3) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def delete_session(self, session_id: str) -> bool:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass
