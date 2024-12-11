from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ..database.base import get_db
from ..database.operations import DatabaseOperations
from ..schemas.schemas import UserCreate, UserResponse
from ..auth import get_password_hash

router = APIRouter(prefix="/users", tags=["Users"])

@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
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