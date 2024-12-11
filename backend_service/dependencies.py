from functools import lru_cache
from redis import Redis
from sqlalchemy.orm import Session
from .database.base import get_db
from .scheduler.scheduler import PriorityScheduler
import os

redis_client = Redis(
    host=os.getenv('REDIS_HOST', 'localhost'),
    port=int(os.getenv('REDIS_PORT', 6379)),
    db=int(os.getenv('REDIS_DB', 0)),
    decode_responses=True
)

_scheduler = None

def init_scheduler(db: Session):
    """Initialize the scheduler"""
    global _scheduler
    _scheduler = PriorityScheduler(db, redis_client)

def get_scheduler():
    """Dependency to get scheduler instance"""
    if _scheduler is None:
        db = next(get_db())
        init_scheduler(db)
    return _scheduler