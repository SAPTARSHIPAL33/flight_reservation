from typing import Union
from fastapi import Depends, APIRouter, status, HTTPException, Body
from sqlalchemy.orm import Session
from .. import schemas, database, model, oauth
from ..waitinglist import priority_queue, allocate_waiting_seat_min_heap


router = APIRouter(tags=["BOOKINGS"])


@router.post("/book", status_code=status.HTTP_201_CREATED, response_model=list[schemas.BookingResponse])
def book_flight(
    booking: Union[schemas.BookingCreate, list[int]] = Body(...),
    ticket_count: int = 1,
    db: Session = Depends(database.get_db),
    current_user: model.User = Depends(oauth.get_the_user),
):
    """
    Process single or multi-leg flight bookings in a single transaction.
    Accepts:
      - {"flight_ids": [101, 204]}
      - {"flight_id": 101}
      - [101, 204]
    """
    if isinstance(booking, list):
        flight_ids = booking
    elif booking.flight_ids is not None:
        flight_ids = booking.flight_ids
    elif booking.flight_id is not None:
        flight_ids = [booking.flight_id]
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="flight_ids array or flight_id is required",
        )

    if not flight_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="flight_ids list cannot be empty",
        )

    # 1. Verify all flights exist (atomic check before making any changes)
    flights = []
    for fid in flight_ids:
        flight = db.query(model.Flight).filter(model.Flight.flight_id == fid).first()
        if not flight:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Flight with ID {fid} not found",
            )
        flights.append(flight)

    # 2. Process all legs in a single database transaction
    bookings = []
    for _ in range(ticket_count):
        for flight in flights:
            if flight.seats_available > 0:
                flight.seats_available -= 1
                ticket_status = "confirmed"
            else:
                ticket_status = "waiting_list"

            new_booking = model.Booking(
                flight_id=flight.flight_id,
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

    was_confirmed = (booking.status == "confirmed")
    booking.status = "cancelled"

    # Allocate freed seat to waiting-list passenger using Min-Heap priority queue
    if was_confirmed:
        allocate_waiting_seat_min_heap(booking.flight_id, db)

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
