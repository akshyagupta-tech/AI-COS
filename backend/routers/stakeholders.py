import heapq
import math
from collections import defaultdict, deque
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.routers.campus_life import ASSETS, HARDWARE_LEDGER, ROOM_CAPACITIES, WASHROOMS
from backend.routers.hardware_os import LABS, SHARED_NOTICES, SENSOR_READINGS

router = APIRouter(tags=["Campus Stakeholders"])

STUDENTS = {
    "STU-101": {"name": "Aanya", "skills": {"Python", "AI", "data science"}, "available": {"12:00", "12:15", "15:00"}},
    "STU-102": {"name": "Kabir", "skills": {"product", "design", "career planning"}, "available": {"12:15", "15:00"}},
    "STU-103": {"name": "Meera", "skills": {"robotics", "AI", "Python"}, "available": {"12:00", "14:00"}},
    "STU-104": {"name": "Arjun", "skills": {"research", "data science", "career planning"}, "available": {"12:00", "15:00"}},
    "STU-105": {"name": "Zoya", "skills": {"design", "product", "entrepreneurship"}, "available": {"12:15", "15:00", "15:15"}},
    "STU-106": {"name": "Ishaan", "skills": {"Python", "robotics", "research"}, "available": {"12:00", "14:00", "15:00"}},
}
MENTORS = {
    "ALU-201": {"name": "Nisha Rao", "role": "Alumni · Data Engineer", "skills": {"Python", "data science", "AI"}, "available": {"12:00", "12:15"}},
    "ALU-202": {"name": "Dev Malhotra", "role": "Alumni · Product Lead", "skills": {"product", "career planning"}, "available": {"12:15", "15:00"}},
    "ALU-203": {"name": "Dr. Sen", "role": "Past teacher · Robotics", "skills": {"robotics", "AI", "research"}, "available": {"12:00", "14:00"}},
    "ALU-204": {"name": "Leena Das", "role": "Alumni · Founder", "skills": {"design", "entrepreneurship", "product"}, "available": {"15:00", "15:15"}},
    "ALU-205": {"name": "Prof. Iyer", "role": "Past teacher · Research", "skills": {"research", "data science", "Python"}, "available": {"12:00", "15:00"}},
}


class MentorshipRequest(BaseModel):
    student_ids: list[str] = Field(min_length=1, max_length=20)


def _hopcroft_karp(
    graph: dict[str, list[tuple[str, str]]],
) -> tuple[dict[str, tuple[str, str]], dict[tuple[str, str], str]]:
    unmatched_distance = math.inf
    pair_left: dict[str, tuple[str, str] | None] = {student: None for student in graph}
    pair_right: dict[tuple[str, str], str] = {}
    distances: dict[str, float] = {}

    def build_layers() -> bool:
        queue: deque[str] = deque()
        for student, matched_slot in pair_left.items():
            if matched_slot is None:
                distances[student] = 0
                queue.append(student)
            else:
                distances[student] = unmatched_distance
        shortest_augmenting_path = unmatched_distance
        while queue:
            student = queue.popleft()
            if distances[student] >= shortest_augmenting_path:
                continue
            for mentor_slot in graph[student]:
                paired_student = pair_right.get(mentor_slot)
                if paired_student is None:
                    shortest_augmenting_path = distances[student] + 1
                elif distances[paired_student] == unmatched_distance:
                    distances[paired_student] = distances[student] + 1
                    queue.append(paired_student)
        return shortest_augmenting_path != unmatched_distance

    def augment(student: str) -> bool:
        for mentor_slot in graph[student]:
            paired_student = pair_right.get(mentor_slot)
            if paired_student is None or (
                distances.get(paired_student, unmatched_distance) == distances[student] + 1
                and augment(paired_student)
            ):
                pair_left[student] = mentor_slot
                pair_right[mentor_slot] = student
                return True
        distances[student] = unmatched_distance
        return False

    while build_layers():
        for student, matched_slot in pair_left.items():
            if matched_slot is None:
                augment(student)
    return (
        {student: slot for student, slot in pair_left.items() if slot is not None},
        pair_right,
    )


@router.post("/stakeholders/alumni/mentorship-matches")
def match_alumni_mentors(request: MentorshipRequest) -> dict[str, Any]:
    unknown_students = set(request.student_ids) - STUDENTS.keys()
    if unknown_students:
        raise HTTPException(status_code=404, detail=f"Unknown student IDs: {', '.join(sorted(unknown_students))}")

    graph: dict[str, list[tuple[str, str]]] = {}
    edge_skills: dict[tuple[str, tuple[str, str]], list[str]] = {}
    for student_id in request.student_ids:
        student = STUDENTS[student_id]
        graph[student_id] = []
        for mentor_id, mentor in MENTORS.items():
            shared_skills = sorted(student["skills"] & mentor["skills"])
            shared_slots = sorted(student["available"] & mentor["available"])
            for slot in shared_slots if shared_skills else []:
                mentor_slot = (mentor_id, slot)
                graph[student_id].append(mentor_slot)
                edge_skills[(student_id, mentor_slot)] = shared_skills

    matched, _ = _hopcroft_karp(graph)
    matches = []
    for student_id, (mentor_id, slot) in matched.items():
        student = STUDENTS[student_id]
        mentor = MENTORS[mentor_id]
        matches.append(
            {
                "student_id": student_id,
                "student_name": student["name"],
                "mentor_id": mentor_id,
                "mentor_name": mentor["name"],
                "mentor_role": mentor["role"],
                "slot": slot,
                "duration_minutes": 15,
                "skill_overlap": edge_skills[(student_id, (mentor_id, slot))],
                "skill_overlap_count": len(edge_skills[(student_id, (mentor_id, slot))]),
            }
        )
    matches.sort(key=lambda item: item["student_id"])
    unmatched = sorted(set(request.student_ids) - matched.keys())
    return {
        "matches": matches,
        "unmatched_students": unmatched,
        "students_requested": len(request.student_ids),
        "matches_found": len(matches),
        "graph_edges": sum(len(edges) for edges in graph.values()),
        "algorithm": "Hopcroft-Karp maximum bipartite matching over skill-compatible mentor-slot vertices",
    }


COMMUTERS = [
    {"person_id": "DS-101", "name": "Aditi", "role": "Day Scholar", "latitude": 28.4741, "longitude": 77.5048},
    {"person_id": "DS-102", "name": "Rohan", "role": "Day Scholar", "latitude": 28.4782, "longitude": 77.5094},
    {"person_id": "DS-103", "name": "Simran", "role": "Day Scholar", "latitude": 28.4812, "longitude": 77.5011},
    {"person_id": "DS-104", "name": "Kabir", "role": "Day Scholar", "latitude": 28.5163, "longitude": 77.3918},
    {"person_id": "DS-105", "name": "Tara", "role": "Day Scholar", "latitude": 28.5207, "longitude": 77.3972},
    {"person_id": "DS-106", "name": "Dev", "role": "Day Scholar", "latitude": 28.5156, "longitude": 77.4015},
    {"person_id": "FC-201", "name": "Prof. Mehta", "role": "Faculty", "latitude": 28.4623, "longitude": 77.5162},
    {"person_id": "FC-202", "name": "Dr. Ali", "role": "Faculty", "latitude": 28.5241, "longitude": 77.3861},
    {"person_id": "FC-203", "name": "Prof. Rao", "role": "Faculty", "latitude": 28.4713, "longitude": 77.4974},
]


def _distance_km(first: dict[str, float], second: dict[str, float]) -> float:
    earth_radius_km = 6371.0
    lat1, lat2 = math.radians(first["latitude"]), math.radians(second["latitude"])
    delta_lat = lat2 - lat1
    delta_lon = math.radians(second["longitude"] - first["longitude"])
    haversine = math.sin(delta_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    return 2 * earth_radius_km * math.asin(math.sqrt(haversine))


@router.get("/stakeholders/carpools")
def cluster_carpools(
    clusters: int = Query(default=3, ge=2, le=5),
    iterations: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    points = [{**person, "latitude": float(person["latitude"]), "longitude": float(person["longitude"])} for person in COMMUTERS]
    cluster_count = min(clusters, len(points))
    seed_indexes = [round(index * (len(points) - 1) / (cluster_count - 1)) for index in range(cluster_count)]
    centroids = [{"latitude": points[index]["latitude"], "longitude": points[index]["longitude"]} for index in seed_indexes]
    labels = [-1] * len(points)

    for _ in range(iterations):
        new_labels = [
            min(range(cluster_count), key=lambda cluster_id: _distance_km(point, centroids[cluster_id]))
            for point in points
        ]
        groups = [[points[index] for index, label in enumerate(new_labels) if label == cluster_id] for cluster_id in range(cluster_count)]
        updated_centroids = []
        for cluster_id, group in enumerate(groups):
            if group:
                updated_centroids.append(
                    {
                        "latitude": sum(point["latitude"] for point in group) / len(group),
                        "longitude": sum(point["longitude"] for point in group) / len(group),
                    }
                )
            else:
                updated_centroids.append(centroids[cluster_id])
        converged = new_labels == labels and updated_centroids == centroids
        labels, centroids = new_labels, updated_centroids
        if converged:
            break

    cluster_results = []
    for cluster_id in range(cluster_count):
        members = []
        for index, person in enumerate(points):
            if labels[index] == cluster_id:
                members.append(
                    {
                        **person,
                        "cluster": f"Carpool {cluster_id + 1}",
                        "distance_to_pickup_km": round(_distance_km(person, centroids[cluster_id]), 2),
                    }
                )
        cluster_results.append(
            {
                "cluster": f"Carpool {cluster_id + 1}",
                "pickup_latitude": round(centroids[cluster_id]["latitude"], 6),
                "pickup_longitude": round(centroids[cluster_id]["longitude"], 6),
                "member_count": len(members),
                "members": members,
            }
        )

    return {
        "clusters_requested": cluster_count,
        "commuters_clustered": len(points),
        "clusters": cluster_results,
        "members": [member for cluster in cluster_results for member in cluster["members"]],
        "algorithm": "Deterministic geospatial K-means using Haversine assignment and local-coordinate centroids",
    }


FACULTY = {
    "FAC-01": {"name": "Dr. A. Mehta", "department": "Computing", "qualified": {"Computer Science", "Programming", "AI"}, "load": 4, "busy": {("Monday", "09:00"), ("Tuesday", "10:00")}},
    "FAC-02": {"name": "Prof. S. Rao", "department": "Computing", "qualified": {"Computer Science", "Programming"}, "load": 3, "busy": {("Monday", "09:00"), ("Wednesday", "11:00")}},
    "FAC-03": {"name": "Dr. P. Iyer", "department": "Mathematics", "qualified": {"Mathematics", "Physics"}, "load": 5, "busy": {("Monday", "09:00"), ("Thursday", "10:00")}},
    "FAC-04": {"name": "Prof. N. Sen", "department": "Sciences", "qualified": {"Physics", "Mathematics"}, "load": 2, "busy": {("Monday", "09:00"), ("Tuesday", "09:00")}},
    "FAC-05": {"name": "Dr. K. Ali", "department": "Computing", "qualified": {"AI", "Computer Science"}, "load": 2, "busy": {("Monday", "10:00"), ("Friday", "09:00")}},
    "FAC-06": {"name": "Prof. R. Das", "department": "Sciences", "qualified": {"Physics"}, "load": 3, "busy": {("Monday", "10:00"), ("Friday", "10:00")}},
    "FAC-07": {"name": "Dr. M. Kapoor", "department": "Computing", "qualified": {"Computer Science", "Programming"}, "load": 1, "busy": {("Tuesday", "11:00")}},
}
CLASS_SECTIONS = [
    {"section_id": "CS101-01", "faculty_id": "FAC-01", "course": "CS101", "subject": "Computer Science"},
    {"section_id": "CS201-01", "faculty_id": "FAC-02", "course": "CS201", "subject": "Computer Science"},
    {"section_id": "MA101-01", "faculty_id": "FAC-03", "course": "MA101", "subject": "Mathematics"},
    {"section_id": "PH101-01", "faculty_id": "FAC-04", "course": "PH101", "subject": "Physics"},
    {"section_id": "AI301-01", "faculty_id": "FAC-05", "course": "AI301", "subject": "AI"},
    {"section_id": "PH201-01", "faculty_id": "FAC-06", "course": "PH201", "subject": "Physics"},
]


class SubstitutionRequest(BaseModel):
    absent_faculty_ids: list[str] = Field(min_length=1, max_length=7)
    day: str = Field(default="Monday", pattern="^(Monday|Tuesday|Wednesday|Thursday|Friday)$")
    time_slot: str = Field(default="09:00", pattern="^(09:00|10:00|11:00|12:00|13:00|14:00|15:00)$")


@router.post("/stakeholders/faculty/substitutions")
def find_faculty_substitutions(request: SubstitutionRequest) -> dict[str, Any]:
    unknown = set(request.absent_faculty_ids) - FACULTY.keys()
    if unknown:
        raise HTTPException(status_code=404, detail=f"Unknown faculty IDs: {', '.join(sorted(unknown))}")
    absent_ids = set(request.absent_faculty_ids)
    absences = [
        section for section in CLASS_SECTIONS
        if section["faculty_id"] in absent_ids
        and (request.day, request.time_slot) in FACULTY[section["faculty_id"]]["busy"]
    ]
    if not absences:
        raise HTTPException(status_code=422, detail="Selected faculty have no seeded class in that time slot.")

    domains: dict[str, list[str]] = {}
    for section in absences:
        domains[section["section_id"]] = sorted(
            [
                faculty_id for faculty_id, faculty in FACULTY.items()
                if faculty_id not in absent_ids
                and section["subject"] in faculty["qualified"]
                and (request.day, request.time_slot) not in faculty["busy"]
            ],
            key=lambda faculty_id: (FACULTY[faculty_id]["load"], faculty_id),
        )

    best_assignment: dict[str, str] = {}

    def solve(remaining: set[str], assigned: dict[str, str], used_faculty: set[str]) -> None:
        nonlocal best_assignment
        if len(assigned) > len(best_assignment):
            best_assignment = assigned.copy()
        if not remaining or len(assigned) + len(remaining) <= len(best_assignment):
            return
        section_id = min(
            remaining,
            key=lambda candidate: sum(faculty_id not in used_faculty for faculty_id in domains[candidate]),
        )
        next_remaining = remaining - {section_id}
        for faculty_id in domains[section_id]:
            if faculty_id not in used_faculty:
                assigned[section_id] = faculty_id
                solve(next_remaining, assigned, used_faculty | {faculty_id})
                assigned.pop(section_id)
        solve(next_remaining, assigned, used_faculty)

    solve({section["section_id"] for section in absences}, {}, set())
    sections_by_id = {section["section_id"]: section for section in absences}
    substitutions = [
        {
            "section_id": section_id,
            "course": sections_by_id[section_id]["course"],
            "subject": sections_by_id[section_id]["subject"],
            "absent_faculty": FACULTY[sections_by_id[section_id]["faculty_id"]]["name"],
            "proxy_faculty_id": faculty_id,
            "proxy_faculty": FACULTY[faculty_id]["name"],
            "proxy_department": FACULTY[faculty_id]["department"],
            "proxy_current_load": FACULTY[faculty_id]["load"],
        }
        for section_id, faculty_id in best_assignment.items()
    ]
    return {
        "day": request.day,
        "time_slot": request.time_slot,
        "substitutions": substitutions,
        "uncovered_sections": sorted(set(sections_by_id) - best_assignment.keys()),
        "sections_to_cover": len(absences),
        "sections_covered": len(substitutions),
        "algorithm": "CSP backtracking with MRV variable ordering, subject eligibility, availability, and all-different proxies",
    }


AMENITY_BOOKINGS = [
    {"booking_id": "HB-101", "amenity": "washing_machine", "resident_id": "H-A101", "block": "A", "priority": 1, "requested_slot": "07:00", "arrival": 1},
    {"booking_id": "HB-102", "amenity": "washing_machine", "resident_id": "H-B204", "block": "B", "priority": 1, "requested_slot": "07:00", "arrival": 2},
    {"booking_id": "HB-103", "amenity": "washing_machine", "resident_id": "H-C310", "block": "C", "priority": 2, "requested_slot": "07:00", "arrival": 3},
    {"booking_id": "HB-104", "amenity": "washing_machine", "resident_id": "H-A119", "block": "A", "priority": 1, "requested_slot": "07:00", "arrival": 4},
    {"booking_id": "HB-105", "amenity": "washing_machine", "resident_id": "H-D021", "block": "D", "priority": 0, "requested_slot": "07:00", "arrival": 5},
    {"booking_id": "HB-201", "amenity": "sports_court", "resident_id": "H-B101", "block": "B", "priority": 1, "requested_slot": "17:00", "arrival": 1},
    {"booking_id": "HB-202", "amenity": "sports_court", "resident_id": "H-C118", "block": "C", "priority": 2, "requested_slot": "17:00", "arrival": 2},
    {"booking_id": "HB-203", "amenity": "sports_court", "resident_id": "H-A208", "block": "A", "priority": 1, "requested_slot": "17:00", "arrival": 3},
    {"booking_id": "HB-204", "amenity": "sports_court", "resident_id": "H-D402", "block": "D", "priority": 1, "requested_slot": "17:00", "arrival": 4},
]
AMENITY_CAPACITY = {"washing_machine": 2, "sports_court": 2}


@router.get("/stakeholders/hostel/amenity-schedule")
def schedule_hostel_amenities(
    amenity: str = Query(default="washing_machine", pattern="^(washing_machine|sports_court)$"),
) -> dict[str, Any]:
    requests = [booking for booking in AMENITY_BOOKINGS if booking["amenity"] == amenity]
    by_priority: dict[int, dict[str, deque[dict[str, Any]]]] = defaultdict(lambda: defaultdict(deque))
    for booking in requests:
        by_priority[booking["priority"]][booking["block"]].append(booking)

    fair_queue: list[tuple[int, int, int, dict[str, Any]]] = []
    turn = 0
    for priority in sorted(by_priority, reverse=True):
        block_queues = by_priority[priority]
        blocks = sorted(block_queues)
        while any(block_queues[block] for block in blocks):
            for block in blocks:
                if block_queues[block]:
                    booking = block_queues[block].popleft()
                    heapq.heappush(fair_queue, (-priority, turn, booking["arrival"], booking))
            turn += 1

    slot_usage: dict[str, int] = defaultdict(int)
    schedule = []
    capacity = AMENITY_CAPACITY[amenity]
    while fair_queue:
        _, _, _, booking = heapq.heappop(fair_queue)
        slot = booking["requested_slot"]
        unit = slot_usage[slot]
        scheduled = unit < capacity
        schedule.append(
            {
                **booking,
                "resource": f"{amenity}-{unit + 1}" if scheduled else None,
                "status": "BOOKED" if scheduled else "WAITLISTED",
                "fairness_order": len(schedule) + 1,
            }
        )
        if scheduled:
            slot_usage[slot] += 1

    return {
        "amenity": amenity,
        "resource_capacity_per_slot": capacity,
        "scheduled_bookings": sum(booking["status"] == "BOOKED" for booking in schedule),
        "waitlisted_bookings": sum(booking["status"] == "WAITLISTED" for booking in schedule),
        "schedule": schedule,
        "algorithm": "Priority heap by urgency with block-level round-robin order for equal priority",
    }


@router.get("/stakeholders/director/pulse")
def director_pulse(
    daylight_threshold_lux: int = Query(default=150, ge=10, le=1000),
) -> dict[str, Any]:
    hostelers = len({booking["resident_id"] for booking in AMENITY_BOOKINGS})
    day_scholars = sum(person["role"] == "Day Scholar" for person in COMMUTERS)
    faculty_count = len(FACULTY)
    alumni_count = len(MENTORS)
    management_count = 3
    active_relays = sum(
        sensor["pir_motion"] and sensor["ambient_lux"] < daylight_threshold_lux
        for sensor in SENSOR_READINGS
    )
    pending_bookings = sum(booking["status"] == "WAITLISTED" for booking in schedule_hostel_amenities("washing_machine")["schedule"])
    return {
        "total_stakeholders": day_scholars + hostelers + faculty_count + alumni_count + management_count,
        "day_scholars": day_scholars,
        "hostelers": hostelers,
        "faculty_and_teachers": faculty_count,
        "alumni_mentors": alumni_count,
        "management": management_count,
        "active_labs": sum(lab["active"] for lab in LABS),
        "equipment_checked_out": sum(asset["status"] == "checked_out" for asset in ASSETS),
        "hardware_ledger_entries": len(HARDWARE_LEDGER),
        "active_lighting_relays": active_relays,
        "shared_notices": len(SHARED_NOTICES),
        "washroom_zones": len(WASHROOMS),
        "waitlisted_bookings": pending_bookings,
        "open_classrooms": len(ROOM_CAPACITIES),
        "stakeholder_distribution": [
            {"group": "Day Scholars", "people": day_scholars},
            {"group": "Hostelers", "people": hostelers},
            {"group": "Faculty", "people": faculty_count},
            {"group": "Alumni", "people": alumni_count},
            {"group": "Management", "people": management_count},
        ],
        "algorithm": "Live aggregation over in-memory academic, facility, hardware, mobility, and hostel registries",
    }