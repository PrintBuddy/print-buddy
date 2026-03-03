from sqlmodel import SQLModel, Field
from datetime import datetime

from ...core.utils import generate_time


class AppConfig(SQLModel, table=True):
    """Generic key-value config store. Values are JSON strings."""
    key: str = Field(primary_key=True)
    value: str  # JSON-encoded string
    updated_at: datetime = Field(default_factory=generate_time, nullable=False)
