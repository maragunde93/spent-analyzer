from enum import Enum


class Currency(str, Enum):
    ARS = "ARS"
    USD = "USD"


class ExpenseSource(str, Enum):
    manual = "manual"
    import_pdf = "import_pdf"
    bank_import = "bank_import"
    cash = "cash"
    transfer = "transfer"
    other = "other"


class ImportLineKind(str, Enum):
    purchase = "purchase"
    refund = "refund"
    payment = "payment"
    tax = "tax"
    fee = "fee"
    adjustment = "adjustment"
    debit_purchase = "debit_purchase"
    cash_withdrawal = "cash_withdrawal"
    card_payment = "card_payment"
    transfer = "transfer"
    income = "income"
    previous_payment = "previous_payment"
