import base64
import os
from typing import Any
from urllib.parse import quote

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
from views.student_life_ui import render_student_life_ui

st.set_page_config(
    page_title="AI-COS | Campus Operations",
    page_icon="C",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_URL = os.getenv("AI_COS_API_URL", "https://ai-cos-backend.onrender.com/api/v1").rstrip("/")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@400;500;600;700&family=Newsreader:opsz,wght@6..72,500;6..72,600&display=swap');
    :root {
        --ink: #193a35;
        --muted: #687e79;
        --paper: #f3f7f4;
        --line: #d8e5df;
        --forest: #1e6253;
        --mint: #dff1e9;
        --coral: #d87254;
    }
    html, body, [class*="css"] { font-family: 'DM Sans', 'Avenir Next', sans-serif; color: var(--ink); }
    .stApp { background: radial-gradient(ellipse at 100% 0%, #e3f2eb 0%, transparent 38%), var(--paper); }
    [data-testid="stSidebar"] { background: #eaf2ed; border-right: 1px solid var(--line); }
    [data-testid="stSidebar"] > div { padding-top: 1.6rem; }
    h1, h2, h3 { color: var(--ink); font-family: 'Newsreader', 'Iowan Old Style', Georgia, serif; letter-spacing: 0; }
    h1 { font-size: 2.25rem; line-height: 1.1; }
    .eyebrow { color: var(--forest); font-family: 'DM Mono', monospace; font-size: .72rem; text-transform: uppercase; letter-spacing: 0; }
    .subtle { color: var(--muted); font-size: .94rem; }
    .status-pill { display: inline-block; border: 1px solid #c5dfd3; background: var(--mint); color: var(--forest); padding: .35rem .65rem; border-radius: 999px; font: 500 .72rem 'DM Mono', monospace; }
    div[data-testid="stMetric"] { background: rgba(255,255,255,.76); border: 1px solid var(--line); border-radius: 6px; padding: .85rem 1rem; }
    div[data-testid="stMetricLabel"] { color: var(--muted); }
    div.stButton > button, div[data-testid="stFormSubmitButton"] button { border-radius: 5px; border: 1px solid var(--forest); background: var(--forest); color: white; min-height: 2.7rem; font-weight: 600; }
    div.stButton > button:hover, div[data-testid="stFormSubmitButton"] button:hover { background: #164a40; border-color: #164a40; color: white; }
    div[data-testid="stForm"] { border: 1px solid var(--line); border-radius: 6px; background: rgba(255,255,255,.72); padding: 1.2rem 1.3rem; }
    [data-testid="stDataFrame"] { border: 1px solid var(--line); border-radius: 5px; }
    hr { border-color: var(--line); }
    </style>
    """,
    unsafe_allow_html=True,
)

LOCATIONS = [
    "Main Gate", "Admin Block", "Library", "Academic Block", "Cafeteria",
    "Hostel", "Sports Complex",
]
FEATURES: dict[str, list[dict[str, Any]]] = {
    "Learning": [
        {"name": "Exam seating", "path": "/exam/seating", "algorithm": "Constraint heuristics", "description": "Generate an adjacent-department-aware seating plan.", "inputs": [("rows", "Rows", 4, 2, 12), ("cols", "Columns", 4, 2, 12)]},
        {"name": "Prerequisite impact", "path": "/academics/prereq-impact", "algorithm": "Graph traversal · BFS", "description": "Trace every course blocked by dropping a prerequisite.", "inputs": [("dropped", "Course to drop", ["CS101", "CS201", "CS301", "CS302", "CS401", "CS402"])]},
        {"name": "Transcript verification", "path": "/verify/transcript", "algorithm": "Cryptographic hashing · SHA-256", "description": "Create a deterministic signature for an academic record.", "inputs": [("roll_no", "Student roll number", "2501331930010")]},
        {"name": "Attendance overview", "path": "/academics/attendance", "algorithm": "Hash-map aggregation", "description": "Review attendance rates and identify courses below threshold."},
        {"name": "Course waitlist", "path": "/academics/waitlist", "algorithm": "Priority queue", "description": "Allocate open seats by student priority and semester.", "inputs": [("course", "Course", ["CS201", "CS301"]), ("seats", "Seats available", 2, 1, 20)]},
        {"name": "Timetable planner", "path": "/academics/timetable", "algorithm": "Graph coloring · greedy", "description": "Assign non-conflicting courses to exam slots.", "inputs": [("slots", "Available time slots", 4, 2, 8)]},
        {"name": "Library search", "path": "/library/search", "algorithm": "Inverted index · hashing", "description": "Find books by title, subject, author, or topic.", "inputs": [("query", "Search terms", "algorithms", "text")]},
        {"name": "Tutor matching", "path": "/student/tutor-matching", "algorithm": "Constraint matching", "description": "Match a subject and learning mode to available tutors.", "inputs": [("subject", "Subject", ["Data Structures", "Linear Algebra", "Artificial Intelligence"]), ("mode", "Session mode", ["Any", "Online", "In person"])]},
    ],
    "Campus": [
        {"name": "Energy optimization", "path": "/facilities/energy-score", "algorithm": "Smart comfort balancing", "description": "Recommend HVAC modes from live zone utilization."},
        {"name": "Campus directions", "path": "/campus/route", "algorithm": "Smart route planning", "description": "Find the lowest-travel-time walking route.", "inputs": [("origin", "From", LOCATIONS), ("destination", "To", LOCATIONS)]},
        {"name": "Shuttle dispatch", "path": "/mobility/shuttle", "algorithm": "Pickup planning", "description": "Assign the closest shuttle and estimate its arrival.", "inputs": [("destination", "Destination", LOCATIONS)]},
        {"name": "Room allocation", "path": "/facilities/room-allocation", "algorithm": "Space matching", "description": "Find the smallest available room that fits an event.", "inputs": [("attendees", "Expected attendees", 30, 1, 500)]},
        {"name": "Parking availability", "path": "/facilities/parking", "algorithm": "Space matching", "description": "Locate an available space for a vehicle type.", "inputs": [("vehicle_type", "Vehicle type", ["car", "bike"])]},
        {"name": "Water anomaly monitor", "path": "/facilities/water-anomalies", "algorithm": "Usage monitoring", "description": "Flag unusual water consumption with a Z-score threshold.", "inputs": [("threshold", "Sensitivity (standard deviations)", 2.0, 1.0, 5.0, 0.5)]},
        {"name": "Maintenance queue", "path": "/facilities/maintenance-priority", "algorithm": "Priority sorting", "description": "Rank maintenance tickets by severity, impact, and age.", "inputs": [("limit", "Tickets to show", 4, 1, 20)]},
        {"name": "Evacuation route", "path": "/safety/evacuation-route", "algorithm": "Fast exit guidance", "description": "Find the nearest reachable emergency exit.", "inputs": [("building", "Starting building", ["Academic Block", "Library", "Admin Block", "Hostel", "Sports Complex", "Main Gate"])]},
    ],
    "Student life": [
        {"name": "Dining recommendations", "path": "/student/dining-recommendations", "algorithm": "Constraint filtering and ranking", "description": "Filter meal options by dietary preference and compare nutrition.", "inputs": [("diet", "Dietary preference", ["any", "vegetarian", "vegan", "gluten-free", "high-protein"])]},
        {"name": "Lost and found", "path": "/student/lost-and-found", "algorithm": "Jaccard similarity", "description": "Match an item description against reported finds.", "inputs": [("query", "Describe the missing item", "blue bottle", "text")]},
    ],
    "Operations": [
        {"name": "Event scheduler", "path": "/operations/event-schedule", "algorithm": "Greedy interval scheduling", "description": "Select the largest set of non-overlapping campus events.", "inputs": [("limit", "Events to show", 5, 1, 20)]},
        {"name": "Budget allocation", "path": "/operations/budget-allocation", "algorithm": "Greedy knapsack", "description": "Prioritize campus projects by impact per budget unit.", "inputs": [("budget", "Available budget units", 400, 0, 10000)]},
    ],
    "Campus life": [
        {"name": "Digital outpass", "path": "/security/outpass", "method": "POST", "algorithm": "Geo-fence + Fernet QR encryption", "description": "Issue a time-limited hostel outpass only from inside campus.", "inputs": [("student_id", "Student ID", "2501330101", "text"), ("destination", "Destination", "Home", "text"), ("latitude", "Current latitude", 28.536, 28.532, 28.541, 0.0001), ("longitude", "Current longitude", 77.391, 77.386, 77.397, 0.0001), ("valid_hours", "Valid for (hours)", 8, 1, 48)]},
        {"name": "Mess waste predictor", "path": "/dining/footfall-prediction", "algorithm": "Moving average × timetable demand", "description": "Forecast dinner attendance and estimated food waste.", "inputs": [("scheduled_sections", "Scheduled evening sections", 22, 0, 60), ("window", "History window (days)", 7, 3, 14)]},
        {"name": "AQI ventilation manager", "path": "/environment/ventilation", "algorithm": "IoT threshold controller", "description": "Select a ventilation mode from the current air quality index.", "inputs": [("aqi", "Air quality index", 85, 0, 500)]},
        {"name": "Hardware ledger", "path": "/inventory/hardware/action", "method": "POST", "algorithm": "B-tree lookup + SHA-256 hash chain", "description": "Check lab equipment in or out and append a tamper-evident ledger entry.", "inputs": [("asset_tag", "Equipment tag", ["LAB-003", "LAB-014", "LAB-027", "LAB-041", "LAB-058", "LAB-073"]), ("student_id", "Student ID", "2501330101", "text"), ("action", "Action", ["checkout", "return"])]},
        {"name": "Hardware ledger history", "path": "/inventory/hardware/ledger", "algorithm": "B-tree inventory + SHA-256 event chain", "description": "Review equipment availability and the complete in-memory checkout history."},
        {"name": "Hygiene dispatch", "path": "/facilities/hygiene-dispatch", "algorithm": "Priority heap + nearest-staff routing", "description": "Route cleaning staff to busy washrooms that have waited longest.", "inputs": [("limit", "Washrooms to dispatch", 5, 1, 20)]},
        {"name": "Study room matchmaker", "path": "/study-rooms/matches", "algorithm": "Interval subtraction + best-fit", "description": "Find classrooms free for a study group during the selected time window.", "inputs": [("day", "Day", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]), ("start_hour", "Window starts (hour)", 9, 8, 19), ("end_hour", "Window ends (hour)", 17, 9, 20), ("minimum_minutes", "Minimum study time (minutes)", 60, 30, 240), ("capacity", "Group size", 4, 1, 120)]},
    ],
    "Hardware and OS": [
        {"name": "Zero-copy notice board", "path": "/os/notice-board", "method": "POST", "multipart": True, "algorithm": "Named OS shared memory", "description": "Publish a campus file once into shared memory for zero-copy subscriber reads.", "inputs": [("file", "Campus file (max 50 MiB)", "file"), ("title", "Notice title", "Campus update", "text"), ("recipients", "Recipient groups, comma-separated", "students, faculty", "text")]},
        {"name": "Notice board directory", "path": "/os/notice-board", "algorithm": "Shared-memory registry", "description": "Browse published files and verify a subscriber can attach without payload copies."},
        {"name": "Power grid load balancer", "path": "/power-grid/arbitration", "algorithm": "Two-tier round-robin bus arbitration", "description": "Allocate backup power to active critical labs before standard labs.", "inputs": [("available_kw", "Backup power available (kW)", 80, 0, 300), ("quantum_kw", "Arbitration quantum (kW)", 10, 1, 50)], "chart": {"list": "allocations", "type": "bar", "x": "lab", "y": "allocated_kw", "color": "power_state"}},
        {"name": "Ambulance dispatch", "path": "/emergency/ambulance-dispatch", "algorithm": "Emergency response planning", "description": "Dispatch the nearest ambulance and optimize its medical equipment loadout.", "inputs": [("incident_location", "Incident location", ["Main Gate", "Admin Block", "Library", "Academic Block", "Cafeteria", "Hostel", "Sports Complex"]), ("severity", "Incident severity", 3, 1, 5), ("equipment_capacity_kg", "Equipment weight limit (kg)", 35, 5, 60)], "chart": {"list": "loadout", "type": "bar", "x": "item", "y": "weight_kg"}},
        {"name": "IoT energy mesh", "path": "/iot/energy-mesh", "algorithm": "PIR occupancy + LDR threshold relays", "description": "Evaluate simulated occupancy and daylight sensors to switch zone lighting.", "inputs": [("daylight_threshold_lux", "Daylight relay threshold (lux)", 150, 10, 1000)], "chart": {"list": "zones", "type": "scatter", "x": "ambient_lux", "y": "estimated_watts", "color": "lighting_state", "size": "fixture_watts"}},
    ],
    "Governance & careers": [
        {"name": "Submit approval request", "path": "/governance/documents", "method": "POST", "algorithm": "Finite-state workflow", "description": "Start a permission request at Faculty review.", "inputs": [("title", "Request title", "Robotics Lab after-hours access", "text"), ("category", "Request category", ["Facilities", "Academic", "Event", "Travel"]), ("requester_id", "Requester ID", "STU-101", "text")]},
        {"name": "Approval queue", "path": "/governance/documents", "algorithm": "Faculty → HOD → Dean FSM", "description": "Review in-memory requests, current states, and approval history."},
        {"name": "Process approval", "path": "/governance/documents/{request_id}/transition", "method": "POST", "algorithm": "Role-guarded FSM transition", "description": "Approve or reject a request at its current hierarchy level.", "inputs": [("request_id", "Request ID", "APR-2026-001", "text"), ("role", "Approver role", ["Faculty", "HOD", "Dean"]), ("actor_id", "Approver ID", "FAC-01", "text"), ("decision", "Decision", ["approve", "reject"]), ("note", "Decision note", "Reviewed", "text")]},
        {"name": "Lost & found report", "path": "/student/lost-found/reports", "method": "POST", "algorithm": "Fuzzy similarity matching", "description": "Submit a lost or found item and see likely counterpart reports.", "inputs": [("report_type", "Report type", ["lost", "found"]), ("description", "Item description", "black laptop sleeve with campus logo", "text"), ("location", "Last seen / found near", "Library", "text"), ("reporter_id", "Reporter ID", "STU-101", "text")]},
        {"name": "Match lost & found reports", "path": "/student/lost-found/matches", "algorithm": "Token overlap + fuzzy string similarity", "description": "Find likely matching reports using descriptions and location.", "inputs": [("report_id", "Report ID", "LF-301", "text"), ("minimum_score", "Minimum match score", 0.15, 0.0, 1.0, 0.05)], "chart": {"list": "matches", "type": "bar", "x": "report_id", "y": "similarity_pct"}},
        {"name": "Placement skill gap", "path": "/placement/skill-gap", "algorithm": "Cosine similarity", "description": "Compare student skills with seeded industry job profiles.", "inputs": [("student_id", "Student profile", ["STU-401", "STU-402", "STU-403", "STU-404"])], "chart": {"list": "job_matches", "type": "bar", "x": "job_title", "y": "cosine_similarity_pct"}},
        {"name": "Hackathon teams", "path": "/hackathon/teams", "algorithm": "Weighted skill-compatibility graph clustering", "description": "Build distinct four-person teams with complementary skills.", "inputs": [("team_count", "Teams to form", 4, 1, 4)], "chart": {"list": "teams", "type": "bar", "x": "team", "y": "skills_covered"}},
    ],
    "Operations Plus": [
        {"name": "Cafeteria queue buster", "path": "/operations/cafeteria-queue", "algorithm": "M/M/c Erlang-C queue model", "description": "Estimate service wait and activate off-peak meal pricing.", "inputs": [("arrivals_last_15m", "Arrivals in the last 15 minutes", 9, 0, 500), ("cashiers", "Open service counters", 4, 1, 20), ("service_minutes", "Average service time (minutes)", 3.0, 0.5, 30.0, 0.5)], "chart": {"list": "menu", "type": "bar", "x": "item", "y": "dynamic_price", "color": "discount_pct"}},
        {"name": "Anonymous support post", "path": "/community/support/posts", "method": "POST", "algorithm": "RSA ring signature", "description": "Publish a message signed by a verified peer ring without revealing the author.", "inputs": [("message", "Support message", "Exam season is difficult; can anyone share study strategies?", "text")]},
        {"name": "Anonymous support board", "path": "/community/support/posts", "algorithm": "Verified anonymous peer board", "description": "Read posts after they have been verified against the campus ring."},
        {"name": "Indoor navigator", "path": "/navigation/indoor", "algorithm": "A* search with Manhattan heuristic", "description": "Route from the indoor map entrance to a classroom around walls.", "inputs": [("classroom_id", "Destination classroom", ["A-101", "A-204", "B-110", "C-302"]), ("start_row", "Start row", 1, 0, 11), ("start_column", "Start column", 1, 0, 14)]},
        {"name": "Scholarship matcher", "path": "/financial-aid/scholarship-matches", "algorithm": "Rule-based eligibility engine", "description": "Compare a student profile with seeded grant requirements.", "inputs": [("student_id", "Student profile", ["STU-401", "STU-402", "STU-403", "STU-404"])], "chart": {"list": "matches", "type": "bar", "x": "scholarship", "y": "requirements_met", "color": "eligible"}},
    ],
    "Community & resources": [
        {"name": "Mentorship & Guidance", "path": "/mentorship-guidance", "ui_only": True, "description": "Connect with alumni, faculty, and experienced mentors for practical academic and career guidance."},
        {"name": "Roommate compatibility", "path": "/residential/roommate-matches", "algorithm": "Gale-Shapley stable matching", "description": "Pair students using preference/profile vectors for study, sleep, and living habits.", "chart": {"list": "pairings", "type": "bar", "x": "student_a", "y": "compatibility_pct"}},
        {"name": "Student council election", "path": "/elections/student-council/vote", "method": "POST", "algorithm": "Anonymous SHA-256 vote chain", "description": "Cast one anonymous vote using a one-time token; each ballot is hash-chained.", "inputs": [("voter_token", "One-time voter token", "student-token-501", "text"), ("choice", "Campus initiative", ["Quiet study spaces", "Campus shuttle frequency", "Club equipment fund"])]},
        {"name": "Election results", "path": "/elections/student-council/results", "algorithm": "Hash-chain audit + vote aggregation", "description": "Review anonymous tallies and verify the ballot chain.", "chart": {"list": "results", "type": "pie", "x": "option", "y": "votes"}},
        {"name": "Resource custody transfer", "path": "/resources/p2p/transfer", "method": "POST", "algorithm": "Directed custody graph", "description": "Transfer a book or device from its current custodian to another participant.", "inputs": [("resource_id", "Resource", ["BOOK-210", "BOOK-315", "HW-044", "HW-052"]), ("from_person", "Current custodian", ["ALUM-11", "STU-520", "FAC-03", "FAC-07", "STU-511", "STU-519"]), ("to_person", "New custodian", ["STU-523", "STU-528", "STU-519"])]},
        {"name": "P2P resource ledger", "path": "/resources/p2p/ledger", "algorithm": "Directed custody graph", "description": "Inspect resource ownership, transfers, and custody paths.", "chart": {"list": "transfers", "type": "bar", "x": "resource_id", "y": "sequence"}},
        {"name": "Upload study PDF", "path": "/resources/study-materials/upload", "method": "POST", "multipart": True, "algorithm": "In-memory PDF storage + SHA-256", "description": "Upload a PDF note into the in-memory study library.", "inputs": [("file", "PDF file (max 10 MiB)", "file"), ("title", "Note title", "Algorithms revision notes", "text"), ("course", "Course code", "CS301", "text"), ("uploader_id", "Uploader profile", ["STU-511", "STU-512", "STU-513", "STU-514", "STU-515"])]},
        {"name": "Study material rankings", "path": "/resources/study-materials/rankings", "algorithm": "Weighted upvotes + downloader reputation", "description": "Rank uploaded notes by peer votes and reputation-weighted downloads.", "chart": {"list": "rankings", "type": "bar", "x": "title", "y": "rank_score", "color": "course"}},
        {"name": "Upvote study material", "path": "/resources/study-materials/{note_id}/upvote", "method": "POST", "algorithm": "Peer quality signal", "description": "Upvote a note you found useful; authors cannot vote for their own note.", "inputs": [("note_id", "Note ID", "NOTE-CS301-01", "text"), ("student_id", "Student profile", ["STU-511", "STU-512", "STU-513", "STU-514", "STU-515"])]},
        {"name": "Record note download", "path": "/resources/study-materials/{note_id}/downloads", "method": "POST", "algorithm": "Reputation-weighted download signal", "description": "Record a peer download so useful notes rank higher.", "inputs": [("note_id", "Note ID", "NOTE-CS301-01", "text"), ("downloader_id", "Downloader profile", ["STU-511", "STU-512", "STU-513", "STU-514", "STU-515"])]},
    ],
}


def request_feature(feature: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    path = feature["path"]
    path_parameters = {
        part[1:-1]
        for part in path.split("/")
        if part.startswith("{") and part.endswith("}")
    }
    for parameter in path_parameters:
        path = path.replace(f"{{{parameter}}}", quote(str(params[parameter]), safe=""))
    request_params = {key: value for key, value in params.items() if key not in path_parameters}
    if feature.get("multipart"):
        uploaded_file = request_params["file"]
        response = requests.post(
            f"{API_URL}{path}",
            data={key: value for key, value in request_params.items() if key != "file"},
            files={"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)},
            timeout=30,
        )
    elif feature.get("method", "GET") == "POST":
        response = requests.post(f"{API_URL}{path}", json=request_params, timeout=10)
    else:
        response = requests.get(f"{API_URL}{path}", params=request_params, timeout=10)
    response.raise_for_status()
    return response.json()


def _plotly_safe_value(value: Any) -> Any:
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(_plotly_safe_value(item)) for item in value)
    if isinstance(value, dict):
        return ", ".join(
            f"{key}: {_plotly_safe_value(item)}" for key, item in value.items()
        )
    return value


def _show_http_error(error: requests.HTTPError) -> None:
    response = error.response
    if response is not None and response.status_code == 502:
        st.warning(
            "The campus server is currently waking up from sleep mode. "
            "Please wait 50 seconds and try again."
        )
        return

    if response is not None and "text/html" in response.headers.get("Content-Type", "").lower():
        st.error("The service returned an unexpected response. Please try again shortly.")
        return

    detail = response.text if response is not None else str(error)
    st.error(f"The service returned an error: {detail}")


def render_mentorship_guidance_ui() -> None:
    mentor_groups = [
        {
            "category": "Alumni",
            "action": "Book a Chat",
            "profiles": [
                {
                    "name": "Aarav Mehta",
                    "expertise": "Product strategy, startups",
                    "organization": "Northstar Labs",
                    "experience": "8 years",
                },
                {
                    "name": "Sana Iqbal",
                    "expertise": "Cloud architecture, distributed systems",
                    "organization": "Vertex Cloud",
                    "experience": "6 years",
                },
            ],
        },
        {
            "category": "Current Faculty",
            "action": "Request Guidance",
            "profiles": [
                {
                    "name": "Dr. Neha Kapoor",
                    "expertise": "Artificial intelligence, research methods",
                    "organization": "Computer Science",
                    "experience": "12 years",
                },
                {
                    "name": "Prof. Rohan Sethi",
                    "expertise": "Embedded systems, robotics",
                    "organization": "Electronics and Communication",
                    "experience": "10 years",
                },
            ],
        },
        {
            "category": "Past Mentors",
            "action": "Book a Chat",
            "profiles": [
                {
                    "name": "Mira Thomas",
                    "expertise": "UX research, portfolio reviews",
                    "organization": "Independent Design Consultant",
                    "experience": "9 years",
                },
                {
                    "name": "Kabir Rao",
                    "expertise": "Data engineering, interview preparation",
                    "organization": "Former Campus Mentor",
                    "experience": "7 years",
                },
            ],
        },
    ]

    st.markdown('<div class="eyebrow">MENTOR NETWORK</div>', unsafe_allow_html=True)
    st.subheader("Find a mentor for your next step")
    st.markdown(
        '<div class="subtle">Browse experienced guides across campus and industry.</div>',
        unsafe_allow_html=True,
    )
    category_columns = st.columns(3, gap="large")

    for column, group in zip(category_columns, mentor_groups):
        with column:
            st.markdown(f"### {group['category']}")
            for index, profile in enumerate(group["profiles"]):
                with st.container(border=True):
                    st.markdown(f"#### {profile['name']}")
                    st.markdown(f"**Expertise**  \n{profile['expertise']}")
                    st.markdown(f"**Department / Company**  \n{profile['organization']}")
                    st.caption(f"{profile['experience']} experience")
                    if st.button(
                        group["action"],
                        key=f"mentor-request-{group['category'].lower().replace(' ', '-')}-{index}",
                        use_container_width=True,
                    ):
                        st.success("Interaction request sent successfully to the mentor!")


def _format_route(value: dict[Any, Any] | list[Any] | tuple[Any, ...]) -> str:
    if isinstance(value, dict):
        stops = [
            str(value[item])
            for item in sorted(
                value,
                key=lambda item: (0, int(item)) if str(item).isdigit() else (1, str(item)),
            )
        ]
    else:
        stops = [str(item) for item in value]
    return " ➔ ".join(stops)


def _build_result_chart(frame: pd.DataFrame, feature: dict[str, Any], key: str) -> Any | None:
    chart_spec = feature.get("chart", {})
    colors = ["#1e6253", "#d87254", "#82b9a2", "#e3b45c"]

    if chart_spec.get("list") == key:
        x_column = chart_spec.get("x")
        y_column = chart_spec.get("y")
        if x_column not in frame.columns or y_column not in frame.columns:
            return None
        color_column = chart_spec.get("color")
        if color_column not in frame.columns:
            color_column = None
        chart_type = chart_spec.get("type", "bar")
        if chart_type == "pie":
            return px.pie(
                frame,
                names=x_column,
                values=y_column,
                color=color_column,
                hole=0.45,
                title=feature["name"],
                color_discrete_sequence=colors,
            )
        chart_function = px.scatter if chart_type == "scatter" else px.bar
        chart_options: dict[str, Any] = {
            "data_frame": frame,
            "x": x_column,
            "y": y_column,
            "color": color_column,
            "title": feature["name"],
            "color_discrete_sequence": colors,
        }
        if chart_spec.get("size") in frame.columns:
            chart_options["size"] = chart_spec["size"]
        return chart_function(**chart_options)

    numeric_columns = frame.select_dtypes(include="number").columns.tolist()
    text_columns = frame.select_dtypes(exclude="number").columns.tolist()
    if numeric_columns and text_columns:
        category = text_columns[0]
        value = numeric_columns[0]
        return px.bar(
            frame,
            x=category,
            y=value,
            color=text_columns[1] if len(text_columns) > 1 else None,
            title=f"{value.replace('_', ' ').title()} by {category.replace('_', ' ')}",
            color_discrete_sequence=colors,
        )
    if len(frame) > 1 and text_columns:
        category = text_columns[0]
        counts = frame[category].astype(str).value_counts().rename_axis(category).reset_index(name="count")
        return px.bar(
            counts,
            x=category,
            y="count",
            title=f"{category.replace('_', ' ').title()} distribution",
            color_discrete_sequence=colors,
        )
    return None


def display_result(data: dict[str, Any], feature: dict[str, Any]) -> None:
    metrics = {
        key: value
        for key, value in data.items()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    }
    if metrics:
        columns = st.columns(min(len(metrics), 4))
        for index, (label, value) in enumerate(metrics.items()):
            columns[index % len(columns)].metric(label.replace("_", " ").title(), value)

    displayed: set[str] = set(metrics)
    for key, value in data.items():
        if key in displayed or key == "algorithm":
            continue
        if isinstance(value, list) and value and all(isinstance(item, dict) for item in value):
            frame = pd.json_normalize(value)
            frame = frame.apply(lambda column: column.map(_plotly_safe_value))
            st.markdown(f"**{key.replace('_', ' ').title()}**")
            chart = _build_result_chart(frame, feature, key)
            if chart is not None:
                chart.update_layout(
                    plot_bgcolor="rgba(255,255,255,0)",
                    paper_bgcolor="rgba(255,255,255,0)",
                    font_color="#193a35",
                    margin=dict(l=12, r=12, t=48, b=12),
                )
                st.plotly_chart(chart, use_container_width=True)
                with st.expander("View detailed results"):
                    st.dataframe(frame, use_container_width=True, hide_index=True)
            else:
                st.dataframe(frame, use_container_width=True, hide_index=True)
            st.download_button(
                "Download CSV",
                data=frame.to_csv(index=False),
                file_name=f"{key}.csv",
                mime="text/csv",
                key=f"download-{key}",
            )
            if chart is not None:
                st.download_button(
                    "Download report",
                    data=frame.to_csv(index=False),
                    file_name=f"{feature['name'].lower().replace(' ', '-')}.csv",
                    mime="text/csv",
                    key=f"report-{key}",
                )
        elif isinstance(value, list) and value and all(isinstance(row, list) for row in value):
            st.markdown(f"**{key.replace('_', ' ').title()}**")
            if key == "map":
                wall_map = [[1 if cell == "#" else 0 for cell in row] for row in value]
                figure = go.Figure(
                    go.Heatmap(
                        z=wall_map,
                        colorscale=[[0, "#e5f1e9"], [1, "#193a35"]],
                        showscale=False,
                        hoverinfo="skip",
                    )
                )
                route = data.get("route", [])
                labels = [
                    "Start" if index == 0 else (
                        data.get("classroom_id", "Destination") if index == len(route) - 1 else ""
                    )
                    for index in range(len(route))
                ]
                figure.add_trace(
                    go.Scatter(
                        x=[point["column"] for point in route],
                        y=[point["row"] for point in route],
                        mode="lines+markers+text",
                        text=labels,
                        textposition="top center",
                        line={"color": "#d87254", "width": 4},
                        marker={"size": 8, "color": "#d87254"},
                        name="Route",
                        hovertemplate="Row %{y}, column %{x}<extra>Route</extra>",
                    )
                )
                figure.update_layout(
                    height=440,
                    plot_bgcolor="#e5f1e9",
                    paper_bgcolor="rgba(255,255,255,0)",
                    font_color="#193a35",
                    margin={"l": 12, "r": 12, "t": 32, "b": 12},
                    yaxis={"autorange": "reversed", "dtick": 1, "title": "Grid row", "scaleanchor": "x"},
                    xaxis={"dtick": 1, "title": "Grid column"},
                )
                st.plotly_chart(figure, use_container_width=True)
            else:
                flattened = [
                    {"Row": row_index + 1, "Seat": col_index + 1, **cell}
                    for row_index, row in enumerate(value)
                    for col_index, cell in enumerate(row)
                    if isinstance(cell, dict)
                ]
                grid_frame = pd.DataFrame(flattened)
                if key == "matrix" and not grid_frame.empty:
                    branches = sorted(grid_frame["branch"].unique())
                    branch_index = {branch: index for index, branch in enumerate(branches)}
                    z_values = [
                        [branch_index[cell["branch"]] for cell in row]
                        for row in value
                    ]
                    labels = [[cell["branch"] for cell in row] for row in value]
                    hover_data = [
                        [f"{cell['id']}<br>{cell['paper']}" for cell in row]
                        for row in value
                    ]
                    colors = ["#1e6253", "#d87254", "#3f80a6", "#e3b45c", "#876d53"]
                    colorscale = []
                    for index, branch in enumerate(branches):
                        position = index / max(len(branches) - 1, 1)
                        colorscale.append([position, colors[index % len(colors)]])
                    figure = go.Figure(
                        go.Heatmap(
                            z=z_values,
                            x=list(range(1, len(value[0]) + 1)),
                            y=list(range(1, len(value) + 1)),
                            text=labels,
                            customdata=hover_data,
                            colorscale=colorscale,
                            zmin=0,
                            zmax=max(len(branches) - 1, 1),
                            texttemplate="%{text}",
                            showscale=True,
                            colorbar={"tickvals": list(range(len(branches))), "ticktext": branches},
                            hovertemplate="Row %{y}, Seat %{x}<br>%{customdata}<br>Branch: %{text}<extra></extra>",
                        )
                    )
                    figure.update_layout(
                        title="Exam seating by branch",
                        height=max(360, len(value) * 72),
                        plot_bgcolor="rgba(255,255,255,0)",
                        paper_bgcolor="rgba(255,255,255,0)",
                        font_color="#193a35",
                        margin={"l": 12, "r": 12, "t": 48, "b": 12},
                        xaxis={"title": "Seat", "dtick": 1},
                        yaxis={"title": "Row", "autorange": "reversed", "dtick": 1},
                    )
                    st.plotly_chart(figure, use_container_width=True)
                    with st.expander("View seat assignments"):
                        st.dataframe(grid_frame, use_container_width=True, hide_index=True)
                else:
                    st.dataframe(grid_frame, use_container_width=True, hide_index=True)
                st.download_button(
                    "Download CSV",
                    data=grid_frame.to_csv(index=False),
                    file_name=f"{key}.csv",
                    mime="text/csv",
                    key=f"download-grid-{key}",
                )
        elif key == "path" and isinstance(value, (dict, list, tuple)):
            st.markdown(f"**Route:** {_format_route(value)}")
        elif isinstance(value, dict):
            st.markdown(f"**{key.replace('_', ' ').title()}**")
            details = []
            for sub_key, sub_value in value.items():
                if isinstance(sub_value, list):
                    details.append(f"- {sub_key.replace('_', ' ').title()}: {', '.join(str(item) for item in sub_value)}")
                else:
                    details.append(f"- {sub_key.replace('_', ' ').title()}: {sub_value}")
            st.write("\n".join(details))
        elif key == "qr_png_base64" and isinstance(value, str):
            st.image(base64.b64decode(value), caption="Encrypted digital outpass QR", width=240)
        elif key == "encrypted_token" and isinstance(value, str):
            st.caption("Encrypted QR token issued.")
        elif isinstance(value, (str, bool)):
            st.markdown(f"**{key.replace('_', ' ').title()}:** {value}")
    if "algorithm" in data and isinstance(data["algorithm"], str):
        st.caption("Live service result")


def render_hardware_health_status() -> None:
    st.subheader("Hardware Health Status")
    status_cards = [
        ("Server cluster", "Healthy", "Green"),
        ("Network fabric", "Monitoring", "Yellow"),
        ("Lab peripherals", "Attention required", "Red"),
    ]
    color_map = {"Green": "#1e6253", "Yellow": "#e3b45c", "Red": "#d87254"}

    columns = st.columns(len(status_cards))
    for index, (name, text, status) in enumerate(status_cards):
        color = color_map[status]
        with columns[index]:
            st.markdown(
                f"""
                <div style="
                    background: rgba(255,255,255,0.72);
                    border: 1px solid {color};
                    border-left: 8px solid {color};
                    border-radius: 8px;
                    padding: 0.9rem 1rem;
                    margin-bottom: 0.5rem;
                ">
                    <div style="color:#687e79; font-size:0.74rem; text-transform:uppercase; letter-spacing:0.04em;">{name}</div>
                    <div style="color:{color}; font-weight:700; font-size:1.08rem; margin-top:0.35rem;">{text}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_placement_trend_analyzer() -> None:
    st.subheader("Placement Trend Analyzer")
    trend = pd.DataFrame(
        [
            {"year": "2022", "placements": 128, "offer_rate": 72},
            {"year": "2023", "placements": 146, "offer_rate": 78},
            {"year": "2024", "placements": 164, "offer_rate": 84},
            {"year": "2025", "placements": 182, "offer_rate": 88},
            {"year": "2026", "placements": 205, "offer_rate": 92},
        ]
    )
    chart = px.bar(
        trend,
        x="year",
        y="placements",
        color="offer_rate",
        title="Placement volume and offer rate by year",
        labels={"placements": "Placements", "offer_rate": "Offer rate (%)"},
        color_continuous_scale=["#d87254", "#e3b45c", "#1e6253"],
    )
    chart.update_layout(
        plot_bgcolor="rgba(255,255,255,0)",
        paper_bgcolor="rgba(255,255,255,0)",
        font_color="#193a35",
        margin=dict(l=12, r=12, t=48, b=12),
    )
    st.plotly_chart(chart, use_container_width=True)


def render_emergency_alert_dispatcher() -> None:
    st.subheader("Emergency Alert Dispatcher")
    if st.button("Dispatch emergency alert", key="emergency-dispatch-btn", type="primary"):
        st.session_state["emergency_alert_dispatched"] = True
    if st.session_state.get("emergency_alert_dispatched"):
        st.warning("🚨 Emergency alert dispatched: campus security, first response teams, and control room have been notified.")


def render_event_calendar_view() -> None:
    st.subheader("Campus Event Calendar")
    events = pd.DataFrame(
        [
            {"date": "2026-10-02", "title": "Orientation briefing", "type": "Academic"},
            {"date": "2026-10-09", "title": "Hackathon kickoff", "type": "Innovation"},
            {"date": "2026-10-15", "title": "Wellness camp", "type": "Community"},
            {"date": "2026-10-21", "title": "Faculty seminar", "type": "Academic"},
            {"date": "2026-10-27", "title": "Volunteer drive", "type": "Community"},
        ]
    )
    events["date"] = pd.to_datetime(events["date"])

    selected_date = st.date_input("Select a date", value=pd.Timestamp("2026-10-15").date(), key="event-calendar-date")
    matching_events = events[events["date"].dt.date == selected_date]
    if matching_events.empty:
        st.info("No campus events are scheduled for this date.")
    else:
        st.dataframe(matching_events[["date", "title", "type"]], hide_index=True, use_container_width=True)

    st.caption("Upcoming community and academic events")


def generate_executive_summary_csv() -> pd.DataFrame:
    summary_rows = []

    for metric_key, section_name in {
        "stakeholder-mentorship": "Alumni mentorship",
        "stakeholder-carpools": "Commuter carpools",
        "stakeholder-substitutions": "Faculty substitutions",
        "stakeholder-amenities": "Hostel amenities",
        "stakeholder-pulse": "Director's pulse",
    }.items():
        result = st.session_state.get(metric_key)
        if not result:
            continue
        for key, value in result.items():
            if isinstance(value, (int, float)):
                summary_rows.append({
                    "Section": section_name,
                    "Metric": str(key).replace("_", " ").title(),
                    "Value": value,
                })

    return pd.DataFrame(summary_rows)


def render_executive_report_panel() -> None:
    st.subheader("Executive Overview")
    if st.button("Generate Executive Report", key="generate-executive-report", type="primary"):
        report = generate_executive_summary_csv()
        if report.empty:
            st.info("No stakeholder metrics are available yet. Run a few dashboard workflows first.")
        else:
            st.session_state["executive_report_df"] = report
            st.success("Executive summary ready for download.")

    if "executive_report_df" in st.session_state:
        report = st.session_state["executive_report_df"]
        st.dataframe(report, use_container_width=True, hide_index=True)
        st.download_button(
            "Download CSV summary",
            data=report.to_csv(index=False),
            file_name="executive_report.csv",
            mime="text/csv",
            key="download-executive-summary",
        )


def render_stakeholder_dashboard(api_url: str) -> None:
    st.markdown('<div class="eyebrow">AI-COS / STAKEHOLDER OPERATIONS</div>', unsafe_allow_html=True)
    st.title("One campus, every community.")
    st.markdown(
        '<div class="subtle">Coordination tools for commuters, residents, faculty, alumni, and campus leadership.</div>',
        unsafe_allow_html=True,
    )
    render_executive_report_panel()
    st.divider()

    def call_service(
        key: str,
        path: str,
        params: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        try:
            if payload is not None:
                response = requests.post(f"{api_url}{path}", json=payload, timeout=10)
            else:
                response = requests.get(f"{api_url}{path}", params=params, timeout=10)
            response.raise_for_status()
            st.session_state[f"stakeholder-{key}"] = response.json()
        except requests.HTTPError as error:
            _show_http_error(error)
        except requests.RequestException as error:
            st.error(f"Could not reach the AI-COS backend at {api_url}. ({error})")

    tabs = st.tabs(
        [
            "Alumni mentorship",
            "Day-scholar carpools",
            "Faculty substitutions",
            "Hostel amenities",
            "Director's pulse",
        ]
    )

    with tabs[0]:
        st.subheader("15-minute mentorship matches")
        with st.form("stakeholder-mentorship-form"):
            student_ids = st.multiselect(
                "Students seeking guidance",
                ["STU-101", "STU-102", "STU-103", "STU-104", "STU-105", "STU-106"],
                default=["STU-101", "STU-102", "STU-103", "STU-104"],
            )
            match_submitted = st.form_submit_button("Find mentor matches", use_container_width=True)
        if match_submitted:
            if student_ids:
                call_service(
                    "mentorship",
                    "/stakeholders/alumni/mentorship-matches",
                    payload={"student_ids": student_ids},
                )
            else:
                st.warning("Select at least one student to create the matching graph.")
        result = st.session_state.get("stakeholder-mentorship")
        if result:
            metric_columns = st.columns(3)
            metric_columns[0].metric("Matches", result["matches_found"])
            metric_columns[1].metric("Requested", result["students_requested"])
            metric_columns[2].metric("Graph edges", result["graph_edges"])
            if result["matches"]:
                frame = pd.DataFrame(result["matches"])
                chart = px.bar(
                    frame,
                    x="student_name",
                    y="skill_overlap_count",
                    color="mentor_name",
                    hover_data=["slot", "skill_overlap"],
                    title="Skill overlap in matched 15-minute slots",
                    color_discrete_sequence=["#1e6253", "#d87254", "#82b9a2", "#e3b45c"],
                )
                st.plotly_chart(chart, use_container_width=True)
                with st.expander("View matched students and mentors"):
                    st.dataframe(frame, use_container_width=True, hide_index=True)
            if result["unmatched_students"]:
                st.info(f"No available match for: {', '.join(result['unmatched_students'])}")
            st.caption("Live service result")

    with tabs[1]:
        st.subheader("Geospatial commuter clusters")
        with st.form("stakeholder-carpool-form"):
            cluster_count = st.slider("Pickup clusters", 2, 5, 3)
            iterations = st.slider("K-means iterations", 1, 100, 20, step=1)
            carpool_submitted = st.form_submit_button("Build carpool groups", use_container_width=True)
        if carpool_submitted:
            call_service(
                "carpools",
                "/stakeholders/carpools",
                params={"clusters": cluster_count, "iterations": iterations},
            )
        result = st.session_state.get("stakeholder-carpools")
        if result:
            st.metric("Commuters grouped", result["commuters_clustered"])
            commuter_frame = pd.DataFrame(result["members"])
            if not commuter_frame.empty:
                chart = px.scatter(
                    commuter_frame,
                    x="longitude",
                    y="latitude",
                    color="cluster",
                    symbol="role",
                    hover_name="name",
                    hover_data=["person_id", "distance_to_pickup_km"],
                    title="Day scholars and faculty by pickup cluster",
                    color_discrete_sequence=["#1e6253", "#d87254", "#3f80a6", "#e3b45c", "#876d53"],
                )
                chart.update_yaxes(scaleanchor="x", scaleratio=1)
                st.plotly_chart(chart, use_container_width=True)
            with st.expander("View commuter assignments"):
                st.dataframe(
                    commuter_frame[["name", "role", "cluster", "distance_to_pickup_km"]],
                    use_container_width=True,
                    hide_index=True,
                )
            st.caption("Live service result")

    with tabs[2]:
        st.subheader("Qualified cover for classes on leave")
        with st.form("stakeholder-substitution-form"):
            absent_faculty = st.multiselect(
                "Faculty on leave",
                ["FAC-01", "FAC-02", "FAC-03", "FAC-04", "FAC-05", "FAC-06", "FAC-07"],
                default=["FAC-01"],
            )
            schedule_columns = st.columns(2)
            day = schedule_columns[0].selectbox("Day", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])
            time_slot = schedule_columns[1].selectbox(
                "Time slot", ["09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00"]
            )
            substitution_submitted = st.form_submit_button("Find qualified proxies", use_container_width=True)
        if substitution_submitted:
            if absent_faculty:
                call_service(
                    "substitutions",
                    "/stakeholders/faculty/substitutions",
                    payload={"absent_faculty_ids": absent_faculty, "day": day, "time_slot": time_slot},
                )
            else:
                st.warning("Select at least one faculty member on leave.")
        result = st.session_state.get("stakeholder-substitutions")
        if result:
            columns = st.columns(3)
            columns[0].metric("Sections covered", result["sections_covered"])
            columns[1].metric("Sections to cover", result["sections_to_cover"])
            columns[2].metric("Uncovered", len(result["uncovered_sections"]))
            if result["substitutions"]:
                frame = pd.DataFrame(result["substitutions"])
                chart = px.bar(
                    frame,
                    x="proxy_faculty",
                    y="proxy_current_load",
                    color="subject",
                    title="Current teaching load of qualified proxies",
                    color_discrete_sequence=["#1e6253", "#d87254", "#82b9a2", "#e3b45c"],
                )
                st.plotly_chart(chart, use_container_width=True)
                with st.expander("View substitution assignments"):
                    st.dataframe(frame, use_container_width=True, hide_index=True)
            if result["uncovered_sections"]:
                st.warning(f"No eligible proxy found for: {', '.join(result['uncovered_sections'])}")
            st.caption("Live service result")

    with tabs[3]:
        st.subheader("Fair hostel amenity scheduling")
        with st.form("stakeholder-amenity-form"):
            amenity = st.selectbox("Amenity", ["washing_machine", "sports_court"])
            amenity_submitted = st.form_submit_button("Schedule bookings", use_container_width=True)
        if amenity_submitted:
            call_service("amenities", "/stakeholders/hostel/amenity-schedule", params={"amenity": amenity})
        result = st.session_state.get("stakeholder-amenities")
        if result:
            columns = st.columns(3)
            columns[0].metric("Booked", result["scheduled_bookings"])
            columns[1].metric("Waitlisted", result["waitlisted_bookings"])
            columns[2].metric("Capacity / slot", result["resource_capacity_per_slot"])
            booking_frame = pd.DataFrame(result["schedule"])
            if result["scheduled_bookings"] or result["waitlisted_bookings"]:
                chart_data = pd.DataFrame(
                    [
                        {"status": "Booked", "requests": result["scheduled_bookings"]},
                        {"status": "Waitlisted", "requests": result["waitlisted_bookings"]},
                    ]
                )
                chart = px.pie(
                    chart_data,
                    names="status",
                    values="requests",
                    hole=0.48,
                    title="Booking allocation",
                    color="status",
                    color_discrete_map={"Booked": "#1e6253", "Waitlisted": "#d87254"},
                )
                st.plotly_chart(chart, use_container_width=True)
            with st.expander("View booking schedule"):
                st.dataframe(booking_frame, use_container_width=True, hide_index=True)
            st.caption("Live service result")

    with tabs[4]:
        st.subheader("Campus-wide operating pulse")
        with st.form("stakeholder-pulse-form"):
            daylight_threshold = st.slider("Lighting daylight threshold (lux)", 10, 1000, 150, step=10)
            pulse_submitted = st.form_submit_button("Refresh director's pulse", use_container_width=True)
        if pulse_submitted:
            call_service(
                "pulse",
                "/stakeholders/director/pulse",
                params={"daylight_threshold_lux": daylight_threshold},
            )
        result = st.session_state.get("stakeholder-pulse")
        if result:
            st.metric("Total stakeholder community", result["total_stakeholders"])
            metrics = [
                ("Day scholars", "day_scholars"),
                ("Hostelers", "hostelers"),
                ("Faculty", "faculty_and_teachers"),
                ("Alumni mentors", "alumni_mentors"),
                ("Active labs", "active_labs"),
                ("Lighting relays", "active_lighting_relays"),
                ("Equipment checked out", "equipment_checked_out"),
                ("Waitlisted bookings", "waitlisted_bookings"),
            ]
            metric_columns = st.columns(4)
            for index, (label, key) in enumerate(metrics):
                metric_columns[index % 4].metric(label, result[key])
            pie = px.pie(
                pd.DataFrame(result["stakeholder_distribution"]),
                names="group",
                values="people",
                hole=0.52,
                title="Stakeholder composition",
                color="group",
                color_discrete_sequence=["#1e6253", "#d87254", "#3f80a6", "#e3b45c", "#876d53"],
            )
            st.plotly_chart(pie, use_container_width=True)
            st.caption("Live service result")


st.sidebar.markdown('<div class="eyebrow">AI-COS / OPERATIONS</div>', unsafe_allow_html=True)
st.sidebar.markdown("## Campus systems")
st.sidebar.caption("Select a workflow to run its campus service.")
group = st.sidebar.radio(
    "Service area",
    [*FEATURES, "Student life tools", "Stakeholders"],
    label_visibility="collapsed",
)
total_features = sum(len(items) for items in FEATURES.values()) + 9
if group == "Student life tools":
    st.sidebar.divider()
    st.sidebar.markdown(f"<span class='status-pill'>{total_features} SERVICES</span>", unsafe_allow_html=True)
    render_student_life_ui(API_URL)
    st.stop()

if group == "Stakeholders":
    st.sidebar.divider()
    st.sidebar.markdown(f"<span class='status-pill'>{total_features} SERVICES</span>", unsafe_allow_html=True)
    st.sidebar.caption("Mentorship · Mobility · Faculty · Hostel · Management")
    render_stakeholder_dashboard(API_URL)
    st.stop()

feature_names = [feature["name"] for feature in FEATURES[group]]
selected_name = st.sidebar.selectbox("Workflow", feature_names)
feature = next(item for item in FEATURES[group] if item["name"] == selected_name)
st.sidebar.divider()
st.sidebar.markdown(f"<span class='status-pill'>{total_features} SERVICES</span>", unsafe_allow_html=True)
st.sidebar.caption("Campus operations dashboard")

if group == "Hardware and OS":
    render_hardware_health_status()
elif group == "Governance & careers":
    render_placement_trend_analyzer()
elif group == "Operations Plus":
    render_emergency_alert_dispatcher()
elif group == "Community & resources":
    render_event_calendar_view()

header_left, header_right = st.columns([4, 1])
with header_left:
    st.markdown('<div class="eyebrow">CAMPUS INTELLIGENCE / LIVE WORKSPACE</div>', unsafe_allow_html=True)
    st.title("Campus operations, in one place.")
    st.markdown('<div class="subtle">Decision tools for the everyday systems that keep a university moving.</div>', unsafe_allow_html=True)
with header_right:
    st.markdown(f"<br><span class='status-pill'>{total_features} DASHBOARD TOOLS</span>", unsafe_allow_html=True)
st.divider()

title_col, method_col = st.columns([3, 2])
with title_col:
    st.subheader(feature["name"])
    st.markdown(f'<div class="subtle">{feature["description"]}</div>', unsafe_allow_html=True)
with method_col:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("<span class='status-pill'>Live campus workflow</span>", unsafe_allow_html=True)

if feature.get("ui_only"):
    render_mentorship_guidance_ui()
    st.stop()

params: dict[str, Any] = {}
with st.form(key=f"form-{feature['path']}"):
    inputs = feature.get("inputs", [])
    if inputs:
        input_columns = st.columns(min(len(inputs), 3))
        for index, specification in enumerate(inputs):
            key, label, *options = specification
            with input_columns[index % len(input_columns)]:
                if len(options) == 1 and isinstance(options[0], list):
                    params[key] = st.selectbox(label, options[0])
                elif options and options[-1] == "file":
                    params[key] = st.file_uploader(
                        label,
                        key=f"upload-{feature['path']}",
                        max_upload_size=50,
                    )
                elif options and options[-1] == "text":
                    params[key] = st.text_input(label, value=options[0])
                elif len(options) == 4:
                    params[key] = st.number_input(label, value=options[0], min_value=options[1], max_value=options[2], step=options[3])
                elif len(options) == 3 and isinstance(options[0], float):
                    params[key] = st.number_input(label, value=options[0], min_value=options[1], max_value=options[2], step=0.5)
                elif len(options) == 3:
                    params[key] = st.number_input(label, value=options[0], min_value=options[1], max_value=options[2], step=1)
                else:
                    params[key] = st.text_input(label, value=str(options[0]) if options else "")
    else:
        st.markdown("This workflow is ready to run with the current campus data.")
    submitted = st.form_submit_button("Run service", use_container_width=True)

if submitted:
    try:
        if feature.get("multipart") and params.get("file") is None:
            st.error("Choose a file before publishing the notice.")
        else:
            result = request_feature(feature, params)
            st.session_state["last_result"] = result
            st.session_state["last_feature"] = feature["path"]
    except requests.HTTPError as error:
        _show_http_error(error)
    except requests.RequestException as error:
        st.error(f"Could not reach the AI-COS backend at {API_URL}. Start the API and try again. ({error})")

if st.session_state.get("last_feature") == feature["path"]:
    st.divider()
    display_result(st.session_state["last_result"], feature)
