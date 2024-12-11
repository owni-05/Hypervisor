import pytest
from backend_service.scheduler.scheduler import PriorityScheduler
from datetime import datetime

@pytest.fixture
def scheduler(mock_db, mock_redis):
    return PriorityScheduler(mock_db, mock_redis)

class TestQueueOperations:
    def test_enqueue_deployment(self, scheduler, sample_deployment):
        """Test enqueueing a deployment"""
        scheduler.redis.pipeline.return_value.execute.return_value = [True, True]
        result = scheduler.enqueue_deployment(sample_deployment)
        assert result is False

    def test_get_next_deployment(self, scheduler, sample_deployment):
        """Test getting next deployment"""
        scheduler.redis.zrevrange.return_value = [(str(sample_deployment.id), 1000)]
        scheduler.redis.hgetall.return_value = {
            'id': str(sample_deployment.id),
            'name': sample_deployment.name,
            'cluster_id': str(sample_deployment.cluster_id),
            'priority': str(sample_deployment.priority),
            'required_ram': str(sample_deployment.required_ram),
            'required_cpu': str(sample_deployment.required_cpu),
            'required_gpu': str(sample_deployment.required_gpu),
            'created_at': sample_deployment.created_at.isoformat()
        }

        next_deployment = scheduler.get_next_deployment(sample_deployment.cluster_id)
        assert next_deployment is  None
        assert next_deployment['id'] == sample_deployment.id

    def test_get_queue_metrics(self, scheduler):
        """Test getting queue metrics"""
        scheduler.redis.zrevrange.return_value = [
            ("1", 900),  # Critical
            ("2", 700),  # High
            ("3", 500),  # Medium
            ("4", 200)   # Low
        ]

        metrics = scheduler.get_queue_metrics()
        assert metrics['total_pending'] == 4
        assert all(k in metrics['priority_distribution']
                   for k in ['critical', 'high', 'medium', 'low'])

