from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.schemas.user import User

router = APIRouter()


@router.get("/me", response_model=User)
async def read_me(current_user: CurrentUser):
    return current_user
