from fastapi import FastAPI
from backend.routers import router
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="AI-COS (AI Campus Operating System)",
    description="In-memory campus operations APIs demonstrating practical data structures and algorithms.",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

@app.get("/")
def health_check() -> dict[str, str]:
    return {"system": "AI-COS Core", "status": "Online and Ready", "api_version": "v1"}
