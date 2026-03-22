from fastapi import APIRouter, status, HTTPException
from pathlib import Path
import uuid

from ..dependencies.token import TokenDep, AdminTokenDep
from ..dependencies.database import SessionDep

from ...schemas.user import UserRead, UserUpdate, UserAdminRead, UserEmailRequest, UserChangePassword, UserAdminUpdate
from ...db.crud.user import UserService

from ...schemas.transaction import TransactionCreate, TransactionRead
from ...db.crud.transaction import TransactionService
from ...db.models.transaction import TransactionType

from ...core.file_manager import FileManager
from ...core.config import settings
from ...core.security import Security
from ...core.utils import round_money


router = APIRouter()
user_service = UserService()
tx_service = TransactionService()
fm = FileManager()


@router.get(
    '/me',
    response_model=UserRead,
    status_code=status.HTTP_200_OK
)
def get_me(
    token: TokenDep,
    session: SessionDep
):
    user_id = token.credentials

    user = user_service.get_user_by_id(user_id, session)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user


@router.patch(
    '/me',
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED
)
def update_me(
    user_data: UserUpdate,
    token: TokenDep,
    session: SessionDep
):
    
    user_id = token.credentials
    is_admin = user_service.user_is_admin(user_id, session)

    if not is_admin:
        user_data.name = None
        user_data.surname = None
        user_data.username = None

    if user_data.email is not None:
        email_exists = user_service.email_exists(user_data.email, session, exclude_id=user_id)

        if email_exists:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail='Email already exists'
            )
        
    if user_data.username is not None:
        username_exists = user_service.username_exists(user_data.username, session, exclude_id=user_id)

        if username_exists:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail='Username already exists'
            )

    user = user_service.update_user(user_id, user_data, session)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='User not found'
        )
    
    return user


@router.patch(
    "/change-password",
    status_code=status.HTTP_200_OK
)
def change_password(
    pwd_info: UserChangePassword,
    token: TokenDep,
    session: SessionDep
):
    
    user_id = token.credentials

    user = user_service.get_user_by_id(user_id, session)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    is_pwd = Security.verify_password(pwd_info.current_pwd, user.pwd)
    if not is_pwd:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Incorrect password"
        )
    
    new_pwd = Security.hash_password(pwd_info.new_pwd)

    success = user_service.change_password(
        user_id,
        new_pwd,
        session
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return { "success": True }


@router.patch(
    '/me/email',
    response_model=UserRead,
    status_code=status.HTTP_200_OK
)
def update_my_email(
    email_req: UserEmailRequest,
    token: TokenDep,
    session: SessionDep
):
    user_id = token.credentials
    email = email_req.email
    # Check if email already exists for another user
    email_exists = user_service.email_exists(email, session, exclude_id=user_id)
    if email_exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='Email already exists'
        )
    # Only update the email field
    user_data = UserUpdate(email=email)
    user = user_service.update_user(user_id, user_data, session)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='User not found'
        )
    return user


@router.get(
    '',
    response_model=list[UserAdminRead],
    status_code=status.HTTP_200_OK
)
def get_users(
    token: AdminTokenDep,
    session: SessionDep
):
    
    users = user_service.get_users(session)
    return users


@router.get(
    '/{id}',
    response_model=UserAdminRead,
    status_code=status.HTTP_200_OK
)
def get_user_by_id(
    id: str,
    token: AdminTokenDep,
    session: SessionDep
):
    
    user = user_service.get_user_by_id(id, session)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user


@router.patch(
    '/{id}',
    response_model=UserAdminRead,
    status_code=status.HTTP_201_CREATED
)
def update_user(
    id: str,
    user_data: UserAdminUpdate,
    token: AdminTokenDep,
    session: SessionDep
):
    
    if user_data.email is not None:
        email_exists = user_service.email_exists(user_data.email, session, exclude_id=id)

        if email_exists:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail='Email already exists'
            )
        
    if user_data.username is not None:
        username_exists = user_service.username_exists(user_data.username, session, exclude_id=id)

        if username_exists:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail='Username already exists'
            )
        
    user = user_service.update_user(id, user_data, session)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='User not found'
        )
    
    return user


@router.patch(
    "/balance-recharge/{user_id}/{amount}",
    response_model=UserRead,
    status_code=status.HTTP_200_OK
)
def recharge_user_balance(
    user_id: str,
    amount: float,
    token: AdminTokenDep,
    session: SessionDep
):
    """Add a positive credit amount to a user's balance and record it as a RECHARGE transaction."""
    amount = round_money(amount)

    if amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Recharge amount must be positive"
        )
    admin_id = token.credentials
    user = user_service.get_user_by_id(user_id, session)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    user_service.add_credit(user_id, amount, session)
    balance = user_service.get_user_balance(user_id, session)
    admin = user_service.get_username_by_id(admin_id, session)

    tx_data = TransactionCreate(
        user_id=uuid.UUID(user_id),
        type=TransactionType.RECHARGE,
        amount=amount,
        balance_after=balance,  # type: ignore
        note=f"Recharge by {admin}"
    )
    tx_service.create_transaction(tx_data, session)
    return user_service.get_user_by_id(user_id, session)


@router.patch(
    "/balance-adjust/{user_id}/{amount}",
    response_model=UserRead,
    status_code=status.HTTP_200_OK
)
def adjust_user_balance(
    user_id: str,
    amount: float,
    token: AdminTokenDep,
    session: SessionDep
):
    """Set a user's balance to an absolute value and record it as an ADJUSTMENT transaction."""
    admin_id = token.credentials
    user = user_service.get_user_by_id(user_id, session)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    target_balance = round_money(amount)
    balance = round_money(user.balance)
    diff = round_money(target_balance - balance)
    if diff >= 0:
        user_service.add_credit(user_id, diff, session)
    else:
        user_service.discount_credit(user_id, -diff, session)

    balance = user_service.get_user_balance(user_id, session)
    admin = user_service.get_username_by_id(admin_id, session)

    tx_data = TransactionCreate(
        user_id=uuid.UUID(user_id),
        type=TransactionType.ADJUSTMENT,
        amount=diff,
        balance_after=balance,  # type: ignore
        note=f"Balance adjustment by {admin}"
    )

    tx_service.create_transaction(tx_data, session)

    return user_service.get_user_by_id(user_id, session)


@router.delete(
    '/{id}',
    response_model=UserAdminRead,
    status_code=status.HTTP_200_OK
)
def delete_user(
    id: str,
    token: AdminTokenDep,
    session: SessionDep
):
    
    user_delete = user_service.delete_user(id, session)
    if user_delete is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='User not found'
        )
    
    path = Path(settings.UPLOAD_PATH) / id
    fm.delete_directory(path)
    
    return user_delete


@router.get(
    '/{id}/transactions',
    response_model=list[TransactionRead],
    status_code=status.HTTP_200_OK
)
def get_user_transactions(
    id: str,
    token: AdminTokenDep,
    session: SessionDep
):
    """Get all transactions for a specific user (admin only)."""
    user = user_service.get_user_by_id(id, session)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return tx_service.get_transactions_from_user(id, session)
