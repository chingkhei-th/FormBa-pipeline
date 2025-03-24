from passlib.context import CryptContext
from datetime import datetime, timedelta
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app import models
from app.database import get_db, SessionLocal
from dotenv import load_dotenv
import os
import requests

load_dotenv()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

SECRET_KEY = os.getenv("SECRET_KEY")
ACCESS_TOKEN_EXPIRE_MINUTES = 30
ALGORITHM = os.getenv("ENCRYPTION_ALGORITHM")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = (
        db.query(models.ReviewUser)
        .filter(models.ReviewUser.username == username)
        .first()
    )
    if user is None:
        raise credentials_exception
    return user


# Optional: Function to handle S3 URLs if you want to proxy through backend
async def get_s3_image(url: str):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.content
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Error fetching image: {str(e)}",
        )


# For formba
def get_current_admin(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
):
    """
    Decodes the JWT token and ensures the token belongs to an admin.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        token_type: str = payload.get("type")
        if username is None or token_type != "admin":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token or insufficient privileges",
                headers={"WWW-Authenticate": "Bearer"},
            )
        admin = db.query(models.Admin).filter(models.Admin.username == username).first()
        if not admin:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return admin
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def authenticate_user(username: str, password: str, db: Session):
    user = db.query(models.Users).filter(models.Users.email == username).first()
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user
