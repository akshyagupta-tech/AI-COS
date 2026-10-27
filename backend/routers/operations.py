from typing import Any

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(tags=["Campus Operations"])

EVENTS = [
    {"event": "Research Symposium", "start": 9, "end": 11, "venue": "Auditorium"},
    {"event": "Robotics Workshop", "start": 10, "end": 13, "venue": "Lab A"},
    {"event": "Career Fair", "start": 11, "end": 14, "venue": "Sports Hall"},
    {"event": "Design Showcase", "start": 13, "end": 15, "venue": "Auditorium"},
    {"event": "Alumni Talk", "start": 15, "end": 16, "venue": "Auditorium"},
]
PROJECTS = [
    {"project": "Accessible ramps", "cost": 120, "impact": 95},
    {"project": "Lab equipment renewal", "cost": 240, "impact": 100},
    {"project": "Library study pods", "cost": 100, "impact": 72},
    {"project": "Solar walkway lights", "cost": 160, "impact": 78},
    {"project": "Water refill stations", "cost": 80, "impact": 65},
]


@router.get("/operations/event-schedule")
def schedule_events(limit: int = Query(default=5, ge=1, le=20)) -> dict[str, Any]:
    venues: dict[str, list[dict[str, Any]]] = {}
    for event in EVENTS:
        venues.setdefault(event["venue"], []).append(event)

    selected = []
    for venue_events in venues.values():
        venue_schedule: list[dict[str, Any]] = []
        for event in sorted(venue_events, key=lambda item: (item["end"], item["start"])):
            if not venue_schedule or event["start"] >= venue_schedule[-1]["end"]:
                venue_schedule.append(event)
        selected.extend(venue_schedule)
    selected.sort(key=lambda item: (item["start"], item["venue"]))
    return {
        "events": selected[:limit],
        "events_scheduled": min(limit, len(selected)),
        "algorithm": "Greedy interval scheduling by earliest finish time",
    }


@router.get("/operations/budget-allocation")
def allocate_budget(budget: int = Query(default=400, ge=0, le=10000)) -> dict[str, Any]:
    selected = []
    remaining = budget
    for project in sorted(PROJECTS, key=lambda item: item["impact"] / item["cost"], reverse=True):
        if project["cost"] <= remaining:
            selected.append({**project, "impact_per_budget_unit": round(project["impact"] / project["cost"], 2)})
            remaining -= project["cost"]
    return {
        "budget": budget,
        "spent": budget - remaining,
        "unallocated": remaining,
        "projects": selected,
        "algorithm": "Greedy knapsack ranked by impact per cost",
    }


@router.get("/health")
def router_health() -> dict[str, str]:
    return {"status": "online"}