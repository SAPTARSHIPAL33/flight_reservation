from fastapi import Depends, APIRouter, status, HTTPException
from sqlalchemy.orm import Session
from .. import schemas, database, model, oauth


router = APIRouter(tags=["BOOKINGS"])


@router.post("/book", status_code=status.HTTP_201_CREATED, response_model=list[schemas.BookingResponse])
def book_flight(
    booking: schemas.BookingCreate,
    ticket_count: int = 1,
    db: Session = Depends(database.get_db),
    current_user: model.User = Depends(oauth.get_the_user),
):
    # Verify the flight exists
    flight = db.query(model.Flight).filter(model.Flight.flight_id == booking.flight_id).first()
    if not flight:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flight not found")

    bookings = []
    for _ in range(ticket_count):
        if flight.seats_available > 0:
            flight.seats_available -= 1
            ticket_status = "confirmed"
        else:
            ticket_status = "waiting_list"

        new_booking = model.Booking(
            flight_id=booking.flight_id,
            passenger_id=current_user.id,
            status=ticket_status,
        )
        db.add(new_booking)
        bookings.append(new_booking)

    db.commit()
    for ticket in bookings:
        db.refresh(ticket)
    return bookings


@router.put("/cancel/{booking_id}", status_code=status.HTTP_200_OK, response_model=schemas.BookingResponse)
def cancel_booking(
    booking_id: int,
    db: Session = Depends(database.get_db),
    current_user: model.User = Depends(oauth.get_the_user),
):
    # Only the owner can cancel their own booking
    booking = db.query(model.Booking).filter(
        model.Booking.booking_id == booking_id,
        model.Booking.passenger_id == current_user.id,
    ).first()

    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    if booking.status == "cancelled":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Booking is already cancelled")

    booking.status = "cancelled"

    flight = db.query(model.Flight).filter(model.Flight.flight_id == booking.flight_id).first()

    # Promote the earliest waiting-list passenger (priority = oldest created_at)
    next_in_line = (
        db.query(model.Booking)
        .filter(
            model.Booking.flight_id == booking.flight_id,
            model.Booking.status == "waiting_list",
        )
        .order_by(model.Booking.created_at.asc())
        .first()
    )

    if next_in_line:
        # A waiting passenger gets the freed seat — no net change to seats_available
        next_in_line.status = "confirmed"
    else:
        # No one waiting; seat goes back to the pool
        flight.seats_available += 1

    db.commit()
    db.refresh(booking)
    return booking


@router.get("/my-bookings", status_code=status.HTTP_200_OK, response_model=list[schemas.BookingResponse])
def get_my_bookings(
    db: Session = Depends(database.get_db),
    current_user: model.User = Depends(oauth.get_the_user),
):
    bookings = db.query(model.Booking).filter(
        model.Booking.passenger_id == current_user.id
    ).all()
    return bookings
