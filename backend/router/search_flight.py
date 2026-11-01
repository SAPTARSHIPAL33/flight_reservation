import os
import re
import sys
import heapq
from collections import defaultdict
from datetime import datetime
from typing import List, Optional, Tuple

# Ensure project root is in sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

try:
    from .. import database, model, oauth, schemas
    from ..dijsktra import AirportGraph
except (ImportError, ValueError):
    from backend import database, model, oauth, schemas
    from backend.dijsktra import AirportGraph

router = APIRouter(tags=["SEARCH"])

CITY_CODE_MAP = {
    "DELHI": "DEL", "NEW DELHI": "DEL", "DEL": "DEL",
    "MUMBAI": "BOM", "BOMBAY": "BOM", "BOM": "BOM",
    "BANGALORE": "BLR", "BENGALURU": "BLR", "BLR": "BLR",
    "HYDERABAD": "HYD", "HYD": "HYD",
    "KOLKATA": "CCU", "CALCUTTA": "CCU", "CCU": "CCU",
    "CHENNAI": "MAA", "MADRAS": "MAA", "MAA": "MAA",
    "AHMEDABAD": "AMD", "AMD": "AMD",
    "KOCHI": "COK", "COCHIN": "COK", "COK": "COK",
    "PUNE": "PNQ", "PNQ": "PNQ",
    "GOA": "GOI", "GOI": "GOI",
}


def resolve_airport_code(term: str, db: Optional[Session] = None) -> str:
    """Normalize input strings (city names, full airport names, or codes) to 3-letter IATA code."""
    if not term:
        return ""
    cleaned = term.strip().upper()
    match = re.search(r"\(([A-Z]{3})\)", cleaned)
    if match:
        return match.group(1)
    if cleaned in CITY_CODE_MAP:
        return CITY_CODE_MAP[cleaned]
    for city, code in CITY_CODE_MAP.items():
        if city in cleaned or cleaned in city:
            return code
    if db is not None:
        try:
            airport = db.query(model.Airport).filter(
                (model.Airport.place.ilike(f"%{cleaned}%")) |
                (model.Airport.name.ilike(f"%{cleaned}%"))
            ).first()
            if airport and airport.place:
                return airport.place.strip().upper()
        except Exception:
            pass
    return cleaned


def build_flight_adjacency_list(flights: List[model.Flight]) -> dict[str, List[model.Flight]]:
    """
    Query the Flight table to build an adjacency list representing the current flight network.
    Key: Origin airport code in uppercase (e.g., 'DEL').
    Value: List of Flight model objects departing from that airport.
    """
    adj: dict[str, List[model.Flight]] = defaultdict(list)
    for flight in flights:
        src = flight.source.strip().upper()
        adj[src].append(flight)
    return adj


def find_all_flight_paths(
    source: str,
    destination: str,
    adj: dict[str, List[model.Flight]],
    max_layovers: int = 2,
) -> List[dict]:
    """
    Depth-First Search (DFS) graph traversal to find ALL valid paths from source to destination.
    - Limits the search to a maximum of 2 layovers (3 legs total) to prevent performance degradation.
    - If time data exists in the schema, ensures layovers are valid (the arrival time of the previous
      leg must be before the departure time of the next leg).
    - Prevents airport cycles in each path.
    """
    source = source.strip().upper()
    destination = destination.strip().upper()

    if source == destination:
        return []

    itineraries: List[dict] = []

    def dfs(current_airport: str, current_legs: List[model.Flight], visited_airports: set[str]):
        if current_airport == destination:
            if current_legs:
                total_stops = len(current_legs) - 1
                total_price = sum(leg.price for leg in current_legs)
                min_seats = min(leg.seats_available for leg in current_legs)
                itineraries.append({
                    "itinerary_id": "-".join(str(leg.flight_id) for leg in current_legs),
                    "source": source,
                    "destination": destination,
                    "departure_time": current_legs[0].departure_time,
                    "arrival_time": current_legs[-1].arrival_time,
                    "price": total_price,
                    "total_price": total_price,
                    "seats_available": min_seats,
                    "total_stops": total_stops,
                    "legs": [
                        {
                            "flight_id": leg.flight_id,
                            "source": leg.source,
                            "destination": leg.destination,
                            "departure_time": leg.departure_time,
                            "arrival_time": leg.arrival_time,
                            "price": leg.price,
                            "seats_available": leg.seats_available,
                        }
                        for leg in current_legs
                    ],
                })
            return

        if len(current_legs) >= max_layovers + 1:
            return

        for next_flight in adj.get(current_airport, []):
            next_dst = next_flight.destination.strip().upper()

            if next_dst in visited_airports:
                continue

            if current_legs:
                prev_leg = current_legs[-1]
                if (
                    prev_leg.arrival_time is not None
                    and next_flight.departure_time is not None
                    and prev_leg.arrival_time >= next_flight.departure_time
                ):
                    continue

            visited_airports.add(next_dst)
            current_legs.append(next_flight)

            dfs(next_dst, current_legs, visited_airports)

            current_legs.pop()
            visited_airports.remove(next_dst)

    dfs(source, [], {source})

    itineraries.sort(
        key=lambda it: (
            it["total_stops"],
            it["departure_time"] or datetime.min,
            it["total_price"],
        )
    )
    return itineraries


@router.get("/shortest-route", status_code=status.HTTP_200_OK)
def find_shortest_route(
    source: str = Query(..., description="Departure airport (e.g. DEL)"),
    destination: str = Query(..., description="Arrival airport (e.g. BLR)"),
    db: Session = Depends(database.get_db),
):
    """
    Find the **shortest in terms of price** route between two airports using Dijkstra's algorithm.
    """
    source = resolve_airport_code(source, db)
    destination = resolve_airport_code(destination, db)

    if source == destination:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source and destination cannot be the same.",
        )

    all_flights = db.query(model.Flight).all()
    if not all_flights:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No flights exist in the system.",
        )

    graph = AirportGraph.from_flights(all_flights)
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

    route = graph.shortest_route_detail(source, destination)
    if route is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No route exists from '{source}' to '{destination}'.",
        )

    return route


@router.get("/all-routes", status_code=status.HTTP_200_OK)
def get_all_routes(
    source: str = Query(..., description="Departure airport (e.g. DEL)"),
    destination: str = Query(..., description="Arrival airport (e.g. BLR)"),
    max_stops: int = Query(2, ge=0, le=5, description="Maximum intermediate stops"),
    db: Session = Depends(database.get_db),
):
    """
    Find all available routes (both direct and indirect) between two airports.
    """
    source = resolve_airport_code(source, db)
    destination = resolve_airport_code(destination, db)

    if not isinstance(max_stops, int):
        try:
            max_stops = int(getattr(max_stops, "default", 2))
        except (TypeError, ValueError):
            max_stops = 2

    if source == destination:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source and destination cannot be the same.",
        )

    all_flights = db.query(model.Flight).all()
    if not all_flights:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No flights exist in the system.",
        )

    graph = AirportGraph.from_flights(all_flights)
    routes = graph.all_routes_detail(source, destination, max_stops=max_stops)
    return {
        "source": source,
        "destination": destination,
        "total_routes": len(routes),
        "routes": routes,
    }


def find_fastest_indirect_dijkstra(
    source: str,
    destination: str,
    adj: dict[str, List[model.Flight]],
    max_layovers: int = 2,
) -> Optional[dict]:
    """
    Run Dijkstra's algorithm to find ONLY the single fastest indirect flight route
    from source to destination by total time (Travel Time + Layover Time).
    Ignores ticket prices for the graph weight.
    """
    source = source.strip().upper()
    destination = destination.strip().upper()

    if source == destination:
        return None

    pq: List[Tuple[float, int, str, List[model.Flight]]] = []
    counter = 0

    for f1 in adj.get(source, []):
        dst1 = f1.destination.strip().upper()
        if dst1 == destination:
            continue

        travel_seconds = (f1.arrival_time - f1.departure_time).total_seconds()
        if travel_seconds <= 0:
            continue

        travel_minutes = travel_seconds / 60.0
        counter += 1
        heapq.heappush(pq, (travel_minutes, counter, dst1, [f1]))

    while pq:
        current_time, _, current_airport, legs = heapq.heappop(pq)

        if current_airport == destination and len(legs) >= 2:
            total_stops = len(legs) - 1
            total_price = sum(leg.price for leg in legs)
            min_seats = min(leg.seats_available for leg in legs)
            return {
                "itinerary_id": "-".join(str(leg.flight_id) for leg in legs),
                "source": source,
                "destination": destination,
                "departure_time": legs[0].departure_time,
                "arrival_time": legs[-1].arrival_time,
                "price": total_price,
                "total_price": total_price,
                "seats_available": min_seats,
                "total_stops": total_stops,
                "is_fastest_layover": True,
                "badge": "Fastest Layover",
                "legs": [
                    {
                        "flight_id": leg.flight_id,
                        "source": leg.source,
                        "destination": leg.destination,
                        "departure_time": leg.departure_time,
                        "arrival_time": leg.arrival_time,
                        "price": leg.price,
                        "seats_available": leg.seats_available,
                    }
                    for leg in legs
                ],
            }

        if len(legs) >= max_layovers + 1:
            continue

        prev_leg = legs[-1]
        visited_airports = {l.source for l in legs} | {l.destination for l in legs}

        for next_flight in adj.get(current_airport, []):
            next_dst = next_flight.destination.strip().upper()

            if next_dst in visited_airports and next_dst != destination:
                continue

            layover_seconds = (next_flight.departure_time - prev_leg.arrival_time).total_seconds()
            if layover_seconds < 0:
                continue

            flight_travel_seconds = (next_flight.arrival_time - next_flight.departure_time).total_seconds()
            if flight_travel_seconds <= 0:
                continue

            edge_weight_minutes = (layover_seconds + flight_travel_seconds) / 60.0
            new_total_time = current_time + edge_weight_minutes

            counter += 1
            heapq.heappush(pq, (new_total_time, counter, next_dst, legs + [next_flight]))

    return None


@router.get("/search", status_code=status.HTTP_200_OK, response_model=List[schemas.ItineraryResponse])
def search_and_sort_flights(
    source: str = Query(..., description="Departure airport (e.g. DEL)"),
    destination: str = Query(..., description="Arrival airport (e.g. BLR)"),
    max_layovers: int = Query(2, ge=0, le=5, description="Maximum intermediate layovers"),
    db: Session = Depends(database.get_db),
):
    """
    Hybrid Search:
    - Returns ALL available direct flights from source to destination.
    - Plus ONLY the single fastest indirect flight calculated using Dijkstra's algorithm
      with edge weights strictly set to 'Travel Time + Layover Time'.
    """
    src = resolve_airport_code(source, db)
    dst = resolve_airport_code(destination, db)

    if not isinstance(max_layovers, int):
        try:
            max_layovers = int(getattr(max_layovers, "default", 2))
        except (TypeError, ValueError):
            max_layovers = 2

    if not src or not dst:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source and destination are required.",
        )

    if src == dst:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source and destination cannot be the same.",
        )

    # 1. Standard database query to fetch ALL direct flights from source to destination
    direct_flights = (
        db.query(model.Flight)
        .filter(
            model.Flight.source == src,
            model.Flight.destination == dst,
        )
        .order_by(model.Flight.departure_time.asc())
        .all()
    )

    itineraries: List[dict] = []
    for flight in direct_flights:
        itineraries.append({
            "itinerary_id": str(flight.flight_id),
            "source": flight.source,
            "destination": flight.destination,
            "departure_time": flight.departure_time,
            "arrival_time": flight.arrival_time,
            "price": flight.price,
            "total_price": flight.price,
            "seats_available": flight.seats_available,
            "total_stops": 0,
            "is_fastest_layover": False,
            "badge": None,
            "legs": [
                {
                    "flight_id": flight.flight_id,
                    "source": flight.source,
                    "destination": flight.destination,
                    "departure_time": flight.departure_time,
                    "arrival_time": flight.arrival_time,
                    "price": flight.price,
                    "seats_available": flight.seats_available,
                }
            ],
        })

    # 2. Query Flight table to build adjacency list in Python memory
    all_flights = db.query(model.Flight).all()
    if all_flights:
        adj = build_flight_adjacency_list(all_flights)

        # 3. Run Dijkstra's algorithm to find ONLY the single fastest indirect flight
        fastest_indirect = find_fastest_indirect_dijkstra(src, dst, adj, max_layovers=max_layovers)
        if fastest_indirect:
            itineraries.append(fastest_indirect)

    return itineraries
