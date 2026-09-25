from pydantic import BaseModel, EmailStr
from typing import Optional
class createUser(BaseModel):
    email:EmailStr
    password:str

class createLogin(BaseModel):
    email:EmailStr
    password:str

class TokenData(BaseModel):
    id:Optional[int]=0