import redis
import json
from datetime import datetime
from typing import Dict, List, Optional
import logging
from sqlalchemy.orm import Session
from ..models.cluster import Cluster, Deployment, DeploymentStatus

logger = logging.getLogger(__name__)

class PriorityScheduler:
    def __init__(self, db: Session, redis_client: redis.Redis):
        self.db = db
        self.redis = redis_client

        # Redis key prefixes
        self.QUEUE_KEY = "deployment:queue"  # Sorted set for priority queue
        self.RESOURCE_KEY = "cluster:resources:{}"  # Hash for cluster resources
        self.DEPLOYMENT_KEY = "deployment:info:{}"  # Hash for deployment details

        # Priority ranges (higher number = higher priority)
        self.PRIORITY_RANGES = {
            "critical": (900, 1000),  # Priority 9-10
            "high": (700, 899),       # Priority 7-8
            "medium": (400, 699),     # Priority 4-6
            "low": (100, 399),        # Priority 1-3
        }


    def update_cluster_resources(self, cluster: Cluster) -> None:
        """Update cluster resources in Redis"""
        # Scale resources to integers
        scaled_resources = {
            'ram': int(cluster.available_ram * self.RESOURCE_SCALE),
            'cpu': int(cluster.available_cpu * self.RESOURCE_SCALE),
            'gpu': int(cluster.available_gpu * self.RESOURCE_SCALE),
            'total_ram': int(cluster.total_ram * self.RESOURCE_SCALE),
            'total_cpu': int(cluster.total_cpu * self.RESOURCE_SCALE),
            'total_gpu': int(cluster.total_gpu * self.RESOURCE_SCALE)
        }

        self.redis.hmset(
            self.RESOURCE_KEY.format(cluster.id),
            scaled_resources
        )

    def get_cluster_resources(self, cluster_id: int) -> Dict:
        """Get cluster resources from Redis"""
        resource_key = self.RESOURCE_KEY.format(cluster_id)
        scaled_resources = self.redis.hgetall(resource_key)

        if not scaled_resources:
            return {}

        # Convert back to floats
        return {
            'ram': float(scaled_resources['ram']) / self.RESOURCE_SCALE,
            'cpu': float(scaled_resources['cpu']) / self.RESOURCE_SCALE,
            'gpu': float(scaled_resources['gpu']) / self.RESOURCE_SCALE,
            'total_ram': float(scaled_resources['total_ram']) / self.RESOURCE_SCALE,
            'total_cpu': float(scaled_resources['total_cpu']) / self.RESOURCE_SCALE,
            'total_gpu': float(scaled_resources['total_gpu']) / self.RESOURCE_SCALE
        }

    def can_schedule(self, available: Dict, required: Dict) -> bool:
        """Check if required resources are available"""
        # Scale both available and required resources
        scaled_available = self._scale_resources(available)
        scaled_required = self._scale_resources(required)

        return (
                scaled_available['ram'] >= scaled_required['ram'] and
                scaled_available['cpu'] >= scaled_required['cpu'] and
                scaled_available['gpu'] >= scaled_required['gpu']
        )

    def release_resources(self, cluster_id: int, resources: Dict) -> None:
        """Release resources back to the cluster"""
        try:
            # Scale resources to integers
            scaled_resources = self._scale_resources(resources)
            resource_key = self.RESOURCE_KEY.format(cluster_id)

            with self.redis.pipeline() as pipe:
                pipe.hincrby(resource_key, 'ram', scaled_resources['ram'])
                pipe.hincrby(resource_key, 'cpu', scaled_resources['cpu'])
                pipe.hincrby(resource_key, 'gpu', scaled_resources['gpu'])
                pipe.execute()

        except Exception as e:
            logger.error(f"Error releasing resources: {str(e)}")
            raise

    def calculate_priority_score(self, priority: int, created_at: datetime) -> float:
        """
        Calculate priority score for sorting.
        Combines priority level with creation time to maintain FIFO within same priority.
        """
        base_score = priority * 10000  # Priority is the main factor
        time_score = created_at.timestamp()  # Earlier times get priority within same level
        return base_score - time_score

    def enqueue_deployment(self, deployment: Deployment) -> bool:
        """Add deployment to priority queue"""
        try:
            # Prepare deployment info
            deployment_info = {
                'id': deployment.id,
                'name': deployment.name,
                'cluster_id': deployment.cluster_id,
                'priority': deployment.priority,
                'required_resources': {
                    'ram': deployment.required_ram,
                    'cpu': deployment.required_cpu,
                    'gpu': deployment.required_gpu
                },
                'created_at': deployment.created_at.isoformat()
            }

            # Calculate priority score
            score = self.calculate_priority_score(
                deployment.priority,
                deployment.created_at
            )

            # Use Redis transaction to ensure atomic operations
            with self.redis.pipeline() as pipe:
                # Store deployment info
                pipe.hmset(
                    self.DEPLOYMENT_KEY.format(deployment.id),
                    deployment_info
                )

                # Add to priority queue
                pipe.zadd(
                    self.QUEUE_KEY,
                    {str(deployment.id): score}
                )

                pipe.execute()

            logger.info(f"Deployment {deployment.id} enqueued with priority score {score}")
            return True

        except Exception as e:
            logger.error(f"Error enqueueing deployment: {str(e)}")
            return False

    def get_next_deployment(self, cluster_id: int) -> Optional[Dict]:
        """Get highest priority deployment that can be scheduled"""
        try:
            # Get available resources for cluster
            resources = self.get_cluster_resources(cluster_id)
            if not resources:
                return None

            # Get all pending deployments sorted by priority
            pending_deployments = self.redis.zrevrange(
                self.QUEUE_KEY,
                0, -1,
                withscores=True
            )

            for deployment_id, score in pending_deployments:
                deployment_info = self.redis.hgetall(
                    self.DEPLOYMENT_KEY.format(deployment_id)
                )

                if not deployment_info:
                    continue

                # Check if deployment belongs to this cluster
                if int(deployment_info['cluster_id']) != cluster_id:
                    continue

                # Check resource requirements
                required = json.loads(deployment_info['required_resources'])
                if self.can_schedule(resources, required):
                    return {
                        'id': deployment_id,
                        'info': deployment_info,
                        'score': score
                    }

            return None

        except Exception as e:
            logger.error(f"Error getting next deployment: {str(e)}")
            return None



    def process_deployments(self, cluster_id: int) -> List[Dict]:
        """Process deployments for a cluster based on priority"""
        scheduled = []

        while True:
            next_deployment = self.get_next_deployment(cluster_id)
            if not next_deployment:
                break

            deployment_id = next_deployment['id']
            deployment_info = next_deployment['info']

            # Start deployment
            success = self.start_deployment(
                cluster_id,
                int(deployment_id),
                json.loads(deployment_info['required_resources'])
            )

            if success:
                scheduled.append(deployment_info)
            else:
                break

        return scheduled

    RESOURCE_SCALE = 1000

    def _scale_resources(self, resources: Dict) -> Dict:
        """Convert float resources to scaled integers"""
        return {
            'ram': int(float(resources['ram']) * self.RESOURCE_SCALE),
            'cpu': int(float(resources['cpu']) * self.RESOURCE_SCALE),
            'gpu': int(float(resources['gpu']) * self.RESOURCE_SCALE)
        }

    def _unscale_resources(self, resources: Dict) -> Dict:
        """Convert scaled integers back to floats"""
        return {
            'ram': float(resources['ram']) / self.RESOURCE_SCALE,
            'cpu': float(resources['cpu']) / self.RESOURCE_SCALE,
            'gpu': float(resources['gpu']) / self.RESOURCE_SCALE
        }

    def start_deployment(self, cluster_id: int, deployment_id: int, required_resources: Dict) -> bool:
        """Start a deployment and allocate resources"""
        try:
            # Scale resources to integers
            scaled_resources = self._scale_resources(required_resources)
            resource_key = self.RESOURCE_KEY.format(cluster_id)

            with self.redis.pipeline() as pipe:
                # Remove from queue
                pipe.zrem(self.QUEUE_KEY, str(deployment_id))

                # Update cluster resources using scaled integers
                pipe.hincrby(resource_key, 'ram', -scaled_resources['ram'])
                pipe.hincrby(resource_key, 'cpu', -scaled_resources['cpu'])
                pipe.hincrby(resource_key, 'gpu', -scaled_resources['gpu'])

                pipe.execute()

            # Update deployment status in database
            deployment = self.db.query(Deployment).get(deployment_id)
            deployment.status = DeploymentStatus.RUNNING
            deployment.started_at = datetime.utcnow()
            self.db.commit()

            return True

        except Exception as e:
            logger.error(f"Error starting deployment: {str(e)}")
            return False
    def get_queue_metrics(self) -> Dict:
        """Get metrics about the current queue state"""
        try:
            all_deployments = self.redis.zrevrange(
                self.QUEUE_KEY,
                0, -1,
                withscores=True
            )

            metrics = {
                'total_pending': len(all_deployments),
                'priority_distribution': {
                    'critical': 0,
                    'high': 0,
                    'medium': 0,
                    'low': 0
                },
                'oldest_deployment': None,
                'highest_priority': 0
            }

            for _, score in all_deployments:
                priority = int(score // 10000)

                # Update priority distribution
                if priority >= 9:
                    metrics['priority_distribution']['critical'] += 1
                elif priority >= 7:
                    metrics['priority_distribution']['high'] += 1
                elif priority >= 4:
                    metrics['priority_distribution']['medium'] += 1
                else:
                    metrics['priority_distribution']['low'] += 1

                # Update highest priority
                metrics['highest_priority'] = max(
                    metrics['highest_priority'],
                    priority
                )

            return metrics

        except Exception as e:
            logger.error(f"Error getting queue metrics: {str(e)}")
            return {}

    def rebalance_queue(self) -> bool:
        """Rebalance queue priorities based on waiting time"""
        try:
            current_time = datetime.utcnow().timestamp()

            # Get all pending deployments
            pending = self.redis.zrange(
                self.QUEUE_KEY,
                0, -1,
                withscores=True
            )

            with self.redis.pipeline() as pipe:
                for deployment_id, old_score in pending:
                    info = self.redis.hgetall(
                        self.DEPLOYMENT_KEY.format(deployment_id)
                    )

                    if not info:
                        continue

                    created_at = datetime.fromisoformat(info['created_at'])
                    wait_time = current_time - created_at.timestamp()

                    # Increase priority for long-waiting deployments
                    if wait_time > 3600:  # Waiting more than 1 hour
                        priority = min(int(info['priority']) + 1, 10)
                        new_score = self.calculate_priority_score(
                            priority,
                            created_at
                        )

                        pipe.zadd(self.QUEUE_KEY, {deployment_id: new_score})

                pipe.execute()
            return True

        except Exception as e:
            logger.error(f"Error rebalancing queue: {str(e)}")
            return False