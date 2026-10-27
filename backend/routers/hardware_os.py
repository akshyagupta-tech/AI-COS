import atexit
import hashlib
import heapq
import secrets
from collections import defaultdict, deque
from multiprocessing import shared_memory
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

router = APIRouter(tags=["Hardware and OS Simulations"])

MAX_NOTICE_BYTES = 50 * 1024 * 1024
SHARED_NOTICES: dict[str, dict[str, Any]] = {}


def _release_shared_notices() -> None:
    for notice in SHARED_NOTICES.values():
        segment: shared_memory.SharedMemory = notice["segment"]
        try:
            segment.close()
            segment.unlink()
        except FileNotFoundError:
            pass


atexit.register(_release_shared_notices)


@router.post("/os/notice-board")
async def publish_shared_notice(
    file: UploadFile = File(...),
    title: str = Form(min_length=2, max_length=120),
    recipients: str = Form(default="students, faculty", max_length=500),
) -> dict[str, Any]:
    content = await file.read(MAX_NOTICE_BYTES + 1)
    if not content:
        raise HTTPException(status_code=422, detail="The notice file is empty.")
    if len(content) > MAX_NOTICE_BYTES:
        raise HTTPException(status_code=413, detail="Notice files are limited to 50 MiB.")

    notice_id = secrets.token_urlsafe(9)
    segment: shared_memory.SharedMemory | None = None
    try:
        segment = shared_memory.SharedMemory(create=True, size=len(content))
        segment.buf[: len(content)] = content
        view = segment.buf[: len(content)]
        try:
            checksum = hashlib.sha256(view).hexdigest()
        finally:
            view.release()
        recipient_list = sorted({item.strip() for item in recipients.split(",") if item.strip()})
        SHARED_NOTICES[notice_id] = {
            "segment": segment,
            "size_bytes": len(content),
            "checksum": checksum,
            "filename": file.filename or "campus-notice",
            "title": title,
            "recipients": recipient_list,
        }
    except Exception:
        if segment is not None:
            segment.close()
            segment.unlink()
        raise
    finally:
        await file.close()

    return {
        "notice_id": notice_id,
        "title": title,
        "filename": file.filename or "campus-notice",
        "size_bytes": len(content),
        "checksum_sha256": checksum,
        "shared_memory_name": segment.name,
        "recipients": recipient_list,
        "subscriber_count": len(recipient_list),
        "payload_copies_after_ingest": 0,
        "ipc_model": "Named OS shared-memory segment; subscribers attach by name and read shared views.",
        "algorithm": "Single shared-memory write + zero-copy named-segment reads",
    }


@router.get("/os/notice-board")
def list_shared_notices() -> dict[str, Any]:
    notices = [
        {
            "notice_id": notice_id,
            "title": notice["title"],
            "filename": notice["filename"],
            "size_bytes": notice["size_bytes"],
            "checksum_sha256": notice["checksum"],
            "shared_memory_name": notice["segment"].name,
            "recipients": notice["recipients"],
        }
        for notice_id, notice in SHARED_NOTICES.items()
    ]
    return {"notices": notices, "notice_count": len(notices), "algorithm": "Shared-memory notice registry"}


@router.get("/os/notice-board/{notice_id}/attach")
def attach_shared_notice(notice_id: str) -> dict[str, Any]:
    notice = SHARED_NOTICES.get(notice_id)
    if notice is None:
        raise HTTPException(status_code=404, detail="Notice not found.")
    try:
        subscriber = shared_memory.SharedMemory(name=notice["segment"].name, create=False)
    except FileNotFoundError as error:
        raise HTTPException(status_code=410, detail="The shared-memory segment is no longer available.") from error

    try:
        view = subscriber.buf[: notice["size_bytes"]]
        try:
            observed_checksum = hashlib.sha256(view).hexdigest()
        finally:
            view.release()
    finally:
        subscriber.close()

    if observed_checksum != notice["checksum"]:
        raise HTTPException(status_code=409, detail="Shared notice checksum does not match its registry entry.")
    return {
        "notice_id": notice_id,
        "shared_memory_name": notice["segment"].name,
        "size_bytes": notice["size_bytes"],
        "checksum_sha256": observed_checksum,
        "checksum_valid": True,
        "copies_made_for_subscriber": 0,
        "algorithm": "Attach named shared memory and hash a memoryview in place",
    }


@router.delete("/os/notice-board/{notice_id}")
def remove_shared_notice(notice_id: str) -> dict[str, str]:
    notice = SHARED_NOTICES.pop(notice_id, None)
    if notice is None:
        raise HTTPException(status_code=404, detail="Notice not found.")
    segment: shared_memory.SharedMemory = notice["segment"]
    segment.close()
    segment.unlink()
    return {"notice_id": notice_id, "status": "released", "algorithm": "Shared-memory close + unlink"}


LABS = [
    {"lab": "Emergency Simulation", "active": True, "critical": True, "demand_kw": 30},
    {"lab": "Network Operations", "active": True, "critical": True, "demand_kw": 20},
    {"lab": "Robotics", "active": True, "critical": False, "demand_kw": 35},
    {"lab": "Bioinformatics", "active": True, "critical": False, "demand_kw": 25},
    {"lab": "Design Studio", "active": False, "critical": False, "demand_kw": 18},
    {"lab": "Lecture Hall 2", "active": False, "critical": False, "demand_kw": 22},
]


@router.get("/power-grid/arbitration")
def arbitrate_backup_power(
    available_kw: int = Query(default=80, ge=0, le=300),
    quantum_kw: int = Query(default=10, ge=1, le=50),
) -> dict[str, Any]:
    allocations = {lab["lab"]: 0 for lab in LABS}
    tiers: dict[int, deque[dict[str, Any]]] = defaultdict(deque)
    for lab in LABS:
        if lab["active"]:
            tiers[0 if lab["critical"] else 1].append(lab)

    remaining_kw = available_kw
    for tier in (0, 1):
        queue = tiers[tier]
        while queue and remaining_kw:
            lab = queue.popleft()
            grant = min(quantum_kw, lab["demand_kw"] - allocations[lab["lab"]], remaining_kw)
            allocations[lab["lab"]] += grant
            remaining_kw -= grant
            if allocations[lab["lab"]] < lab["demand_kw"]:
                queue.append(lab)

    report = [
        {
            **lab,
            "allocated_kw": allocations[lab["lab"]],
            "load_pct": round(allocations[lab["lab"]] / lab["demand_kw"] * 100, 1),
            "power_state": "BACKUP_ON" if allocations[lab["lab"]] else "OFF",
        }
        for lab in LABS
    ]
    return {
        "available_kw": available_kw,
        "allocated_kw": available_kw - remaining_kw,
        "unallocated_kw": remaining_kw,
        "allocations": report,
        "bus_tiers": {"tier_0": "critical active labs", "tier_1": "standard active labs"},
        "arbitration_quantum_kw": quantum_kw,
        "algorithm": "Two-tier priority arbitration with round-robin grants within each tier",
    }


EMERGENCY_ROADS: dict[str, dict[str, int]] = {
    "Main Gate": {"Admin Block": 4, "Sports Complex": 7},
    "Admin Block": {"Main Gate": 4, "Library": 3, "Academic Block": 2},
    "Library": {"Admin Block": 3, "Academic Block": 2, "Hostel": 5},
    "Academic Block": {"Admin Block": 2, "Library": 2, "Cafeteria": 3},
    "Cafeteria": {"Academic Block": 3, "Hostel": 4, "Sports Complex": 6},
    "Hostel": {"Library": 5, "Cafeteria": 4, "Sports Complex": 3},
    "Sports Complex": {"Main Gate": 7, "Cafeteria": 6, "Hostel": 3},
}
AMBULANCE_BASES = ["Main Gate", "Hostel"]
MEDICAL_EQUIPMENT = [
    {"item": "AED", "weight_kg": 4, "medical_value": 10},
    {"item": "Trauma kit", "weight_kg": 6, "medical_value": 10},
    {"item": "Oxygen cylinder", "weight_kg": 12, "medical_value": 9},
    {"item": "Splint set", "weight_kg": 5, "medical_value": 7},
    {"item": "Portable suction", "weight_kg": 7, "medical_value": 8},
    {"item": "Burn dressings", "weight_kg": 3, "medical_value": 5},
    {"item": "OB kit", "weight_kg": 5, "medical_value": 6},
]


def _shortest_emergency_route(start: str, destination: str) -> tuple[list[str], int]:
    if start not in EMERGENCY_ROADS or destination not in EMERGENCY_ROADS:
        raise HTTPException(status_code=404, detail="Unknown campus location.")
    distances = {location: float("inf") for location in EMERGENCY_ROADS}
    previous: dict[str, str] = {}
    distances[start] = 0
    queue: list[tuple[int, str]] = [(0, start)]
    while queue:
        distance, location = heapq.heappop(queue)
        if distance > distances[location]:
            continue
        if location == destination:
            break
        for neighbor, travel_minutes in EMERGENCY_ROADS[location].items():
            candidate = distance + travel_minutes
            if candidate < distances[neighbor]:
                distances[neighbor] = candidate
                previous[neighbor] = location
                heapq.heappush(queue, (candidate, neighbor))

    path = [destination]
    while path[-1] != start:
        if path[-1] not in previous:
            raise HTTPException(status_code=404, detail="No ambulance route is available.")
        path.append(previous[path[-1]])
    path.reverse()
    return path, int(distances[destination])


def _equipment_knapsack(capacity_kg: int) -> tuple[list[dict[str, Any]], int, int]:
    item_count = len(MEDICAL_EQUIPMENT)
    best = [[0] * (capacity_kg + 1) for _ in range(item_count + 1)]
    for index, item in enumerate(MEDICAL_EQUIPMENT, start=1):
        for capacity in range(capacity_kg + 1):
            best[index][capacity] = best[index - 1][capacity]
            if item["weight_kg"] <= capacity:
                candidate = best[index - 1][capacity - item["weight_kg"]] + item["medical_value"]
                best[index][capacity] = max(best[index][capacity], candidate)

    selected = []
    remaining = capacity_kg
    for index in range(item_count, 0, -1):
        if best[index][remaining] != best[index - 1][remaining]:
            item = MEDICAL_EQUIPMENT[index - 1]
            selected.append(item)
            remaining -= item["weight_kg"]
    selected.reverse()
    total_weight = sum(item["weight_kg"] for item in selected)
    return selected, total_weight, best[item_count][capacity_kg]


@router.get("/emergency/ambulance-dispatch")
def dispatch_ambulance(
    incident_location: str = Query(default="Academic Block"),
    severity: int = Query(default=3, ge=1, le=5),
    equipment_capacity_kg: int = Query(default=35, ge=5, le=60),
) -> dict[str, Any]:
    routes = []
    for base in AMBULANCE_BASES:
        path, eta = _shortest_emergency_route(base, incident_location)
        routes.append({"base": base, "path": path, "eta_minutes": eta})
    ambulance = min(routes, key=lambda route: route["eta_minutes"])
    loadout, loadout_weight, medical_value = _equipment_knapsack(equipment_capacity_kg)
    return {
        "incident_location": incident_location,
        "severity": severity,
        "ambulance_base": ambulance["base"],
        "route": ambulance["path"],
        "eta_minutes": ambulance["eta_minutes"],
        "equipment_capacity_kg": equipment_capacity_kg,
        "loadout": loadout,
        "loadout_weight_kg": loadout_weight,
        "medical_value_score": medical_value,
        "algorithm": "Dijkstra nearest-ambulance routing + 0/1 knapsack medical loadout",
    }


SENSOR_READINGS = [
    {"zone": "Library Reading Hall", "pir_motion": True, "ambient_lux": 72, "fixture_watts": 180},
    {"zone": "Lecture Hall B", "pir_motion": False, "ambient_lux": 34, "fixture_watts": 240},
    {"zone": "Robotics Lab", "pir_motion": True, "ambient_lux": 410, "fixture_watts": 320},
    {"zone": "North Corridor", "pir_motion": True, "ambient_lux": 48, "fixture_watts": 120},
    {"zone": "Seminar Room 3", "pir_motion": False, "ambient_lux": 290, "fixture_watts": 160},
    {"zone": "Design Studio", "pir_motion": True, "ambient_lux": 95, "fixture_watts": 200},
]


@router.get("/iot/energy-mesh")
def evaluate_energy_mesh(
    daylight_threshold_lux: int = Query(default=150, ge=10, le=1000),
) -> dict[str, Any]:
    zones = []
    for sensor in SENSOR_READINGS:
        relay_on = sensor["pir_motion"] and sensor["ambient_lux"] < daylight_threshold_lux
        zones.append(
            {
                **sensor,
                "relay_on": relay_on,
                "lighting_state": "ON" if relay_on else "OFF",
                "reason": "motion + low daylight" if relay_on else "unoccupied or sufficient daylight",
                "estimated_watts": sensor["fixture_watts"] if relay_on else 0,
            }
        )
    return {
        "daylight_threshold_lux": daylight_threshold_lux,
        "zones": zones,
        "active_relays": sum(zone["relay_on"] for zone in zones),
        "estimated_load_watts": sum(zone["estimated_watts"] for zone in zones),
        "algorithm": "PIR occupancy AND LDR daylight threshold control for each lighting relay",
    }