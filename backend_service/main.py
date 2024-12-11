from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from redis import Redis
import os
from .scheduler.scheduler import PriorityScheduler
from .api import auth, users, organisations, clusters, deployments
from .database.base import get_db

# Create FastAPI app with metadata for Swagger/OpenAPI
app = FastAPI(
    title="Backend Cluster Service",
    description="API for managing clusters and deployments",
    version="1.0.0",
    openapi_url="/api/v1/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Initialize Redis client
redis_client = Redis(
    host=os.getenv('REDIS_HOST', 'localhost'),
    port=int(os.getenv('REDIS_PORT', 6379)),
    db=int(os.getenv('REDIS_DB', 0)),
    decode_responses=True
)

# Initialize scheduler
scheduler = None

@app.on_event("startup")
async def startup_event():
    global scheduler
    db = next(get_db())
    scheduler = PriorityScheduler(db, redis_client)

def get_scheduler():
    return scheduler

# Include routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(organisations.router)
app.include_router(clusters.router)
app.include_router(deployments.router)

@app.get("/", tags=["Health Check"])
async def root():
    """
    Root endpoint for API health check
    """
    return {
        "status": "healthy",
        "service": "Backend Cluster Service",
        "version": "1.0.0"
    }