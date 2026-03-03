from pydantic import BaseModel, EmailStr
from datetime import datetime
import uuid


class UserCreate(BaseModel):
    email: EmailStr
    username: str
    name: str
    surname: str
    pwd: str


class UserLogin(BaseModel):
    username: str
    pwd: str


class UserRead(BaseModel):
    email: EmailStr
    username: str
    name: str
    surname: str
    balance: float
    credit_limit: float
    is_admin: bool


class UserAdminRead(UserRead):
    id: uuid.UUID
    is_admin: bool
    is_active: bool
    created_at: datetime


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    username: str | None = None
    name: str | None = None
    surname: str | None = None


class UserAdminUpdate(UserUpdate):
    balance: float | None = None
    credit_limit: float | None = None
    is_active: bool | None = None
    is_admin: bool | None = None


class UserChangePassword(BaseModel):
    current_pwd: str
    new_pwd: str


class UserBase(BaseModel):
    username: str
    name: str
    surname: str
    email: EmailStr


class UserEmailRequest(BaseModel):
    email: EmailStr


class UserPwdReset(BaseModel):
    new_pwd: str