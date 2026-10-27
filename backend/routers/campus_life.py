import base64
import hashlib
import heapq
import io
import json
import logging
import os
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import qrcode
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(tags=["Campus Life"])
logger = logging.getLogger(__name__)

CAMPUS_GEOFENCE = {
    "min_latitude": 28.532,
    "max_latitude": 28.541,
    "min_longitude": 77.386,
    "max_longitude": 77.397,
}

configured_fernet_key = os.getenv("AI_COS_FERNET_KEY")
if configured_fernet_key:
    try:
        OUTPASS_CIPHER = Fernet(configured_fernet_key.encode("ascii"))
    except (UnicodeEncodeError, ValueError) as error:
        raise RuntimeError("AI_COS_FERNET_KEY must be a valid Fernet key.") from error
else:
    OUTPASS_CIPHER = Fernet(Fernet.generate_key())
    logger.warning("Using an ephemeral outpass key; configure AI_COS_FERNET_KEY outside local demos.")

OUTPASSES: dict[str, dict[str, Any]] = {}

DINNER_HISTORY = [
    (438, 18), (462, 20), (451, 19), (487, 21), (475, 20), (509, 22), (470, 19),
    (522, 23), (498, 21), (536, 24), (515, 22), (548, 24), (529, 23), (557, 25),
]

WASHROOMS = [
    {"id": "W-101", "location": "Academic Block", "traffic_index": 92, "hours_since_cleaning": 3},
    {"id": "W-204", "location": "Library", "traffic_index": 78, "hours_since_cleaning": 6},
    {"id": "W-310", "location": "Hostel", "traffic_index": 96, "hours_since_cleaning": 9},
    {"id": "W-402", "location": "Cafeteria", "traffic_index": 88, "hours_since_cleaning": 2},
    {"id": "W-515", "location": "Sports Complex", "traffic_index": 61, "hours_since_cleaning": 12},
]
CLEANING_STAFF = [
    {"staff_id": "CL-01", "location": "Admin Block"},
    {"staff_id": "CL-02", "location": "Library"},
    {"staff_id": "CL-03", "location": "Hostel"},
]
WALKING_MINUTES = {
    "Academic Block": {"Admin Block": 2, "Library": 2, "Cafeteria": 3, "Hostel": 5, "Sports Complex": 8},
    "Library": {"Admin Block": 3, "Academic Block": 2, "Cafeteria": 5, "Hostel": 5, "Sports Complex": 8},
    "Hostel": {"Admin Block": 8, "Academic Block": 5, "Library": 5, "Cafeteria": 4, "Sports Complex": 3},
    "Cafeteria": {"Admin Block": 5, "Academic Block": 3, "Library": 5, "Hostel": 4, "Sports Complex": 6},
    "Sports Complex": {"Admin Block": 9, "Academic Block": 8, "Library": 8, "Hostel": 3, "Cafeteria": 6},
    "Admin Block": {"Academic Block": 2, "Library": 3, "Hostel": 8, "Cafeteria": 5, "Sports Complex": 9},
}

ROOM_TIMETABLE: dict[str, list[dict[str, Any]]] = {
    "A-101": [
        {"day": "Monday", "start": 9, "end": 11, "class": "CS101"},
        {"day": "Monday", "start": 13, "end": 15, "class": "CS201"},
        {"day": "Tuesday", "start": 10, "end": 12, "class": "CS101"},
    ],
    "A-204": [
        {"day": "Monday", "start": 10, "end": 12, "class": "MA201"},
        {"day": "Monday", "start": 14, "end": 16, "class": "CS301"},
        {"day": "Tuesday", "start": 9, "end": 11, "class": "EC201"},
    ],
    "L-110": [
        {"day": "Monday", "start": 8, "end": 10, "class": "IT101"},
        {"day": "Monday", "start": 12, "end": 14, "class": "CS202"},
        {"day": "Tuesday", "start": 13, "end": 15, "class": "IT201"},
    ],
    "S-12": [
        {"day": "Monday", "start": 9, "end": 12, "class": "ME101"},
        {"day": "Tuesday", "start": 11, "end": 13, "class": "CE201"},
    ],
}
ROOM_CAPACITIES = {"A-101": 40, "A-204": 80, "L-110": 36, "S-12": 24}


class OutpassRequest(BaseModel):
    student_id: str = Field(min_length=5, max_length=20)
    destination: str = Field(min_length=2, max_length=100)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    valid_hours: int = Field(default=8, ge=1, le=48)


class EquipmentAction(BaseModel):
    asset_tag: str = Field(min_length=3, max_length=30)
    student_id: str = Field(min_length=5, max_length=20)
    action: Literal["checkout", "return"]


class OutpassVerification(BaseModel):
    encrypted_token: str = Field(min_length=20, max_length=4096)


@router.post("/security/outpass")
def create_outpass(request: OutpassRequest) -> dict[str, Any]:
    bounds = CAMPUS_GEOFENCE
    in_geofence = (
        bounds["min_latitude"] <= request.latitude <= bounds["max_latitude"]
        and bounds["min_longitude"] <= request.longitude <= bounds["max_longitude"]
    )
    if not in_geofence:
        raise HTTPException(status_code=403, detail="Outpass requests must be submitted from inside the campus geofence.")

    issued_at = datetime.now(timezone.utc)
    outpass_id = secrets.token_urlsafe(9)
    payload = {
        "outpass_id": outpass_id,
        "student_id": request.student_id,
        "destination": request.destination,
        "issued_at": issued_at.isoformat(),
        "expires_at": (issued_at + timedelta(hours=request.valid_hours)).isoformat(),
    }
    encrypted_token = OUTPASS_CIPHER.encrypt(json.dumps(payload, sort_keys=True).encode()).decode("ascii")
    qr_image = qrcode.make(encrypted_token)
    image_buffer = io.BytesIO()
    qr_image.save(image_buffer, format="PNG")
    OUTPASSES[outpass_id] = payload

    return {
        **payload,
        "geofence_verified": True,
        "encrypted_token": encrypted_token,
        "qr_png_base64": base64.b64encode(image_buffer.getvalue()).decode("ascii"),
        "algorithm": "Campus coordinate bounds + Fernet authenticated encryption + QR encoding",
    }


@router.post("/security/outpass/verify")
def verify_outpass(request: OutpassVerification) -> dict[str, Any]:
    try:
        payload = json.loads(OUTPASS_CIPHER.decrypt(request.encrypted_token.encode("ascii")).decode("utf-8"))
    except (InvalidToken, UnicodeEncodeError, json.JSONDecodeError, ValueError) as error:
        raise HTTPException(status_code=400, detail="Outpass QR is invalid or was not issued by this campus.") from error

    stored = OUTPASSES.get(payload.get("outpass_id"))
    if stored != payload:
        raise HTTPException(status_code=404, detail="Outpass is not active in the campus ledger.")
    is_expired = datetime.fromisoformat(payload["expires_at"]) <= datetime.now(timezone.utc)
    return {"valid": not is_expired, "expired": is_expired, **payload}


@router.get("/dining/footfall-prediction")
def predict_dinner_footfall(
    scheduled_sections: int = Query(default=22, ge=0, le=60),
    window: int = Query(default=7, ge=3, le=14),
) -> dict[str, Any]:
    history_start = datetime.now(timezone.utc).date() - timedelta(days=len(DINNER_HISTORY) - 1)
    history = [
        {
            "date": (history_start + timedelta(days=index)).isoformat(),
            "footfall": footfall,
            "scheduled_sections": sections,
        }
        for index, (footfall, sections) in enumerate(DINNER_HISTORY)
    ]
    recent = DINNER_HISTORY[-window:]
    per_section_average = sum(footfall / sections for footfall, sections in recent) / len(recent)
    moving_average = sum(footfall for footfall, _ in recent) / len(recent)
    predicted = round(per_section_average * scheduled_sections)

    return {
        "scheduled_sections": scheduled_sections,
        "moving_average_baseline": round(moving_average),
        "predicted_footfall": predicted,
        "predicted_food_waste_kg": round(predicted * 0.085, 1),
        "history": history,
        "algorithm": f"{window}-day moving average normalized by scheduled academic sections",
    }


@router.get("/environment/ventilation")
def manage_ventilation(aqi: int = Query(default=85, ge=0, le=500)) -> dict[str, Any]:
    if aqi <= 100:
        mode, outdoor_air, alert = "NORMAL", "STANDARD", "Good air quality"
    elif aqi <= 200:
        mode, outdoor_air, alert = "INCREASED_EXCHANGE", "INCREASED", "Elevated AQI: increase air exchange"
    else:
        mode, outdoor_air, alert = "FILTERED_RECIRCULATION", "FILTERED", "Poor AQI: filter incoming air"
    return {
        "aqi": aqi,
        "hvac_mode": mode,
        "outdoor_air_intake": outdoor_air,
        "alert": alert,
        "thresholds": [
            {"max_aqi": 100, "mode": "NORMAL"},
            {"max_aqi": 200, "mode": "INCREASED_EXCHANGE"},
            {"max_aqi": 500, "mode": "FILTERED_RECIRCULATION"},
        ],
        "algorithm": "IoT-style threshold controller with hysteresis-free demo rules",
    }


@dataclass
class _BTreeNode:
    keys: list[str] = field(default_factory=list)
    values: list[dict[str, Any]] = field(default_factory=list)
    children: list["_BTreeNode"] = field(default_factory=list)
    leaf: bool = True


class BTreeIndex:
    """Small minimum-degree-2 B-tree index for equipment tags."""

    def __init__(self) -> None:
        self.root = _BTreeNode()

    def search(self, key: str) -> dict[str, Any] | None:
        node = self.root
        while True:
            index = 0
            while index < len(node.keys) and key > node.keys[index]:
                index += 1
            if index < len(node.keys) and node.keys[index] == key:
                return node.values[index]
            if node.leaf:
                return None
            node = node.children[index]

    def insert(self, key: str, value: dict[str, Any]) -> None:
        if len(self.root.keys) == 3:
            new_root = _BTreeNode(leaf=False, children=[self.root])
            self._split_child(new_root, 0)
            self.root = new_root
        self._insert_nonfull(self.root, key, value)

    def _insert_nonfull(self, node: _BTreeNode, key: str, value: dict[str, Any]) -> None:
        index = len(node.keys) - 1
        if node.leaf:
            while index >= 0 and key < node.keys[index]:
                index -= 1
            insert_at = index + 1
            if insert_at < len(node.keys) and node.keys[insert_at] == key:
                node.values[insert_at] = value
                return
            node.keys.insert(insert_at, key)
            node.values.insert(insert_at, value)
            return

        while index >= 0 and key < node.keys[index]:
            index -= 1
        child_index = index + 1
        if len(node.children[child_index].keys) == 3:
            self._split_child(node, child_index)
            if key > node.keys[child_index]:
                child_index += 1
            elif key == node.keys[child_index]:
                node.values[child_index] = value
                return
        self._insert_nonfull(node.children[child_index], key, value)

    @staticmethod
    def _split_child(parent: _BTreeNode, child_index: int) -> None:
        child = parent.children[child_index]
        right = _BTreeNode(
            keys=child.keys[2:],
            values=child.values[2:],
            children=child.children[2:] if not child.leaf else [],
            leaf=child.leaf,
        )
        median_key, median_value = child.keys[1], child.values[1]
        child.keys = child.keys[:1]
        child.values = child.values[:1]
        if not child.leaf:
            child.children = child.children[:2]
        parent.keys.insert(child_index, median_key)
        parent.values.insert(child_index, median_value)
        parent.children.insert(child_index + 1, right)


ASSETS = [
    {"asset_tag": "LAB-003", "name": "Arduino Sensor Kit", "lab": "IoT Lab", "status": "available", "holder": None},
    {"asset_tag": "LAB-014", "name": "Digital Oscilloscope", "lab": "Electronics Lab", "status": "available", "holder": None},
    {"asset_tag": "LAB-027", "name": "Raspberry Pi 5 Kit", "lab": "Embedded Lab", "status": "available", "holder": None},
    {"asset_tag": "LAB-041", "name": "Thermal Camera", "lab": "Robotics Lab", "status": "available", "holder": None},
    {"asset_tag": "LAB-058", "name": "3D Printer Caliper", "lab": "Fabrication Lab", "status": "available", "holder": None},
    {"asset_tag": "LAB-073", "name": "Logic Analyzer", "lab": "Electronics Lab", "status": "available", "holder": None},
]
ASSET_INDEX = BTreeIndex()
for asset in ASSETS:
    ASSET_INDEX.insert(asset["asset_tag"], asset)
HARDWARE_LEDGER: list[dict[str, Any]] = []


@router.post("/inventory/hardware/action")
def update_hardware_ledger(request: EquipmentAction) -> dict[str, Any]:
    asset = ASSET_INDEX.search(request.asset_tag)
    if asset is None:
        raise HTTPException(status_code=404, detail="Equipment tag was not found in the B-tree index.")
    if request.action == "checkout" and asset["status"] != "available":
        raise HTTPException(status_code=409, detail=f"Equipment is already checked out by {asset['holder']}.")
    if request.action == "return" and asset["holder"] != request.student_id:
        raise HTTPException(status_code=409, detail="Only the current borrower can return this equipment.")

    asset["status"] = "checked_out" if request.action == "checkout" else "available"
    asset["holder"] = request.student_id if request.action == "checkout" else None
    event = {
        "sequence": len(HARDWARE_LEDGER) + 1,
        "asset_tag": asset["asset_tag"],
        "action": request.action,
        "student_id": request.student_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "previous_hash": HARDWARE_LEDGER[-1]["record_hash"] if HARDWARE_LEDGER else "GENESIS",
    }
    event["record_hash"] = hashlib.sha256(json.dumps(event, sort_keys=True).encode()).hexdigest()
    HARDWARE_LEDGER.append(event)
    return {
        "asset": asset,
        "ledger_entry": event,
        "ledger_length": len(HARDWARE_LEDGER),
        "search_algorithm": "B-tree index",
        "integrity_algorithm": "SHA-256 hash chain",
    }


@router.get("/inventory/hardware/ledger")
def get_hardware_ledger() -> dict[str, Any]:
    return {
        "assets": ASSETS,
        "entries": HARDWARE_LEDGER,
        "asset_count": len(ASSETS),
        "entry_count": len(HARDWARE_LEDGER),
        "algorithm": "B-tree tag lookup + append-only SHA-256 hash chain",
    }


@router.get("/facilities/hygiene-dispatch")
def dispatch_hygiene_staff(limit: int = Query(default=5, ge=1, le=20)) -> dict[str, Any]:
    priority_queue: list[tuple[float, str, dict[str, Any]]] = []
    for washroom in WASHROOMS:
        priority_score = washroom["traffic_index"] * (1 + washroom["hours_since_cleaning"] / 8)
        heapq.heappush(priority_queue, (-priority_score, washroom["id"], {**washroom, "priority_score": round(priority_score, 1)}))

    staff = [dict(person) for person in CLEANING_STAFF]
    assignments = []
    for _ in range(min(limit, len(priority_queue))):
        _, _, washroom = heapq.heappop(priority_queue)

        def travel_time(person: dict[str, Any]) -> int:
            if person["location"] == washroom["location"]:
                return 0
            return WALKING_MINUTES[person["location"]][washroom["location"]]

        cleaner = min(
            staff,
            key=travel_time,
        )
        travel_minutes = travel_time(cleaner)
        assignments.append(
            {
                **washroom,
                "assigned_staff": cleaner["staff_id"],
                "staff_origin": cleaner["location"],
                "route_minutes": travel_minutes,
            }
        )
        cleaner["location"] = washroom["location"]

    return {
        "assignments": assignments,
        "washrooms_routed": len(assignments),
        "algorithm": "Max-heap by traffic and cleaning age, nearest available staff by campus travel time",
    }


@router.get("/study-rooms/matches")
def match_study_rooms(
    day: str = Query(default="Monday", pattern="^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday)$"),
    start_hour: int = Query(default=9, ge=8, le=19),
    end_hour: int = Query(default=17, ge=9, le=20),
    minimum_minutes: int = Query(default=60, ge=30, le=240),
    capacity: int = Query(default=1, ge=1, le=120),
) -> dict[str, Any]:
    if end_hour <= start_hour:
        raise HTTPException(status_code=422, detail="end_hour must be later than start_hour.")

    matches = []
    required_hours = minimum_minutes / 60
    for room, classes in ROOM_TIMETABLE.items():
        if ROOM_CAPACITIES[room] < capacity:
            continue
        occupied = sorted(
            (max(start_hour, item["start"]), min(end_hour, item["end"]))
            for item in classes
            if item["day"] == day and item["start"] < end_hour and item["end"] > start_hour
        )
        free_blocks = []
        cursor = start_hour
        for busy_start, busy_end in occupied:
            if busy_start > cursor and busy_start - cursor >= required_hours:
                free_blocks.append({"start_hour": cursor, "end_hour": busy_start})
            cursor = max(cursor, busy_end)
        if end_hour - cursor >= required_hours:
            free_blocks.append({"start_hour": cursor, "end_hour": end_hour})
        if free_blocks:
            matches.append({"room": room, "capacity": ROOM_CAPACITIES[room], "free_blocks": free_blocks})

    matches.sort(key=lambda item: (item["capacity"], item["room"]))
    return {
        "day": day,
        "requested_window": {"start_hour": start_hour, "end_hour": end_hour},
        "minimum_minutes": minimum_minutes,
        "matches": matches,
        "recommended_room": matches[0]["room"] if matches else None,
        "algorithm": "Interval subtraction against the academic timetable, then best-fit capacity",
    }