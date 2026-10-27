import hashlib
import heapq
import json
from collections import defaultdict, deque
from typing import Any

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(tags=["Academics"])

DEPARTMENTS = ["CSE", "ECE", "MECH", "IT", "CIVIL"]
PREREQUISITES = {
    "CS101": [],
    "CS201": ["CS101"],
    "CS301": ["CS201"],
    "CS302": ["CS201"],
    "CS401": ["CS301"],
    "CS402": ["CS302"],
}
ATTENDANCE = [
    {"course": "CS101", "present": 43, "total": 48},
    {"course": "CS201", "present": 39, "total": 46},
    {"course": "MA201", "present": 31, "total": 45},
    {"course": "CS301", "present": 42, "total": 44},
]
WAITLIST = [
    {"student": "2501330101", "course": "CS201", "priority": 5, "semester": 3},
    {"student": "2501330128", "course": "CS201", "priority": 3, "semester": 2},
    {"student": "2501330140", "course": "CS201", "priority": 4, "semester": 3},
    {"student": "2501330225", "course": "CS301", "priority": 5, "semester": 5},
    {"student": "2501330230", "course": "CS301", "priority": 4, "semester": 4},
]
TIMETABLE_COURSES = ["CS101", "CS201", "CS202", "MA201", "CS301", "EC201"]
TIMETABLE_CONFLICTS = [
    ("CS101", "CS201"),
    ("CS101", "MA201"),
    ("CS201", "CS202"),
    ("CS201", "CS301"),
    ("CS202", "MA201"),
    ("CS202", "EC201"),
    ("MA201", "CS301"),
    ("CS301", "EC201"),
]
TRANSCRIPTS = {
    "2501331930010": {
        "roll_no": "2501331930010",
        "cgpa": 8.85,
        "status": "VERIFIED",
    }
}


@router.get("/exam/seating")
def generate_optimal_seating(
    rows: int = Query(default=4, ge=2, le=12),
    cols: int = Query(default=4, ge=2, le=12),
) -> dict[str, Any]:
    """Arrange departments in a repeating pattern to avoid adjacent conflicts."""
    grid: list[list[dict[str, str]]] = []
    student_index = 0
    for row_index in range(rows):
        row: list[dict[str, str]] = []
        for col_index in range(cols):
            branch = DEPARTMENTS[(row_index + col_index) % len(DEPARTMENTS)]
            row.append(
                {
                    "id": f"250133{student_index:04d}",
                    "branch": branch,
                    "paper": "Set A" if (row_index + col_index) % 2 == 0 else "Set B",
                }
            )
            student_index += 1
        grid.append(row)
    return {"status": "OPTIMIZED", "dimensions": f"{rows}x{cols}", "matrix": grid}


@router.get("/academics/prereq-impact")
def analyze_prerequisite_impact(dropped: str = "CS201") -> dict[str, Any]:
    if dropped not in PREREQUISITES:
        raise HTTPException(status_code=404, detail="Course not found in prerequisite graph")

    blocked: list[str] = []
    queue = deque([dropped])
    visited = {dropped}
    while queue:
        prerequisite = queue.popleft()
        for course, requirements in PREREQUISITES.items():
            if prerequisite in requirements and course not in visited:
                visited.add(course)
                blocked.append(course)
                queue.append(course)
    return {
        "target": dropped,
        "cascading_blocks": blocked,
        "risk_level": "CRITICAL" if len(blocked) > 2 else "WARNING",
        "algorithm": "Breadth-first search over the prerequisite DAG",
    }


@router.get("/verify/transcript")
def verify_transcript(roll_no: str = Query(default="2501331930010", min_length=5, max_length=20)) -> dict[str, Any]:
    record = TRANSCRIPTS.get(roll_no)
    if record is None:
        return {
            "roll_no": roll_no,
            "signature": None,
            "authentic": False,
            "message": "No transcript exists for this roll number.",
            "algorithm": "SHA-256",
        }
    signature = hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()
    return {**record, "signature": signature, "authentic": True, "algorithm": "SHA-256"}


@router.get("/academics/attendance")
def get_attendance_summary() -> dict[str, Any]:
    courses = [
        {**course, "attendance_pct": round(course["present"] / course["total"] * 100, 1)}
        for course in ATTENDANCE
    ]
    overall = sum(item["present"] for item in ATTENDANCE) / sum(
        item["total"] for item in ATTENDANCE
    ) * 100
    return {
        "overall_attendance_pct": round(overall, 1),
        "below_threshold": [item["course"] for item in courses if item["attendance_pct"] < 75],
        "courses": courses,
        "algorithm": "Hash-map aggregation by course",
    }


@router.get("/academics/waitlist")
def allocate_waitlist(
    course: str = Query(default="CS201", min_length=3, max_length=10),
    seats: int = Query(default=2, ge=1, le=100),
) -> dict[str, Any]:
    candidates = [item for item in WAITLIST if item["course"] == course]
    if not candidates:
        raise HTTPException(status_code=404, detail="No students are waiting for this course")

    priority_queue: list[tuple[int, int, str, dict[str, Any]]] = []
    for student in candidates:
        heapq.heappush(
            priority_queue,
            (-student["priority"], student["semester"], student["student"], student),
        )
    admitted = [heapq.heappop(priority_queue)[3] for _ in range(min(seats, len(priority_queue)))]
    return {
        "course": course,
        "seats_available": seats,
        "admitted": admitted,
        "remaining_waitlist": len(priority_queue),
        "algorithm": "Priority queue: priority, then earliest semester",
    }


@router.get("/academics/timetable")
def generate_timetable(slots: int = Query(default=4, ge=2, le=8)) -> dict[str, Any]:
    graph: dict[str, set[str]] = defaultdict(set)
    for first, second in TIMETABLE_CONFLICTS:
        graph[first].add(second)
        graph[second].add(first)

    assignments: dict[str, int] = {}
    for course in sorted(TIMETABLE_COURSES, key=lambda item: len(graph[item]), reverse=True):
        used = {assignments[neighbor] for neighbor in graph[course] if neighbor in assignments}
        available = next((slot for slot in range(1, slots + 1) if slot not in used), None)
        if available is None:
            raise HTTPException(
                status_code=422,
                detail=f"Cannot schedule all courses in {slots} slots; add another slot.",
            )
        assignments[course] = available

    return {
        "slots": slots,
        "schedule": [{"course": course, "slot": slot} for course, slot in assignments.items()],
        "conflict_edges": len(TIMETABLE_CONFLICTS),
        "algorithm": "Degree-ordered greedy graph coloring",
    }