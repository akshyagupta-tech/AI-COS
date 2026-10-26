from fastapi import FastAPI
from backend.campus_features import router
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="AI-COS (AI Campus Operating System)",
    description="Top-Notch Backend APIs for Project Based Learning",
    version="2.0.0"
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

@app.get("/")
def health_check():
    return {"system": "AI-COS Core", "status": "Online and Ready"}
