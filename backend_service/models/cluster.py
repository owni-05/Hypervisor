from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum, func
from sqlalchemy.orm import relationship
from ..database.base import Base
import enum

class DeploymentStatus(str, enum.Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class Cluster(Base):
    __tablename__ = 'clusters'
    __table_args__ = {'schema': 'cluster'}

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    organization_id = Column(Integer, ForeignKey('organization.organizations.id'))
    total_ram = Column(Float, nullable=False)
    total_cpu = Column(Float, nullable=False)
    total_gpu = Column(Float, nullable=False)
    available_ram = Column(Float, nullable=False)
    available_cpu = Column(Float, nullable=False)
    available_gpu = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Deployment(Base):
    __tablename__ = 'deployments'
    __table_args__ = {'schema': 'cluster'}

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    docker_image = Column(String(255), nullable=False)
    user_id = Column(Integer, ForeignKey('auth.users.id'))
    cluster_id = Column(Integer, ForeignKey('cluster.clusters.id'))
    status = Column(Enum(DeploymentStatus), nullable=False)
    priority = Column(Integer, nullable=False)
    required_ram = Column(Float, nullable=False)
    required_cpu = Column(Float, nullable=False)
    required_gpu = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))