import heapq
from collections import deque
from statistics import mean, pstdev
from typing import Any

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(tags=["Facilities and Mobility"])

CAMPUS_ROAD_GRAPH: dict[str, dict[str, int]] = {
    "Main Gate": {"Admin Block": 4, "Sports Complex": 7},
    "Admin Block": {"Main Gate": 4, "Library": 3, "Academic Block": 2},
    "Library": {"Admin Block": 3, "Academic Block": 2, "Hostel": 5},
    "Academic Block": {"Admin Block": 2, "Library": 2, "Cafeteria": 3},
    "Cafeteria": {"Academic Block": 3, "Hostel": 4, "Sports Complex": 6},
    "Hostel": {"Library": 5, "Cafeteria": 4, "Sports Complex": 3},
    "Sports Complex": {"Main Gate": 7, "Cafeteria": 6, "Hostel": 3},
}
SHUTTLES = [
    {"id": "SH-01", "at": "Main Gate", "seats": 12},
    {"id": "SH-02", "at": "Hostel", "seats": 8},
    {"id": "SH-03", "at": "Cafeteria", "seats": 16},
]
ROOMS = [
    {"room": "A-101", "building": "Academic Block", "capacity": 40, "features": ["projector"]},
    {"room": "A-204", "building": "Academic Block", "capacity": 80, "features": ["projector", "hybrid"]},
    {"room": "S-12", "building": "Admin Block", "capacity": 24, "features": ["projector"]},
    {"room": "L-01", "building": "Library", "capacity": 120, "features": ["hybrid"]},
]
PARKING = {
    "car": [{"spot": "C-01", "occupied": True}, {"spot": "C-02", "occupied": False}, {"spot": "C-03", "occupied": False}],
    "bike": [{"spot": "B-01", "occupied": False}, {"spot": "B-02", "occupied": False}],
}
WATER_READINGS = [41, 42, 40, 44, 39, 43, 41, 42, 91, 40, 39, 43]
MAINTENANCE_TICKETS = [
    {"id": "M-104", "location": "Library", "severity": 4, "age_hours": 8, "impact": 5},
    {"id": "M-107", "location": "Hostel", "severity": 3, "age_hours": 26, "impact": 4},
    {"id": "M-112", "location": "Academic Block", "severity": 5, "age_hours": 2, "impact": 3},
    {"id": "M-118", "location": "Cafeteria", "severity": 2, "age_hours": 48, "impact": 2},
]
EVACUATION_GRAPH: dict[str, list[str]] = {
    "Academic Block": ["Library", "Admin Block", "East Exit"],
    "Library": ["Academic Block", "Hostel", "North Exit"],
    "Admin Block": ["Academic Block", "Main Gate", "West Exit"],
    "Hostel": ["Library", "Sports Complex", "South Exit"],
    "Sports Complex": ["Hostel", "South Exit"],
    "Main Gate": ["Admin Block", "West Exit"],
    "East Exit": [],
    "North Exit": [],
    "West Exit": [],
    "South Exit": [],
}
EXITS = {"East Exit", "North Exit", "West Exit", "South Exit"}


def shortest_path(start: str, finish: str) -> tuple[list[str], int]:
    if start not in CAMPUS_ROAD_GRAPH or finish not in CAMPUS_ROAD_GRAPH:
        raise HTTPException(status_code=404, detail="Unknown campus location")
    distances = {location: float("inf") for location in CAMPUS_ROAD_GRAPH}
    previous: dict[str, str] = {}
    distances[start] = 0
    queue: list[tuple[int, str]] = [(0, start)]
    while queue:
        distance, location = heapq.heappop(queue)
        if distance != distances[location]:
            continue
        if location == finish:
            break
        for neighbor, weight in CAMPUS_ROAD_GRAPH[location].items():
            candidate = distance + weight
            if candidate < distances[neighbor]:
                distances[neighbor] = candidate
                previous[neighbor] = location
                heapq.heappush(queue, (candidate, neighbor))
    path = [finish]
    while path[-1] != start:
        if path[-1] not in previous:
            raise HTTPException(status_code=404, detail="No connected route found")
        path.append(previous[path[-1]])
    path.reverse()
    return path, int(distances[finish])


@router.get("/facilities/energy-score")
def calculate_energy_score() -> dict[str, Any]:
    zones = [
        {"zone": "Engineering", "capacity": 200, "occupancy": 15},
        {"zone": "Library", "capacity": 50, "occupancy": 0},
        {"zone": "Labs", "capacity": 80, "occupancy": 75},
    ]
    report = []
    for zone in zones:
        utilization = zone["occupancy"] / zone["capacity"] * 100
        saved, mode = (5.2, "DEEP_SLEEP") if zone["occupancy"] == 0 else (
            (2.4, "ECO_MODE") if utilization < 30 else (0.0, "ACTIVE")
        )
        report.append({"zone": zone["zone"], "utilization_pct": round(utilization, 1), "mode": mode, "kwh_saved": saved})
    return {
        "total_kwh_saved": round(sum(zone["kwh_saved"] for zone in report), 2),
        "zones": report,
        "algorithm": "Occupancy threshold heuristic",
    }


@router.get("/campus/route")
def get_campus_route(
    origin: str = Query(default="Main Gate"),
    destination: str = Query(default="Library"),
) -> dict[str, Any]:
    path, distance = shortest_path(origin, destination)
    return {"origin": origin, "destination": destination, "path": path, "distance_minutes": distance, "algorithm": "Dijkstra shortest path"}


@router.get("/mobility/shuttle")
def dispatch_shuttle(destination: str = Query(default="Library")) -> dict[str, Any]:
    if destination not in CAMPUS_ROAD_GRAPH:
        raise HTTPException(status_code=404, detail="Unknown campus destination")
    candidates = []
    for shuttle in SHUTTLES:
        path, eta = shortest_path(shuttle["at"], destination)
        candidates.append((eta, shuttle["id"], shuttle, path))
    eta, _, shuttle, path = min(candidates)
    return {
        "assigned_shuttle": shuttle["id"],
        "current_location": shuttle["at"],
        "destination": destination,
        "eta_minutes": eta,
        "seats_available": shuttle["seats"],
        "path": path,
        "algorithm": "Minimum-ETA resource allocation using Dijkstra",
    }


@router.get("/facilities/room-allocation")
def allocate_room(attendees: int = Query(default=30, ge=1, le=500)) -> dict[str, Any]:
    available = [room for room in ROOMS if room["capacity"] >= attendees]
    if not available:
        raise HTTPException(status_code=404, detail="No room has sufficient capacity")
    room = min(available, key=lambda item: item["capacity"] - attendees)
    return {"attendees": attendees, "allocation": room, "unused_seats": room["capacity"] - attendees, "algorithm": "Best-fit resource allocation"}


@router.get("/facilities/parking")
def allocate_parking(vehicle_type: str = Query(default="car", pattern="^(car|bike)$")) -> dict[str, Any]:
    spot = next((item for item in PARKING[vehicle_type] if not item["occupied"]), None)
    if spot is None:
        raise HTTPException(status_code=409, detail=f"No {vehicle_type} spaces are available")
    return {"vehicle_type": vehicle_type, "allocated_spot": spot["spot"], "algorithm": "First-fit scan over available spaces"}


@router.get("/facilities/water-anomalies")
def detect_water_anomalies(threshold: float = Query(default=2.0, ge=1.0, le=5.0)) -> dict[str, Any]:
    average = mean(WATER_READINGS)
    deviation = pstdev(WATER_READINGS)
    anomalies = [
        {"reading_index": index + 1, "liters": reading, "z_score": round((reading - average) / deviation, 2)}
        for index, reading in enumerate(WATER_READINGS)
        if deviation and abs((reading - average) / deviation) >= threshold
    ]
    return {"mean_liters": round(average, 1), "threshold": threshold, "anomalies": anomalies, "algorithm": "Z-score outlier detection"}


@router.get("/facilities/maintenance-priority")
def prioritize_maintenance(limit: int = Query(default=4, ge=1, le=20)) -> dict[str, Any]:
    queue: list[tuple[float, str, dict[str, Any]]] = []
    for ticket in MAINTENANCE_TICKETS:
        score = ticket["severity"] * ticket["impact"] * (1 + ticket["age_hours"] / 24)
        heapq.heappush(queue, (-score, ticket["id"], {**ticket, "priority_score": round(score, 1)}))
    return {"tickets": [heapq.heappop(queue)[2] for _ in range(min(limit, len(queue)))], "algorithm": "Max-priority heap weighted by severity, impact, and age"}


@router.get("/safety/evacuation-route")
def get_evacuation_route(building: str = Query(default="Academic Block")) -> dict[str, Any]:
    if building not in EVACUATION_GRAPH or building in EXITS:
        raise HTTPException(status_code=404, detail="Unknown building or starting location")
    queue = deque([[building]])
    visited = {building}
    while queue:
        path = queue.popleft()
        location = path[-1]
        if location in EXITS:
            return {"building": building, "nearest_exit": location, "path": path, "steps": len(path) - 1, "algorithm": "Breadth-first search on the evacuation graph"}
        for neighbor in EVACUATION_GRAPH[location]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append([*path, neighbor])
    raise HTTPException(status_code=404, detail="No exit is reachable from this building")