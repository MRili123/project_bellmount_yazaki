from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv
from database import init_db
from routers import auth, switches, captures, admin

load_dotenv()

# Initialize database
init_db()

app = FastAPI(
    title="Bellmounth API",
    description="Multi-user cable measurement system",
    version="2.0.0"
)

# CORS configuration
origins = [
    "http://localhost",
    "http://localhost:8000",
    "http://127.0.0.1",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(switches.router)
app.include_router(captures.router)
app.include_router(admin.router)

@app.get("/")
def root():
    return {
        "message": "Bellmounth API v2.0",
        "status": "running"
    }

if __name__ == "__main__":
    import uvicorn
    api_port = int(os.getenv("API_PORT", 8000))
    api_host = os.getenv("API_HOST", "0.0.0.0")
    uvicorn.run(app, host=api_host, port=api_port)
