import uuid
from sqlmodel import Session, select

from ..models.user import User
from ...schemas.user import UserCreate, UserUpdate
from ...core.utils import round_money


class UserService:


   ########################## CREATE #########################

    def create_user(
        self, 
        user_data: UserCreate,
        session: Session
    ) -> User:
        
        user = User(**user_data.model_dump())

        session.add(user)
        session.commit()

        return user
    
    ########################## READ ##########################

    def user_is_admin(
        self,
        id: str,
        session: Session
    ) -> bool:
        
        stmt = select(User).where(User.id == id)
        user = session.exec(stmt).first()
        
        if user is None:
            return False
        
        return user.is_admin

    def email_exists(
        self,
        email: str,
        session: Session,
        exclude_id: str | None = None
    ) -> bool:

        statement = select(User).where(User.email == email)
        if exclude_id is not None:
            statement = statement.where(User.id != uuid.UUID(exclude_id))
        user = session.exec(statement).first()
        return user is not None

    def username_exists(
        self,
        username: str,
        session: Session,
        exclude_id: str | None = None
    ):
        statement = select(User).where(User.username == username)
        if exclude_id is not None:
            statement = statement.where(User.id != uuid.UUID(exclude_id))
        user = session.exec(statement).first()
        return user is not None

    def get_user_by_username(
        self,
        username: str,
        session: Session
    ) -> User | None:

        statement = select(User).where(User.username == username)
        user = session.exec(statement).first()

        return user
    
    def get_username_by_id(self, user_id: str, session: Session):
        stmt = select(User.username).where(User.id == user_id)
        username = session.exec(stmt).first()

        return username
    
    def get_user_by_id(
        self,
        id: str,
        session: Session
    ):
        statement = select(User).where(User.id == id)
        user = session.exec(statement).first()

        return user

    def get_user_by_email(
        self,
        email: str,
        session: Session
    ):
        statement = select(User).where(User.email == email)
        user = session.exec(statement).first()

        return user
    
    def get_users(
        self,
        session: Session
    ):
        stmt = select(User)
        users = session.exec(stmt).all()

        return users

    def get_usernames(
        self,
        session: Session
    ) -> set[str]:
        stmt = select(User.username)
        return {username.casefold() for username in session.exec(stmt).all()}
    
    def get_admin_emails(self, session: Session) -> list[str]:
        stmt = select(User.email).where(User.is_admin == True, User.is_active == True)
        return list(session.exec(stmt).all())

    def get_user_balance(
        self,
        user_id: str,
        session: Session
    ):
        stmt = select(User.balance).where(User.id == user_id)
        balance = session.exec(stmt).first()
        if balance is None:
            return None
        return round_money(balance)
    
    def get_user_credit_limit(
        self,
        user_id: str,
        session: Session
    ):
        stmt = select(User.credit_limit).where(User.id == user_id)
        credit_limit = session.exec(stmt).first()
        if credit_limit is None:
            return None
        return round_money(credit_limit)
    
    ######################## UPDATE ##########################

    def update_user(
        self,
        user_id: str,
        user_data: UserUpdate,
        session: Session
    ):
        
        stmt = select(User).where(User.id == user_id)
        user = session.exec(stmt).first()

        if user is None:
            return
        
        data = user_data.model_dump(exclude_none=True)
        if "balance" in data:
            data["balance"] = round_money(data["balance"])
        if "credit_limit" in data:
            data["credit_limit"] = round_money(data["credit_limit"])
        for key, value in data.items():
            setattr(user, key, value)

        if user_data.email is not None:
            user.email_to_set = False

        session.commit()

        return user
    
    def change_password(
        self,
        user_id: str,
        new_pwd: str,
        session: Session
    ):
        
        stmt = select(User).where(User.id == user_id)
        user = session.exec(stmt).first()
        if user is None:
            return False

        user.pwd = new_pwd
        session.commit()

        return True

    
    def discount_credit(self, user_id: str, cost: float, session: Session):
        stmt = select(User).where(User.id == user_id)
        user = session.exec(stmt).first()

        if user is None:
            return False
        
        user.balance = round_money(user.balance - cost)
        session.commit()

        return True
    
    def add_credit(self, user_id: str, amount: float, session: Session):
        stmt = select(User).where(User.id == user_id)
        user = session.exec(stmt).first()

        if user is None:
            return False
        
        user.balance = round_money(user.balance + amount)
        session.commit()

        return True
    
    ######################## DELETE ##########################

    def delete_user(
        self,
        id: str,
        session: Session
    ):
        stmt = select(User).where(User.id == id)
        user = session.exec(stmt).first()

        if user is None:
            return None
        
        session.delete(user)
        session.commit()
        return user
        
