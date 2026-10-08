from __future__ import annotations
import heapq
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple


class AirportGraph:
    """Weighted, undirected graph of airport connections."""

    def __init__(self) -> None:
        # adjacency list: { airport_code: [(neighbour, distance), ...] }
        self._adj: Dict[str, List[Tuple[str, float]]] = {}
        # flight index: { (origin, destination): [flight_obj, ...] }
        # Stores actual Flight ORM objects so we can retrieve details per leg.
        self._flight_index: Dict[Tuple[str, str], List[Any]] = defaultdict(list)

    # ------------------------------------------------------------------
    # Build from database Flight rows
    # ------------------------------------------------------------------

    @classmethod
    def from_flights(cls, flights: List[Any]) -> "AirportGraph":
        """
        Build the graph from a list of Flight ORM objects.

        Each unique (source, destination) pair becomes an edge whose weight
        is the **cheapest** price among all flights on that leg.  All flight
        objects are stored in ``_flight_index`` so the caller can look up
        the actual flights that cover each leg of the shortest path.

        Parameters
        ----------
        flights : list
            Flight ORM rows (must have ``.source``, ``.destination``,
            ``.price`` attributes).

        Returns
        -------
        AirportGraph
            A fully-constructed graph ready for ``shortest_path()``.
        """
        graph = cls()

        # Collect cheapest price per (source, dest) pair
        cheapest: Dict[Tuple[str, str], float] = {}

        for flight in flights:
            src = flight.source.upper()
            dst = flight.destination.upper()
            key = (src, dst)

            graph._flight_index[key].append(flight)

            # Use the cheapest flight on this leg as the edge weight
            if key not in cheapest or flight.price < cheapest[key]:
                cheapest[key] = flight.price

        # Build edges (directed — A→B does NOT imply B→A unless a
        # return flight exists in the data)
        for (src, dst), price in cheapest.items():
            graph.add_airport(src)
            graph.add_airport(dst)
            graph._adj[src].append((dst, price))

        return graph

    # ------------------------------------------------------------------
    # Graph construction
    # ------------------------------------------------------------------

    def add_airport(self, code: str) -> None:
        """Register an airport node (optional – add_route does this automatically)."""
        code = code.upper()
        if code not in self._adj:
            self._adj[code] = []

    def add_route(
        self,
        origin: str,
        destination: str,
        distance: float,
        bidirectional: bool = True,
    ) -> None:
        """
        Add a route (edge) between two airports.

        Parameters
        ----------
        origin : str
            IATA code of the departure airport (e.g. "DEL").
        destination : str
            IATA code of the arrival airport (e.g. "BOM").
        distance : float
            Weight of the edge (km, miles, cost – whatever unit you choose).
        bidirectional : bool, default True
            If True the route works in both directions (undirected edge).
        """
        origin, destination = origin.upper(), destination.upper()
        self.add_airport(origin)
        self.add_airport(destination)
        self._adj[origin].append((destination, distance))
        if bidirectional:
            self._adj[destination].append((origin, distance))

    def get_airports(self) -> List[str]:
        """Return a sorted list of all airport codes in the graph."""
        return sorted(self._adj.keys())

    def get_routes(self, airport: str) -> List[Tuple[str, float]]:
        """Return all direct connections from the given airport."""
        airport = airport.upper()
        if airport not in self._adj:
            raise ValueError(f"Airport '{airport}' not found in the graph.")
        return list(self._adj[airport])

    # ------------------------------------------------------------------
    # Dijkstra's algorithm
    # ------------------------------------------------------------------

    def shortest_path(
        self, source: str, target: str
    ) -> Optional[Dict]:
        """
        Find the shortest path between *source* and *target* using
        Dijkstra's algorithm.

        Returns
        -------
        dict | None
            ``{"distance": <total_distance>, "path": [<ordered airport codes>]}``
            or ``None`` if no path exists.

        Raises
        ------
        ValueError
            If *source* or *target* is not in the graph.
        """
        source, target = source.upper(), target.upper()

        if source not in self._adj:
            raise ValueError(f"Source airport '{source}' not found in the graph.")
        if target not in self._adj:
            raise ValueError(f"Target airport '{target}' not found in the graph.")

        # dist[node]  = shortest known distance from source
        # prev[node]  = previous node on that shortest path
        dist: Dict[str, float] = {node: float("inf") for node in self._adj}
        prev: Dict[str, Optional[str]] = {node: None for node in self._adj}
        dist[source] = 0.0

        # Min-heap: (distance, airport_code)
        heap: List[Tuple[float, str]] = [(0.0, source)]
        visited: set = set()

        while heap:
            current_dist, current = heapq.heappop(heap)

            if current in visited:
                continue
            visited.add(current)

            # Early exit once we've settled the target node
            if current == target:
                break

            for neighbour, weight in self._adj[current]:
                if neighbour in visited:
                    continue
                new_dist = current_dist + weight
                if new_dist < dist[neighbour]:
                    dist[neighbour] = new_dist
                    prev[neighbour] = current
                    heapq.heappush(heap, (new_dist, neighbour))

        # Reconstruct path
        if dist[target] == float("inf"):
            return None  # no path exists

        path: List[str] = []
        node: Optional[str] = target
        while node is not None:
            path.append(node)
            node = prev[node]
        path.reverse()

        return {"distance": dist[target], "path": path}

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------

    def all_shortest_paths(
        self, source: str
    ) -> Dict[str, Optional[Dict]]:
        """
        Compute shortest paths from *source* to **every** other airport.

        Returns a dict keyed by airport code, each value is the same
        format as ``shortest_path()`` returns.
        """
        source = source.upper()
        if source not in self._adj:
            raise ValueError(f"Source airport '{source}' not found in the graph.")

        results: Dict[str, Optional[Dict]] = {}
        for airport in self._adj:
            if airport == source:
                continue
            results[airport] = self.shortest_path(source, airport)
        return results

    def shortest_route_detail(
        self, source: str, target: str
    ) -> Optional[Dict]:
        """
        Find the cheapest route (possibly multi-leg) and return full
        flight details for every leg.

        Returns
        -------
        dict | None
            {
              "source": "DEL",
              "destination": "BLR",
              "total_price": 5200.0,
              "num_legs": 2,
              "path": ["DEL", "HYD", "BLR"],
              "legs": [
                {
                  "leg": 1,
                  "from": "DEL",
                  "to": "HYD",
                  "cheapest_price": 2800.0,
                  "available_flights": [ ... ]
                },
                ...
              ]
            }
        """
        result = self.shortest_path(source, target)
        if result is None:
            return None

        path = result["path"]
        legs: List[Dict] = []

        for i in range(len(path) - 1):
            leg_src = path[i]
            leg_dst = path[i + 1]
            key = (leg_src, leg_dst)

            # Get stored flight objects for this leg
            flight_objs = self._flight_index.get(key, [])
            available = []
            for f in sorted(flight_objs, key=lambda x: x.price):
                available.append({
                    "flight_id": f.flight_id,
                    "source": f.source,
                    "destination": f.destination,
                    "departure_time": str(f.departure_time),
                    "arrival_time": str(f.arrival_time),
                    "price": f.price,
                    "seats_available": f.seats_available,
                })

            cheapest_price = available[0]["price"] if available else 0.0

            legs.append({
                "leg": i + 1,
                "from": leg_src,
                "to": leg_dst,
                "cheapest_price": cheapest_price,
                "available_flights": available,
            })

        return {
            "source": path[0],
            "destination": path[-1],
            "total_price": result["distance"],
            "num_legs": len(legs),
            "path": path,
            "legs": legs,
        }

    def __repr__(self) -> str:
        return (
            f"AirportGraph(airports={len(self._adj)}, "
            f"routes={sum(len(v) for v in self._adj.values())})"
        )

