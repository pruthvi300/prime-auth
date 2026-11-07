from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

# In-memory storage is fine for a single instance. With several replicas,
# pass storage_uri="redis://..." so all instances share the counters.
limiter = Limiter(key_func=get_remote_address, enabled=settings.RATE_LIMIT_ENABLED)
