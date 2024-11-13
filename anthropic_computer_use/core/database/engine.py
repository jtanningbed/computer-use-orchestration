from abc import ABC, abstractmethod
from typing import Any, Optional, Tuple

class DatabaseEngine(ABC):
    """Abstract base class for database engines"""
    
    @abstractmethod
    def connect(self) -> None:
        """Establish database connection"""
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """Close database connection"""
        pass
    
    @abstractmethod
    def execute(self, query: str, params: Optional[Tuple] = None) -> Any:
        """Execute a database query"""
        pass
    
    @abstractmethod
    def fetch_all(self, query: str, params: Optional[Tuple] = None) -> list[dict[str, Any]]:
        """Fetch all results from a query"""
        pass
    
    @abstractmethod
    def fetch_one(self, query: str, params: Optional[Tuple] = None) -> Optional[dict[str, Any]]:
        """Fetch single result from a query"""
        pass
