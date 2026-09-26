from fastapi import FastAPI, Depends, HTTPException, status,APIRouter
from sqlalchemy.orm import Session
from .. import schemas,database,model,oauth
from ..flight_management import FlightAVLTree

router=APIRouter(tags=["SEARCH"])

@router.get("/search",status_code=status.HTTP_200_OK)
def search_and_sort_flights(travel:schemas.SearchModule=Depends(), db: Session = Depends(database.get_db),user:int=Depends(oauth.get_the_user)):
    # 1. Extract all rows for this route from PostgreSQL
    db_flights = db.query(model.Flight).filter(
        model.Flight.source == travel.source,
        model.Flight.destination == travel.destination
    ).all()

    if not db_flights:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No flights found for this route")

    # 2. Initialize the dynamic AVL Tree
    avl = FlightAVLTree()
    root = None

    # 3. Insert each flight into the tree
    for flight in db_flights:
        root = avl.insert(
            root, 
            flight_id=flight.flight_id, 
            depart_time=flight.departure_time,
            arrival_time=flight.arrival_time,
            price=flight.price, 
            seats_available=flight.seats_available
        )

    # 4. Perform in-order traversal to get the final sorted list
    sorted_results = avl.get_sorted_flights(root)

    return {"route": f"{travel.source} to {travel.destination}", "flights": sorted_results}