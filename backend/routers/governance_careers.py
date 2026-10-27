import itertools
import math
import re
import secrets
from difflib import SequenceMatcher
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(tags=["Governance and Careers"])

APPROVAL_FLOW = {
    "PENDING_FACULTY": {"role": "Faculty", "approved_state": "PENDING_HOD"},
    "PENDING_HOD": {"role": "HOD", "approved_state": "PENDING_DEAN"},
    "PENDING_DEAN": {"role": "Dean", "approved_state": "APPROVED"},
}
APPROVAL_REQUESTS: dict[str, dict[str, Any]] = {
    "APR-2026-001": {
        "request_id": "APR-2026-001",
        "title": "Robotics Lab after-hours access",
        "category": "Facilities",
        "requester_id": "STU-101",
        "status": "PENDING_FACULTY",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "history": [],
    }
}


class DocumentSubmission(BaseModel):
    title: str = Field(min_length=4, max_length=120)
    category: str = Field(min_length=2, max_length=40)
    requester_id: str = Field(min_length=4, max_length=24)


class ApprovalTransition(BaseModel):
    role: Literal["Faculty", "HOD", "Dean"]
    actor_id: str = Field(min_length=3, max_length=32)
    decision: Literal["approve", "reject"]
    note: str = Field(default="", max_length=300)


@router.post("/governance/documents")
def submit_document(request: DocumentSubmission) -> dict[str, Any]:
    request_id = f"APR-{secrets.token_hex(4).upper()}"
    record = {
        "request_id": request_id,
        "title": request.title,
        "category": request.category,
        "requester_id": request.requester_id,
        "status": "PENDING_FACULTY",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "history": [],
    }
    APPROVAL_REQUESTS[request_id] = record
    return {**record, "next_approver": "Faculty", "algorithm": "Finite-state workflow initialized at Faculty review"}


@router.post("/governance/documents/{request_id}/transition")
def transition_document(request_id: str, action: ApprovalTransition) -> dict[str, Any]:
    record = APPROVAL_REQUESTS.get(request_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Approval request not found.")
    current_state = record["status"]
    required_approval = APPROVAL_FLOW.get(current_state)
    if required_approval is None:
        raise HTTPException(status_code=409, detail=f"Request is already in terminal state {current_state}.")
    if action.role != required_approval["role"]:
        raise HTTPException(
            status_code=403,
            detail=f"{current_state} can only be actioned by {required_approval['role']}.",
        )

    new_state = "REJECTED" if action.decision == "reject" else required_approval["approved_state"]
    event = {
        "role": action.role,
        "actor_id": action.actor_id,
        "decision": action.decision,
        "from_state": current_state,
        "to_state": new_state,
        "note": action.note,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    record["status"] = new_state
    record["history"].append(event)
    next_approver = APPROVAL_FLOW.get(new_state, {}).get("role")
    return {
        **record,
        "next_approver": next_approver,
        "algorithm": "Validated finite-state transition: Faculty -> HOD -> Dean -> Approved",
    }


@router.get("/governance/documents")
def list_document_requests() -> dict[str, Any]:
    return {
        "requests": list(APPROVAL_REQUESTS.values()),
        "request_count": len(APPROVAL_REQUESTS),
        "states": [*APPROVAL_FLOW, "APPROVED", "REJECTED"],
        "algorithm": "In-memory finite-state request registry",
    }


LOST_FOUND_REPORTS: dict[str, dict[str, Any]] = {
    "LF-301": {"report_id": "LF-301", "report_type": "lost", "description": "black laptop sleeve with university logo", "location": "Library", "reporter_id": "STU-101", "status": "open"},
    "LF-302": {"report_id": "LF-302", "report_type": "found", "description": "black laptop pouch bearing campus emblem", "location": "Central Library", "reporter_id": "STU-207", "status": "open"},
    "LF-303": {"report_id": "LF-303", "report_type": "lost", "description": "blue steel water bottle", "location": "Sports Complex", "reporter_id": "STU-114", "status": "open"},
    "LF-304": {"report_id": "LF-304", "report_type": "found", "description": "blue metal flask near athletics field", "location": "Sports Complex", "reporter_id": "STU-209", "status": "open"},
    "LF-305": {"report_id": "LF-305", "report_type": "lost", "description": "student identity card in a clear case", "location": "Cafeteria", "reporter_id": "STU-128", "status": "open"},
    "LF-306": {"report_id": "LF-306", "report_type": "found", "description": "clear ID holder with student card", "location": "Cafeteria", "reporter_id": "STU-221", "status": "open"},
}


class LostFoundReport(BaseModel):
    report_type: Literal["lost", "found"]
    description: str = Field(min_length=4, max_length=240)
    location: str = Field(min_length=2, max_length=80)
    reporter_id: str = Field(min_length=4, max_length=24)


def _normalized_words(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.lower()))


def _rank_lost_found(report: dict[str, Any], minimum_score: float) -> list[dict[str, Any]]:
    opposite_type = "found" if report["report_type"] == "lost" else "lost"
    source_words = _normalized_words(report["description"])
    candidates = []
    for candidate in LOST_FOUND_REPORTS.values():
        if candidate["report_type"] != opposite_type or candidate["status"] != "open":
            continue
        candidate_words = _normalized_words(candidate["description"])
        union = source_words | candidate_words
        token_overlap = len(source_words & candidate_words) / len(union) if union else 0.0
        text_similarity = SequenceMatcher(
            None,
            " ".join(sorted(source_words)),
            " ".join(sorted(candidate_words)),
        ).ratio()
        location_bonus = 0.12 if report["location"].casefold() == candidate["location"].casefold() else 0.0
        score = min(1.0, 0.65 * text_similarity + 0.35 * token_overlap + location_bonus)
        if score >= minimum_score:
            candidates.append({**candidate, "similarity_pct": round(score * 100, 1)})
    candidates.sort(key=lambda item: (-item["similarity_pct"], item["report_id"]))
    return candidates


@router.post("/student/lost-found/reports")
def submit_lost_found_report(request: LostFoundReport) -> dict[str, Any]:
    report_id = f"LF-{secrets.token_hex(3).upper()}"
    report = {
        "report_id": report_id,
        "report_type": request.report_type,
        "description": request.description,
        "location": request.location,
        "reporter_id": request.reporter_id,
        "status": "open",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    LOST_FOUND_REPORTS[report_id] = report
    return {
        "report": report,
        "suggested_matches": _rank_lost_found(report, 0.15),
        "algorithm": "Fuzzy matching: token-set similarity + SequenceMatcher + exact-location bonus",
    }


@router.get("/student/lost-found/matches")
def match_lost_found_reports(
    report_id: str = Query(min_length=4, max_length=32),
    minimum_score: float = Query(default=0.15, ge=0.0, le=1.0),
) -> dict[str, Any]:
    report = LOST_FOUND_REPORTS.get(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Lost/found report not found.")
    matches = _rank_lost_found(report, minimum_score)
    return {
        "source_report": report,
        "matches": matches,
        "match_count": len(matches),
        "algorithm": "Fuzzy matching: token-set similarity + SequenceMatcher + exact-location bonus",
    }


@router.get("/placement/skill-gap")
def analyze_placement_skill_gap(
    student_id: str = Query(default="STU-401", min_length=4, max_length=24),
) -> dict[str, Any]:
    student_skills = PLACEMENT_STUDENTS.get(student_id)
    if student_skills is None:
        raise HTTPException(status_code=404, detail="Student skill profile not found.")

    job_matches = []
    for job in JOB_PROFILES:
        required = set(job["required_skills"])
        vocabulary = required | student_skills
        student_vector = [int(skill in student_skills) for skill in vocabulary]
        job_vector = [int(skill in required) for skill in vocabulary]
        dot_product = sum(left * right for left, right in zip(student_vector, job_vector))
        student_norm = math.sqrt(sum(value * value for value in student_vector))
        job_norm = math.sqrt(sum(value * value for value in job_vector))
        similarity = dot_product / (student_norm * job_norm) if student_norm and job_norm else 0.0
        matched = sorted(student_skills & required)
        missing = sorted(required - student_skills)
        job_matches.append(
            {
                "job_title": job["title"],
                "company": job["company"],
                "cosine_similarity_pct": round(similarity * 100, 1),
                "matched_skills": matched,
                "missing_skills": missing,
                "skill_coverage_pct": round(len(matched) / len(required) * 100, 1),
            }
        )
    job_matches.sort(key=lambda item: (-item["cosine_similarity_pct"], item["job_title"]))
    return {
        "student_id": student_id,
        "student_skills": sorted(student_skills),
        "job_matches": job_matches,
        "best_match": job_matches[0] if job_matches else None,
        "algorithm": "Cosine similarity over binary student and job-requirement skill vectors",
    }


PLACEMENT_STUDENTS = {
    "STU-401": {"Python", "SQL", "pandas", "statistics", "Git", "machine learning"},
    "STU-402": {"JavaScript", "React", "CSS", "Git", "accessibility", "testing"},
    "STU-403": {"Python", "FastAPI", "SQL", "Docker", "Git", "cloud"},
    "STU-404": {"Java", "data structures", "SQL", "testing", "Git"},
}
JOB_PROFILES = [
    {"title": "Data Analyst", "company": "Northstar Analytics", "required_skills": {"Python", "SQL", "pandas", "statistics", "data visualization"}},
    {"title": "Machine Learning Associate", "company": "Vector Labs", "required_skills": {"Python", "machine learning", "statistics", "SQL", "model evaluation"}},
    {"title": "Frontend Engineer", "company": "Brightside Products", "required_skills": {"JavaScript", "React", "CSS", "accessibility", "testing"}},
    {"title": "Backend Developer", "company": "Cloudline Systems", "required_skills": {"Python", "FastAPI", "SQL", "Docker", "cloud"}},
    {"title": "Software Engineer", "company": "Cedar Software", "required_skills": {"Java", "data structures", "testing", "SQL", "Git"}},
]


HACKATHON_STUDENTS = [
    {"student_id": "H-101", "name": "Aarav", "skills": {"Python", "FastAPI", "SQL"}, "track": "Backend"},
    {"student_id": "H-102", "name": "Mira", "skills": {"React", "TypeScript", "CSS"}, "track": "Frontend"},
    {"student_id": "H-103", "name": "Kabir", "skills": {"PyTorch", "Python", "data science"}, "track": "AI / Data"},
    {"student_id": "H-104", "name": "Tara", "skills": {"Figma", "UX research", "prototyping"}, "track": "Product Design"},
    {"student_id": "H-105", "name": "Rohan", "skills": {"Java", "Spring", "PostgreSQL"}, "track": "Backend"},
    {"student_id": "H-106", "name": "Zoya", "skills": {"Vue", "JavaScript", "CSS"}, "track": "Frontend"},
    {"student_id": "H-107", "name": "Ishaan", "skills": {"computer vision", "Python", "OpenCV"}, "track": "AI / Data"},
    {"student_id": "H-108", "name": "Nina", "skills": {"product strategy", "Figma", "user research"}, "track": "Product Design"},
    {"student_id": "H-109", "name": "Dev", "skills": {"Go", "Docker", "cloud"}, "track": "Backend"},
    {"student_id": "H-110", "name": "Anya", "skills": {"Svelte", "TypeScript", "accessibility"}, "track": "Frontend"},
    {"student_id": "H-111", "name": "Neil", "skills": {"NLP", "Python", "machine learning"}, "track": "AI / Data"},
    {"student_id": "H-112", "name": "Leela", "skills": {"service design", "prototyping", "storytelling"}, "track": "Product Design"},
    {"student_id": "H-113", "name": "Sam", "skills": {"Rust", "APIs", "systems"}, "track": "Backend"},
    {"student_id": "H-114", "name": "Ira", "skills": {"Angular", "JavaScript", "accessibility"}, "track": "Frontend"},
    {"student_id": "H-115", "name": "Om", "skills": {"recommendation systems", "Python", "data science"}, "track": "AI / Data"},
    {"student_id": "H-116", "name": "Pia", "skills": {"visual design", "UX research", "Figma"}, "track": "Product Design"},
]


def _team_compatibility(first: dict[str, Any], second: dict[str, Any]) -> float:
    first_skills, second_skills = first["skills"], second["skills"]
    shared = len(first_skills & second_skills)
    unique = len(first_skills ^ second_skills)
    return unique + 0.25 * shared


def _team_score(team: tuple[str, ...], students: dict[str, dict[str, Any]], graph: dict[tuple[str, str], float]) -> float:
    edge_score = sum(graph[tuple(sorted(pair))] for pair in itertools.combinations(team, 2))
    members = [students[student_id] for student_id in team]
    skill_coverage = len(set().union(*(member["skills"] for member in members)))
    track_coverage = len({member["track"] for member in members})
    return edge_score + 2.0 * skill_coverage + 3.0 * track_coverage


@router.get("/hackathon/teams")
def create_hackathon_teams(
    team_count: int = Query(default=4, ge=1, le=4),
) -> dict[str, Any]:
    students = {student["student_id"]: student for student in HACKATHON_STUDENTS}
    student_ids = sorted(students)
    index_to_id = {index: student_id for index, student_id in enumerate(student_ids)}
    compatibility_graph = {
        tuple(sorted((first_id, second_id))): _team_compatibility(students[first_id], students[second_id])
        for first_id, second_id in itertools.combinations(students, 2)
    }

    @lru_cache(maxsize=None)
    def best_partition(remaining_mask: int, teams_remaining: int) -> tuple[float, tuple[tuple[str, ...], ...]]:
        if teams_remaining == 0:
            return 0.0, ()
        if remaining_mask.bit_count() < teams_remaining * 4:
            return -math.inf, ()

        first_bit = remaining_mask & -remaining_mask
        first_index = first_bit.bit_length() - 1
        surplus_students = remaining_mask.bit_count() - teams_remaining * 4
        other_indexes = [
            index for index in range(len(student_ids))
            if remaining_mask & (1 << index) and index != first_index
        ]
        best_score = -math.inf
        best_teams: tuple[tuple[str, ...], ...] = ()
        if surplus_students > 0:
            best_score, best_teams = best_partition(remaining_mask ^ first_bit, teams_remaining)
        for additional_indexes in itertools.combinations(other_indexes, 3):
            team_indexes = (first_index, *additional_indexes)
            team_mask = sum(1 << index for index in team_indexes)
            team_ids = tuple(index_to_id[index] for index in team_indexes)
            current_score = _team_score(team_ids, students, compatibility_graph)
            remaining_score, remaining_teams = best_partition(
                remaining_mask ^ team_mask,
                teams_remaining - 1,
            )
            total_score = current_score + remaining_score
            if total_score > best_score:
                best_score = total_score
                best_teams = (team_ids, *remaining_teams)
        return best_score, best_teams

    full_mask = (1 << len(student_ids)) - 1
    best_score, selected_teams = best_partition(full_mask, team_count)
    if not math.isfinite(best_score):
        raise HTTPException(status_code=422, detail="Not enough unassigned students to form another four-person team.")

    teams = []
    assigned = set()
    for team_number, team_ids in enumerate(selected_teams, start=1):
        members = [students[student_id] for student_id in team_ids]
        covered_skills = sorted(set().union(*(member["skills"] for member in members)))
        teams.append(
            {
                "team": f"Team {team_number}",
                "members": [
                    {
                        "student_id": member["student_id"],
                        "name": member["name"],
                        "track": member["track"],
                        "skills": sorted(member["skills"]),
                    }
                    for member in members
                ],
                "tracks_covered": len({member["track"] for member in members}),
                "skills_covered": len(covered_skills),
                "covered_skills": covered_skills,
                "compatibility_score": round(_team_score(team_ids, students, compatibility_graph), 2),
            }
        )
        assigned.update(team_ids)
    return {
        "teams": teams,
        "team_count": len(teams),
        "team_size": 4,
        "students_assigned": len(teams) * 4,
        "unassigned_students": [students[student_id]["name"] for student_id in student_ids if student_id not in assigned],
        "graph_edges": len(compatibility_graph),
        "total_compatibility_score": round(best_score, 2),
        "algorithm": "Weighted compatibility graph + exact bitmask-DP maximum-score disjoint four-node partition",
    }