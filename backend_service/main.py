from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List
import secrets
import json
import os
from .database.base import get_db
from .database.operations import DatabaseOperations
from .auth import get_current_user, create_access_token, get_password_hash, verify_password
from .schemas.schemas import (
    UserCreate, UserResponse, OrganizationCreate, OrganizationResponse,
    ClusterCreate, ClusterResponse, DeploymentCreate, DeploymentResponse,
    Token
)
from .models.auth import User
from .models.organisation import Organization
from .models.cluster import Cluster, DeploymentStatus,Deployment
from redis import Redis
from .scheduler.scheduler import PriorityScheduler


app = FastAPI(title="Backend Cluster Service")

# Initialize Redis and scheduler
redis_client = Redis(
    host=os.getenv('REDIS_HOST', 'localhost'),
    port=int(os.getenv('REDIS_PORT', 6379)),
    db=int(os.getenv('REDIS_DB', 0)),
    decode_responses=True
)

scheduler = None

@app.on_event("startup")
async def startup_event():
    global scheduler
    db = next(get_db())
    scheduler = PriorityScheduler(db, redis_client)

# Authentication routes
@app.post("/token", response_model=Token)
async def login(
        form_data: OAuth2PasswordRequestForm = Depends(),
        db: Session = Depends(get_db)
):
    user = DatabaseOperations.get_user_by_email(db, form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

# User routes
@app.post("/users/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = DatabaseOperations.get_user_by_email(db, user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = get_password_hash(user.password)
    return DatabaseOperations.create_user(
        db=db,
        email=user.email,
        username=user.username,
        hashed_password=hashed_password
    )

# Organization routes
@app.post("/organizations/", response_model=OrganizationResponse)
async def create_organization(
        org: OrganizationCreate,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    invite_code = secrets.token_urlsafe(16)
    org_data = DatabaseOperations.create_organization(db, org.name, invite_code)
    DatabaseOperations.add_organization_member(db, current_user.id, org_data.id, "admin")
    return org_data

@app.post("/organizations/{invite_code}/join")
async def join_organization(
        invite_code: str,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    org = db.query(Organization).filter(Organization.invite_code == invite_code).first()
    if not org:
        raise HTTPException(status_code=404, detail="Invalid invite code")

    existing_member = DatabaseOperations.get_organization_member(db, current_user.id, org.id)
    if existing_member:
        raise HTTPException(status_code=400, detail="Already a member")

    return DatabaseOperations.add_organization_member(db, current_user.id, org.id, "member")

# Cluster routes
@app.post("/clusters/", response_model=ClusterResponse)
async def create_cluster(
        cluster: ClusterCreate,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    # Verify user is admin in organization
    member = DatabaseOperations.get_organization_member(db, current_user.id, cluster.organization_id)
    if not member or member.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to create clusters")

    return DatabaseOperations.create_cluster(
        db=db,
        name=cluster.name,
        organization_id=cluster.organization_id,
        total_ram=cluster.total_ram,
        total_cpu=cluster.total_cpu,
        total_gpu=cluster.total_gpu
    )


#deployemnt routes

@app.post("/deployments/", response_model=DeploymentResponse)
async def create_deployment(
        deployment: DeploymentCreate,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    # ... (existing validation code) ...

    # Create deployment
    db_deployment = DatabaseOperations.create_deployment(
        db=db,
        name=deployment.name,
        docker_image=deployment.docker_image,
        user_id=current_user.id,
        cluster_id=deployment.cluster_id,
        priority=deployment.priority,
        required_ram=deployment.required_ram,
        required_cpu=deployment.required_cpu,
        required_gpu=deployment.required_gpu
    )

    # Add to priority queue
    if not scheduler.enqueue_deployment(db_deployment):
        raise HTTPException(
            status_code=500,
            detail="Failed to schedule deployment"
        )

    return db_deployment

# Add queue monitoring endpoint
@app.get("/deployments/queue/metrics")
async def get_queue_metrics(
        current_user: User = Depends(get_current_user)
):
    """Get metrics about the deployment queue"""
    return scheduler.get_queue_metrics()

# Add queue rebalancing endpoint (admin only)
@app.post("/deployments/queue/rebalance")
async def rebalance_queue(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Rebalance queue priorities"""
    # Check if user is admin
    if not current_user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="Only admins can rebalance the queue"
        )

    if scheduler.rebalance_queue():
        return {"message": "Queue rebalanced successfully"}
    raise HTTPException(
        status_code=500,
        detail="Failed to rebalance queue"
    )

@app.get("/clusters/{cluster_id}/resources")
async def get_cluster_resources(
        cluster_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Get current resource allocation for a cluster"""
    # Verify access
    cluster = db.query(Cluster).filter(Cluster.id == cluster_id).first()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    member = DatabaseOperations.get_organization_member(db, current_user.id, cluster.organization_id)
    if not member:
        raise HTTPException(status_code=403, detail="Not authorized to view this cluster")

    # Update and get cluster resources
    scheduler.update_cluster_resources(cluster)
    return scheduler.get_cluster_resources(cluster_id)

# Process pending deployments for a cluster
@app.post("/clusters/{cluster_id}/process-deployments")
async def process_cluster_deployments(
        cluster_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Process pending deployments for a cluster"""
    # Verify admin access
    cluster = db.query(Cluster).filter(Cluster.id == cluster_id).first()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    member = DatabaseOperations.get_organization_member(db, current_user.id, cluster.organization_id)
    if not member or member.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to process deployments")

    scheduled = scheduler.process_deployments(cluster_id)
    return {
        "message": f"Processed {len(scheduled)} deployments",
        "scheduled_deployments": scheduled
    }

# Get next deployment to be processed
@app.get("/clusters/{cluster_id}/next-deployment")
async def get_next_deployment(
        cluster_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Get information about the next deployment to be processed"""
    cluster = db.query(Cluster).filter(Cluster.id == cluster_id).first()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    member = DatabaseOperations.get_organization_member(db, current_user.id, cluster.organization_id)
    if not member:
        raise HTTPException(status_code=403, detail="Not authorized to view this cluster")

    next_deployment = scheduler.get_next_deployment(cluster_id)
    if not next_deployment:
        raise HTTPException(status_code=404, detail="No pending deployments")
    return next_deployment

# Release resources when deployment is complete
@app.post("/deployments/{deployment_id}/release")
async def release_deployment_resources(
        deployment_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Release resources when a deployment is complete"""
    deployment = db.query(Deployment).filter(Deployment.id == deployment_id).first()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")

    # Verify access
    cluster = db.query(Cluster).filter(Cluster.id == deployment.cluster_id).first()
    member = DatabaseOperations.get_organization_member(db, current_user.id, cluster.organization_id)
    if not member or member.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to release resources")

    resources = {
        'ram': deployment.required_ram,
        'cpu': deployment.required_cpu,
        'gpu': deployment.required_gpu
    }

    scheduler.release_resources(deployment.cluster_id, resources)
    return {"message": "Resources released successfully"}

# Start a specific deployment
@app.post("/deployments/{deployment_id}/start")
async def start_deployment(
        deployment_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Manually start a specific deployment"""
    deployment = db.query(Deployment).filter(Deployment.id == deployment_id).first()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")

    # Verify access
    cluster = db.query(Cluster).filter(Cluster.id == deployment.cluster_id).first()
    member = DatabaseOperations.get_organization_member(db, current_user.id, cluster.organization_id)
    if not member or member.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to start deployments")

    resources = {
        'ram': deployment.required_ram,
        'cpu': deployment.required_cpu,
        'gpu': deployment.required_gpu
    }

    success = scheduler.start_deployment(
        deployment.cluster_id,
        deployment_id,
        resources
    )

    if success:
        return {"message": "Deployment started successfully"}
    raise HTTPException(status_code=400, detail="Failed to start deployment")