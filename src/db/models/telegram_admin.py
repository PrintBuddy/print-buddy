from sqlmodel import SQLModel, Field
from datetime import datetime
import uuid

from ...core.utils import generate_time


class TelegramAdmin(SQLModel, table=True):
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True
    )

    user_id: uuid.UUID = Field(
        foreign_key="user.id",
        ondelete="CASCADE"
    )

    telegram_id: str = Field(
        nullable=False
    )

    # Payment contact info shown to users on the "who do I pay" list —
    # every admin accepts cash (phone_number), transfer is opt-in per
    # admin since not everyone wants to share bank details.
    phone_number: str | None = Field(default=None, nullable=True)
    accepts_transfer: bool = Field(default=False, nullable=False)
    bank_name: str | None = Field(default=None, nullable=True)
    bank_iban: str | None = Field(default=None, nullable=True)
    bank_link: str | None = Field(default=None, nullable=True)

    created_at: datetime = Field(
        nullable=False,
        default_factory=generate_time
    )
