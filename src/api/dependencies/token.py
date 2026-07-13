from fastapi.security import HTTPBearer
from fastapi import status, HTTPException
from fastapi.security.http import HTTPAuthorizationCredentials
from fastapi import Request, Depends
from typing import Annotated

from sqlmodel import Session
from ...db.main import engine
from ...core.security import Security
from ...db.crud.user import UserService 


user_service = UserService()

class TokenBearer(HTTPBearer):

    def __init__(self, auto_error: bool = True):
        super().__init__(auto_error=auto_error)

    async def __call__(self, request: Request) -> HTTPAuthorizationCredentials | None:
        creds = await super().__call__(request)

        token = Security.decode_token(creds.credentials) if creds else None

        if token is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized access"
            )

        uid = token.get("uid")
        if uid is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized access"
            )

        if creds is not None:
            return HTTPAuthorizationCredentials(
                scheme=creds.scheme,
                credentials=uid
            )
    

class AdminTokenBearer(TokenBearer):

    def __init__(self, auto_error: bool = True):
        super().__init__(auto_error=auto_error)

    async def __call__(self, request: Request) -> HTTPAuthorizationCredentials | None:
        creds = await super().__call__(request)
        if creds is None:
            return creds

        user_id = creds.credentials

        with Session(engine) as session:
            is_admin = user_service.user_is_admin(user_id, session)
            if not is_admin:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User not authorized AAAAA"
                )
            
        return creds


TokenDep = Annotated[
    HTTPAuthorizationCredentials, Depends(TokenBearer())
]

AdminTokenDep = Annotated[
    HTTPAuthorizationCredentials, Depends(AdminTokenBearer())
]
