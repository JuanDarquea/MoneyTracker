import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Transaction
from app.schemas.transaction import TransactionCreate, TransactionUpdate


def create_transaction(db: Session, user_id: uuid.UUID, payload: TransactionCreate) -> Transaction:
    txn = Transaction(id=uuid.uuid4(), user_id=user_id, **payload.model_dump())
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


def list_transactions(db: Session, user_id: uuid.UUID) -> list[Transaction]:
    stmt = select(Transaction).where(Transaction.user_id == user_id).order_by(Transaction.occurred_on.desc())
    return list(db.scalars(stmt))


def get_transaction(db: Session, user_id: uuid.UUID, transaction_id: uuid.UUID) -> Transaction | None:
    stmt = select(Transaction).where(Transaction.id == transaction_id, Transaction.user_id == user_id)
    return db.scalars(stmt).first()


def update_transaction(db: Session, transaction: Transaction, payload: TransactionUpdate) -> Transaction:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(transaction, field, value)
    db.commit()
    db.refresh(transaction)
    return transaction


def delete_transaction(db: Session, transaction: Transaction) -> None:
    db.delete(transaction)
    db.commit()
