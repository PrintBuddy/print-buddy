from fastapi import APIRouter, status, HTTPException

from ..dependencies.token import AdminTokenDep
from ..dependencies.database import SessionDep
from ..dependencies.pagination import PaginationDep

from ...schemas.expense import ExpenseCreate, ExpenseRead
from ...db.crud.expense import ExpenseService


router = APIRouter()

expense_service = ExpenseService()


@router.post(
    "",
    response_model=ExpenseRead,
    status_code=status.HTTP_201_CREATED,
)
def create_expense(
    data: ExpenseCreate,
    token: AdminTokenDep,
    session: SessionDep,
):
    admin_id = token.credentials
    return expense_service.create_expense(
        data.category,
        data.amount,
        data.description,
        admin_id,
        session,
        receipt_file_id=str(data.receipt_file_id) if data.receipt_file_id else None,
    )


@router.get(
    "",
    response_model=list[ExpenseRead],
    status_code=status.HTTP_200_OK,
)
def get_all_expenses(
    token: AdminTokenDep,
    session: SessionDep,
    pagination: PaginationDep,
):
    return expense_service.get_all_expenses(session, pagination.limit, pagination.offset)


@router.get(
    "/{expense_id}",
    response_model=ExpenseRead,
    status_code=status.HTTP_200_OK,
)
def get_expense(
    expense_id: str,
    token: AdminTokenDep,
    session: SessionDep,
):
    expense = expense_service.get_expense_by_id(expense_id, session)
    if expense is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")
    return expense
