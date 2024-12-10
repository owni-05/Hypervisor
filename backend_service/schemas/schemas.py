from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

class UserBase(BaseModel):
    email: EmailStr
    username: str

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        orm_mode = True

class OrganizationBase(BaseModel):
    name: str

class OrganizationCreate(OrganizationBase):
    pass

class OrganizationResponse(OrganizationBase):
    id: int
    invite_code: str
    created_at: datetime

    class Config:
        orm_mode = True

class ClusterBase(BaseModel):
    name: str
    total_ram: float = Field(..., gt=0)
    total_cpu: float = Field(..., gt=0)
    total_gpu: float = Field(..., ge=0)

class ClusterCreate(ClusterBase):
    organization_id: int

class ClusterResponse(ClusterBase):
    id: int
    organization_id: int
    available_ram: float
    available_cpu: float
    available_gpu: float
    created_at: datetime

    class Config:
        orm_mode = True

class DeploymentBase(BaseModel):
    name: str
    docker_image: str
    required_ram: float = Field(..., gt=0)
    required_cpu: float = Field(..., gt=0)
    required_gpu: float = Field(..., ge=0)
    priority: int = Field(..., ge=1, le=10)

class DeploymentCreate(DeploymentBase):
    cluster_id: int

class DeploymentResponse(DeploymentBase):
    id: int
    user_id: int
    cluster_id: int
    status: str
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        orm_mode = True

class Token(BaseModel):
    access_token: str
    token_type: str