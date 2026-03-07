class InvoiceRepository(BaseRepository[Invoice]):
    def __init__(self):
        super().__init__(Invoice)

    