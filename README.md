# AI Campus Operating System (AI-COS)

An in-memory campus operations demo with a modular FastAPI backend and an interactive Streamlit dashboard. Campus records are seeded in Python collections and reset when the backend restarts; no database is required.

## Project structure

```text
backend/
  main.py
  modules/
    student_life.py
  routers/
    academics.py
    campus_life.py
    facilities.py
    hardware_os.py
    operations.py
    student_services.py
frontend/
  app.py
  views/
    student_life_ui.py
backend.Dockerfile
frontend.Dockerfile
docker-compose.yml
requirements.txt
```

## Run locally

Python 3.11 or newer is recommended.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
uvicorn backend.main:app --reload
```

In a second terminal, run the dashboard:

```bash
streamlit run frontend/app.py
```

Open the dashboard at `http://localhost:8501` and the API documentation at `http://localhost:8000/docs`.

## Run with Docker

```bash
docker compose up --build
```

The dashboard is available at `http://localhost:8501`; the API is available at `http://localhost:8000/docs`.

## Campus services

| Service | Endpoint | Core concept |
| --- | --- | --- |
| Exam seating | `GET /api/v1/exam/seating` | Constraint heuristic |
| Prerequisite impact | `GET /api/v1/academics/prereq-impact` | Breadth-first graph traversal |
| Transcript verification | `GET /api/v1/verify/transcript` | SHA-256 hashing |
| Attendance overview | `GET /api/v1/academics/attendance` | Hash-map aggregation |
| Course waitlist | `GET /api/v1/academics/waitlist` | Priority queue |
| Timetable planner | `GET /api/v1/academics/timetable` | Greedy graph coloring |
| Library search | `GET /api/v1/library/search` | Inverted index |
| Tutor matching | `GET /api/v1/student/tutor-matching` | Constraint matching and ranking |
| Energy optimization | `GET /api/v1/facilities/energy-score` | Occupancy heuristic |
| Campus directions | `GET /api/v1/campus/route` | Dijkstra shortest path |
| Shuttle dispatch | `GET /api/v1/mobility/shuttle` | Shortest path and resource allocation |
| Room allocation | `GET /api/v1/facilities/room-allocation` | Best-fit allocation |
| Parking availability | `GET /api/v1/facilities/parking` | First-fit allocation |
| Water anomaly monitor | `GET /api/v1/facilities/water-anomalies` | Z-score outlier detection |
| Maintenance queue | `GET /api/v1/facilities/maintenance-priority` | Max-priority heap |
| Evacuation route | `GET /api/v1/safety/evacuation-route` | Breadth-first graph traversal |
| Dining recommendations | `GET /api/v1/student/dining-recommendations` | Constraint filtering and ranking |
| Lost and found | `GET /api/v1/student/lost-and-found` | Jaccard similarity |
| Event scheduler | `GET /api/v1/operations/event-schedule` | Greedy interval scheduling per venue |
| Budget allocation | `GET /api/v1/operations/budget-allocation` | Greedy knapsack heuristic |
| Geo-fenced digital outpass | `POST /api/v1/security/outpass` | Campus bounds + Fernet-encrypted QR |
| Verify digital outpass | `POST /api/v1/security/outpass/verify` | Authenticated token decryption |
| Mess footfall predictor | `GET /api/v1/dining/footfall-prediction` | Timetable-adjusted moving average |
| AQI ventilation manager | `GET /api/v1/environment/ventilation` | IoT threshold controller |
| Hardware checkout | `POST /api/v1/inventory/hardware/action` | B-tree search + SHA-256 hash chain |
| Hardware ledger | `GET /api/v1/inventory/hardware/ledger` | In-memory append-only ledger |
| Hygiene dispatch | `GET /api/v1/facilities/hygiene-dispatch` | Priority heap + nearest-staff routing |
| Study room matchmaker | `GET /api/v1/study-rooms/matches` | Interval subtraction + best-fit capacity |
| Alumni mentorship matchmaker | `POST /api/v1/stakeholders/alumni/mentorship-matches` | Hopcroft-Karp bipartite matching |
| Day-scholar carpool router | `GET /api/v1/stakeholders/carpools` | Geospatial K-means clustering |
| Faculty substitution engine | `POST /api/v1/stakeholders/faculty/substitutions` | CSP backtracking with MRV |
| Hostel amenity scheduler | `GET /api/v1/stakeholders/hostel/amenity-schedule` | Priority heap + block round robin |
| Director's pulse | `GET /api/v1/stakeholders/director/pulse` | In-memory operational aggregation |
| Document approval submission / queue | `POST, GET /api/v1/governance/documents` | Faculty → HOD → Dean finite-state machine |
| Document approval transition | `POST /api/v1/governance/documents/{request_id}/transition` | Role-guarded state transitions |
| Lost/found report and matcher | `POST /api/v1/student/lost-found/reports`, `GET /api/v1/student/lost-found/matches` | Token overlap + fuzzy string similarity |
| Placement skill-gap analyzer | `GET /api/v1/placement/skill-gap` | Cosine similarity over skill vectors |
| Hackathon team matchmaker | `GET /api/v1/hackathon/teams` | Weighted compatibility graph clustering |
| Cafeteria queue and pricing | `GET /api/v1/operations/cafeteria-queue` | M/M/c Erlang-C wait estimate + off-peak pricing |
| Anonymous support ring | `GET /api/v1/community/support/ring` | RSA public-key ring |
| Anonymous support posts | `POST, GET /api/v1/community/support/posts` | RSA ring-signature verification |
| Indoor classroom navigator | `GET /api/v1/navigation/indoor` | A* with Manhattan heuristic |
| Scholarship matcher | `GET /api/v1/financial-aid/scholarship-matches` | Rule-based eligibility engine |
| Roommate compatibility | `GET /api/v1/residential/roommate-matches` | Gale-Shapley deferred acceptance |
| Student council election | `POST /api/v1/elections/student-council/vote`, `GET /api/v1/elections/student-council/results` | Salted anonymous voter nullifiers + SHA-256 hash chain |
| P2P custody transfer and ledger | `POST /api/v1/resources/p2p/transfer`, `GET /api/v1/resources/p2p/ledger` | Directed custody graph |
| Study PDF upload and ranking | `POST /api/v1/resources/study-materials/upload`, `GET /api/v1/resources/study-materials/rankings` | Weighted upvotes + downloader reputation |
| Study note quality signals | `POST /api/v1/resources/study-materials/{note_id}/upvote`, `POST /api/v1/resources/study-materials/{note_id}/downloads` | Reputation-weighted ranking updates |
| Student-life mess forecast | `GET /api/v1/student-life/mess/forecast` | Section-adjusted moving average |
| Student-life roommate matches | `GET /api/v1/student-life/roommates/matches` | Gale-Shapley stable matching |
| Student-life amenity schedule | `GET /api/v1/student-life/amenities/schedule` | Priority heap + fair hall round robin |
| Student-life cafeteria queue | `GET /api/v1/student-life/cafeteria/queue` | M/M/c Erlang-C waiting estimate + dynamic pricing |

Interactive API documentation is generated by FastAPI at `/docs`. The dashboard backend URL can be overridden with `AI_COS_API_URL` (for example, `http://backend:8000/api/v1` in Docker Compose).

For non-ephemeral outpass encryption keys, set `AI_COS_FERNET_KEY` to a Fernet key generated with `Fernet.generate_key()` before starting the backend. Without it, a random process-local key is generated for local demos, and existing QR tokens stop verifying after a restart.

The hardware/OS simulations add a zero-copy notice board (`/api/v1/os/notice-board`), two-tier backup-power arbitration (`/api/v1/power-grid/arbitration`), ambulance dispatch with equipment optimization (`/api/v1/emergency/ambulance-dispatch`), and PIR/LDR relay evaluation (`/api/v1/iot/energy-mesh`). Notice uploads use named shared memory and are limited to 50 MiB; consumers can attach through `/api/v1/os/notice-board/{notice_id}/attach`. These are local simulations, not a replacement for a production message broker, power controller, or dispatch system.

The support-board RSA ring keys are generated in memory at startup and rotate when the backend restarts. This demonstrates signature verification and identity omission within the demo; production anonymity also requires client-side signing, authenticated ring enrollment, and removal of identifying request metadata from infrastructure logs.

Election tokens are salted and stored only as one-time nullifiers; ballot records contain choices but no voter IDs. This is an in-memory simulation, not a production anonymous-voting protocol: network logs, token issuance, and server access still need independent privacy controls.