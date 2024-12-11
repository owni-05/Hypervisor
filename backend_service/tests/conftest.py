import pytest
from unittest.mock import Mock
import redis
from datetime import datetime
from sqlalchemy.orm import Session
from backend_service.models.cluster import Cluster, Deployment, DeploymentStatus

@pytest.fixture
def mock_redis():
    """Mock Redis client"""
    mock_client = Mock(spec=redis.Redis)
    mock_client.hset = Mock(return_value=True)
    mock_client.zadd = Mock(return_value=True)
    mock_client.hgetall = Mock(return_value={})
    mock_client.pipeline = Mock(return_value=Mock())
    return mock_client

@pytest.fixture
def mock_db():
    """Mock database session"""
    return Mock(spec=Session)

@pytest.fixture
def sample_cluster():
    """Create a sample cluster"""
    return Cluster(
        id=1,
        name="Test Cluster",
        organization_id=1,
        total_ram=32.0,
        total_cpu=8.0,
        total_gpu=2.0,
        available_ram=32.0,
        available_cpu=8.0,
        available_gpu=2.0
    )

@pytest.fixture
def sample_deployment():
    """Create a sample deployment"""
    return Deployment(
        id=1,
        name="Test Deployment",
        docker_image="test:latest",
        cluster_id=1,
        user_id=1,
        status=DeploymentStatus.PENDING,
        priority=5,
        required_ram=4.0,
        required_cpu=2.0,
        required_gpu=0.0,
        created_at=datetime.utcnow()
    )