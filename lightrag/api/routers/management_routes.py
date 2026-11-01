"""Minimal user and workspace management API backed by SQLite."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from ..auth import auth_handler
from ..control_plane import ControlPlane
from ..utils_api import get_combined_auth_dependency


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=8, max_length=256)
    display_name: str | None = Field(default=None, max_length=128)
    role: Literal["admin", "user"] = "user"

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Username cannot be empty")
        return value


class UserUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=128)
    password: str | None = Field(default=None, min_length=8, max_length=256)
    role: Literal["admin", "user"] | None = None
    status: Literal["active", "disabled"] | None = None


class WorkspaceCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    slug: str = Field(min_length=1, max_length=64)
    description: str = Field(default="", max_length=500)
    storage_namespace: str | None = Field(default=None, max_length=64)

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str) -> str:
        value = value.strip()
        if not value or not value.replace("_", "").isalnum():
            raise ValueError("Workspace slug may contain only letters, numbers, and underscores")
        return value


class WorkspaceUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=500)


class MemberRequest(BaseModel):
    user_id: str = Field(min_length=1)
    role: Literal["admin", "editor", "viewer"] = "viewer"


class MemberRoleRequest(BaseModel):
    role: Literal["admin", "editor", "viewer"]


def _public_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        key: user[key]
        for key in (
            "id", "username", "display_name", "role", "status",
            "created_at", "updated_at", "last_login_at",
        )
        if key in user
    }


def _get_bearer_token(request: Request) -> str:
    value = request.headers.get("Authorization", "")
    scheme, _, token = value.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Bearer token required")
    return token


def create_management_routes(control_plane: ControlPlane, api_key: str | None = None):
    combined_auth = get_combined_auth_dependency(api_key, respect_whitelist=False)
    router = APIRouter(
        prefix="/api/v1",
        tags=["management"],
        dependencies=[Depends(combined_auth)],
    )

    async def current_user(request: Request) -> dict[str, Any]:
        token_info = auth_handler.validate_token(_get_bearer_token(request))
        user = control_plane.get_user(token_info["username"])
        if not user or user["status"] != "active":
            raise HTTPException(status_code=401, detail="User is disabled or missing")
        return user

    async def admin_user(user: dict[str, Any] = Depends(current_user)):
        if user["role"] != "admin":
            raise HTTPException(status_code=403, detail="Administrator permission required")
        return user

    def workspace_or_404(workspace_id: str) -> dict[str, Any]:
        workspace = control_plane.get_workspace(workspace_id)
        if not workspace:
            raise HTTPException(status_code=404, detail="Workspace not found")
        return workspace

    async def workspace_member(
        workspace_id: str,
        user: dict[str, Any] = Depends(current_user),
    ) -> dict[str, Any]:
        workspace_or_404(workspace_id)
        if user["role"] == "admin":
            return user
        if control_plane.get_member_role(workspace_id, user["id"]) is None:
            raise HTTPException(status_code=403, detail="Workspace access denied")
        return user

    async def workspace_admin(
        workspace_id: str,
        user: dict[str, Any] = Depends(current_user),
    ) -> dict[str, Any]:
        workspace_or_404(workspace_id)
        role = control_plane.get_member_role(workspace_id, user["id"])
        if user["role"] != "admin" and role != "admin":
            raise HTTPException(status_code=403, detail="Workspace administrator permission required")
        return user

    @router.get("/auth/me")
    async def get_me(user: dict[str, Any] = Depends(current_user)):
        return _public_user(user)

    @router.get("/users")
    async def list_users(_: dict[str, Any] = Depends(admin_user)):
        return {"items": [_public_user(user) for user in control_plane.list_users()]}

    @router.post("/users", status_code=201)
    async def create_user(
        payload: UserCreateRequest,
        _: dict[str, Any] = Depends(admin_user),
    ):
        try:
            user = control_plane.create_user(
                payload.username,
                payload.password,
                payload.display_name or payload.username,
                payload.role,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _public_user(user)

    @router.patch("/users/{user_id}")
    async def update_user(
        user_id: str,
        payload: UserUpdateRequest,
        _: dict[str, Any] = Depends(admin_user),
    ):
        user = control_plane.update_user(
            user_id,
            display_name=payload.display_name,
            role=payload.role,
            status=payload.status,
            password=payload.password,
        )
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return _public_user(user)

    @router.get("/workspaces")
    async def list_workspaces(user: dict[str, Any] = Depends(current_user)):
        user_id = None if user["role"] == "admin" else user["id"]
        return {"items": control_plane.list_workspaces(user_id)}

    @router.post("/workspaces", status_code=201)
    async def create_workspace(
        payload: WorkspaceCreateRequest,
        user: dict[str, Any] = Depends(admin_user),
    ):
        try:
            workspace = control_plane.create_workspace(
                name=payload.name.strip(),
                slug=payload.slug,
                description=payload.description,
                storage_namespace=payload.storage_namespace or payload.slug,
                owner_id=user["id"],
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return workspace

    @router.get("/workspaces/{workspace_id}")
    async def get_workspace(
        workspace_id: str,
        _: dict[str, Any] = Depends(workspace_member),
    ):
        return workspace_or_404(workspace_id)

    @router.patch("/workspaces/{workspace_id}")
    async def update_workspace(
        workspace_id: str,
        payload: WorkspaceUpdateRequest,
        _: dict[str, Any] = Depends(workspace_admin),
    ):
        workspace = control_plane.update_workspace(
            workspace_id, name=payload.name, description=payload.description
        )
        if not workspace:
            raise HTTPException(status_code=404, detail="Workspace not found")
        return workspace

    @router.post("/workspaces/{workspace_id}/archive")
    async def archive_workspace(
        workspace_id: str,
        _: dict[str, Any] = Depends(workspace_admin),
    ):
        if not control_plane.archive_workspace(workspace_id):
            raise HTTPException(status_code=404, detail="Workspace not found")
        return {"status": "archived", "workspace_id": workspace_id}

    @router.get("/workspaces/{workspace_id}/members")
    async def list_members(
        workspace_id: str,
        _: dict[str, Any] = Depends(workspace_member),
    ):
        workspace_or_404(workspace_id)
        return {"items": control_plane.get_members(workspace_id)}

    @router.post("/workspaces/{workspace_id}/members")
    async def add_member(
        workspace_id: str,
        payload: MemberRequest,
        _: dict[str, Any] = Depends(workspace_admin),
    ):
        workspace_or_404(workspace_id)
        if not control_plane.get_user_by_id(payload.user_id):
            raise HTTPException(status_code=404, detail="User not found")
        control_plane.set_member(workspace_id, payload.user_id, payload.role)
        return {"workspace_id": workspace_id, "user_id": payload.user_id, "role": payload.role}

    @router.patch("/workspaces/{workspace_id}/members/{user_id}")
    async def update_member(
        workspace_id: str,
        user_id: str,
        payload: MemberRoleRequest,
        _: dict[str, Any] = Depends(workspace_admin),
    ):
        workspace_or_404(workspace_id)
        if not control_plane.get_user_by_id(user_id):
            raise HTTPException(status_code=404, detail="User not found")
        control_plane.set_member(workspace_id, user_id, payload.role)
        return {"workspace_id": workspace_id, "user_id": user_id, "role": payload.role}

    @router.delete("/workspaces/{workspace_id}/members/{user_id}")
    async def remove_member(
        workspace_id: str,
        user_id: str,
        _: dict[str, Any] = Depends(workspace_admin),
    ):
        workspace_or_404(workspace_id)
        if not control_plane.remove_member(workspace_id, user_id):
            raise HTTPException(status_code=404, detail="Member not found")
        return {"status": "removed"}

    return router
