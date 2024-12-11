import pytest
from backend_service.scheduler.scheduler import PriorityScheduler

@pytest.fixture
def scheduler(mock_db, mock_redis):
    return PriorityScheduler(mock_db, mock_redis)

class TestResourceManagement:
    def test_update_cluster_resources(self, scheduler, sample_cluster):
        """Test updating cluster resources in Redis"""
        scheduler.update_cluster_resources(sample_cluster)
        scheduler.redis.hset.assert_called_once()

    def test_get_cluster_resources(self, scheduler, sample_cluster):
        """Test getting cluster resources from Redis"""
        scheduler.redis.hgetall.return_value = {
            'ram': '32000',
            'cpu': '8000',
            'gpu': '2000',
            'total_ram': '32000',
            'total_cpu': '8000',
            'total_gpu': '2000'
        }
        resources = scheduler.get_cluster_resources(sample_cluster.id)
        assert all(k in resources for k in ['ram', 'cpu', 'gpu'])

    def test_release_resources(self, scheduler, sample_cluster):
        """Test releasing resources"""
        resources = {'ram': 4.0, 'cpu': 2.0, 'gpu': 0.0}
        scheduler.release_resources(sample_cluster.id, resources)
        scheduler.redis.pipeline.assert_called_once()

    def test_can_schedule_with_sufficient_resources(self, scheduler):
        """Test resource availability check with sufficient resources"""
        available = {'ram': 8.0, 'cpu': 4.0, 'gpu': 1.0}
        required = {'ram': 4.0, 'cpu': 2.0, 'gpu': 0.0}
        assert scheduler.can_schedule(available, required) is True

    def test_can_schedule_with_insufficient_resources(self, scheduler):
        """Test resource availability check with insufficient resources"""
        available = {'ram': 2.0, 'cpu': 1.0, 'gpu': 0.0}
        required = {'ram': 4.0, 'cpu': 2.0, 'gpu': 0.0}
        assert scheduler.can_schedule(available, required) is False