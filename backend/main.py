import os
import re
import sys
import heapq
from collections import defaultdict
from datetime import datetime
from typing import List, Optional, Tuple

# Ensure project root is in sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

try:
    from .database import base, engine, get_db, SessionLocal
    from .router import search_flight, user, auth, admin, booking
    from . import model, schemas

    from .dijsktra import AirportGraph
    from .waitinglist import priority_queue
except (ImportError, ValueError):
    from backend.database import base, engine, get_db, SessionLocal
    from backend.router import search_flight, user, auth, admin, booking
    from backend import model, schemas
    from backend.dijsktra import AirportGraph
    from backend.waitinglist import priority_queue

# Ensure database tables exist
model.base.metadata.create_all(bind=engine)

app = FastAPI(title="Flight Reservation API")

@app.on_event("startup")
def check_and_seed_db():
    """Ensure database has flights on startup so layover routes always work even after system restart."""
    db = SessionLocal()
    try:
        count = db.query(model.Flight).count()
        if count == 0:
            print("Database has no flights. Automatically seeding coordinated flight network...")
            import seed_db
            seed_db.seed()
        else:
            # Check if any flights exist in the future; if all flights are in the past, refresh schedules
            latest = db.query(model.Flight.departure_time).order_by(model.Flight.departure_time.desc()).first()
            if latest and latest[0] < datetime.now():
                print("Flight schedules are in the past. Refreshing upcoming coordinated schedule...")
                import seed_db
                seed_db.seed()
    except Exception as e:
        print(f"Startup database check: {e}")
    finally:
        db.close()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],   # allows GET, POST, PUT, DELETE, etc.
    allow_headers=["*"],
)


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


# ─── Graph Traversal & Search Algorithm ──────────────────────────────

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
        # Reached destination: build itinerary
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

        # Limit to max_layovers (max 2 layovers = max 3 legs total)
        if len(current_legs) >= max_layovers + 1:
            return

        for next_flight in adj.get(current_airport, []):
            next_dst = next_flight.destination.strip().upper()

            # Prevent cycles in airport visits
            if next_dst in visited_airports:
                continue

            # Ensure layovers are valid: previous leg arrival must be before next leg departure
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

    # Sort itineraries: direct flights first (0 stops) sorted by departure time,
    # then indirect flights sorted by total stops, then total price
    itineraries.sort(
        key=lambda it: (
            it["total_stops"],
            it["departure_time"] or datetime.min,
            it["total_price"],
        )
    )
    return itineraries


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

    # Priority queue stores tuples: (cumulative_time_minutes, counter, current_airport, legs_list)
    pq: List[Tuple[float, int, str, List[model.Flight]]] = []
    counter = 0

    # Initialize priority queue with outbound flights from source to intermediate airports (excluding destination)
    for f1 in adj.get(source, []):
        dst1 = f1.destination.strip().upper()
        if dst1 == destination:
            continue  # Direct legs are handled separately; we specifically seek indirect routes (>= 2 legs)

        travel_seconds = (f1.arrival_time - f1.departure_time).total_seconds()
        if travel_seconds <= 0:
            continue

        travel_minutes = travel_seconds / 60.0
        counter += 1
        heapq.heappush(pq, (travel_minutes, counter, dst1, [f1]))

    while pq:
        current_time, _, current_airport, legs = heapq.heappop(pq)

        # Reached destination with >= 2 legs (indirect flight)
        # In Dijkstra with non-negative edge weights, the first time destination is popped with >= 2 legs,
        # it is mathematically guaranteed to be the shortest path by total time.
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

        # Layover limit check (e.g. max 2 layovers = max 3 legs)
        if len(legs) >= max_layovers + 1:
            continue

        prev_leg = legs[-1]
        visited_airports = {l.source for l in legs} | {l.destination for l in legs}

        for next_flight in adj.get(current_airport, []):
            next_dst = next_flight.destination.strip().upper()

            # Prevent cycles within the route (destination is only allowed as terminal)
            if next_dst in visited_airports and next_dst != destination:
                continue

            # Calculate Layover Time: departure of next leg minus arrival of previous leg
            layover_seconds = (next_flight.departure_time - prev_leg.arrival_time).total_seconds()
            if layover_seconds < 0:
                continue  # Impossible connection (flight departs before incoming flight arrives)

            # Calculate Travel Time of the next leg
            flight_travel_seconds = (next_flight.arrival_time - next_flight.departure_time).total_seconds()
            if flight_travel_seconds <= 0:
                continue

            # Edge weight strictly set to "Travel Time + Layover Time"
            edge_weight_minutes = (layover_seconds + flight_travel_seconds) / 60.0
            new_total_time = current_time + edge_weight_minutes

            counter += 1
            heapq.heappush(pq, (new_total_time, counter, next_dst, legs + [next_flight]))

    return None


# ─── Search Endpoint on app ──────────────────────────────────────────

@app.get("/search", status_code=status.HTTP_200_OK, response_model=List[schemas.ItineraryResponse])
def search_flights_main(
    source: str = Query(..., description="Departure airport (e.g. DEL)"),
    destination: str = Query(..., description="Arrival airport (e.g. BOM)"),
    max_layovers: int = Query(2, ge=0, le=5, description="Maximum layovers (default 2, meaning up to 3 legs)"),
    db: Session = Depends(get_db),
):
    """
    Search and return ALL available flight routes (both direct and indirect).
    Uses Dijkstra's algorithm to calculate the single fastest indirect route based strictly
    on total time (flight duration + layover time), and appends "badge": "Recommended" to that itinerary.
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

    all_flights = db.query(model.Flight).all()
    if not all_flights:
        return []

    # 1. Build in-memory adjacency list from Flight table
    adj = build_flight_adjacency_list(all_flights)

    # 2. Graph traversal (DFS) to find ALL valid paths (direct and indirect, max 3 legs)
    itineraries = find_all_flight_paths(src, dst, adj, max_layovers=max_layovers)
    if not itineraries:
        return []

    # 3. Dijkstra algorithm to find the single fastest indirect route based strictly on total time
    fastest_indirect = find_fastest_indirect_dijkstra(src, dst, adj, max_layovers=max_layovers)
    fastest_id = fastest_indirect["itinerary_id"] if fastest_indirect else None

    # 4. If an indirect itinerary matches the exact path found by Dijkstra, append "badge": "Recommended"
    for it in itineraries:
        if fastest_id and it["itinerary_id"] == fastest_id and it["total_stops"] > 0:
            it["badge"] = "Recommended"
            it["is_fastest_layover"] = True
        else:
            it["badge"] = None
            it["is_fastest_layover"] = False

    # Sort itineraries: direct flights first (0 stops), then Recommended layover, then other layovers
    itineraries.sort(
        key=lambda it: (
            0 if it["total_stops"] == 0 else (1 if it.get("badge") == "Recommended" else 2),
            it["total_stops"],
            it["departure_time"] or datetime.min,
            it["total_price"],
        )
    )

    return itineraries


# ─── Include Routers ─────────────────────────────────────────────────

app.include_router(search_flight.router)
app.include_router(user.router)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(booking.router)

# ─── Static Files & Frontend Mount ───────────────────────────────────

frontend_dir = os.path.join(root_dir, "frontend")
if os.path.isdir(frontend_dir):
    js_dir = os.path.join(frontend_dir, "js")
    if os.path.isdir(js_dir):
        app.mount("/js", StaticFiles(directory=js_dir), name="js")

    app.mount("/frontend", StaticFiles(directory=frontend_dir), name="frontend")

    @app.get("/", include_in_schema=False)
    def serve_frontend_root():
        return FileResponse(os.path.join(frontend_dir, "index.html"))

    @app.get("/index.html", include_in_schema=False)
    def serve_frontend_index():
        return FileResponse(os.path.join(frontend_dir, "index.html"))

    @app.get("/login.html", include_in_schema=False)
    def serve_frontend_login():
        return FileResponse(os.path.join(frontend_dir, "login.html"))

    @app.get("/signup.html", include_in_schema=False)
    def serve_frontend_signup():
        return FileResponse(os.path.join(frontend_dir, "signup.html"))

    @app.get("/dashboard.html", include_in_schema=False)
    def serve_frontend_dashboard():
        return FileResponse(os.path.join(frontend_dir, "dashboard.html"))

    @app.get("/admin.html", include_in_schema=False)
    def serve_frontend_admin():
        return FileResponse(os.path.join(frontend_dir, "admin.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
