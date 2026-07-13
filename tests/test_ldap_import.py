from sqlmodel import Session, SQLModel, create_engine, select

from src.core.ldap_assistant import LDAPAssistant
from src.core.security import Security
from src.db.models.user import User


class TestLDAPImport:
    def setup_method(self):
        self.engine = create_engine("sqlite://")
        SQLModel.metadata.create_all(self.engine)

    def teardown_method(self):
        SQLModel.metadata.drop_all(self.engine)

    def test_import_only_creates_missing_users(self):
        assistant = LDAPAssistant()
        directory_users = [
            {"username": "existing.user", "first_name": "Existing", "last_name": "User"},
            {"username": "new.user", "first_name": "New", "last_name": "User"},
            {"username": "PALESTRA-PC$", "first_name": "Gym", "last_name": "Pc"},
        ]

        class FakeConn:
            def unbind(self):
                return None

        assistant._connect_for_directory_search = lambda username, pwd: FakeConn()
        assistant._search_all_users_in_ldap = lambda conn: directory_users

        with Session(self.engine) as session:
            assistant._get_or_create_user_in_db(
                "existing.user",
                "secret",
                {"first_name": "Existing", "last_name": "User"},
                session
            )

            preview = assistant.preview_import_users("admin.user", "secret", session)
            result = assistant.import_users("admin.user", "secret", session)
            users = session.exec(select(User).order_by(User.username)).all()

        assert preview == {
            "total_found": 3,
            "importable_count": 1,
            "skipped_count": 2,
            "skipped_invalid_count": 1,
            "candidates": [
                {"username": "new.user", "name": "New", "surname": "User"}
            ],
            "detail": "Found 1 AD user(s) ready to import. Skipped 2 existing or non-importable entry(ies), including 1 invalid AD username(s)."
        }
        assert result == {
            "total_found": 3,
            "imported_count": 1,
            "skipped_count": 2,
            "skipped_invalid_count": 1,
            "detail": "Imported 1 new AD user(s). Skipped 2 existing or non-importable entry(ies), including 1 invalid AD username(s)."
        }
        assert len(users) == 2
        assert users[0].username == "existing.user"
        assert users[0].pwd != ""
        assert users[0].email_to_set is True
        assert users[1].username == "new.user"
        assert users[1].pwd == ""
        assert users[1].email_to_set is True

    def test_first_ad_login_backfills_missing_password(self):
        assistant = LDAPAssistant()

        with Session(self.engine) as session:
            imported_user = User(
                email=None,
                username="new.user",
                pwd="",
                name="New",
                surname="User",
                email_to_set=True
            )
            session.add(imported_user)
            session.commit()

            user = assistant._get_or_create_user_in_db(
                "new.user",
                "real-password",
                {"first_name": "New", "last_name": "User"},
                session
            )
            pwd = user.pwd

        assert pwd != ""
        assert Security.verify_password("real-password", pwd)
