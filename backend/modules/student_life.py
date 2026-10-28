import heapq
import json
import math
from collections import defaultdict, deque
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from backend.database import get_connection

router = APIRouter(prefix="/student-life", tags=["Student Life"])


def _load_mess_history() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT day, dinner_diners, scheduled_sections FROM student_life_history ORDER BY rowid"
        ).fetchall()
    return [dict(row) for row in rows]


def _load_roommates() -> dict[str, dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT student_id, name, preferences, profile, group_name FROM roommate_profiles"
        ).fetchall()
    roommates: dict[str, dict[str, Any]] = {}
    for row in rows:
        roommates[row["student_id"]] = {
            "name": row["name"],
            "preferences": tuple(json.loads(row["preferences"])),
            "profile": tuple(json.loads(row["profile"])),
            "group": row["group_name"],
        }
    return roommates


def _load_amenity_requests() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT request_id, amenity, resident, hall, priority, slot, arrival FROM amenity_requests ORDER BY rowid"
        ).fetchall()
    return [dict(row) for row in rows]


def _load_cafeteria_menu() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT item, regular_price FROM cafeteria_menu ORDER BY rowid"
        ).fetchall()
    return [dict(row) for row in rows]


@router.get("/mess/forecast")
def forecast_mess_demand(
    scheduled_sections: int = Query(default=22, ge=0, le=60),
    window: int = Query(default=7, ge=3, le=14),
) -> dict[str, Any]:
    history = _load_mess_history()
    recent = history[-window:]
    section_adjusted_rates = [
        item["dinner_diners"] / max(item["scheduled_sections"], 1)
        for item in recent
    ]
    average_diners = sum(item["dinner_diners"] for item in recent) / len(recent)
    diners_per_section = sum(section_adjusted_rates) / len(section_adjusted_rates)
    predicted_diners = round(diners_per_section * scheduled_sections)
    forecast = [
        *history,
        {
            "day": "Forecast",
            "dinner_diners": predicted_diners,
            "scheduled_sections": scheduled_sections,
        },
    ]
    return {
        "window_days": window,
        "scheduled_sections": scheduled_sections,
        "moving_average_diners": round(average_diners),
        "predicted_diners": predicted_diners,
        "estimated_food_waste_kg": round(predicted_diners * 0.075, 1),
        "history": forecast,
        "algorithm": f"{window}-day moving average normalized by scheduled sections",
    }


ROOMMATE_FEATURES = ("quiet", "cleanliness", "sleep_schedule", "social", "study_style")


def _roommate_score(preferences: tuple[int, ...], profile: tuple[int, ...]) -> float:
    distance = sum(abs(desired - observed) for desired, observed in zip(preferences, profile))
    return round((1 - distance / (4 * len(ROOMMATE_FEATURES))) * 100, 1)


@router.get("/roommates/matches")
def create_roommate_matches() -> dict[str, Any]:
    roommates = _load_roommates()
    if not roommates:
        raise HTTPException(status_code=404, detail="Roommate data is not available yet.")

    proposers = sorted(student_id for student_id, student in roommates.items() if student["group"] == "North")
    receivers = sorted(student_id for student_id, student in roommates.items() if student["group"] == "South")
    if len(proposers) != len(receivers):
        raise HTTPException(status_code=409, detail="Gale-Shapley matching requires equally sized student groups.")

    preferences = {
        proposer: sorted(
            receivers,
            key=lambda receiver: (
                -_roommate_score(roommates[proposer]["preferences"], roommates[receiver]["profile"]),
                receiver,
            ),
        )
        for proposer in proposers
    }
    rankings = {
        receiver: {
            proposer: rank
            for rank, proposer in enumerate(
                sorted(
                    proposers,
                    key=lambda proposer: (
                        -_roommate_score(roommates[receiver]["preferences"], roommates[proposer]["profile"]),
                        proposer,
                    ),
                )
            )
        }
        for receiver in receivers
    }

    free = deque(proposers)
    next_proposal = {proposer: 0 for proposer in proposers}
    engaged: dict[str, str] = {}
    proposal_count = 0
    while free:
        proposer = free.popleft()
        receiver = preferences[proposer][next_proposal[proposer]]
        next_proposal[proposer] += 1
        proposal_count += 1
        current = engaged.get(receiver)
        if current is None or rankings[receiver][proposer] < rankings[receiver][current]:
            if current is not None:
                free.append(current)
            engaged[receiver] = proposer
        else:
            free.append(proposer)

    pairings = []
    for receiver, proposer in sorted(engaged.items()):
        first, second = roommates[proposer], roommates[receiver]
        pairings.append(
            {
                "student_a_id": proposer,
                "student_a": first["name"],
                "student_b_id": receiver,
                "student_b": second["name"],
                "a_to_b_score": _roommate_score(first["preferences"], second["profile"]),
                "b_to_a_score": _roommate_score(second["preferences"], first["profile"]),
                "compatibility_pct": round(
                    (
                        _roommate_score(first["preferences"], second["profile"])
                        + _roommate_score(second["preferences"], first["profile"])
                    ) / 2,
                    1,
                ),
            }
        )
    return {
        "pairings": pairings,
        "pair_count": len(pairings),
        "proposal_count": proposal_count,
        "preference_dimensions": list(ROOMMATE_FEATURES),
        "algorithm": "Gale-Shapley deferred acceptance with vector-distance preference rankings",
    }


AMENITY_CAPACITY = {"washing_machine": 2, "sports_court": 2}


@router.get("/amenities/schedule")
def schedule_amenities(
    amenity: str = Query(default="washing_machine", pattern="^(washing_machine|sports_court)$"),
) -> dict[str, Any]:
    requests = [item for item in _load_amenity_requests() if item["amenity"] == amenity]
    queues: dict[int, dict[str, deque[dict[str, Any]]]] = defaultdict(lambda: defaultdict(deque))
    for request in requests:
        queues[request["priority"]][request["hall"]].append(request)

    priority_queue: list[tuple[int, int, int, dict[str, Any]]] = []
    round_index = 0
    for priority in sorted(queues, reverse=True):
        halls = sorted(queues[priority])
        while any(queues[priority][hall] for hall in halls):
            for hall in halls:
                if queues[priority][hall]:
                    request = queues[priority][hall].popleft()
                    heapq.heappush(priority_queue, (-priority, round_index, request["arrival"], request))
            round_index += 1

    usage: dict[str, int] = defaultdict(int)
    capacity = AMENITY_CAPACITY[amenity]
    schedule = []
    while priority_queue:
        _, _, _, request = heapq.heappop(priority_queue)
        slot = request["slot"]
        resource_index = usage[slot]
        booked = resource_index < capacity
        schedule.append(
            {
                **request,
                "resource": f"{amenity}-{resource_index + 1}" if booked else None,
                "status": "BOOKED" if booked else "WAITLISTED",
                "queue_position": len(schedule) + 1,
            }
        )
        if booked:
            usage[slot] += 1
    return {
        "amenity": amenity,
        "capacity_per_slot": capacity,
        "booked_count": sum(item["status"] == "BOOKED" for item in schedule),
        "waitlisted_count": sum(item["status"] == "WAITLISTED" for item in schedule),
        "schedule": schedule,
        "algorithm": "Priority heap with hall-level round robin for equal-priority requests",
    }


def _erlang_c_wait(arrivals_per_minute: float, service_minutes: float, servers: int) -> tuple[float | None, float]:
    if arrivals_per_minute == 0:
        return 0.0, 0.0
    service_rate = 1 / service_minutes
    offered_load = arrivals_per_minute / service_rate
    utilization = offered_load / servers
    if utilization >= 1:
        return None, utilization

    base_sum = sum(offered_load**index / math.factorial(index) for index in range(servers))
    tail = offered_load**servers / (math.factorial(servers) * (1 - utilization))
    idle_probability = 1 / (base_sum + tail)
    wait_probability = tail * idle_probability
    wait_minutes = wait_probability / (servers * service_rate - arrivals_per_minute)
    return wait_minutes, utilization


@router.get("/cafeteria/queue")
def calculate_cafeteria_queue(
    arrivals_last_15m: int = Query(default=9, ge=0, le=500),
    open_counters: int = Query(default=4, ge=1, le=20),
    service_minutes: float = Query(default=3.0, ge=0.5, le=30),
) -> dict[str, Any]:
    arrival_rate = arrivals_last_15m / 15
    wait_minutes, utilization = _erlang_c_wait(arrival_rate, service_minutes, open_counters)
    if utilization < 0.55 and (wait_minutes or 0) <= 3:
        discount_pct, pricing_state = 15, "OFF_PEAK_PROMOTION"
    elif utilization < 0.75 and (wait_minutes or 0) <= 6:
        discount_pct, pricing_state = 8, "MODERATE_FLOW_PROMOTION"
    else:
        discount_pct, pricing_state = 0, "PEAK_PRICE"
    menu = [
        {
            "item": item["item"],
            "regular_price": item["regular_price"],
            "discount_pct": discount_pct,
            "dynamic_price": round(item["regular_price"] * (1 - discount_pct / 100), 2),
        }
        for item in _load_cafeteria_menu()
    ]
    return {
        "arrivals_last_15m": arrivals_last_15m,
        "open_counters": open_counters,
        "service_minutes": service_minutes,
        "utilization_pct": round(utilization * 100, 1),
        "estimated_wait_minutes": round(wait_minutes, 1) if wait_minutes is not None else None,
        "queue_state": "OVER_CAPACITY" if wait_minutes is None else "STABLE",
        "pricing_state": pricing_state,
        "discount_pct": discount_pct,
        "menu": menu,
        "algorithm": "M/M/c Erlang-C waiting-time estimate with utilization-based dynamic pricing",
    }