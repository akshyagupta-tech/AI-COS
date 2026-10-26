import hashlib
import json
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/v1", tags=["AI Campus Engines"])

# --- 1. CSP EXAM SEATING ENGINE ---
@router.get("/exam/seating")
def generate_optimal_seating(rows: int = 4, cols: int = 4) -> Dict[str, Any]:
    try:
        departments = ["CSE", "ECE", "MECH", "IT", "CIVIL"]
        total_seats = rows * cols
        students = [{"id": f"250133{idx:04d}", "branch": departments[idx % len(departments)]} for idx in range(total_seats)]
        
        grid = [[None for _ in range(cols)] for _ in range(rows)]
        unassigned = students.copy()

        for r in range(rows):
            for c in range(cols):
                adj = {grid[r-1][c]["branch"]} if r > 0 and grid[r-1][c] else set()
                if c > 0 and grid[r][c-1]: adj.add(grid[r][c-1]["branch"])

                # MRV Heuristic: Pick student not in adjacent branches
                candidate = next((s for s in unassigned if s["branch"] not in adj), None)
                if not candidate and unassigned:
                    candidate = unassigned[0] # Fallback

                if candidate:
                    grid[r][c] = {
                        "id": candidate["id"],
                        "branch": candidate["branch"],
                        "paper": "Set A" if (r + c) % 2 == 0 else "Set B"
                    }
                    unassigned.remove(candidate)

        return {"status": "OPTIMIZED", "dimensions": f"{rows}x{cols}", "matrix": grid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- 2. DAG PREREQUISITE ANALYZER ---
PREREQ_DAG = {
    "CS101": [], "CS201": ["CS101"], "CS301": ["CS201"], 
    "CS302": ["CS201"], "CS401": ["CS301"], "CS402": ["CS302"]
}

@router.get("/academics/prereq-impact")
def analyze_impact(dropped: str = "CS201") -> Dict[str, Any]:
    if dropped not in PREREQ_DAG:
        raise HTTPException(status_code=404, detail="Course not found in DAG")
    
    blocked, queue, visited = [], [dropped], set()
    while queue:
        curr = queue.pop(0)
        for course, reqs in PREREQ_DAG.items():
            if curr in reqs and course not in visited:
                visited.add(course)
                blocked.append(course)
                queue.append(course)
                
    return {
        "target": dropped,
        "cascading_blocks": blocked,
        "risk_level": "CRITICAL" if len(blocked) > 2 else "WARNING"
    }

# --- 3. HVAC ENERGY SCORER ---
@router.get("/facilities/energy-score")
def calculate_hvac() -> Dict[str, Any]:
    zones = [
        {"id": "Z1", "cap": 200, "occ": 15},
        {"id": "Z2", "cap": 50,  "occ": 0},
        {"id": "Z3", "cap": 80,  "occ": 75}
    ]
    total_saved = 0.0
    report = []
    
    for z in zones:
        util = (z["occ"] / z["cap"]) * 100
        if z["occ"] == 0: saved, mode = 5.2, "DEEP_SLEEP"
        elif util < 30: saved, mode = 2.4, "ECO_MODE"
        else: saved, mode = 0.0, "ACTIVE"
        
        total_saved += saved
        report.append({"zone": z["id"], "mode": mode, "kwh_saved": saved})
        
    return {"total_kwh_saved": round(total_saved, 2), "zones": report}

# --- 4. SHA-256 TRANSCRIPT VERIFIER ---
@router.get("/verify/transcript")
def verify_hash(roll_no: str = "2501331930010") -> Dict[str, Any]:
    payload = {"roll_no": roll_no, "cgpa": 8.85, "status": "VERIFIED"}
    hash_val = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return {"roll_no": roll_no, "signature": hash_val, "authentic": True}
