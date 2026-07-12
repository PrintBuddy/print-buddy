from ldap3 import Server, Connection, ALL, core
from ldap3.utils.conv import escape_filter_chars
from pydantic import ValidationError
from sqlmodel import Session

from ..db.crud.user import UserService

from ..schemas.user import UserCreate

from .logger import logger
from .security import Security


user_service = UserService()


class LDAPAssistant:
    def __init__(self):
        self.server_url: str = ""
        self.domain: str = ""
        self.base_dn: str = ""

    def configure(self, server_url, domain, base_dn):
        self.server_url = server_url
        self.domain = domain
        self.base_dn = base_dn
        logger.info(f"LDAP Assistant configured with server URL: {self.server_url}")

    def login_user(self, username: str, pwd: str, session: Session):
        
        # 1. Try to authenticate with LDAP
        conn = self._authenticate_with_ldap(username, pwd)
        if not conn:
            logger.warning(f"LDAP authentication failed for user '{username}'. Login aborted.")
            return None
        
        # 2. If successful, search for the user details in LDAP
        user_details = self._search_user_in_ldap(conn, username)
        if not user_details:
            logger.warning(f"User '{username}' authenticated with LDAP but user details not found. Login aborted.")
            conn.unbind()
            return None

        # 3. If user details found, check if user exists in our DB. If not, create it.
        user = self._get_or_create_user_in_db(username, pwd, user_details, session)
        conn.unbind()
        # 4. Return the user details (from our DB) or raise an exception if any step fails
        return user

    def import_users(self, username: str, pwd: str, session: Session):
        preview = self.preview_import_users(username, pwd, session)
        if preview is None:
            return None

        imported_count = 0
        existing_usernames = user_service.get_usernames(session)
        for candidate in preview["candidates"]:
            candidate_username = candidate["username"]
            if candidate_username.casefold() in existing_usernames:
                continue

            user_data = UserCreate(
                username=candidate_username,
                pwd="",
                name=candidate.get("name", ""),
                surname=candidate.get("surname", ""),
                email_to_set=True
            )
            user_service.create_user(user_data, session)
            existing_usernames.add(candidate_username.casefold())
            imported_count += 1

        return {
            "total_found": preview["total_found"],
            "imported_count": imported_count,
            "skipped_count": preview["total_found"] - imported_count,
            "skipped_invalid_count": preview["skipped_invalid_count"],
            "detail": (
                f"Imported {imported_count} new AD user(s). "
                f"Skipped {preview['total_found'] - imported_count} existing or non-importable entry(ies), "
                f"including {preview['skipped_invalid_count']} invalid AD username(s)."
            )
        }

    def preview_import_users(self, username: str, pwd: str, session: Session):
        conn = self._connect_for_directory_search(username, pwd)
        if not conn:
            logger.warning("LDAP directory search connection could not be established.")
            return None

        try:
            directory_users = self._search_all_users_in_ldap(conn)
            if directory_users is None:
                return None

            existing_usernames = user_service.get_usernames(session)
            candidates = []
            skipped_invalid_count = 0

            for directory_user in directory_users:
                username_value = directory_user["username"]
                if self._should_skip_directory_username(username_value):
                    skipped_invalid_count += 1
                    logger.info(f"Skipping non-importable LDAP account '{username_value}'")
                    continue

                if username_value.casefold() in existing_usernames:
                    continue

                try:
                    user_data = UserCreate(
                        username=username_value,
                        pwd="",
                        name=directory_user.get("first_name", ""),
                        surname=directory_user.get("last_name", ""),
                        email_to_set=True
                    )
                except ValidationError as exc:
                    skipped_invalid_count += 1
                    logger.warning(f"Skipping LDAP entry with invalid username '{username_value}': {exc}")
                    continue

                candidates.append({
                    "username": user_data.username,
                    "name": user_data.name,
                    "surname": user_data.surname,
                })

            total_found = len(directory_users)
            importable_count = len(candidates)
            skipped_count = total_found - importable_count
            return {
                "total_found": total_found,
                "importable_count": importable_count,
                "skipped_count": skipped_count,
                "skipped_invalid_count": skipped_invalid_count,
                "candidates": candidates,
                "detail": (
                    f"Found {importable_count} AD user(s) ready to import. "
                    f"Skipped {skipped_count} existing or non-importable entry(ies), "
                    f"including {skipped_invalid_count} invalid AD username(s)."
                )
            }
        finally:
            conn.unbind()


    def _authenticate_with_ldap(self, username: str, pwd: str):
        ad_user = f'{escape_filter_chars(username)}@{self.domain}'
        try:
            server = Server(self.server_url, get_info=ALL)
            conn = Connection(server, user=ad_user, password=pwd, auto_bind=True)
            logger.info(f"LDAP authentication successful for user '{username}'")
            return conn
        except core.exceptions.LDAPBindError as e:  # type: ignore
            logger.warning(f"LDAP authentication failed for user '{username}': {e}")
            return None
        except Exception as e:
            logger.error(f"An error occurred during LDAP authentication for user '{username}': {e}")
            return None

    def _connect_for_directory_search(self, username: str, pwd: str):
        conn = self._authenticate_with_ldap(username, pwd)
        if conn:
            logger.info(f"LDAP directory search connection established for user '{username}'")
        return conn
        
    def _search_user_in_ldap(self, conn: Connection, username: str):
        search_filter = f'(sAMAccountName={escape_filter_chars(username)})'
        attributes_to_fetch = ['givenName', 'sn']

        logger.info(f"Searching for user '{username}' details in LDAP...")
        conn.search(
            search_base=self.base_dn,
            search_filter=search_filter,
            attributes=attributes_to_fetch
        )

        if len(conn.entries) > 0:
            user_entry = conn.entries[0]
            user_details = {
                "first_name": user_entry.givenName.value,
                "last_name": user_entry.sn.value
            }
            logger.info(f"User '{username}' details found in LDAP: {user_details}")
            return user_details
        else:
            logger.warning(f"User '{username}' authenticated successfully but not found in LDAP search.")
            return None

    def _search_all_users_in_ldap(self, conn: Connection):
        attributes_to_fetch = ['sAMAccountName', 'givenName', 'sn']
        search_filter = '(&(objectClass=user)(sAMAccountName=*))'

        logger.info("Searching LDAP for importable users...")
        conn.search(
            search_base=self.base_dn,
            search_filter=search_filter,
            attributes=attributes_to_fetch
        )

        users = []
        for user_entry in conn.entries:
            username = getattr(user_entry, "sAMAccountName", None)
            username_value = username.value if username is not None else None
            if not username_value:
                continue

            given_name = getattr(user_entry, "givenName", None)
            surname = getattr(user_entry, "sn", None)

            users.append({
                "username": username_value,
                "first_name": given_name.value if given_name is not None and given_name.value else "",
                "last_name": surname.value if surname is not None and surname.value else ""
            })

        logger.info(f"LDAP search found {len(users)} importable users")
        return users

    def _should_skip_directory_username(self, username: str) -> bool:
        username = username.strip()
        return not username or username.endswith("$")
        
    def _get_or_create_user_in_db(self, username: str, pwd: str, user_details: dict, session: Session):
        user = user_service.get_user_by_username(username, session)
        if not user:
        
            logger.info(f"User '{username}' not found in DB. Creating new user with details: {user_details}")
            user_data = UserCreate(
                username=username,
                pwd=Security.hash_password(pwd), 
                name=user_details.get("first_name", ""),
                surname=user_details.get("last_name", ""),
                email_to_set=True
            )
            user = user_service.create_user(user_data, session)
            logger.info(f"User '{username}' created in DB with ID: {user.id}")

        else:
            logger.info(f"User '{username}' already exists in DB with ID: {user.id}")
            if pwd and not user.pwd:
                user_service.change_password(str(user.id), Security.hash_password(pwd), session)
                logger.info(f"Local password stored for imported LDAP user '{username}'")

        return user
