from abc import ABC, abstractmethod
from typing import Any, Dict, List

class BaseERPClient(ABC):

    @abstractmethod
    def authenticate(self) -> None: ...

    @abstractmethod
    def create_invoice(self, vals: Dict[str, Any]) -> Any: ...

    @abstractmethod
    def read_invoice(self, record_id: Any) -> Dict[str, Any]: ...

    @abstractmethod
    def update_invoice(self, record_id: Any, vals: Dict[str, Any]) -> bool: ...

    @abstractmethod
    def search_invoices(self, filters: Dict[str, Any], limit: int) -> List[Dict]: ...

    @abstractmethod
    def get_monthly_revenue(self, year: int, month: int) -> float: ...