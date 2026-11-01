from collections import defaultdict
from datetime import datetime
from typing import List, Optional, Union
import re

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import database, model, oauth, schemas
from ..waitinglist import (
    allocate_waiting_seat_min_heap,
    get_booking_waitlist_position,
    get_flight_waitlist_length,
    get_waitlist_ranks_for_flight,
)

router = APIRouter(tags=["BOOKINGS"])


def format_pnr(booking_id: int) -> str:
    """Format an integer booking_id as a human-friendly PNR code (e.g. 'PNR-10025')."""
    return f"PNR-{booking_id:05d}"


def parse_booking_id(ref: str) -> Optional[int]:
    """Extract integer booking_id from various input shapes: 'PNR-00025', 'PNR25', '#25', or '25'."""
    if not ref:
        return None
    cleaned = str(ref).strip().upper()
    digits = re.findall(r"\d+", cleaned)
    if digits:
        try:
            return int(digits[0])
        except ValueError:
            return None
    return None


@router.post("/book", status_code=status.HTTP_201_CREATED, response_model=List[schemas.BookingResponse])
def book_flight(
    booking: Union[schemas.BookingCreate, List[int], dict] = Body(...),
    ticket_count: int = 1,
    db: Session = Depends(database.get_db),
    current_user: model.User = Depends(oauth.get_the_user),
):
    """
    Process single or multi-leg flight bookings in a single transaction.
    Uses existing 'booking_id' as the unique identifier without requiring any schema changes.
    Accepts:
      - {"flight_ids": [101, 204]}
      - {"flight_id": 101}
      - [101, 204]
    """
    # 1. Extract flight_ids from various input shapes
    if isinstance(booking, list):
        flight_ids = booking
    elif isinstance(booking, dict):
        if booking.get("flight_ids"):
            flight_ids = booking["flight_ids"]
        elif booking.get("flight_id"):
            flight_ids = [booking["flight_id"]]
        else:
            flight_ids = []
    elif hasattr(booking, "flight_ids") and booking.flight_ids is not None:
        flight_ids = booking.flight_ids
    elif hasattr(booking, "flight_id") and booking.flight_id is not None:
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

    # 2. Verify all flights exist in database
    flights = []
    for fid in flight_ids:
        flight = db.query(model.Flight).filter(model.Flight.flight_id == fid).first()
        if not flight:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Flight with ID {fid} not found",
            )
        flights.append(flight)

    # 3. Insert bookings using standard database columns: booking_id, flight_id, passenger_id, status, created_at
    tx_time = datetime.now()
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
                created_at=tx_time,
            )
            db.add(new_booking)
            bookings.append(new_booking)

    db.commit()

    # Build response using existing booking_id and assigned waitlist positions
    response_items = []
    for ticket in bookings:
        db.refresh(ticket)
        wl_pos = None
        if (ticket.status or "").lower() in ["waiting_list", "pending"]:
            wl_pos = get_booking_waitlist_position(ticket.flight_id, ticket.booking_id, db)

        response_items.append(
            schemas.BookingResponse(
                booking_id=ticket.booking_id,
                flight_id=ticket.flight_id,
                passenger_id=ticket.passenger_id,
                status=ticket.status,
                pnr=format_pnr(ticket.booking_id),
                created_at=ticket.created_at,
                waitlist_position=wl_pos,
            )
        )

    return response_items


@router.delete("/bookings/{booking_ref}", status_code=status.HTTP_200_OK)
def cancel_journey(
    booking_ref: str,
    db: Session = Depends(database.get_db),
    current_user: model.User = Depends(oauth.get_the_user),
):
    """
    Cancel a journey identified by booking_id (e.g. '25' or 'PNR-00025').
    If the journey has multiple legs booked together (same created_at transaction), cancels all companion legs.
    Crucial Waitlist Logic:
    - Increments seats_available for all associated flights.
    - Checks Min-Heap priority queue on each flight and promotes highest priority waitlisted passenger.
    """
    bid = parse_booking_id(booking_ref)
    if bid is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid booking identifier: {booking_ref}",
        )

    # Find the target booking belonging to the current user
    target_booking = (
        db.query(model.Booking)
        .filter(
            model.Booking.booking_id == bid,
            model.Booking.passenger_id == current_user.id,
        )
        .first()
    )

    if not target_booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Booking #{bid} not found for current passenger",
        )

    # Find companion legs created in the same transaction timestamp
    companion_bookings = (
        db.query(model.Booking)
        .filter(
            model.Booking.passenger_id == current_user.id,
            model.Booking.created_at == target_booking.created_at,
        )
        .all()
    )
    if not companion_bookings:
        companion_bookings = [target_booking]

    if all(b.status.lower() == "cancelled" for b in companion_bookings):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Booking #{bid} has already been cancelled",
        )

    promoted_passengers = []

    for b in companion_bookings:
        if b.status.lower() == "cancelled":
            continue

        was_confirmed = (b.status.lower() == "confirmed")
        b.status = "cancelled"

        if was_confirmed:
            flight = db.query(model.Flight).filter(model.Flight.flight_id == b.flight_id).first()
            if flight:
                # 1. Restore seat
                flight.seats_available += 1

                # 2. Allocate newly freed seat to highest-priority waitlisted passenger via Min-Heap
                promoted = allocate_waiting_seat_min_heap(b.flight_id, db)
                if promoted:
                    promoted_passengers.append({
                        "flight_id": b.flight_id,
                        "promoted_booking_id": promoted.booking_id,
                        "promoted_passenger_id": promoted.passenger_id,
                    })

    db.commit()

    return {
        "message": f"Journey {format_pnr(bid)} cancelled successfully",
        "booking_id": bid,
        "pnr": format_pnr(bid),
        "promoted_passengers": promoted_passengers,
    }


@router.put("/cancel/{booking_id}", status_code=status.HTTP_200_OK, response_model=schemas.BookingResponse)
def cancel_booking_legacy(
    booking_id: int,
    db: Session = Depends(database.get_db),
    current_user: model.User = Depends(oauth.get_the_user),
):
    """Backwards-compatible single ticket cancellation."""
    booking = (
        db.query(model.Booking)
        .filter(
            model.Booking.booking_id == booking_id,
            model.Booking.passenger_id == current_user.id,
        )
        .first()
    )

    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    if booking.status == "cancelled":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Booking is already cancelled")

    was_confirmed = (booking.status.lower() == "confirmed")
    booking.status = "cancelled"

    if was_confirmed:
        flight = db.query(model.Flight).filter(model.Flight.flight_id == booking.flight_id).first()
        if flight:
            flight.seats_available += 1
            allocate_waiting_seat_min_heap(booking.flight_id, db)

    db.commit()
    db.refresh(booking)
    return schemas.BookingResponse(
        booking_id=booking.booking_id,
        flight_id=booking.flight_id,
        passenger_id=booking.passenger_id,
        status=booking.status,
        pnr=format_pnr(booking.booking_id),
        created_at=booking.created_at,
    )


@router.get("/dashboard", status_code=status.HTTP_200_OK, response_model=schemas.DashboardResponse)
def get_passenger_dashboard(
    db: Session = Depends(database.get_db),
    current_user: model.User = Depends(oauth.get_the_user),
):
    """
    Returns three categorized lists for the authenticated passenger:
      - upcoming_flights: confirmed journeys whose departure/arrival is today or in the future
      - waitlisted_tickets: journeys with waitlisted/pending status
      - past_flights: journeys completed in the past or cancelled
    Multi-leg journeys booked together are grouped and identified by booking_id.
    """
    try:
        bookings = (
            db.query(model.Booking)
            .filter(model.Booking.passenger_id == current_user.id)
            .order_by(model.Booking.booking_id.asc())
            .all()
        )
    except Exception as e:
        db.rollback()
        import traceback
        print(f"get_passenger_dashboard error: {e}")
        traceback.print_exc()
        bookings = []

    if not bookings:
        return schemas.DashboardResponse(
            upcoming_flights=[],
            waitlisted_tickets=[],
            past_flights=[],
        )

    # Group companion legs booked together in the exact same transaction timestamp
    groups = defaultdict(list)
    for b in bookings:
        time_key = b.created_at.strftime("%Y-%m-%d %H:%M:%S.%f") if b.created_at else str(b.booking_id)
        groups[time_key].append(b)

    now = datetime.now()

    upcoming_flights = []
    waitlisted_tickets = []
    past_flights = []

    for _, leg_bookings in groups.items():
        legs_data = []
        for lb in leg_bookings:
            f = lb.flight
            if not f:
                f = db.query(model.Flight).filter(model.Flight.flight_id == lb.flight_id).first()
            if not f:
                continue
            legs_data.append({
                "booking_id": lb.booking_id,
                "flight_id": f.flight_id,
                "source": f.source,
                "destination": f.destination,
                "departure_time": f.departure_time or datetime.now(),
                "arrival_time": f.arrival_time or datetime.now(),
                "price": f.price or 0.0,
                "status": lb.status or "confirmed",
            })

        if not legs_data:
            continue

        legs_data.sort(key=lambda x: x["departure_time"] or datetime.min)

        # Primary booking_id formats the human-readable PNR
        lead_booking_id = leg_bookings[0].booking_id
        pnr_label = format_pnr(lead_booking_id)

        origin = legs_data[0]["source"]
        destination = legs_data[-1]["destination"]
        dep_time = legs_data[0]["departure_time"]
        arr_time = legs_data[-1]["arrival_time"]
        total_stops = max(0, len(legs_data) - 1)
        layovers = [legs_data[i]["destination"] for i in range(len(legs_data) - 1)]
        total_price = sum(ld["price"] for ld in legs_data)
        booking_created_at = leg_bookings[0].created_at or datetime.now()

        # Determine overall journey status
        statuses = [ld["status"].lower() for ld in legs_data]
        if all(s == "cancelled" for s in statuses):
            journey_status = "cancelled"
        elif any(s in ["waiting_list", "pending"] for s in statuses):
            journey_status = "waiting_list"
        else:
            journey_status = "confirmed"

        # Calculate dynamic waitlist positions via Min-Heap for legs and journey
        leg_positions = []
        clean_legs = []
        for ld in legs_data:
            leg_status_lower = (ld["status"] or "").lower()
            leg_pos = None
            if leg_status_lower in ["waiting_list", "pending"]:
                leg_pos = get_booking_waitlist_position(ld["flight_id"], ld["booking_id"], db)
                if leg_pos is not None:
                    leg_positions.append(leg_pos)

            clean_legs.append(
                schemas.JourneyLeg(
                    booking_id=ld["booking_id"],
                    flight_id=ld["flight_id"],
                    source=ld["source"],
                    destination=ld["destination"],
                    departure_time=ld["departure_time"],
                    arrival_time=ld["arrival_time"],
                    price=ld["price"],
                    status=ld["status"],
                    current_position=leg_pos,
                )
            )

        journey_current_pos = None
        if journey_status in ["waiting_list", "pending"]:
            journey_current_pos = max(leg_positions) if leg_positions else None

        journey = schemas.JourneyResponse(
            pnr=pnr_label,
            source=origin,
            destination=destination,
            departure_time=dep_time,
            arrival_time=arr_time,
            total_stops=total_stops,
            layovers=layovers,
            total_price=total_price,
            status=journey_status,
            created_at=booking_created_at,
            legs=clean_legs,
            current_position=journey_current_pos,
        )

        # Categorize into three lists:
        # 1. Cancelled -> Travel History
        # 2. Waitlisted -> Waitlist Tracker
        # 3. Active Upcoming (flight departs today or in the future) -> Active Itineraries
        # 4. Departed in past -> Travel History
        is_upcoming = (arr_time >= now or dep_time.date() >= now.date())

        if journey_status == "cancelled":
            past_flights.append(journey)
        elif journey_status in ["waiting_list", "pending"]:
            waitlisted_tickets.append(journey)
        elif is_upcoming:
            upcoming_flights.append(journey)
        else:
            past_flights.append(journey)

    upcoming_flights.sort(key=lambda j: j.departure_time)
    waitlisted_tickets.sort(key=lambda j: j.created_at or datetime.min)
    past_flights.sort(key=lambda j: j.departure_time, reverse=True)

    return schemas.DashboardResponse(
        upcoming_flights=upcoming_flights,
        waitlisted_tickets=waitlisted_tickets,
        past_flights=past_flights,
    )


@router.get("/my-bookings", status_code=status.HTTP_200_OK, response_model=List[schemas.BookingResponse])
def get_my_bookings(
    db: Session = Depends(database.get_db),
    current_user: model.User = Depends(oauth.get_the_user),
):
    bookings = db.query(model.Booking).filter(
        model.Booking.passenger_id == current_user.id
    ).all()

    return [
        schemas.BookingResponse(
            booking_id=b.booking_id,
            flight_id=b.flight_id,
            passenger_id=b.passenger_id,
            status=b.status,
            pnr=format_pnr(b.booking_id),
            created_at=b.created_at,
        )
        for b in bookings
    ]
