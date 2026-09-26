from pydantic import BaseModel, EmailStr
from typing import Optional

class createUser(BaseModel):
    email:EmailStr
    password:str

class createLogin(BaseModel):
    email:EmailStr
    password:str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    id:Optional[int]=0

class SearchModule(BaseModel):
    source:str
    destination:str
