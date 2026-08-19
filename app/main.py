from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, vocabulary, progress, ai, users, units, admin
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Tilts API — Latvian Hungarian Learning")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(vocabulary.router, prefix="/vocabulary", tags=["vocabulary"])
app.include_router(progress.router, prefix="/progress", tags=["progress"])
app.include_router(ai.router, prefix="/ai", tags=["ai"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(units.router, prefix="/units", tags=["units"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])

@app.get("/")
def root():
    return {
        "status": "Tilts API is running",
        "version": "2.0",
        "description": "Latvian-Hungarian language learning platform"
    }