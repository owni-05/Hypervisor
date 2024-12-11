import pytest
from backend_service.scheduler.scheduler import PriorityScheduler
from backend_service.models.cluster import DeploymentStatus

@pytest.fixture
def scheduler(mock_db, mock_redis):
    return PriorityScheduler(mock_db, mock_redis)

class TestDeploymentOperations:
    def test_start_deployment(self, scheduler, sample_deployment):
        """Test starting a deployment"""
        scheduler.db.query.return_value.get.return_value = sample_deployment
        resources = {
            'ram': sample_deployment.required_ram,
            'cpu': sample_deployment.required_cpu,
            'gpu': sample_deployment.required_gpu
        }

        result = scheduler.start_deployment(
            sample_deployment.cluster_id,
            sample_deployment.id,
            resources
        )

        assert result is True
        assert sample_deployment.status == DeploymentStatus.RUNNING

    def test_complete_deployment(self, scheduler, sample_deployment):
        """Test completing a deployment"""
        scheduler.db.query.return_value.get.return_value = sample_deployment

        result = scheduler.complete_deployment(
            sample_deployment.id,
            DeploymentStatus.COMPLETED,
            {"message": "Success"}
        )

        assert result is True
        assert sample_deployment.status == DeploymentStatus.COMPLETED

    def test_handle_deployment_timeout(self, scheduler, sample_deployment):
        """Test deployment timeout handling"""
        scheduler.db.query.return_value.get.return_value = sample_deployment
        result = scheduler.handle_deployment_timeout(sample_deployment.id)
        assert isinstance(result, bool)

    def test_handle_failed_deployment(self, scheduler, sample_deployment):
        """Test handling failed deployment"""
        scheduler.db.query.return_value.get.return_value = sample_deployment
        result = scheduler.handle_failed_deployment(
            sample_deployment.id,
            {"error": "Test error"}
        )
        assert result is True

    def test_get_deployment_status(self, scheduler, sample_deployment):
        """Test getting deployment status"""
        scheduler.db.query.return_value.get.return_value = sample_deployment
        status = scheduler.get_deployment_status(sample_deployment.id)
        assert status is not None
        assert "status" in status