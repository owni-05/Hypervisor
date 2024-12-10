from sqlalchemy.orm import Session
from sqlalchemy import and_
from ..models.auth import User
from ..models.organisation import Organization, OrganizationMember
from ..models.cluster import Cluster, Deployment, DeploymentStatus
from typing import Optional, List, Dict

class DatabaseOperations:
    @staticmethod
    def create_user(db: Session, email: str, username: str, hashed_password: str) -> User:
        user = User(
            email=email,
            username=username,
            hashed_password=hashed_password
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def get_user_by_email(db: Session, email: str) -> Optional[User]:
        return db.query(User).filter(User.email == email).first()

    @staticmethod
    def create_organization(db: Session, name: str, invite_code: str) -> Organization:
        org = Organization(
            name=name,
            invite_code=invite_code
        )
        db.add(org)
        db.commit()
        db.refresh(org)
        return org

    @staticmethod
    def add_organization_member(
            db: Session, user_id: int, organization_id: int, role: str
    ) -> OrganizationMember:
        member = OrganizationMember(
            user_id=user_id,
            organization_id=organization_id,
            role=role
        )
        db.add(member)
        db.commit()
        db.refresh(member)
        return member

    @staticmethod
    def get_organization_member(
            db: Session, user_id: int, organization_id: int
    ) -> Optional[OrganizationMember]:
        return db.query(OrganizationMember).filter(
            and_(
                OrganizationMember.user_id == user_id,
                OrganizationMember.organization_id == organization_id
            )
        ).first()

    @staticmethod
    def create_cluster(
            db: Session, name: str, organization_id: int,
            total_ram: float, total_cpu: float, total_gpu: float
    ) -> Cluster:
        cluster = Cluster(
            name=name,
            organization_id=organization_id,
            total_ram=total_ram,
            total_cpu=total_cpu,
            total_gpu=total_gpu,
            available_ram=total_ram,
            available_cpu=total_cpu,
            available_gpu=total_gpu
        )
        db.add(cluster)
        db.commit()
        db.refresh(cluster)
        return cluster

    @staticmethod
    def create_deployment(
            db: Session, name: str, docker_image: str,
            user_id: int, cluster_id: int, priority: int,
            required_ram: float, required_cpu: float, required_gpu: float
    ) -> Deployment:
        deployment = Deployment(
            name=name,
            docker_image=docker_image,
            user_id=user_id,
            cluster_id=cluster_id,
            status=DeploymentStatus.PENDING,
            priority=priority,
            required_ram=required_ram,
            required_cpu=required_cpu,
            required_gpu=required_gpu
        )
        db.add(deployment)
        db.commit()
        db.refresh(deployment)
        return deployment

    @staticmethod
    def get_pending_deployments(db: Session, cluster_id: int):
        return db.query(Deployment).filter(
            and_(
                Deployment.cluster_id == cluster_id,
                Deployment.status == DeploymentStatus.PENDING
            )
        ).order_by(
            Deployment.priority.desc(),
            Deployment.created_at.asc()
        ).all()