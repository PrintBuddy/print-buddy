from bcrypt import hashpw, gensalt, checkpw
from datetime import timedelta
from jose import jwt, JWTError
from itsdangerous import URLSafeTimedSerializer
import uuid

from .utils import generate_time
from .config import settings
from .logger import logger


class Security:

    serializer = URLSafeTimedSerializer(settings.SECRET_KEY)
    
    @classmethod
    def hash_password(cls, password: str) -> str:
        """
        A class method to hash a password. Returns the hashed password
        """
        return hashpw(password.encode(), gensalt()).decode()
    
    @classmethod
    def verify_password(cls, plain_pwd: str, hashed_pwd: str) -> bool:
        """
        Verifies if the plain password coincides with the hashed password.
        Returns True or False
        """
        try:
            if not hashed_pwd:
                return False
            return checkpw(plain_pwd.encode(), hashed_pwd.encode())
        except (ValueError, TypeError):
            logger.warning("Stored password hash is missing or invalid")
            return False
    
    @classmethod
    def create_token(cls, data: dict) -> str:
        """
        Creates a JWT token.
        """
        delta = timedelta(minutes=settings.ACCESS_TOKEN_EXP_MIN)
        exp_time = generate_time() + delta

        to_encode = data.copy()

        payload = {
            "exp": exp_time,
            "jti": str(uuid.uuid4())
        }

        to_encode.update(payload)

        token = jwt.encode(
            claims=to_encode,
            key=settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )

        return token
    
    @classmethod
    def decode_token(cls, token: str) -> dict | None:
        """
        Decodes a JWT token
        """
        try:
            payload = jwt.decode(
                token=token,
                key=settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )

            if "uid" not in payload:
                logger.warning("Token payload is missing the 'uid' claim")
                return None

            return payload

        except JWTError as e:
            logger.warning("Received an invalid or expired token")
            return None
        
    @classmethod
    def generate_pwd_reset_token(cls, email: str) -> str:
        """
        Generates a password reset token
        """
        return cls.serializer.dumps(email, salt=settings.PWD_RESET_SALT)

    @classmethod
    def verify_pwd_reset_token(cls, token: str, expiration: int = settings.PWD_RESET_TIME_MIN * 60) -> str | None:
        """
        Verifies a password reset token
        """
        try:
            email = cls.serializer.loads(
                token,
                salt=settings.PWD_RESET_SALT,
                max_age=expiration
            )
            return email
        except Exception as e:
            logger.warning("Invalid or expired password reset token")
            return None
