from datetime import datetime
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import Numeric
from pydantic import EmailStr
from enum import Enum
import uuid

from ...core.utils import generate_time


class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


# Database model
class User(SQLModel, table=True):
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4, 
        primary_key=True, 
        index=True
    )

    email: EmailStr = Field( 
        unique=True, 
        nullable=True
    )

    username: str = Field(
        index=True, 
        unique=True, 
        nullable=False
    )

    name: str = Field(
        nullable=False
    )

    surname: str = Field(
        nullable=False
    )

    pwd: str = Field(nullable=False)

    is_active: bool = Field(default=True)

    role: UserRole = Field(default=UserRole.USER, nullable=False)

    @property
    def is_admin(self) -> bool:
        """Derived from `role`, not stored — ADMIN and SUPER_ADMIN both
        count as "an admin" for the many call sites that only need the
        binary check; `role`/`is_super_admin` are for the finer-grained
        checks that actually need to tell the two apart."""
        return self.role != UserRole.USER

    @property
    def is_super_admin(self) -> bool:
        return self.role == UserRole.SUPER_ADMIN

    balance: float = Field(
        default=0.0,
        sa_column=Column(Numeric(10, 2, asdecimal=False), nullable=False)
    )

    credit_limit: float = Field(
        default=0.0,
        sa_column=Column(Numeric(10, 2, asdecimal=False), nullable=False)
    )

    email_to_set: bool = Field(default=False)

    has_seen_tutorial: bool = Field(default=False)

    created_at: datetime = Field(
        default_factory=generate_time, 
        nullable=False
    )

    updated_at: datetime = Field(
        default_factory=generate_time, 
        nullable=False,
        sa_column_kwargs={
            "onupdate": generate_time
        }
    )
