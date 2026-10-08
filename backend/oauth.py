#for access token

from jose import JWTError, jwt
from datetime import datetime, timedelta
from . import schemas,database,model
from fastapi import Depends, status,HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from .config import settings

oauth2_scheme= OAuth2PasswordBearer(tokenUrl="login")
SECRET_KEY = settings.secret_key
ALGORITHM = settings.algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes
#header is created by the algorithm itself
#payload is the data passed
#signature=secret key + algorithm
#token = header + payload = signature

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_data = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_data

def verify_access_token(token:str, credentials_exception):
    try:
        payload=jwt.decode(token,SECRET_KEY,algorithms=[ALGORITHM])
        id:int=payload.get("user_id")
        if id is None:
            raise credentials_exception
        token_data = schemas.TokenData(id=id)
    except JWTError:
        raise credentials_exception
    return token_data

def get_the_user(token:str=Depends(oauth2_scheme),db:Session=Depends(database.get_db)):
    credentials_exception= HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials", headers={"WWW-Authenticate":"Bearer"})
    info=verify_access_token(token,credentials_exception )
    user = db.query(model.User).filter(model.User.id==info.id).first()
    return user

def require_role(required_role: str):
    """Dependency factory: returns a dependency that enforces a specific role."""
    def role_checker(current_user = Depends(get_the_user)):
        if current_user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. '{required_role}' role required."
            )
        return current_user
    return role_checker