from fastapi import APIRouter, Request, status, BackgroundTasks
from fastapi import HTTPException

from ...core.limiter import limiter
from ...core.config import settings

from .settings import AD_CONFIG_KEY

from ..dependencies.database import SessionDep

from ...schemas.user import UserCreate, UserRead, UserLogin, UserEmailRequest, UserBase, UserPwdReset
from ...schemas.token import AccessTokenResponse

from ...db.crud.user import UserService
from ...db.crud.app_config import AppConfigService

from ...core.security import Security
from ...core.mail_assistant import send_reset_email
from ...core.ldap_assistant import LDAPAssistant


user_service = UserService()
config_service = AppConfigService()  
ldap_assistant = LDAPAssistant()

router = APIRouter()


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=UserRead
)
def register(
    user: UserCreate,
    session: SessionDep,
):
    
    email = user.email
    email_exists = user_service.email_exists(email, session) if email else True
    if email_exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already exists"
        )
    
    username = user.username
    username_exists = user_service.username_exists(username, session)
    if username_exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists"
        )
    
    user.pwd = Security.hash_password(user.pwd)
    new_user = user_service.create_user(user, session)

    return new_user


@router.post(
    "/login",
    status_code=status.HTTP_200_OK,
    response_model=AccessTokenResponse
)
@limiter.limit(settings.LOGIN_RATE_LIMIT)
def login(
    request: Request,
    user: UserLogin,
    session: SessionDep
):
    
    valid = False

    username = user.username
    pwd = user.pwd

    user_db = user_service.get_user_by_username(username, session)
    if user_db is not None:
        valid = Security.verify_password(plain_pwd=pwd, hashed_pwd=user_db.pwd)

    if valid:
        payload = {"uid": str(user_db.id)}  # type: ignore
        token = Security.create_token(data=payload)

        return AccessTokenResponse(token=token)

    # VERIFY WITH ACTIVE DIRECTORY IF ENABLED
    ad_config = config_service.get(AD_CONFIG_KEY, session)
    if ad_config and ad_config.get("enabled", False):
        server = ad_config.get("server")
        base_dn = ad_config.get("base_dn")
        domain = ad_config.get("domain")

        ldap_assistant.configure(server, domain, base_dn)
        ldap_user = ldap_assistant.login_user(username, pwd, session)
        if ldap_user:
            payload = {"uid": str(ldap_user.id)}  # type: ignore
            token = Security.create_token(data=payload)

            return AccessTokenResponse(token=token)

    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Username or password incorrect"
    )


@router.post(
    "/pwd-reset-request",
    status_code=status.HTTP_200_OK
)
def password_reset_request(
    email: UserEmailRequest,
    session: SessionDep,
    background_tasks: BackgroundTasks
):
    
    user_db = user_service.get_user_by_email(email.email, session)
    if user_db is None:
        return {"detail": "Password reset email sent"}  # Avoid user enumeration
    
    token = Security.generate_pwd_reset_token(user_db.email)

    background_tasks.add_task(
        send_reset_email,
        user=UserBase(
            **user_db.model_dump()
        ),
        token=token
    )

    return {"detail": "Password reset email sent"}


@router.post(
    "/pwd-reset/{token}",
    status_code=status.HTTP_200_OK
)
def password_reset(
    token: str,
    new_pwd: UserPwdReset,
    session: SessionDep
):
    email = Security.verify_pwd_reset_token(token)
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired token"
        )

    user_db = user_service.get_user_by_email(email, session)
    if user_db is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    hashed_pwd = Security.hash_password(new_pwd.new_pwd)
    user_service.change_password(str(user_db.id), hashed_pwd, session)

    return {"detail": "Password updated successfully"}
