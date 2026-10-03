from fastapi import FastAPI, Depends, HTTPException, status, APIRouter, Query
from sqlalchemy.orm import Session
from .. import schemas, database, model, oauth
from ..flight_management import FlightAVLTree
from ..dijsktra import AirportGraph

router = APIRouter(tags=["SEARCH"])


@router.get("/shortest-route", status_code=status.HTTP_200_OK)
def find_shortest_route(
    source: str = Query(..., description="Departure airport (e.g. DEL)"),
    destination: str = Query(..., description="Arrival airport (e.g. BLR)"),
    db: Session = Depends(database.get_db),
    user: int = Depends(oauth.get_the_user),
):
    """
    Find the **cheapest** route between two airports.

    The algorithm considers ALL flights in the system and uses Dijkstra's
    shortest-path algorithm to find the optimal route — which may involve
    one or more intermediate stops (connecting flights).

    Query Parameters
    ----------------
    source : str
        IATA code of the departure airport.
    destination : str
        IATA code of the arrival airport.

    Returns
    -------
    JSON with the shortest path, total price, number of legs,
    and available flights for each leg.
    """
    source = source.strip().upper()
    destination = destination.strip().upper()

    if source == destination:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source and destination cannot be the same.",
        )

    # 1. Fetch ALL flights from the database
    all_flights = db.query(model.Flight).all()

    if not all_flights:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No flights exist in the system.",
        )

    # 2. Build the graph from all flights (price = edge weight)
    graph = AirportGraph.from_flights(all_flights)

    # 3. Validate that both airports exist in the graph
    airports_in_graph = graph.get_airports()
    if source not in airports_in_graph:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No flights originate from airport '{source}'.",
        )
    if destination not in airports_in_graph:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No flights arrive at airport '{destination}'.",
        )

    # 4. Run Dijkstra and get detailed leg-by-leg results
    route = graph.shortest_route_detail(source, destination)

    if route is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No route exists from '{source}' to '{destination}' "
                   f"(not even via connecting flights).",
        )

    return route


@router.get("/search", status_code=status.HTTP_200_OK)
def search_and_sort_flights(
    travel: schemas.SearchModule = Depends(),
    db: Session = Depends(database.get_db),
    user: int = Depends(oauth.get_the_user),
):
    """
    Search for **direct** flights between two airports, sorted by
    departure time using an AVL tree.

    For multi-leg / connecting-flight routes, use ``/shortest-route``.
    """
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