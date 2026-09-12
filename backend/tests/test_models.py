import uuid
from datetime import date
from decimal import Decimal

from app.models import Transaction, TransactionType


def test_transaction_stores_amount_as_decimal(db, seeded_category):
    txn = Transaction(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        category_id=seeded_category.id,
        type=TransactionType.EXPENSE,
        amount=Decimal("12.50"),
        occurred_on=date(2026, 9, 1),
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)

    assert isinstance(txn.amount, Decimal)
    assert txn.amount == Decimal("12.50")
