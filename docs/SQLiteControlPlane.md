# SQLite User and Workspace Management

The API server now includes a small SQLite control plane for local users, workspaces, and workspace memberships.

## Configuration

Set these values in `.env` before the first start:

```ini
CONTROL_DB_PATH=./rag_storage/control.db
INITIAL_ADMIN_USERNAME=admin
INITIAL_ADMIN_PASSWORD=change-this-password
TOKEN_SECRET=replace-with-a-long-random-secret
DEFAULT_WORKSPACE_NAME=Default Workspace
```

The first startup creates the administrator and a `default` workspace. The configured `WORKSPACE` value remains the LightRAG storage namespace; an empty `WORKSPACE` is represented by the logical `default` workspace.

After the first startup, change or remove `INITIAL_ADMIN_PASSWORD`. User passwords are stored as bcrypt hashes in the SQLite file.

## Login

```bash
curl -X POST http://127.0.0.1:9621/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=change-this-password"
```

Use the returned token as:

```http
Authorization: Bearer <access_token>
```

## Management API

The management API is under `/api/v1`:

```text
GET    /api/v1/auth/me
GET    /api/v1/users
POST   /api/v1/users
PATCH  /api/v1/users/{user_id}
GET    /api/v1/workspaces
POST   /api/v1/workspaces
GET    /api/v1/workspaces/{workspace_id}
PATCH  /api/v1/workspaces/{workspace_id}
POST   /api/v1/workspaces/{workspace_id}/archive
GET    /api/v1/workspaces/{workspace_id}/members
POST   /api/v1/workspaces/{workspace_id}/members
PATCH  /api/v1/workspaces/{workspace_id}/members/{user_id}
DELETE /api/v1/workspaces/{workspace_id}/members/{user_id}
```

The global `admin` role manages all users and workspaces. Workspace roles are `admin`, `editor`, and `viewer`.

## Current scope

This is intentionally a minimal control plane. It manages accounts and workspace membership while existing document, query, graph, and MCP routes continue to use the server's configured LightRAG workspace. Dynamic per-request LightRAG runtime switching is not included in this first version.

For multiple independent data workspaces, run one LightRAG process per workspace or add a later runtime-manager layer before exposing workspace switching to end users.
