from ldap3 import Server, Connection, ALL, core
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


    def _authenticate_with_ldap(self, username: str, pwd: str):
        ad_user = f'{username}@{self.domain}' 
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
        
    def _search_user_in_ldap(self, conn: Connection, username: str):
        search_filter = f'(sAMAccountName={username})' 
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

        return user