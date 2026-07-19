import uuid

from sqlmodel import Session, select

from ..models.expense import Expense, ExpenseCategory
from ..models.transaction import Transaction, TransactionType, ActorType


class ExpenseService:

    def create_expense(
        self,
        category: ExpenseCategory,
        amount: float,
        description: str | None,
        recorded_by_admin_id: str,
        session: Session,
        *,
        receipt_file_id: str | None = None,
    ) -> Expense:
        expense = Expense(
            category=category,
            amount=amount,
            description=description,
            recorded_by_admin_id=uuid.UUID(recorded_by_admin_id),
            receipt_file_id=uuid.UUID(receipt_file_id) if receipt_file_id else None,
        )
        session.add(expense)
        session.commit()
        session.refresh(expense)

        # Every expense appears in the unified transaction timeline too,
        # even though it never touches a user's balance — outflow is
        # negative, matching the sign convention PRINT debits already use.
        tx = Transaction(
            type=TransactionType.EXPENSE,
            amount=-abs(amount),
            actor_id=uuid.UUID(recorded_by_admin_id),
            actor_type=ActorType.ADMIN,
            related_expense_id=expense.id,
            note=description,
        )
        session.add(tx)
        session.commit()

        return expense

    def get_all_expenses(
        self,
        session: Session,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Expense]:
        stmt = (
            select(Expense)
            .order_by(Expense.created_at.desc())  # type: ignore
            .limit(limit)
            .offset(offset)
        )
        return list(session.exec(stmt).all())

    def get_expense_by_id(self, expense_id: str, session: Session) -> Expense | None:
        stmt = select(Expense).where(Expense.id == uuid.UUID(expense_id))
        return session.exec(stmt).first()
