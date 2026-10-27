import hashlib
import heapq
import math
import secrets
from datetime import datetime, timezone
from typing import Any

from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(tags=["Campus Operational Tools"])

MENU = [
    {"item": "Veg rice bowl", "regular_price": 90},
    {"item": "Paneer wrap", "regular_price": 120},
    {"item": "Chicken meal box", "regular_price": 150},
    {"item": "Fruit and yogurt cup", "regular_price": 65},
]


def _mmc_wait_minutes(arrivals_per_minute: float, service_minutes: float, servers: int) -> tuple[float | None, float]:
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


@router.get("/operations/cafeteria-queue")
def estimate_cafeteria_queue(
    arrivals_last_15m: int = Query(default=9, ge=0, le=500),
    cashiers: int = Query(default=4, ge=1, le=20),
    service_minutes: float = Query(default=3.0, ge=0.5, le=30),
) -> dict[str, Any]:
    arrival_rate = arrivals_last_15m / 15
    wait_minutes, utilization = _mmc_wait_minutes(arrival_rate, service_minutes, cashiers)
    if utilization < 0.55 and (wait_minutes or 0) <= 3:
        discount_pct = 15
        pricing_state = "OFF_PEAK_PROMOTION"
    elif utilization < 0.75 and (wait_minutes or 0) <= 6:
        discount_pct = 8
        pricing_state = "MODERATE_FLOW_PROMOTION"
    else:
        discount_pct = 0
        pricing_state = "PEAK_PRICE"

    menu = [
        {
            **item,
            "discount_pct": discount_pct,
            "dynamic_price": round(item["regular_price"] * (1 - discount_pct / 100), 2),
            "estimated_wait_minutes": round(wait_minutes, 1) if wait_minutes is not None else None,
        }
        for item in MENU
    ]
    return {
        "arrivals_last_15m": arrivals_last_15m,
        "cashiers": cashiers,
        "service_minutes": service_minutes,
        "utilization_pct": round(utilization * 100, 1),
        "estimated_wait_minutes": round(wait_minutes, 1) if wait_minutes is not None else None,
        "queue_state": "OVER_CAPACITY" if wait_minutes is None else "STABLE",
        "pricing_state": pricing_state,
        "discount_pct": discount_pct,
        "menu": menu,
        "algorithm": "M/M/c Erlang-C queue estimate with utilization-triggered off-peak pricing",
    }


RING_SIZE = 4
RING_PRIVATE_KEYS = [
    rsa.generate_private_key(public_exponent=65537, key_size=2048)
    for _ in range(RING_SIZE)
]
RING_PUBLIC_KEYS = [key.public_key().public_numbers() for key in RING_PRIVATE_KEYS]
ANONYMOUS_POSTS: list[dict[str, Any]] = []


def _ring_challenge(message: bytes, value: int) -> int:
    challenge_input = message + value.to_bytes((value.bit_length() + 7) // 8 or 1, "big")
    return int.from_bytes(hashlib.sha256(challenge_input).digest(), "big")


def _create_ring_signature(message: bytes, signer_index: int) -> dict[str, Any]:
    responses: list[int | None] = [None] * RING_SIZE
    challenges: list[int | None] = [None] * RING_SIZE
    signer_key = RING_PRIVATE_KEYS[signer_index]
    signer_numbers = signer_key.private_numbers()
    signer_public = signer_numbers.public_numbers
    nonce = secrets.randbits(256)

    next_index = (signer_index + 1) % RING_SIZE
    challenges[next_index] = _ring_challenge(message, nonce)
    index = next_index
    while index != signer_index:
        public_numbers = RING_PUBLIC_KEYS[index]
        modulus = public_numbers.n
        response = secrets.randbelow(modulus - 1) + 1
        responses[index] = response
        transformed = pow(response, public_numbers.e, modulus)
        challenges[(index + 1) % RING_SIZE] = _ring_challenge(
            message,
            transformed ^ challenges[index],
        )
        index = (index + 1) % RING_SIZE

    signer_challenge = challenges[signer_index]
    if signer_challenge is None:
        raise RuntimeError("Ring signature challenge chain did not close.")
    responses[signer_index] = pow(nonce ^ signer_challenge, signer_numbers.d, signer_public.n)
    initial_challenge = challenges[0]
    if initial_challenge is None or any(response is None for response in responses):
        raise RuntimeError("Ring signature generation was incomplete.")
    return {
        "initial_challenge": str(initial_challenge),
        "responses": [str(response) for response in responses],
        "ring_fingerprint": hashlib.sha256(
            b"".join(number.n.to_bytes((number.n.bit_length() + 7) // 8, "big") for number in RING_PUBLIC_KEYS)
        ).hexdigest(),
    }


def _verify_ring_signature(message: bytes, signature: dict[str, Any]) -> bool:
    try:
        challenge = int(signature["initial_challenge"])
        responses = [int(value) for value in signature["responses"]]
        if len(responses) != RING_SIZE:
            return False
        for response, public_numbers in zip(responses, RING_PUBLIC_KEYS):
            transformed = pow(response, public_numbers.e, public_numbers.n)
            challenge = _ring_challenge(message, transformed ^ challenge)
        return str(challenge) == signature["initial_challenge"]
    except (KeyError, TypeError, ValueError):
        return False


class SupportPost(BaseModel):
    message: str = Field(min_length=8, max_length=2000)


@router.get("/community/support/ring")
def get_support_ring() -> dict[str, Any]:
    public_members = [
        {
            "member": f"Verified peer {index + 1}",
            "modulus": str(public_key.n),
            "exponent": public_key.e,
        }
        for index, public_key in enumerate(RING_PUBLIC_KEYS)
    ]
    return {
        "ring_size": RING_SIZE,
        "members": public_members,
        "algorithm": "RSA-based Rivest-Shamir-Tauman ring signature; public keys only",
    }


@router.post("/community/support/posts")
def create_anonymous_support_post(request: SupportPost) -> dict[str, Any]:
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="A support message cannot be blank.")
    signer_index = secrets.randbelow(RING_SIZE)
    signature = _create_ring_signature(message.encode("utf-8"), signer_index)
    verified = _verify_ring_signature(message.encode("utf-8"), signature)
    if not verified:
        raise HTTPException(status_code=500, detail="The anonymous ring signature could not be verified.")

    post = {
        "post_id": f"SUP-{secrets.token_hex(4).upper()}",
        "message": message,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "verified_member": True,
        "author": "Anonymous",
        "signature": signature,
    }
    ANONYMOUS_POSTS.append(post)
    return {
        **post,
        "identity_disclosed": False,
        "algorithm": "RSA ring signature verified against the campus peer ring; author identity is omitted",
    }


@router.get("/community/support/posts")
def list_anonymous_support_posts() -> dict[str, Any]:
    return {
        "posts": ANONYMOUS_POSTS,
        "post_count": len(ANONYMOUS_POSTS),
        "algorithm": "In-memory anonymous peer board; no author identifiers are stored",
    }


INDOOR_GRID = [
    "###############",
    "#S....#......A#",
    "#.##..#.####..#",
    "#....##......##",
    "####....###...#",
    "#......#......#",
    "#.####.#.###..#",
    "#......#...#..#",
    "#..##......#..#",
    "#......####...#",
    "#..#.......#..#",
    "###############",
]
CLASSROOMS = {
    "A-101": (1, 13),
    "A-204": (3, 12),
    "B-110": (5, 13),
    "C-302": (9, 3),
}
INDOOR_START = (1, 1)


def _astar(start: tuple[int, int], goal: tuple[int, int]) -> list[tuple[int, int]]:
    rows, columns = len(INDOOR_GRID), len(INDOOR_GRID[0])
    if not (0 <= start[0] < rows and 0 <= start[1] < columns):
        raise HTTPException(status_code=422, detail="Start position is outside the indoor map.")
    if INDOOR_GRID[start[0]][start[1]] == "#":
        raise HTTPException(status_code=422, detail="Start position is blocked by a wall.")

    frontier = [(0, 0, start)]
    came_from: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    path_cost = {start: 0}
    while frontier:
        _, current_cost, current = heapq.heappop(frontier)
        if current == goal:
            break
        if current_cost != path_cost[current]:
            continue
        for row_delta, column_delta in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            neighbor = current[0] + row_delta, current[1] + column_delta
            row, column = neighbor
            if not (0 <= row < rows and 0 <= column < columns) or INDOOR_GRID[row][column] == "#":
                continue
            candidate_cost = current_cost + 1
            if candidate_cost < path_cost.get(neighbor, math.inf):
                path_cost[neighbor] = candidate_cost
                came_from[neighbor] = current
                heuristic = abs(row - goal[0]) + abs(column - goal[1])
                heapq.heappush(frontier, (candidate_cost + heuristic, candidate_cost, neighbor))

    if goal not in came_from:
        raise HTTPException(status_code=404, detail="No walkable route to the selected classroom.")
    path = []
    current: tuple[int, int] | None = goal
    while current is not None:
        path.append(current)
        current = came_from[current]
    path.reverse()
    return path


@router.get("/navigation/indoor")
def find_indoor_route(
    classroom_id: str = Query(default="A-101", pattern="^(A-101|A-204|B-110|C-302)$"),
    start_row: int = Query(default=1, ge=0, le=11),
    start_column: int = Query(default=1, ge=0, le=14),
) -> dict[str, Any]:
    goal = CLASSROOMS[classroom_id]
    path = _astar((start_row, start_column), goal)
    route_steps = [
        {"step": index, "row": row, "column": column}
        for index, (row, column) in enumerate(path)
    ]
    return {
        "classroom_id": classroom_id,
        "start": {"row": start_row, "column": start_column},
        "destination": {"row": goal[0], "column": goal[1]},
        "distance_steps": len(path) - 1,
        "route": route_steps,
        "map": [list(row) for row in INDOOR_GRID],
        "algorithm": "A* search with Manhattan distance over a four-direction indoor grid",
    }


STUDENT_PROFILES = {
    "STU-401": {"cgpa": 3.78, "extracurriculars": 4, "annual_income": 320000, "program": "Computer Science", "first_generation": True},
    "STU-402": {"cgpa": 3.42, "extracurriculars": 2, "annual_income": 780000, "program": "Design", "first_generation": False},
    "STU-403": {"cgpa": 3.91, "extracurriculars": 1, "annual_income": 260000, "program": "Computer Science", "first_generation": False},
    "STU-404": {"cgpa": 3.25, "extracurriculars": 5, "annual_income": 410000, "program": "Mechanical Engineering", "first_generation": True},
}
SCHOLARSHIPS = [
    {"name": "Academic Excellence Grant", "minimum_cgpa": 3.7, "minimum_extracurriculars": 0, "maximum_income": None, "programs": []},
    {"name": "Community Leadership Award", "minimum_cgpa": 3.2, "minimum_extracurriculars": 3, "maximum_income": None, "programs": []},
    {"name": "First Generation Support Grant", "minimum_cgpa": 3.0, "minimum_extracurriculars": 0, "maximum_income": 500000, "programs": []},
    {"name": "Future Technologists Scholarship", "minimum_cgpa": 3.5, "minimum_extracurriculars": 1, "maximum_income": 600000, "programs": ["Computer Science"]},
]


@router.get("/financial-aid/scholarship-matches")
def match_scholarships(
    student_id: str = Query(default="STU-401", pattern="^STU-40[1-4]$"),
) -> dict[str, Any]:
    student = STUDENT_PROFILES.get(student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student profile not found.")

    matches = []
    for scholarship in SCHOLARSHIPS:
        checks = [
            {"requirement": "Minimum CGPA", "met": student["cgpa"] >= scholarship["minimum_cgpa"], "student_value": student["cgpa"], "required_value": scholarship["minimum_cgpa"]},
            {"requirement": "Extracurricular participation", "met": student["extracurriculars"] >= scholarship["minimum_extracurriculars"], "student_value": student["extracurriculars"], "required_value": scholarship["minimum_extracurriculars"]},
            {"requirement": "Income threshold", "met": scholarship["maximum_income"] is None or student["annual_income"] <= scholarship["maximum_income"], "student_value": student["annual_income"], "required_value": scholarship["maximum_income"]},
            {"requirement": "Eligible program", "met": not scholarship["programs"] or student["program"] in scholarship["programs"], "student_value": student["program"], "required_value": scholarship["programs"] or "Any"},
        ]
        matches.append(
            {
                "scholarship": scholarship["name"],
                "eligible": all(check["met"] for check in checks),
                "requirements_met": sum(check["met"] for check in checks),
                "requirements_total": len(checks),
                "checks": checks,
                "missing_requirements": [check["requirement"] for check in checks if not check["met"]],
            }
        )
    matches.sort(key=lambda item: (-item["eligible"], -item["requirements_met"], item["scholarship"]))
    return {
        "student_id": student_id,
        "student_profile": student,
        "eligible_count": sum(item["eligible"] for item in matches),
        "matches": matches,
        "algorithm": "Rule-based evaluation of CGPA, extracurriculars, income, and program requirements",
    }