import json
from sqlmodel import Session

from ..models.app_config import AppConfig
from ...core.utils import generate_time


class AppConfigService:

    def get(self, key: str, session: Session):
        """Return the parsed value for a key, or None if not found."""
        row = session.get(AppConfig, key)
        if row is None:
            return None
        return json.loads(row.value)

    def set(self, key: str, value, session: Session) -> AppConfig:
        """Insert or update a config key with a JSON-serialisable value."""
        row = session.get(AppConfig, key)
        if row is None:
            row = AppConfig(key=key, value=json.dumps(value))
            session.add(row)
        else:
            row.value = json.dumps(value)
            row.updated_at = generate_time()
        session.commit()
        session.refresh(row)
        return row
