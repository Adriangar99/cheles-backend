class TransactionNotFound(Exception):
    pass


class UnknownCategory(Exception):
    pass


class UndatedTransaction(Exception):
    """The bank sent a transaction with no booking, value or transaction date."""


class UnknownImportTarget(Exception):
    """An import sends a wallet to an account that does not exist; the message is shown to the user."""
