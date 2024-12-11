from fastapi import FastAPI
from .api import auth, users, organisations, clusters, deployments
from .dependencies import init_scheduler, get_db

app = FastAPI(title="Backend Cluster Service")

@app.on_event("startup")
async def startup_event():
    db = next(get_db())
    init_scheduler(db)

# Include routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(organisations.router)
app.include_router(clusters.router)
app.include_router(deployments.router)

@app.get("/")
async def root():
    return {"message": "Backend Cluster Service API"}