import re
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(tags=["Student Services"])

BOOKS = [
    {"id": "B-101", "title": "Introduction to Algorithms", "author": "T. Cormen", "tags": ["algorithms", "computer science", "graphs"]},
    {"id": "B-204", "title": "Clean Code", "author": "R. Martin", "tags": ["software", "programming", "design"]},
    {"id": "B-318", "title": "Artificial Intelligence: A Modern Approach", "author": "S. Russell", "tags": ["artificial intelligence", "search", "planning"]},
    {"id": "B-422", "title": "Database System Concepts", "author": "A. Silberschatz", "tags": ["database", "systems", "computer science"]},
]
MENU = [
    {"item": "Lentil rice bowl", "diet": ["vegetarian", "vegan"], "calories": 480, "protein_g": 18, "price": 95},
    {"item": "Grilled paneer wrap", "diet": ["vegetarian"], "calories": 540, "protein_g": 26, "price": 120},
    {"item": "Chicken grain plate", "diet": ["high-protein"], "calories": 610, "protein_g": 38, "price": 150},
    {"item": "Seasonal fruit cup", "diet": ["vegetarian", "vegan", "gluten-free"], "calories": 180, "protein_g": 3, "price": 55},
]
LOST_ITEMS = [
    {"id": "LF-12", "description": "black laptop sleeve with university logo", "location": "Library", "status": "found"},
    {"id": "LF-18", "description": "blue water bottle near sports ground", "location": "Sports Complex", "status": "found"},
    {"id": "LF-23", "description": "student ID card in cafeteria", "location": "Cafeteria", "status": "found"},
]
TUTORS = [
    {"name": "Aarav S.", "subject": "Data Structures", "rating": 4.9, "hours_available": 4, "mode": "In person"},
    {"name": "Mira K.", "subject": "Data Structures", "rating": 4.7, "hours_available": 7, "mode": "Online"},
    {"name": "Dev P.", "subject": "Linear Algebra", "rating": 4.8, "hours_available": 5, "mode": "In person"},
    {"name": "Sara R.", "subject": "Artificial Intelligence", "rating": 4.9, "hours_available": 3, "mode": "Online"},
]


def tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


@router.get("/library/search")
def search_library(query: str = Query(min_length=2, max_length=100)) -> dict[str, Any]:
    inverted_index: dict[str, set[str]] = defaultdict(set)
    for book in BOOKS:
        for token in tokenize(" ".join([book["title"], book["author"], *book["tags"]])):
            inverted_index[token].add(book["id"])
    query_tokens = tokenize(query)
    scores: dict[str, int] = defaultdict(int)
    for token in query_tokens:
        for book_id in inverted_index[token]:
            scores[book_id] += 1
    matches = [
        {**book, "match_score": scores[book["id"]]}
        for book in BOOKS
        if scores[book["id"]]
    ]
    matches.sort(key=lambda book: (-book["match_score"], book["title"]))
    return {"query": query, "results": matches, "algorithm": "Token inverted index with hash-map lookup"}


@router.get("/student/dining-recommendations")
def recommend_dining(diet: str = Query(default="any", pattern="^(any|vegetarian|vegan|gluten-free|high-protein)$")) -> dict[str, Any]:
    candidates = [item for item in MENU if diet == "any" or diet in item["diet"]]
    ranked = sorted(candidates, key=lambda item: (-item["protein_g"], item["price"]))
    return {"diet": diet, "recommendations": ranked, "algorithm": "Constraint filtering then protein-to-price ranking"}


@router.get("/student/lost-and-found")
def match_lost_item(query: str = Query(min_length=2, max_length=100)) -> dict[str, Any]:
    query_tokens = tokenize(query)
    if not query_tokens:
        raise HTTPException(status_code=422, detail="Enter a description to search")
    results = []
    for item in LOST_ITEMS:
        item_tokens = tokenize(item["description"])
        union = query_tokens | item_tokens
        score = len(query_tokens & item_tokens) / len(union) if union else 0
        if score:
            results.append({**item, "similarity_pct": round(score * 100, 1)})
    results.sort(key=lambda item: (-item["similarity_pct"], item["id"]))
    return {"query": query, "matches": results, "algorithm": "Jaccard similarity over normalized description tokens"}


@router.get("/student/tutor-matching")
def match_tutor(
    subject: str = Query(default="Data Structures", min_length=3, max_length=50),
    mode: str = Query(default="Any", pattern="^(Any|Online|In person)$"),
) -> dict[str, Any]:
    candidates = [
        tutor for tutor in TUTORS
        if tutor["subject"].lower() == subject.lower() and (mode == "Any" or tutor["mode"] == mode)
    ]
    candidates.sort(key=lambda tutor: (-tutor["rating"], -tutor["hours_available"]))
    return {"subject": subject, "matches": candidates, "algorithm": "Constraint filter then rating and availability ranking"}