from pydantic import BaseModel, EmailStr, field_serializer, field_validator
from datetime import datetime
import re
import uuid

from ..core.utils import round_money

_USERNAME_REGEX = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_.-]{2,19}$')


class UserCreate(BaseModel):
    email: EmailStr | None = None
    username: str
    name: str
    surname: str
    pwd: str
    email_to_set: bool = False

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not _USERNAME_REGEX.match(v):
            raise ValueError(
                "Username must be 3–20 characters long, start with a letter or "
                "underscore, and contain only letters, digits, underscores, dots, or hyphens."
            )
        return v


class UserLogin(BaseModel):
    username: str
    pwd: str


class UserRead(BaseModel):
    email: EmailStr | None = None
    username: str
    name: str
    surname: str
    balance: float
    credit_limit: float
    is_admin: bool
    email_to_set: bool

    @field_serializer("balance", "credit_limit")
    def serialize_money(self, value: float) -> float:
        return round_money(value)


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

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str | None) -> str | None:
        if v is not None and not _USERNAME_REGEX.match(v):
            raise ValueError(
                "Username must be 3–20 characters long, start with a letter or "
                "underscore, and contain only letters, digits, underscores, dots, or hyphens."
            )
        return v


class UserAdminUpdate(UserUpdate):
    balance: float | None = None
    credit_limit: float | None = None
    is_active: bool | None = None
    is_admin: bool | None = None

    @field_validator("balance", "credit_limit")
    @classmethod
    def validate_money_fields(cls, value: float | None) -> float | None:
        if value is None:
            return None
        return round_money(value)


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
