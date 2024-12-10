from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List
import secrets

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
from .models.cluster import Cluster

app = FastAPI(title="Backend Cluster Service")

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

# Deployment routes
@app.post("/deployments/", response_model=DeploymentResponse)
async def create_deployment(
        deployment: DeploymentCreate,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    # Verify cluster exists and user has access
    cluster = db.query(Cluster).filter(Cluster.id == deployment.cluster_id).first()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    member = DatabaseOperations.get_organization_member(db, current_user.id, cluster.organization_id)
    if not member:
        raise HTTPException(status_code=403, detail="Not authorized to deploy to this cluster")

    # Check resource availability
    if (cluster.available_ram < deployment.required_ram or
            cluster.available_cpu < deployment.required_cpu or
            cluster.available_gpu < deployment.required_gpu):
        raise HTTPException(status_code=400, detail="Insufficient cluster resources")

    return DatabaseOperations.create_deployment(
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

@app.get("/deployments/cluster/{cluster_id}", response_model=List[DeploymentResponse])
async def list_deployments(
        cluster_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    # Verify cluster exists and user has access
    cluster = db.query(Cluster).filter(Cluster.id == cluster_id).first()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    member = DatabaseOperations.get_organization_member(db, current_user.id, cluster.organization_id)
    if not member:
        raise HTTPException(status_code=403, detail="Not authorized to view this cluster")

    return DatabaseOperations.get_pending_deployments(db, cluster_id)