import hashlib
import heapq
import io
import json
import secrets
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

router = APIRouter(tags=["Community and Resources"])

ROOMMATE_FEATURES = ("quiet", "cleanliness", "sleep_schedule", "social", "study_style")
ROOMMATES = {
    "STU-501": {"name": "Aanya", "cohort": "North", "preference": (5, 5, 4, 2, 5), "profile": (5, 4, 5, 2, 5)},
    "STU-502": {"name": "Rohan", "cohort": "North", "preference": (2, 3, 2, 5, 2), "profile": (2, 3, 2, 5, 2)},
    "STU-503": {"name": "Meera", "cohort": "North", "preference": (4, 4, 5, 3, 4), "profile": (4, 5, 4, 3, 4)},
    "STU-504": {"name": "Kabir", "cohort": "North", "preference": (3, 2, 3, 4, 3), "profile": (3, 2, 3, 4, 2)},
    "STU-505": {"name": "Ira", "cohort": "South", "preference": (5, 4, 5, 2, 5), "profile": (5, 5, 4, 2, 5)},
    "STU-506": {"name": "Dev", "cohort": "South", "preference": (2, 3, 2, 5, 2), "profile": (2, 3, 2, 4, 2)},
    "STU-507": {"name": "Tara", "cohort": "South", "preference": (4, 5, 4, 3, 4), "profile": (4, 4, 5, 3, 4)},
    "STU-508": {"name": "Neil", "cohort": "South", "preference": (3, 2, 3, 4, 3), "profile": (3, 2, 2, 5, 3)},
}


def _vector_similarity(preference: tuple[int, ...], profile: tuple[int, ...]) -> float:
    distance = sum(abs(desired - observed) for desired, observed in zip(preference, profile))
    max_distance = 4 * len(ROOMMATE_FEATURES)
    return round((1 - distance / max_distance) * 100, 1)


@router.get("/residential/roommate-matches")
def match_roommates() -> dict[str, Any]:
    proposers = sorted(student_id for student_id, student in ROOMMATES.items() if student["cohort"] == "North")
    receivers = sorted(student_id for student_id, student in ROOMMATES.items() if student["cohort"] == "South")
    if len(proposers) != len(receivers):
        raise HTTPException(status_code=409, detail="Gale-Shapley pairing requires equally sized cohorts.")

    preference_order = {
        proposer: sorted(
            receivers,
            key=lambda receiver: (
                -_vector_similarity(ROOMMATES[proposer]["preference"], ROOMMATES[receiver]["profile"]),
                receiver,
            ),
        )
        for proposer in proposers
    }
    receiver_rank = {
        receiver: {
            proposer: rank
            for rank, proposer in enumerate(
                sorted(
                    proposers,
                    key=lambda proposer: (
                        -_vector_similarity(ROOMMATES[receiver]["preference"], ROOMMATES[proposer]["profile"]),
                        proposer,
                    ),
                )
            )
        }
        for receiver in receivers
    }

    free_proposers = list(proposers)
    next_proposal = {proposer: 0 for proposer in proposers}
    engaged_to: dict[str, str] = {}
    proposal_count = 0
    while free_proposers:
        proposer = free_proposers.pop(0)
        choices = preference_order[proposer]
        if next_proposal[proposer] >= len(choices):
            continue
        receiver = choices[next_proposal[proposer]]
        next_proposal[proposer] += 1
        proposal_count += 1
        current = engaged_to.get(receiver)
        if current is None or receiver_rank[receiver][proposer] < receiver_rank[receiver][current]:
            if current is not None:
                free_proposers.append(current)
            engaged_to[receiver] = proposer
        else:
            free_proposers.append(proposer)

    pairs = []
    for receiver, proposer in sorted(engaged_to.items()):
        left, right = ROOMMATES[proposer], ROOMMATES[receiver]
        pairs.append(
            {
                "student_a_id": proposer,
                "student_a": left["name"],
                "student_b_id": receiver,
                "student_b": right["name"],
                "a_to_b_score": _vector_similarity(left["preference"], right["profile"]),
                "b_to_a_score": _vector_similarity(right["preference"], left["profile"]),
                "compatibility_pct": round(
                    (_vector_similarity(left["preference"], right["profile"])
                    + _vector_similarity(right["preference"], left["profile"])) / 2,
                    1,
                ),
            }
        )
    return {
        "pairings": pairs,
        "pair_count": len(pairs),
        "proposals_made": proposal_count,
        "preference_features": list(ROOMMATE_FEATURES),
        "algorithm": "Gale-Shapley deferred acceptance; North cohort proposes using preference/profile-vector distance",
    }


ELECTION = {
    "election_id": "SG-2026-01",
    "question": "Which campus initiative should receive the student activity fund?",
    "options": ["Quiet study spaces", "Campus shuttle frequency", "Club equipment fund"],
    "ballots": [],
    "used_voter_tokens": set(),
}
VOTER_SALT = secrets.token_bytes(32)


class VoteRequest(BaseModel):
    voter_token: str = Field(min_length=8, max_length=80)
    choice: str = Field(min_length=3, max_length=80)


def _ballot_hash(ballot: dict[str, Any]) -> str:
    payload = {key: value for key, value in ballot.items() if key != "record_hash"}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _verify_vote_chain(ballots: list[dict[str, Any]]) -> bool:
    previous_hash = "GENESIS"
    for ballot in ballots:
        if ballot.get("previous_hash") != previous_hash or ballot.get("record_hash") != _ballot_hash(ballot):
            return False
        previous_hash = ballot["record_hash"]
    return True


@router.post("/elections/student-council/vote")
def cast_student_vote(request: VoteRequest) -> dict[str, Any]:
    if request.choice not in ELECTION["options"]:
        raise HTTPException(status_code=422, detail="Choose one of the listed election options.")
    nullifier = hashlib.sha256(VOTER_SALT + request.voter_token.encode()).hexdigest()
    if nullifier in ELECTION["used_voter_tokens"]:
        raise HTTPException(status_code=409, detail="This anonymous voter token has already been used.")

    ballot = {
        "sequence": len(ELECTION["ballots"]) + 1,
        "choice": request.choice,
        "cast_at": datetime.now(timezone.utc).isoformat(),
        "previous_hash": ELECTION["ballots"][-1]["record_hash"] if ELECTION["ballots"] else "GENESIS",
    }
    ballot["record_hash"] = _ballot_hash(ballot)
    ELECTION["used_voter_tokens"].add(nullifier)
    ELECTION["ballots"].append(ballot)
    return {
        "election_id": ELECTION["election_id"],
        "ballot_sequence": ballot["sequence"],
        "ballot_hash": ballot["record_hash"],
        "chain_valid": _verify_vote_chain(ELECTION["ballots"]),
        "identity_stored": False,
        "algorithm": "One-time salted voter nullifier + append-only SHA-256 ballot hash chain",
    }


@router.get("/elections/student-council/results")
def get_student_election_results() -> dict[str, Any]:
    counts = {option: 0 for option in ELECTION["options"]}
    for ballot in ELECTION["ballots"]:
        counts[ballot["choice"]] += 1
    return {
        "election_id": ELECTION["election_id"],
        "question": ELECTION["question"],
        "total_votes": len(ELECTION["ballots"]),
        "chain_valid": _verify_vote_chain(ELECTION["ballots"]),
        "results": [{"option": option, "votes": votes} for option, votes in counts.items()],
        "algorithm": "Vote aggregation with full SHA-256 hash-chain integrity verification",
    }


RESOURCES = {
    "BOOK-210": {"title": "Designing Data-Intensive Applications", "kind": "Book", "owner": "ALUM-11", "custody": ["ALUM-11"]},
    "BOOK-315": {"title": "Operating Systems: Three Easy Pieces", "kind": "Book", "owner": "STU-520", "custody": ["FAC-03", "STU-520"]},
    "HW-044": {"title": "Portable Logic Analyzer", "kind": "Hardware", "owner": "FAC-07", "custody": ["FAC-07"]},
    "HW-052": {"title": "Raspberry Pi Sensor Kit", "kind": "Hardware", "owner": "STU-511", "custody": ["STU-511", "STU-519"]},
}
CUSTODY_GRAPH: dict[str, set[str]] = {}
RESOURCE_TRANSFERS: list[dict[str, Any]] = []
KNOWN_CUSTODIANS = {"ALUM-11", "STU-520", "FAC-03", "FAC-07", "STU-511", "STU-519", "STU-523", "STU-528"}
for resource_id, resource in RESOURCES.items():
    for previous_owner, next_owner in zip(resource["custody"], resource["custody"][1:]):
        edge = {
            "sequence": len(RESOURCE_TRANSFERS) + 1,
            "from": previous_owner,
            "to": next_owner,
            "resource_id": resource_id,
        }
        RESOURCE_TRANSFERS.append(edge)
        CUSTODY_GRAPH.setdefault(previous_owner, set()).add(next_owner)
        CUSTODY_GRAPH.setdefault(next_owner, set())


class ResourceTransfer(BaseModel):
    resource_id: str = Field(min_length=3, max_length=24)
    from_person: str = Field(min_length=3, max_length=24)
    to_person: str = Field(min_length=3, max_length=24)


@router.post("/resources/p2p/transfer")
def transfer_resource(request: ResourceTransfer) -> dict[str, Any]:
    resource = RESOURCES.get(request.resource_id)
    if resource is None:
        raise HTTPException(status_code=404, detail="Resource not found in the campus ledger.")
    if request.from_person not in KNOWN_CUSTODIANS or request.to_person not in KNOWN_CUSTODIANS:
        raise HTTPException(status_code=404, detail="Both custodians must be registered campus participants.")
    if resource["owner"] != request.from_person:
        raise HTTPException(status_code=409, detail=f"Current custodian is {resource['owner']}, not {request.from_person}.")
    if request.from_person == request.to_person:
        raise HTTPException(status_code=422, detail="A resource cannot be transferred to its current custodian.")

    edge = {
        "sequence": len(RESOURCE_TRANSFERS) + 1,
        "from": request.from_person,
        "to": request.to_person,
        "resource_id": request.resource_id,
    }
    RESOURCE_TRANSFERS.append(edge)
    CUSTODY_GRAPH.setdefault(request.from_person, set()).add(request.to_person)
    CUSTODY_GRAPH.setdefault(request.to_person, set())
    resource["owner"] = request.to_person
    resource["custody"].append(request.to_person)
    return {
        "resource_id": request.resource_id,
        "resource": resource["title"],
        "current_custodian": resource["owner"],
        "custody_chain": resource["custody"],
        "transfer_edge": edge,
        "algorithm": "Directed custody graph with ownership validation and in-memory transfer history",
    }


@router.get("/resources/p2p/ledger")
def get_p2p_resource_ledger() -> dict[str, Any]:
    resources = [
        {"resource_id": resource_id, **resource}
        for resource_id, resource in RESOURCES.items()
    ]
    graph_edges = [
        dict(transfer)
        for transfer in RESOURCE_TRANSFERS
    ]
    return {
        "resources": resources,
        "transfers": graph_edges,
        "custody_nodes": len(CUSTODY_GRAPH),
        "transfer_count": len(graph_edges),
        "algorithm": "Directed graph adjacency sets plus per-resource custody paths",
    }


STUDENT_REPUTATION = {"STU-511": 1.0, "STU-512": 1.4, "STU-513": 0.8, "STU-514": 1.7, "STU-515": 1.2}
STUDY_NOTES: dict[str, dict[str, Any]] = {
    "NOTE-CS301-01": {
        "note_id": "NOTE-CS301-01",
        "title": "Graph Algorithms: Exam Revision Pack",
        "course": "CS301",
        "filename": "graph-algorithms.pdf",
        "content": b"%PDF-1.4\nSeeded demo PDF metadata\n",
        "sha256": hashlib.sha256(b"graph-algorithms-seed").hexdigest(),
        "uploader_id": "STU-511",
        "upvoters": {"STU-512", "STU-514"},
        "downloaders": {"STU-512", "STU-513", "STU-514"},
        "created_at": datetime.now(timezone.utc).isoformat(),
    },
    "NOTE-MA201-02": {
        "note_id": "NOTE-MA201-02",
        "title": "Linear Algebra Worked Examples",
        "course": "MA201",
        "filename": "linear-algebra.pdf",
        "content": b"%PDF-1.4\nSeeded demo PDF metadata\n",
        "sha256": hashlib.sha256(b"linear-algebra-seed").hexdigest(),
        "uploader_id": "STU-512",
        "upvoters": {"STU-511"},
        "downloaders": {"STU-511", "STU-515"},
        "created_at": datetime.now(timezone.utc).isoformat(),
    },
    "NOTE-AI301-03": {
        "note_id": "NOTE-AI301-03",
        "title": "Machine Learning Model Evaluation Cheatsheet",
        "course": "AI301",
        "filename": "model-evaluation.pdf",
        "content": b"%PDF-1.4\nSeeded demo PDF metadata\n",
        "sha256": hashlib.sha256(b"model-evaluation-seed").hexdigest(),
        "uploader_id": "STU-514",
        "upvoters": {"STU-511", "STU-512", "STU-515"},
        "downloaders": {"STU-512", "STU-513", "STU-515"},
        "created_at": datetime.now(timezone.utc).isoformat(),
    },
}
MAX_PDF_BYTES = 10 * 1024 * 1024


def _public_note(note: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in note.items() if key != "content"}


def _rank_study_notes() -> list[dict[str, Any]]:
    ranked = []
    for note in STUDY_NOTES.values():
        downloader_reputation = sum(STUDENT_REPUTATION.get(student_id, 0.5) for student_id in note["downloaders"])
        upvote_score = len(note["upvoters"]) * 2.0
        reputation_score = downloader_reputation * 1.5
        score = upvote_score + reputation_score
        ranked.append(
            {
                **_public_note(note),
                "upvote_count": len(note["upvoters"]),
                "download_count": len(note["downloaders"]),
                "downloader_reputation": round(downloader_reputation, 2),
                "rank_score": round(score, 2),
            }
        )
    ranked.sort(key=lambda note: (-note["rank_score"], -note["upvote_count"], note["note_id"]))
    for rank, note in enumerate(ranked, start=1):
        note["rank"] = rank
    return ranked


@router.post("/resources/study-materials/upload")
async def upload_study_material(
    file: UploadFile = File(...),
    title: str = Form(min_length=4, max_length=140),
    course: str = Form(min_length=3, max_length=24),
    uploader_id: str = Form(min_length=4, max_length=24),
) -> dict[str, Any]:
    if uploader_id not in STUDENT_REPUTATION:
        raise HTTPException(status_code=404, detail="Uploader profile is not registered.")
    content = await file.read(MAX_PDF_BYTES + 1)
    await file.close()
    if not content.startswith(b"%PDF-"):
        raise HTTPException(status_code=415, detail="Only PDF documents can be uploaded.")
    if len(content) > MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail="Study PDFs are limited to 10 MiB.")

    note_id = f"NOTE-{secrets.token_hex(5).upper()}"
    note = {
        "note_id": note_id,
        "title": title,
        "course": course,
        "filename": file.filename or f"{note_id}.pdf",
        "content": content,
        "sha256": hashlib.sha256(content).hexdigest(),
        "uploader_id": uploader_id,
        "upvoters": set(),
        "downloaders": set(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    STUDY_NOTES[note_id] = note
    return {
        **_public_note(note),
        "size_bytes": len(content),
        "algorithm": "PDF bytes retained in memory; SHA-256 content fingerprint recorded for ranking integrity",
    }


@router.get("/resources/study-materials/rankings")
def get_study_material_rankings() -> dict[str, Any]:
    rankings = _rank_study_notes()
    return {
        "rankings": rankings,
        "note_count": len(rankings),
        "algorithm": "Weighted score = 2 × peer upvotes + 1.5 × sum of downloader reputation",
    }


@router.get("/resources/study-materials/{note_id}/file")
def download_study_material(
    note_id: str,
    downloader_id: str = Query(min_length=4, max_length=24),
) -> Response:
    note = STUDY_NOTES.get(note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Study material not found.")
    if downloader_id not in STUDENT_REPUTATION:
        raise HTTPException(status_code=404, detail="Downloader profile is not registered.")
    note["downloaders"].add(downloader_id)
    safe_filename = note["filename"].replace('"', "")
    return Response(
        content=note["content"],
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe_filename}"'},
    )


class NoteUpvote(BaseModel):
    student_id: str = Field(min_length=4, max_length=24)


class NoteDownload(BaseModel):
    downloader_id: str = Field(min_length=4, max_length=24)


@router.post("/resources/study-materials/{note_id}/downloads")
def record_note_download(note_id: str, request: NoteDownload) -> dict[str, Any]:
    note = STUDY_NOTES.get(note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Study material not found.")
    if request.downloader_id not in STUDENT_REPUTATION:
        raise HTTPException(status_code=404, detail="Downloader profile is not registered.")
    note["downloaders"].add(request.downloader_id)
    return {
        "note_id": note_id,
        "download_count": len(note["downloaders"]),
        "downloader_reputation": STUDENT_REPUTATION[request.downloader_id],
        "rankings": _rank_study_notes(),
        "algorithm": "Downloader reputation contributes to weighted material ranking",
    }


@router.post("/resources/study-materials/{note_id}/upvote")
def upvote_study_material(note_id: str, request: NoteUpvote) -> dict[str, Any]:
    note = STUDY_NOTES.get(note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Study material not found.")
    if request.student_id not in STUDENT_REPUTATION:
        raise HTTPException(status_code=404, detail="Student profile is not registered.")
    if request.student_id == note["uploader_id"]:
        raise HTTPException(status_code=403, detail="Authors cannot upvote their own notes.")
    if request.student_id in note["upvoters"]:
        raise HTTPException(status_code=409, detail="This student has already upvoted the note.")
    note["upvoters"].add(request.student_id)
    return {
        "note_id": note_id,
        "upvote_count": len(note["upvoters"]),
        "rankings": _rank_study_notes(),
        "algorithm": "Idempotent peer upvote contributes to the weighted material score",
    }