from datetime import datetime
from sqlmodel import SQLModel, Field
from pydantic import EmailStr
import uuid

from ...core.utils import generate_time


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

    is_admin: bool = Field(default=False)

    balance: float = Field(nullable=False, default=0.0)

    credit_limit: float = Field(nullable=False, default=0.0)

    email_to_set: bool = Field(default=False)

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
