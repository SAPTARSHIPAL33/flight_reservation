"""
Dijkstra's Algorithm – Shortest Route Between Airports
========================================================
Standalone graph module.  No database dependency – just pure algorithm.

Usage:
    from app.dijkstra import AirportGraph

    graph = AirportGraph()
    graph.add_route("DEL", "BOM", 1148)
    graph.add_route("BOM", "BLR", 842)
    graph.add_route("DEL", "BLR", 1740)

    result = graph.shortest_path("DEL", "BLR")
    # result => {"distance": 1740, "path": ["DEL", "BLR"]}
"""

from __future__ import annotations

import heapq
from typing import Dict, List, Optional, Tuple


class AirportGraph:
    """Weighted, undirected graph of airport connections."""

    def __init__(self) -> None:
        # adjacency list: { airport_code: [(neighbour, distance), ...] }
        self._adj: Dict[str, List[Tuple[str, float]]] = {}

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

    def __repr__(self) -> str:
        return (
            f"AirportGraph(airports={len(self._adj)}, "
            f"routes={sum(len(v) for v in self._adj.values())})"
        )
