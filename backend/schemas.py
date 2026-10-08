from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


# ─── User Schemas ───

class createUser(BaseModel):
    name:str
    email:EmailStr
    password:str
    mob_no:Optional[str]=None

class UserResponse(BaseModel):
    id:int
    name:str
    email:str
    mob_no:Optional[str]=None
    role:str

    class Config:
        from_attributes = True

class createLogin(BaseModel):
    email:EmailStr
    password:str


# ─── Auth Schemas ───

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    id:Optional[int]=0


# ─── Search Schemas ───

class SearchModule(BaseModel):
    source:str
    destination:str


# ─── Airport Schemas ───

class AirportCreate(BaseModel):
    name:str
    place:str
    latitude:float
    longitude:float

class AirportResponse(BaseModel):
    id:int
    name:str
    place:str
    latitude:float
    longitude:float

    class Config:
        from_attributes = True


# ─── Flight Schemas ───

class FlightCreate(BaseModel):
    source:str
    destination:str
    distance:float
    departure_time:datetime
    arrival_time:datetime
    price:float
    seats_available:int

class FlightUpdate(BaseModel):
    source:Optional[str]=None
    destination:Optional[str]=None
    departure_time:Optional[datetime]=None
    arrival_time:Optional[datetime]=None
    price:Optional[float]=None
    seats_available:Optional[int]=None

class FlightResponse(BaseModel):
    flight_id:int
    source:str
    destination:str
    departure_time:datetime
    arrival_time:datetime
    price:float
    seats_available:int

    class Config:
        from_attributes = True


# ─── Booking Schemas ───

class BookingCreate(BaseModel):
    flight_id:int

class BookingResponse(BaseModel):
    booking_id:int
    flight_id:int
    passenger_id:int
    status:str

    class Config:
        from_attributes = True
