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
        self.DEPLOYMENT_TIMEOUT = 3600  # 1 hour in seconds
        self.RESOURCE_SCALE = 1000  # Scale factor for float to int conversion

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
        try:
            # Scale resources to integers
            scaled_resources = {
                'ram': int(cluster.available_ram * self.RESOURCE_SCALE),
                'cpu': int(cluster.available_cpu * self.RESOURCE_SCALE),
                'gpu': int(cluster.available_gpu * self.RESOURCE_SCALE),
                'total_ram': int(cluster.total_ram * self.RESOURCE_SCALE),
                'total_cpu': int(cluster.total_cpu * self.RESOURCE_SCALE),
                'total_gpu': int(cluster.total_gpu * self.RESOURCE_SCALE)
            }

            # Validate resources are not negative
            if any(value < 0 for value in scaled_resources.values()):
                raise ValueError("Resource values cannot be negative")

            self.redis.hset(
                self.RESOURCE_KEY.format(cluster.id),
                mapping=scaled_resources
            )
            logger.info(f"Updated resources for cluster {cluster.id}")

        except Exception as e:
            logger.error(f"Error updating cluster resources: {e}")
            raise

    def get_cluster_resources(self, cluster_id: int) -> Dict:
        """Get cluster resources from Redis"""
        try:
            resource_key = self.RESOURCE_KEY.format(cluster_id)
            scaled_resources = self.redis.hgetall(resource_key)

            if not scaled_resources:
                logger.warning(f"No resources found for cluster {cluster_id}")
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
        except Exception as e:
            logger.error(f"Error getting cluster resources: {e}")
            return {}

    def enqueue_deployment(self, deployment: Deployment) -> bool:
        """
        Add deployment to queue only if resources aren't immediately available
        Returns True if deployment was scheduled or queued successfully
        """
        try:
            # First check if we can schedule it immediately
            cluster_resources = self.get_cluster_resources(deployment.cluster_id)
            required_resources = {
                'ram': deployment.required_ram,
                'cpu': deployment.required_cpu,
                'gpu': deployment.required_gpu
            }

            # If resources are available, start deployment immediately
            if self.can_schedule(cluster_resources, required_resources):
                logger.info(f"Resources available for deployment {deployment.id}, starting immediately")
                return self.start_deployment(
                    deployment.cluster_id,
                    deployment.id,
                    required_resources
                )

            # If resources aren't available, queue the deployment
            logger.info(f"Resources not available for deployment {deployment.id}, adding to queue")
            deployment_info = {
                'id': str(deployment.id),
                'name': deployment.name,
                'cluster_id': str(deployment.cluster_id),
                'priority': str(deployment.priority),
                'required_ram': str(deployment.required_ram),
                'required_cpu': str(deployment.required_cpu),
                'required_gpu': str(deployment.required_gpu),
                'created_at': deployment.created_at.isoformat()
            }

            # Calculate priority score
            score = self.calculate_priority_score(
                deployment.priority,
                deployment.created_at
            )

            # Add to queue using Redis transaction
            with self.redis.pipeline() as pipe:
                pipe.hset(
                    self.DEPLOYMENT_KEY.format(deployment.id),
                    mapping=deployment_info
                )
                pipe.zadd(
                    self.QUEUE_KEY,
                    {str(deployment.id): score}
                )
                pipe.execute()

            # Update deployment status to QUEUED in database
            deployment.status = DeploymentStatus.QUEUED
            self.db.commit()

            logger.info(f"Deployment {deployment.id} queued with priority {deployment.priority}")
            return True

        except Exception as e:
            logger.error(f"Error handling deployment {deployment.id}: {str(e)}")
            self.db.rollback()
            return False

    def get_next_deployment(self, cluster_id: int) -> Optional[Dict]:
        """Get highest priority deployment that can be scheduled"""
        try:
            # Get available resources for cluster
            resources = self.get_cluster_resources(cluster_id)
            if not resources:
                logger.warning(f"No resources available for cluster {cluster_id}")
                return None

            # Get all pending deployments sorted by priority
            pending_deployments = self.redis.zrevrange(
                self.QUEUE_KEY,
                0, -1,
                withscores=True
            )

            for deployment_id, score in pending_deployments:
                # Get deployment info from Redis
                deployment_info = self.redis.hgetall(
                    self.DEPLOYMENT_KEY.format(deployment_id)
                )

                if not deployment_info:
                    continue

                # Convert stored string values back to appropriate types
                deployment_info['id'] = int(deployment_info['id'])
                deployment_info['cluster_id'] = int(deployment_info['cluster_id'])
                deployment_info['priority'] = int(deployment_info['priority'])
                deployment_info['required_ram'] = float(deployment_info['required_ram'])
                deployment_info['required_cpu'] = float(deployment_info['required_cpu'])
                deployment_info['required_gpu'] = float(deployment_info['required_gpu'])

                # Check if deployment belongs to this cluster
                if deployment_info['cluster_id'] != cluster_id:
                    continue

                # Check resource requirements
                required_resources = {
                    'ram': deployment_info['required_ram'],
                    'cpu': deployment_info['required_cpu'],
                    'gpu': deployment_info['required_gpu']
                }

                if self.can_schedule(resources, required_resources):
                    logger.info(f"Found suitable deployment {deployment_id} for cluster {cluster_id}")
                    return {
                        'id': deployment_info['id'],
                        'info': deployment_info,
                        'score': score
                    }

            logger.info(f"No suitable deployments found for cluster {cluster_id}")
            return None

        except Exception as e:
            logger.error(f"Error getting next deployment: {str(e)}")
            return None

    def process_deployments(self, cluster_id: int) -> List[Dict]:
        """
        Process queued deployments for a cluster based on priority
        Only called when resources become available
        """
        scheduled = []

        try:
            resources = self.get_cluster_resources(cluster_id)
            if not resources:
                logger.warning(f"No resources found for cluster {cluster_id}")
                return scheduled

            while True:
                next_deployment = self.get_next_deployment(cluster_id)
                if not next_deployment:
                    break

                deployment_id = next_deployment['id']
                deployment_info = next_deployment['info']

                required_resources = {
                    'ram': deployment_info['required_ram'],
                    'cpu': deployment_info['required_cpu'],
                    'gpu': deployment_info['required_gpu']
                }

                # Double-check resources are still available
                if not self.can_schedule(resources, required_resources):
                    logger.info(f"Resources no longer available for deployment {deployment_id}")
                    break

                # Start deployment
                success = self.start_deployment(
                    cluster_id,
                    int(deployment_id),
                    required_resources
                )

                if success:
                    scheduled.append(deployment_info)
                    logger.info(f"Successfully scheduled queued deployment {deployment_id}")

                    # Update available resources for next iteration
                    resources = self.get_cluster_resources(cluster_id)
                else:
                    logger.warning(f"Failed to start deployment {deployment_id}")
                    break

            return scheduled

        except Exception as e:
            logger.error(f"Error processing deployments: {str(e)}")
            return scheduled

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
            if not deployment:
                raise ValueError(f"Deployment {deployment_id} not found")

            deployment.status = DeploymentStatus.RUNNING
            deployment.started_at = datetime.utcnow()
            self.db.commit()

            logger.info(f"Started deployment {deployment_id}")
            return True

        except Exception as e:
            logger.error(f"Error starting deployment {deployment_id}: {str(e)}")
            self.db.rollback()
            return False

    def complete_deployment(
            self,
            deployment_id: int,
            status: DeploymentStatus,
            completion_details: Optional[Dict] = None
    ) -> bool:
        """Handle deployment completion"""
        try:
            # Get deployment from database
            deployment = self.db.query(Deployment).get(deployment_id)
            if not deployment:
                logger.error(f"Deployment {deployment_id} not found")
                return False

            # Validate status transition
            if deployment.status == DeploymentStatus.COMPLETED:
                logger.error(f"Deployment {deployment_id} is already completed")
                return False

            # Create resources dict from deployment attributes
            resources = {
                'ram': deployment.required_ram,
                'cpu': deployment.required_cpu,
                'gpu': deployment.required_gpu
            }

            # Update deployment status in database
            deployment.status = status
            deployment.completed_at = datetime.utcnow()

            if completion_details:
                deployment.completion_details = completion_details

            # Remove from Redis and release resources
            with self.redis.pipeline() as pipe:
                # Remove from queue if still there
                pipe.zrem(self.QUEUE_KEY, str(deployment_id))
                pipe.delete(self.DEPLOYMENT_KEY.format(deployment_id))
                pipe.execute()

            # Release cluster resources
            self.release_resources(deployment.cluster_id, resources)

            # Commit database changes
            self.db.commit()

            # Process next pending deployments
            next_deployments = self.process_deployments(deployment.cluster_id)
            if next_deployments:
                logger.info(f"Scheduled {len(next_deployments)} deployments after completion")

            logger.info(f"Completed deployment {deployment_id} with status {status}")
            return True

        except Exception as e:
            logger.error(f"Error completing deployment {deployment_id}: {str(e)}")
            self.db.rollback()
            return False

    def release_resources(self, cluster_id: int, resources: Dict) -> None:
        """Release resources back to the cluster"""
        try:
            # Scale resources to integers
            scaled_resources = self._scale_resources(resources)
            resource_key = self.RESOURCE_KEY.format(cluster_id)

            # Get current resources
            current_resources = self.get_cluster_resources(cluster_id)
            if not current_resources:
                raise ValueError("Cluster resources not found")

            with self.redis.pipeline() as pipe:
                pipe.hincrby(resource_key, 'ram', scaled_resources['ram'])
                pipe.hincrby(resource_key, 'cpu', scaled_resources['cpu'])
                pipe.hincrby(resource_key, 'gpu', scaled_resources['gpu'])
                pipe.execute()

            logger.info(f"Released resources for cluster {cluster_id}: {resources}")

        except Exception as e:
            logger.error(f"Error releasing resources: {str(e)}")
            raise

    def _scale_resources(self, resources: Dict) -> Dict:
        """Convert float resources to scaled integers"""
        return {
            'ram': int(float(resources['ram']) * self.RESOURCE_SCALE),
            'cpu': int(float(resources['cpu']) * self.RESOURCE_SCALE),
            'gpu': int(float(resources['gpu']) * self.RESOURCE_SCALE)
        }

    def calculate_priority_score(self, priority: int, created_at: datetime) -> float:
        """Calculate priority score for sorting"""
        base_score = priority * 10000
        time_score = created_at.timestamp()
        return base_score - time_score

    def can_schedule(self, available: Dict, required: Dict) -> bool:
        """Check if required resources are available"""
        try:
            # Scale both available and required resources
            scaled_available = self._scale_resources(available)
            scaled_required = self._scale_resources(required)

            return (
                    scaled_available['ram'] >= scaled_required['ram'] and
                    scaled_available['cpu'] >= scaled_required['cpu'] and
                    scaled_available['gpu'] >= scaled_required['gpu']
            )
        except Exception as e:
            logger.error(f"Error checking resource availability: {e}")
            return False

    def get_queue_metrics(self) -> Dict:
        """Get queue metrics"""
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

                if priority >= 9:
                    metrics['priority_distribution']['critical'] += 1
                elif priority >= 7:
                    metrics['priority_distribution']['high'] += 1
                elif priority >= 4:
                    metrics['priority_distribution']['medium'] += 1
                else:
                    metrics['priority_distribution']['low'] += 1

                metrics['highest_priority'] = max(
                    metrics['highest_priority'],
                    priority
                )

            return metrics

        except Exception as e:
            logger.error(f"Error getting queue metrics: {str(e)}")
            return {}


    def handle_deployment_timeout(self, deployment_id: int) -> bool:
        """Handle deployments that have timed out"""
        try:
            deployment = self.db.query(Deployment).get(deployment_id)
            if not deployment or deployment.status != DeploymentStatus.RUNNING:
                return False

            # Check if deployment has exceeded timeout
            if deployment.started_at:
                elapsed_time = datetime.utcnow() - deployment.started_at
                if elapsed_time.total_seconds() > self.DEPLOYMENT_TIMEOUT:
                    return self.complete_deployment(
                        deployment_id,
                        DeploymentStatus.FAILED,
                        {"reason": "Deployment timed out"}
                    )
            return False

        except Exception as e:
            logger.error(f"Error handling deployment timeout: {str(e)}")
            return False

    def handle_failed_deployment(
            self,
            deployment_id: int,
            error_details: Dict
    ) -> bool:
        """Handle failed deployments"""
        return self.complete_deployment(
            deployment_id,
            DeploymentStatus.FAILED,
            {"error": error_details}
        )

    def handle_successful_deployment(
            self,
            deployment_id: int,
            success_details: Optional[Dict] = None
    ) -> bool:
        """Handle successful deployments"""
        return self.complete_deployment(
            deployment_id,
            DeploymentStatus.COMPLETED,
            success_details
        )

    def get_deployment_status(
            self,
            deployment_id: int
    ) -> Optional[Dict]:
        """Get detailed deployment status"""
        try:
            # Get from database
            deployment = self.db.query(Deployment).get(deployment_id)
            if not deployment:
                return None

            # Get Redis info if available
            deployment_info = self.redis.hgetall(
                self.DEPLOYMENT_KEY.format(deployment_id)
            )

            return {
                "id": deployment.id,
                "status": deployment.status,
                "started_at": deployment.started_at,
                "completed_at": deployment.completed_at,
                "completion_details": getattr(deployment, 'completion_details', None),
                "queue_info": deployment_info if deployment_info else None
            }

        except Exception as e:
            logger.error(f"Error getting deployment status: {str(e)}")
            return None