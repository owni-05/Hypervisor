import pytest
from backend_service.scheduler.scheduler import PriorityScheduler

@pytest.fixture
def scheduler(mock_db, mock_redis):
    return PriorityScheduler(mock_db, mock_redis)

class TestSchedulerIntegration:
    def test_process_deployments(self, scheduler, sample_deployment):
        """Test processing deployments"""
        # Set up mock responses
        scheduler.get_next_deployment.return_value = {
            'id': sample_deployment.id,
            'info': {
                'id': str(sample_deployment.id),
                'required_ram': str(sample_deployment.required_ram),
                'required_cpu': str(sample_deployment.required_cpu),
                'required_gpu': str(sample_deployment.required_gpu)
            },
            'score': 1000
        }
        scheduler.start_deployment = Mock(return_value=True)

        # Process deployments
        result = scheduler.process_deployments(sample_deployment.cluster_id)
        assert len(result) > 0

    def test_full_deployment_lifecycle(self, scheduler, sample_deployment):
        """Test full deployment lifecycle"""
        # Enqueue
        assert scheduler.enqueue_deployment(sample_deployment)

        # Start
        resources = {
            'ram': sample_deployment.required_ram,
            'cpu': sample_deployment.required_cpu,
            'gpu': sample_deployment.required_gpu
        }
        assert scheduler.start_deployment(
            sample_deployment.cluster_id,
            sample_deployment.id,
            resources
        )

        # Complete
        assert scheduler.complete_deployment(
            sample_deployment.id,
            DeploymentStatus.COMPLETED,
            {"message": "Success"}
        )

    def test_error_handling(self, scheduler, sample_deployment):
        """Test error handling in scheduler"""
        # Simulate Redis error
        scheduler.redis.hset.side_effect = redis.RedisError("Test error")
        result = scheduler.enqueue_deployment(sample_deployment)
        assert result is False

        # Simulate DB error
        scheduler.db.commit.side_effect = Exception("Test error")
        result = scheduler.complete_deployment(
            sample_deployment.id,
            DeploymentStatus.COMPLETED
        )
        assert result is False