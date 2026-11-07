# Import every model here so Base.metadata knows all tables (used by Alembic and tests).
from app.db.base_class import Base  # noqa: F401
from app.models.refresh_token import RefreshToken  # noqa: F401
from app.models.user import User  # noqa: F401
