from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import secrets
from ..database.base import get_db
from ..database.operations import DatabaseOperations
from ..schemas.schemas import OrganizationCreate, OrganizationResponse
from ..auth import get_current_user
from ..models.auth import User
from ..models.organisation import Organization
from ..dependencies import get_scheduler

router = APIRouter(prefix="/organizations", tags=["Organizations"])

@router.post("/", response_model=OrganizationResponse)
async def create_organization(
        org: OrganizationCreate,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    invite_code = secrets.token_urlsafe(16)
    org_data = DatabaseOperations.create_organization(db, org.name, invite_code)
    DatabaseOperations.add_organization_member(db, current_user.id, org_data.id, "admin")
    return org_data

@router.post("/{invite_code}/join")
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