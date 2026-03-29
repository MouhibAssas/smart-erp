from app.models.invoice import Invoice
from app.repositories.base_repository import BaseRepository

class InvoiceRepository(BaseRepository[Invoice]):
    def __init__(self):
        super().__init__(Invoice)

