from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database.base import get_db
from ..database.operations import DatabaseOperations
from ..schemas.schemas import ClusterCreate, ClusterResponse
from ..auth import get_current_user
from ..models.auth import User
from ..models.cluster import Cluster
from ..dependencies import get_scheduler

router = APIRouter(prefix="/clusters", tags=["Clusters"])

@router.post("/", response_model=ClusterResponse)
async def create_cluster(
        cluster: ClusterCreate,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
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

@router.get("/{cluster_id}/resources")
async def get_cluster_resources(
        cluster_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
        scheduler = Depends(get_scheduler)
):
    cluster = db.query(Cluster).filter(Cluster.id == cluster_id).first()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    member = DatabaseOperations.get_organization_member(db, current_user.id, cluster.organization_id)
    if not member:
        raise HTTPException(status_code=403, detail="Not authorized to view this cluster")

    scheduler.update_cluster_resources(cluster)
    return scheduler.get_cluster_resources(cluster_id)

@router.post("/{cluster_id}/process-deployments")
async def process_cluster_deployments(
        cluster_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
        scheduler = Depends(get_scheduler)
):
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