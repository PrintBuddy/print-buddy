from sqlmodel import Session, select


from ...db.models.transaction import Transaction
from ...schemas.transaction import TransactionCreate


class TransactionService:

    ########################## CREATE #########################

    def create_transaction(
        self,
        transaction_data: TransactionCreate,
        session: Session
    ):
        transaction = Transaction(**transaction_data.model_dump())

        session.add(transaction)
        session.commit()

        return transaction
    
    ########################## READ #########################

    def get_transactions_from_user(
        self,
        user_id: str,
        session: Session
    ):
        stmt = select(Transaction).where(
            Transaction.user_id == user_id
        ).order_by(Transaction.created_at.desc())  # type: ignore
        return list(session.exec(stmt).all())

    def get_all_transactions(
        self,
        session: Session
    ):
        stmt = select(Transaction).order_by(Transaction.created_at.desc())  # type: ignore
        return list(session.exec(stmt).all())
