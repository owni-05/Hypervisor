
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from ..database.base import OrganizationBase
from .auth import User

class Organization(OrganizationBase):
    __tablename__ = 'organizations'
    __table_args__ = {'schema': 'organization'}

    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True, nullable=False)
    invite_code = Column(String(255), unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class OrganizationMember(OrganizationBase):
    __tablename__ = 'members'
    __table_args__ = {'schema': 'organization'}

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('auth.users.id'))
    organization_id = Column(Integer, ForeignKey('organization.organizations.id'))
    role = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())