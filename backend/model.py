from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base 
from pydantic import EmailStr

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(EmailStr, unique=True, index=True, nullable=False)
    mob_no = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="passenger") 
    bookings = relationship("Booking", back_populates="passenger")


class Airport(Base):
    __tablename__ = "airports"  # Replaces your 'airport location' table

    id = Column(Integer, primary_key=True, index=True)
    place = Column(String, unique=True, index=True, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)


class Flight(Base):
    __tablename__ = "flights"
    flight_id = Column(Integer, primary_key=True, index=True)
    source = Column(String, nullable=False) 
    destination = Column(String, nullable=False)
    depart_time = Column(DateTime, nullable=False)
    arrival_time = Column(DateTime, nullable=False)
    price = Column(Float, nullable=False)
    seats_available = Column(Integer, nullable=False)


class Booking(Base):
    __tablename__ = "bookings"
    booking_id = Column(Integer, primary_key=True, index=True)
    flight_id = Column(Integer, ForeignKey("flights.flight_id"), nullable=False)
    passenger_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String, default="confirmed") 
    flight = relationship("Flight", back_populates="bookings")
    passenger = relationship("User", back_populates="bookings")