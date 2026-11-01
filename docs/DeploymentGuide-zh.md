# LightRAG 远程 Linux 部署操作文档（Git Clone + 自建 Docker 镜像）

本文档适用于「**本地提交代码到自己的 GitHub → Linux 服务器 clone → Docker Compose 部署**」的路径，
并且包含你自己新加的控制面（用户/工作空间管理）、MCP、侧边栏 UI 等改动。

> 关键结论先放在最前面：**必须用 `docker compose up -d --build` 从源码构建镜像**。
> 官方镜像 `ghcr.io/hkuds/lightrag:latest` 不含你的控制面 / MCP / 管理界面改动，
> 直接 `docker compose up -d`（不带 `--build`）会拉官方镜像，你的功能会全部消失。

---

## 0. 总体流程

```
本地：提交代码（不含 .env）──▶ 推送到你的 GitHub
                                        │
服务器：安装 Docker ──▶ git clone 你的仓库 ──▶ 准备 .env ──▶ 建数据目录 ──▶ docker compose up -d --build
                                                                                        │
                                                              验证 ──▶ 反向代理 + HTTPS（可选）──▶ 上线
```

---

## 1. 本地：提交代码到你的 GitHub

### 1.1 提交前先确认「不该提交的东西」没有进暂存区

```bash
cd /path/to/lightrag
git status
```

必须确认以下内容**没有**出现在 `Changes to be committed`（或 `Untracked`）里：

- `.env` —— 含所有密钥，已被 `.gitignore` 忽略（第 15 行）
- `rag_storage/`、`inputs/` —— 本地数据，已被忽略
- `lightrag_webui/package-lock.json` —— 这是你本地用 npm 装依赖产生的，项目用 `bun.lock`，不要提交

如果你的新功能文件（`lightrag/api/control_plane.py`、`lightrag/api/routers/management_routes.py`、
`lightrag/mcp/`、`lightrag_webui/src/features/ManagementPage.tsx`、`lightrag_webui/src/components/Sidebar.tsx`
等）显示为 `Untracked`，这些**要提交**。

### 1.2 提交并推送

```bash
git add -A
git status                       # 再次确认 .env / rag_storage 不在里面
git commit -m "feat: control plane + user/workspace management UI + MCP + sidebar layout"
git remote add origin https://github.com/<你的用户名>/<你的仓库名>.git   # 首次
git push -u origin main
```

> 如果上面 `git status` 意外看到 `.env` 或数据目录，先 `git reset` 撤出，再逐个 `git add` 需要的文件，别用 `git add -A`。

---

## 2. 服务器：准备环境

### 2.1 安装 Docker 与 Compose 插件

以 Debian / Ubuntu 为例：

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER     # 免 sudo 运行 docker；执行后重新登录生效
docker --version
docker compose version
```

### 2.2 克隆你的仓库

```bash
cd /opt
sudo git clone https://github.com/<你的用户名>/<你的仓库名>.git lightrag
cd lightrag
```

---

## 3. 服务器：准备 `.env`

### 3.1 方法 A（推荐）：把本机已跑通的 `.env` 拷上去再改密钥

本机 `.env` 里的远程端点（DeepSeek / 百炼 / MinerU / OpenSearch）都是现成的，拷过去最省事：

```bash
# 在本机执行
scp /path/to/lightrag/.env  user@服务器IP:/opt/lightrag/.env
```

### 3.2 方法 B：从 `env.example` 重新生成

```bash
cd /opt/lightrag
cp env.example .env
# 按第 3.4 节的参考模板逐项填写
```

### 3.3 必须修改的配置清单

| 配置项 | 为什么改 | 改成什么 |
|---|---|---|
| `TOKEN_SECRET` | 现在是占位符，任何人可伪造登录态 | `openssl rand -hex 32` 的输出 |
| `INITIAL_ADMIN_PASSWORD` | 现在口令已知 | 新的强密码 |
| `MCP_API_KEY` | 已知 | 新的强随机值 |
| `OPENSEARCH_PASSWORD` | 已知 | 新的强密码 |
| `CONTROL_DB_PATH` | Docker 里相对路径会落到 `/app/rag_storage/control.db`，**不在挂载卷里，容器重建后数据丢失** | **删掉这一行**（让它默认落到 `WORKING_DIR/control.db` = `/app/data/rag_storage/control.db`） |
| `OPENSEARCH_HOSTS` | 确认是新服务器能访问的地址 | 保持你的远程 OpenSearch 地址（方案 A），或改成本机自建存储（方案 B） |

**LLM / Embedding / MinerU 三项不用改**（都是公网远程服务），只要服务器能出网即可。

### 3.4 完整 `.env` 参考模板（占位符）

```bash
# ===== LLM：DeepSeek（OpenAI 兼容） =====
LLM_BINDING=openai
LLM_BINDING_HOST=https://api.deepseek.com
LLM_BINDING_API_KEY=<你的DeepSeek密钥>
LLM_MODEL=deepseek-v4-pro

# ===== Embedding：阿里云百炼（OpenAI 兼容） =====
EMBEDDING_BINDING=openai
EMBEDDING_BINDING_HOST=<你的百炼compatible-mode/v1地址>
EMBEDDING_BINDING_API_KEY=<你的百炼密钥>
EMBEDDING_MODEL=qwen3.7-text-embedding-flash
EMBEDDING_DIM=1024

# ===== 文档解析：MinerU 官方云 =====
MINERU_API_MODE=official
MINERU_API_TOKEN=<你的MinerU token>
MINERU_OFFICIAL_ENDPOINT=https://mineru.net
LIGHTRAG_PARSER=pdf:mineru

# ===== 存储：OpenSearch（远程，全后端） =====
LIGHTRAG_KV_STORAGE=OpenSearchKVStorage
LIGHTRAG_VECTOR_STORAGE=OpenSearchVectorDBStorage
LIGHTRAG_GRAPH_STORAGE=OpenSearchGraphStorage
LIGHTRAG_DOC_STATUS_STORAGE=OpenSearchDocStatusStorage
OPENSEARCH_HOSTS=<你的OpenSearch地址:9200>
OPENSEARCH_USER=admin
OPENSEARCH_PASSWORD=<强随机密码>
OPENSEARCH_USE_SSL=true
OPENSEARCH_VERIFY_CERTS=false          # 有正规证书后改成 true

# ===== MCP =====
MCP_TRANSPORT=streamable-http
MCP_API_KEY=<强随机值>
MCP_HOST=0.0.0.0
MCP_PORT=8001

# ===== 控制面 / 用户管理（SQLite） =====
# 注意：不要写相对路径，下面这行直接删掉/注释掉，让它默认落在 WORKING_DIR
# CONTROL_DB_PATH=./rag_storage/control.db
INITIAL_ADMIN_USERNAME=admin
INITIAL_ADMIN_PASSWORD=<强密码>
DEFAULT_WORKSPACE_NAME=默认空间
TOKEN_SECRET=<openssl rand -hex 32 的输出>
```

生成密钥的命令：

```bash
openssl rand -hex 32          # 用于 TOKEN_SECRET
openssl rand -base64 24       # 用于 MCP_API_KEY 等
```

> `.env` 保持 UTF-8 编码（里面有中文 `默认空间`）。

---

## 4. 服务器：数据目录 + 启动

### 4.1 建数据目录

```bash
cd /opt/lightrag
mkdir -p data/rag_storage data/inputs data/prompts
```

### 4.2 构建并启动（务必 `--build`）

```bash
docker compose up -d --build
```

- 第一次构建会下载基础镜像并编译前端，可能需要几分钟。
- 之后查看日志：

```bash
docker compose logs -f lightrag
```

看到类似 `Uvicorn running on http://0.0.0.0:9621` 即启动成功。

### 4.3 如果 MCP 需要对服务器外部开放

默认 `docker-compose.yml` 只发布了 9621 端口。若外部要访问 MCP（8001），编辑 `docker-compose.yml` 的 `ports` 段：

```yaml
    ports:
      - "${HOST:-0.0.0.0}:${PORT:-9621}:9621"
      - "${MCP_PORT:-8001}:8001"      # ← 新增这行
```

改完 `docker compose up -d` 即可。

---

## 5. 验证部署

```bash
# 1) 健康检查（服务本身）
curl http://127.0.0.1:9621/health

# 2) 页面（会 302 到登录页或 WebUI）
curl -I http://127.0.0.1:9621/

# 3) 浏览器访问（本机先做端口转发或直接开安全组后访问）
#    http://<服务器IP>:9621/
```

浏览器打开后：用 `INITIAL_ADMIN_USERNAME` / `INITIAL_ADMIN_PASSWORD` 登录 → 进入「用户管理」确认工作空间/用户管理可用 → 上传一个文档验证提取和检索正常。

---

## 6. 反向代理 + HTTPS（强烈建议，别裸暴露 9621）

### Caddy（最简单，自动申请证书）

```bash
sudo apt-get install -y caddy
```

编辑 `/etc/caddy/Caddyfile`：

```caddyfile
rag.example.com {
    reverse_proxy 127.0.0.1:9621
}
```

```bash
sudo systemctl reload caddy
```

### Nginx 示例

```nginx
server {
    listen 80;
    server_name rag.example.com;
    location / {
        proxy_pass http://127.0.0.1:9621;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

再配 TLS（certbot 或云厂商证书）。

---

## 7. 安全加固清单

1. **先跑安全审计**：`make env-security-check`（在本机或服务器上都行）。
2. 第 3.3 节表里的密钥全部轮换（`TOKEN_SECRET`、`INITIAL_ADMIN_PASSWORD`、`MCP_API_KEY`、`OPENSEARCH_PASSWORD`）。
3. **防火墙只放行 80/443**，9621 / 8001 只对本机反向代理开放，不要直接暴露公网：
   ```bash
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   sudo ufw enable
   ```
4. `OPENSEARCH_VERIFY_CERTS` 有正规证书后改 `true`；`OPENSEARCH_USE_SSL` 保持 `true`。
5. 服务器安全组确保**出站**能访问：DeepSeek、百炼、MinerU、以及你的远程 OpenSearch（`<OpenSearch地址>:9200`）；OpenSearch 那边也要放行新服务器 IP。

---

## 8. 常见问题排查

| 现象 | 原因 / 处理 |
|---|---|
| 登录后没有「用户管理」、没有侧边栏、没有 MCP | 用了官方镜像。用 `docker compose up -d --build` 重建 |
| 用户/工作空间管理数据「重启就没了」 | `CONTROL_DB_PATH` 用了相对路径。删掉该行，让它落到 `WORKING_DIR/control.db` |
| 启动报连不上 OpenSearch | 检查服务器到 `<OpenSearch地址>:9200` 的**出站**网络 + OpenSearch 白名单；确认 `OPENSEARCH_USE_SSL` / 密码正确 |
| 构建报 `bun install --frozen-lockfile` 失败 | 你本地若改过 `package.json` 而没更新 `bun.lock`，先在本机 `bun install` 更新 `bun.lock` 再提交（不要提交 npm 的 `package-lock.json`） |
| 改了前端样式但服务器没变化 | 没带 `--build`；或浏览器缓存，强制刷新 `Ctrl+Shift+R` |
| 上传的文档解析不出来 | 服务器需能出网访问 MinerU；看日志 `docker compose logs -f lightrag` |

---

## 9. 后续更新代码（增量发布）

```bash
# 本机：提交并推送
git add -A && git commit -m "fix: ..." && git push

# 服务器：拉取并重建
cd /opt/lightrag
git pull
docker compose up -d --build
```

> 注意：`docker compose up -d --build` 会重建镜像并重启容器；数据在 `data/rag_storage`、`data/inputs` 挂载卷里，不受影响。
