from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, List, Optional, Any
from ..database.base import get_db
from ..database.operations import DatabaseOperations
from ..schemas.schemas import DeploymentCreate, DeploymentResponse
from ..auth import get_current_user
from ..models.auth import User
from ..models.cluster import Cluster, Deployment
from ..dependencies import get_scheduler

router = APIRouter(prefix="/deployments", tags=["Deployments"])

@router.post("/", response_model=DeploymentResponse)
async def create_deployment(
        deployment: DeploymentCreate,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
        scheduler = Depends(get_scheduler)
):
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

    if not scheduler.enqueue_deployment(db_deployment):
        raise HTTPException(status_code=500, detail="Failed to schedule deployment")

    return db_deployment

@router.get("/queue/metrics")
async def get_queue_metrics(
        current_user: User = Depends(get_current_user),
        scheduler = Depends(get_scheduler)
):
    return scheduler.get_queue_metrics()

@router.post("/{deployment_id}/release")
async def release_deployment_resources(
        deployment_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
        scheduler = Depends(get_scheduler)
):
    deployment = db.query(Deployment).filter(Deployment.id == deployment_id).first()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")

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



@router.post("/{deployment_id}/complete")
async def complete_deployment(
        deployment_id: int,
        success_details: Optional[Dict] = None,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
        scheduler = Depends(get_scheduler)
):
    """Mark a deployment as successfully completed"""
    deployment = db.query(Deployment).filter(Deployment.id == deployment_id).first()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")

    # Verify access
    cluster = db.query(Cluster).filter(Cluster.id == deployment.cluster_id).first()
    member = DatabaseOperations.get_organization_member(
        db, current_user.id, cluster.organization_id
    )
    if not member or member.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Not authorized to complete deployments"
        )

    success = scheduler.handle_successful_deployment(
        deployment_id,
        success_details
    )

    if success:
        return {"message": "Deployment completed successfully"}
    raise HTTPException(
        status_code=500,
        detail="Failed to complete deployment"
    )

@router.post("/{deployment_id}/fail")
async def fail_deployment(
        deployment_id: int,
        error_details: Dict,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
        scheduler = Depends(get_scheduler)
):
    """Mark a deployment as failed"""
    deployment = db.query(Deployment).filter(Deployment.id == deployment_id).first()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")

    # Verify access
    cluster = db.query(Cluster).filter(Cluster.id == deployment.cluster_id).first()
    member = DatabaseOperations.get_organization_member(
        db, current_user.id, cluster.organization_id
    )
    if not member or member.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Not authorized to mark deployments as failed"
        )

    success = scheduler.handle_failed_deployment(
        deployment_id,
        error_details
    )

    if success:
        return {"message": "Deployment marked as failed"}
    raise HTTPException(
        status_code=500,
        detail="Failed to update deployment status"
    )

@router.get("/{deployment_id}/status")
async def get_deployment_status(
        deployment_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
        scheduler = Depends(get_scheduler)
):
    """Get detailed deployment status"""
    deployment = db.query(Deployment).filter(Deployment.id == deployment_id).first()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")

    # Verify access
    cluster = db.query(Cluster).filter(Cluster.id == deployment.cluster_id).first()
    member = DatabaseOperations.get_organization_member(
        db, current_user.id, cluster.organization_id
    )
    if not member:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to view this deployment"
        )

    status = scheduler.get_deployment_status(deployment_id)
    if status:
        return status
    raise HTTPException(
        status_code=500,
        detail="Failed to get deployment status"
    )