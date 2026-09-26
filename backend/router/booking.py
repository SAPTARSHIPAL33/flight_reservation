from fastapi import Depends, APIRouter, status, HTTPException
from sqlalchemy.orm import Session
from .. import schemas, database, model, oauth


router = APIRouter(tags=["BOOKINGS"])


@router.post("/book", status_code=status.HTTP_201_CREATED, response_model=schemas.BookingResponse)
def book_flight(booking: schemas.BookingCreate, db: Session = Depends(database.get_db),
                current_user: model.User = Depends(oauth.get_the_user)):
    # Verify the flight exists
    flight = db.query(model.Flight).filter(model.Flight.flight_id == booking.flight_id).first()
    if not flight:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flight not found")

    # Check seat availability
    if flight.seats_available <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No seats available on this flight")

    # Prevent duplicate active bookings on the same flight
    existing = db.query(model.Booking).filter(
        model.Booking.flight_id == booking.flight_id,
        model.Booking.passenger_id == current_user.id,
        model.Booking.status == "confirmed"
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="You already have an active booking on this flight")

    # Decrement seats and create the booking
    flight.seats_available -= 1
    new_booking = model.Booking(flight_id=booking.flight_id, passenger_id=current_user.id)
    db.add(new_booking)
    db.commit()
    db.refresh(new_booking)
    return new_booking


@router.put("/cancel/{booking_id}", status_code=status.HTTP_200_OK, response_model=schemas.BookingResponse)
def cancel_booking(booking_id: int, db: Session = Depends(database.get_db),
                   current_user: model.User = Depends(oauth.get_the_user)):
    # Only the owner can cancel their own booking
    booking = db.query(model.Booking).filter(
        model.Booking.booking_id == booking_id,
        model.Booking.passenger_id == current_user.id
    ).first()

    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    if booking.status == "cancelled":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Booking is already cancelled")

    # Cancel and restore the seat
    booking.status = "cancelled"
    flight = db.query(model.Flight).filter(model.Flight.flight_id == booking.flight_id).first()
    flight.seats_available += 1
    db.commit()
    db.refresh(booking)
    return booking


@router.get("/my-bookings", status_code=status.HTTP_200_OK, response_model=list[schemas.BookingResponse])
def get_my_bookings(db: Session = Depends(database.get_db),
                    current_user: model.User = Depends(oauth.get_the_user)):
    bookings = db.query(model.Booking).filter(
        model.Booking.passenger_id == current_user.id
    ).all()
    return bookings
