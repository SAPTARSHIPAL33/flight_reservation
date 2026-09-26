from fastapi import Depends, APIRouter, status, HTTPException
from sqlalchemy.orm import Session
from .. import schemas, database, model, oauth


router = APIRouter(prefix="/admin", tags=["ADMIN"])


# ─── Airport Management ─────────────────────────────────────────────

@router.post("/airports", status_code=status.HTTP_201_CREATED, response_model=schemas.AirportResponse)
def add_airport(airport: schemas.AirportCreate, db: Session = Depends(database.get_db),
                current_user: model.User = Depends(oauth.require_role("admin"))):
    existing = db.query(model.Airport).filter(model.Airport.place == airport.place).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=f"Airport '{airport.place}' already exists")

    new_airport = model.Airport(**airport.model_dump())
    db.add(new_airport)
    db.commit()
    db.refresh(new_airport)
    return new_airport


@router.get("/airports", status_code=status.HTTP_200_OK, response_model=list[schemas.AirportResponse])
def list_airports(db: Session = Depends(database.get_db),
                  current_user: model.User = Depends(oauth.require_role("admin"))):
    return db.query(model.Airport).all()


@router.delete("/airports/{id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_airport(id: int, db: Session = Depends(database.get_db),
                   current_user: model.User = Depends(oauth.require_role("admin"))):
    airport = db.query(model.Airport).filter(model.Airport.id == id)
    if airport.first() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Airport not found")
    airport.delete()
    db.commit()


# ─── Flight Management ──────────────────────────────────────────────

@router.post("/flights", status_code=status.HTTP_201_CREATED, response_model=schemas.FlightResponse)
def add_flight(flight: schemas.FlightCreate, db: Session = Depends(database.get_db),
               current_user: model.User = Depends(oauth.require_role("admin"))):
    new_flight = model.Flight(**flight.model_dump())
    db.add(new_flight)
    db.commit()
    db.refresh(new_flight)
    return new_flight


@router.put("/flights/{flight_id}", response_model=schemas.FlightResponse)
def update_flight(flight_id: int, updates: schemas.FlightUpdate, db: Session = Depends(database.get_db),
                  current_user: model.User = Depends(oauth.require_role("admin"))):
    flight_query = db.query(model.Flight).filter(model.Flight.flight_id == flight_id)
    flight = flight_query.first()
    if flight is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flight not found")

    update_data = updates.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided to update")

    flight_query.update(update_data, synchronize_session=False)
    db.commit()
    return flight_query.first()


@router.delete("/flights/{flight_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_flight(flight_id: int, db: Session = Depends(database.get_db),
                  current_user: model.User = Depends(oauth.require_role("admin"))):
    flight = db.query(model.Flight).filter(model.Flight.flight_id == flight_id)
    if flight.first() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flight not found")
    flight.delete()
    db.commit()
