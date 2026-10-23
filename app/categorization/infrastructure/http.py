"""FastAPI adapter for categorization: the category listing."""

from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.categorization.application.use_cases import CategorizationServices
from app.identity.public import AuthenticatedUser, require_user


def categorization_services() -> CategorizationServices:
    """Placeholder dependency; the composition root (app.bootstrap.wire) overrides it with a real provider."""
    raise RuntimeError("Categorization is not wired: call app.bootstrap.wire(app, container)")


class CategoryOut(BaseModel):
    id: int
    name: str
    kind: Literal["expense", "income"]
    icon: str
    color: str


router = APIRouter()


@router.get("/api/categories", response_model=list[CategoryOut])
def list_categories(
    services: CategorizationServices = Depends(categorization_services),
    _: AuthenticatedUser = Depends(require_user),
) -> list[dict[str, Any]]:
    return [
        {"id": c.id, "name": c.name, "kind": c.kind, "icon": c.icon, "color": c.color}
        for c in services.list_categories()
    ]
