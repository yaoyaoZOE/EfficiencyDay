# EfficiencyDay

个人日常工作项管理工具。当前已接通个人账号登录/退出、工作项创建、分页列表及详情读取；编辑、状态流转和四象限视图尚未开放。仓库同时提供本地开发和 Docker Compose 部署配置，配置存在不代表已完成服务器部署验收。

## 技术栈

- 前端：React 19、TypeScript、Vite、TanStack Query。
- 后端：Python、FastAPI、SQLAlchemy 2.x。
- 数据库：SQLite、Alembic 迁移。
- 测试：pytest、Vitest、React Testing Library。

## 开发环境

- Python 3.12+。
- Node.js 20.19+（20.x）或 22.12+，建议使用受支持的 LTS。
- 以下命令在 Windows PowerShell 中执行，起始目录为仓库根目录。

### 1. 安装依赖

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e .\backend

Set-Location frontend
npm ci
Set-Location ..
```

已有 `.venv` 时不必重新创建。安装依赖后，VS Code 中选择仓库的 `.venv\Scripts\python.exe` 作为解释器。

若本机 npm 配置了不可用的企业源，且允许使用公共 npm 源，可在安装时增加 `--registry=https://registry.npmjs.org`；不要修改或提交私人凭据。

本次搭建使用 Python 3.14 和 Node.js 22.12 验证。本机 npm 10 在首次解析依赖时出现了 `edgesOut` 内部错误，使用临时 npm 11 完成安装，没有更改全局 npm。遇到相同错误时，可在 `frontend` 目录执行：

```powershell
npm.cmd exec --yes --registry=https://registry.npmjs.org --package=npm@11 -- npm ci --registry=https://registry.npmjs.org
```

### 2. 初始化数据库

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m alembic upgrade head
Set-Location ..
```

默认数据文件位于 `backend\data\efficiencyday.db`，已从 Git 忽略。不会在应用启动时自动建表，缺少迁移时就绪接口返回 503。

可复制 `backend\.env.example` 为 `backend\.env`，修改 `EFFICIENCYDAY_DATABASE_PATH`。相对路径始终以 `backend` 为基准，应用和迁移使用相同配置。不要将数据文件放入前端静态目录。

首次使用空的、已迁移数据库时，在不提交的 `backend\.env` 中配置 `EFFICIENCYDAY_INITIAL_USERNAME` 和 `EFFICIENCYDAY_INITIAL_PASSWORD`，启动后端时创建个人账号；两项必须同时配置。已有账号不会被启动配置覆盖，创建后可移除这两项。不要将密码或 `.env` 提交到 Git。

本地登录还需设置 `EFFICIENCYDAY_PUBLIC_ORIGIN=http://127.0.0.1:8327`，与浏览器地址栏的协议、主机、端口完全一致；使用 `localhost` 时相应改为 `http://localhost:8327`。不要保留示例中的 `https://example.com`，否则登录和写请求会被拒绝。会话默认有效 7 天，可通过 `EFFICIENCYDAY_SESSION_TTL_DAYS` 设置正整数天数。

### 3. 启动

双击仓库根目录的 `start-dev.bat`，脚本会检查本地 Python、Node.js/npm、`backend\.env` 和端口占用，先执行数据库迁移，再分别打开前后端终端窗口。出错时会提示原因并停止；不会自动换端口，也不会关闭占用端口的进程。关闭前后端终端窗口即可停止服务。

也可以在 VS Code 中执行 **终端 → 运行任务 → dev: all**，先执行迁移再启动两端；或在两个终端中手动启动。端口被占用时，请先停止对应的现有服务。

也可以在两个终端中手动启动：

后端：

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 6931 --reload
```

前端：

```powershell
Set-Location frontend
npm run dev
```

| 地址 | 用途 |
| --- | --- |
| http://127.0.0.1:8327 | 个人工作台与登录入口 |
| http://127.0.0.1:6931/docs | FastAPI 交互式接口文档 |
| http://127.0.0.1:6931/api/v1/health/live | 进程存活检查，不依赖数据库就绪 |
| http://127.0.0.1:6931/api/v1/health/ready | 数据库连接和 Alembic 版本检查 |

前端使用相对路径 `/api/v1`，由 Vite 代理到 `127.0.0.1:6931`，不需要开放跨域。页面底部的“开发环境状态”可展开查看真实的数据库就绪结果，并允许失败后重试。请求超时会显示错误，不伪装为健康。

当前只监听本机地址，不对局域网或公网开放；这不是生产配置。

### 4. 使用与当前边界

- 打开页面时检查登录态，登录后自动读取工作项。登录 Cookie 为 `HttpOnly`、`Secure`、`SameSite=Lax`；浏览器需支持本机回环地址的安全上下文例外，非本机 HTTP 地址应使用 HTTPS，不能通过关闭 Cookie 安全属性绕过。
- 创建时填写标题，可选紧急/重要程度、颜色、目标完成日期、背景和目标。任一优先级未设置即为待分类；颜色只是标记。日历日期不做时区转换，系统时间按账号时区显示。
- 列表按录入时间和 ID 倒序，每页最多 50 条；后端尚未提供总数，满页后可能有空的下一页。点击标题单独读取详情；刷新页面或重新获得焦点会重新取数。
- 创建成功后清空表单、刷新列表并读取详情。失败时保留输入；超时或网络中断显示“保存未确认”，应先刷新列表核对，避免重复创建。写请求不会自动重试。
- 会话失效后隐藏工作项并清理查询/写操作缓存。同一账号在当前页面重新登录后可继续草稿；切换账号或确认退出会清空草稿。草稿仅在页面内存中，刷新或关闭页面会丢失；密码和令牌不写入本地存储。
- 本轮不包含编辑、状态流转、执行清单、过程记录、模板和四象限；服务器 HTTPS 与容器重建持久化仍需单独验收。

## 验证命令

从仓库根目录执行：

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
.\.venv\Scripts\python.exe -m ruff check backend
.\.venv\Scripts\python.exe -m ruff format --check backend

Set-Location frontend
npm test
npm run build
```

VS Code 也提供 `test: backend`、`test: frontend` 和 `build: frontend` 任务。

前端 `npm run build` 包含 TypeScript 检查。测试使用单 worker 的线程池，避免本机 Windows 下子进程测试池启动超时。

`npm run preview` 在同一端口 8327 预览构建产物，继承开发 API 代理，需单独保持后端运行，并先停止占用该端口的开发服务。它不是生产服务器，容器部署由 Nginx 统一代理。

## Docker Compose 部署

需要 Docker Engine 和 Docker Compose v2；Windows 可使用 Docker Desktop，切换为 Linux 容器。以下 PowerShell 命令均从仓库根目录执行，不需要本机安装 Python 或 Node.js。首次构建需要访问镜像源、PyPI 和 npm。

```powershell
docker compose config --quiet
docker compose build
docker compose run --rm --no-deps backend python -m alembic upgrade head
docker compose up -d --wait --wait-timeout 120
docker compose ps
curl.exe --fail http://127.0.0.1:8327/
curl.exe --fail http://127.0.0.1:8327/api/v1/health/ready
```

访问 http://127.0.0.1:8327 查看页面。默认端口与本地开发前端相同，启动前请先停止占用该端口的开发服务，或修改端口。

- 前端使用 Node.js 22 多阶段构建，最终镜像仅保留 Nginx 和静态产物，不运行 Vite 开发服务器。Nginx 提供 SPA 路由回退，并将 `/api/` 请求原样代理到后端；API 错误不会回退成 HTML。
- 后端使用 Python 3.14，以非 root 用户运行，按现有锁文件约束安装运行依赖，不安装测试和 lint 工具。迁移必须通过上面的独立命令执行，确认成功后才启动服务；容器启动仅运行单进程 Uvicorn，不会自动迁移，缺少迁移时就绪检查返回 503。
- 后端就绪检查通过后，Compose 才启动前端。后端仅通过容器网络访问，不发布 6931 端口。两端都有健康检查和 `unless-stopped` 重启策略；健康检查失败本身不会触发 Docker 自动重启。
- SQLite 文件及 WAL 文件保存在 `backend-data` 命名卷的 `/app/data` 中，不会写入镜像，也不会自动导入本地开发数据库。构建上下文使用白名单，不包含本地 `.env`、数据库、虚拟环境或 `node_modules`。

### 监听地址和端口

默认仅监听宿主机 `127.0.0.1:8327`。可以通过 PowerShell 环境变量调整，或在仓库根目录创建不提交的 `.env` 文件（不是 `backend\.env`）：

```dotenv
EFFICIENCYDAY_BIND_ADDRESS=127.0.0.1
EFFICIENCYDAY_PORT=8327
```

修改后重新执行 `docker compose up -d --wait`。需要通过局域网访问时，可显式将监听地址设置为 `0.0.0.0`，并配置宿主机防火墙。**当前应用已有身份认证，但部署配置不提供 HTTPS，不应直接暴露到公网。** 公网及非本机浏览器登录还需要外层 TLS 反向代理、访问控制及相应安全配置。将 `EFFICIENCYDAY_PUBLIC_ORIGIN` 设置为准确的浏览器访问源；首次创建账号时，在根目录不提交的 `.env` 配置初始化用户名和密码，迁移成功并启动后再移除初始化凭据。

容器固定使用 `/app/data/efficiencyday.db`，不会读取宿主机 `backend\.env`。不要扩容后端副本；当前 SQLite 和启动迁移方案面向单实例部署。

### 日志、升级与停止

```powershell
docker compose logs --tail 100 backend frontend
# 升级前先按下文备份数据库，再更新源码并重建。
docker compose build --pull
docker compose run --rm --no-deps backend python -m alembic upgrade head
docker compose up -d --wait --wait-timeout 120
# 停止并移除容器、网络，但保留数据库卷。
docker compose down
```

基础镜像使用版本系列标签，后端和前端应用依赖分别由现有锁文件约束；基础镜像更新可能改变系统依赖，需要重新构建并验证。迁移失败时查看 `docker compose logs backend`，修复原因后再启动，不要删除数据卷来绕过问题。

`docker compose down -v` **会永久删除数据库卷**，只适用于明确需要清空数据的场景。保持相同的 Compose 项目名（默认来自仓库目录名）；换目录或使用不同的 `-p` 会创建另一组卷，看起来像是空数据库。

### 数据备份和恢复

为确保 SQLite 数据及 WAL 一致，采用停机备份整个数据目录。备份包含完整数据库，请保存在安全位置，不要提交到 Git。

```powershell
# 先停止所有写入，再将整个数据目录复制到宿主机。
docker compose stop frontend backend
New-Item -ItemType Directory -Force .\backups | Out-Null
$backup = Join-Path (Resolve-Path .\backups).Path ("data-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
docker compose cp backend:/app/data $backup
# 确认上一条命令成功，且备份目录中存在 efficiencyday.db 后再继续。
docker compose up -d --wait --wait-timeout 120
```

备份恢复到空卷时，可按以下步骤操作。先用 `docker compose down` 保留现有卷，然后使用独立项目名创建全新容器和卷，避免覆盖当前数据。将备份路径替换为实际绝对路径：

```powershell
$backup = "D:\Backups\data-20261019-160000"
docker compose -p efficiencyday-restore create backend
docker compose -p efficiencyday-restore cp "${backup}\." backend:/app/data
# cp 可能改变文件所有者；启动非 root 后端前修正卷权限。
docker compose -p efficiencyday-restore run --rm --no-deps --user root backend chown -R 10001:10001 /app/data
docker compose -p efficiencyday-restore run --rm --no-deps backend python -m alembic upgrade head
docker compose -p efficiencyday-restore up -d --wait --wait-timeout 120
curl.exe --fail http://127.0.0.1:8327/api/v1/health/ready
```

仅在每一步成功后继续。恢复环境通过独立迁移命令升级到当前源码的数据库版本，因此应使用兼容版本，恢复前保留原始备份。升级后降级镜像不保证兼容已经迁移的数据库；回退应使用升级前的数据备份和相应旧版源码。

可在测试部署中执行一次 `docker compose down` 后重新 `up`，再访问就绪接口，确认保留卷后仍可启动。更严格的持久化验收应先在测试数据库写入已知数据，重建容器后核对该数据，而不只是检查健康状态。

## 数据库迁移

在 `backend` 目录执行：

```powershell
..\.venv\Scripts\python.exe -m alembic current
..\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "describe schema change"
..\.venv\Scripts\python.exe -m alembic upgrade head
```

模型定义在 `app\db\models.py`；生成的迁移脚本必须人工审核。配置已开启 SQLite batch migration，复杂改表仍需在副本上测试。生产迁移前必须备份，不在真实数据库上随意执行降级。

`backend\requirements.lock` 锁定后端开发依赖，`frontend\package-lock.json` 锁定前端依赖。修改后端依赖后可使用 uv 重新生成锁文件，再重新安装并验证：

```powershell
uv pip compile backend\pyproject.toml --extra dev --output-file backend\requirements.lock
```

## 目录

```text
backend/
  app/
    api/          HTTP 路由
    core/         配置
    db/           ORM 模型及数据库连接
    main.py       应用工厂与生命周期
  migrations/     Alembic 配置与版本脚本
  tests/          后端测试
frontend/
  src/
    api/          HTTP 请求及响应校验
    test/         测试初始化
    components/   登录、工作项表单、列表、详情及环境检查
    App.tsx       登录态恢复与受保护工作台入口
.vscode/          本地启动、测试和构建任务
docs/archi/       架构及需求文档
```

数据库迁移包含 `app_metadata` 基线及 `users`、`sessions`、`work_items` 三张业务表。当前已具备受保护的登录和工作项创建/读取链路；后续按开发进度逐步完成编辑、状态流转与其他功能。
