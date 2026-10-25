class TransactionNotFound(Exception):
    pass


class UnknownCategory(Exception):
    pass


class UndatedTransaction(Exception):
    """The bank sent a transaction with no booking, value or transaction date."""
