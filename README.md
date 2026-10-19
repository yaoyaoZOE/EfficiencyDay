# EfficiencyDay

个人日常工作项管理工具。当前仓库提供可运行的开发骨架，尚未实现登录、任务管理或生产部署。

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

### 3. 启动

在 VS Code 中执行 **终端 → 运行任务 → dev: all**，会先执行迁移，再启动两端。可通过“终止任务”分别停止；占用端口时应停止对应进程，不会自动换到其他端口。

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
| http://127.0.0.1:8327 | 前端状态页 |
| http://127.0.0.1:6931/docs | FastAPI 交互式接口文档 |
| http://127.0.0.1:6931/api/v1/health/live | 进程存活检查，不依赖数据库就绪 |
| http://127.0.0.1:6931/api/v1/health/ready | 数据库连接和 Alembic 版本检查 |

前端使用相对路径 `/api/v1`，由 Vite 代理到 `127.0.0.1:6931`，不需要开放跨域。页面展示真实的数据库就绪结果，并允许失败后重试。请求超时会显示错误，不伪装为健康。

当前只监听本机地址，不对局域网或公网开放；这不是生产配置。

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

`npm run preview` 在同一端口 8327 预览构建产物，继承开发 API 代理，需单独保持后端运行，并先停止占用该端口的开发服务。它不是生产服务器，生产环境以后由 Nginx 统一代理。

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
    App.tsx       项目状态页
.vscode/          本地启动、测试和构建任务
docs/archi/       架构及需求文档
```

骨架仅创建 `app_metadata` 表用于建立迁移基线，未预先固化业务模型。后续再逐步接入身份认证与工作项功能。
