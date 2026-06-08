from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, vocabulary, progress, ai
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Latvian Learning API")

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

@app.get("/")
def root():
    return {"status": "Latvian API is running"}