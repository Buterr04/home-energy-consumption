<div align="center"> 
<h1>home-energy-consumption</h1>
<p>
  <img src="https://img.shields.io/github/stars/Buterr04/home-energy-consumption.svg?style=social">
  <img src="https://img.shields.io/github/issues/Buterr04/home-energy-consumption.svg">
  <img src="https://img.shields.io/github/license/Buterr04/home-energy-consumption.svg">
  <img src="https://img.shields.io/badge/Language-Python-blue?logo=python&logoColor=white">
  <img src="https://img.shields.io/badge/Framework-FastAPI-green?logo=fastapi&logoColor=white">
  <img src="https://img.shields.io/badge/Frontend-Vue%203%20%2B%20Vite-42b883?logo=vuedotjs&logoColor=white">
  <img src="https://img.shields.io/badge/Database-SQLite-lightgrey?logo=sqlite&logoColor=white">
  <img src="https://img.shields.io/badge/Animation%20Library-ReactBits-blueviolet?logo=react&logoColor=white">
  
  </p>
  <img src=https://socialify.git.ci/Buterr04/home-energy-consumption/image?custom_language=Python&issues=1&language=1&name=1&owner=1&stargazers=1&theme=Light />
</div>

## Quick Start

当前仓库已完成 FastAPI 服务、SQLite 建表、CSV 导入、账号与角色权限、离线模型推理、核心 P0/P1 接口和自包含测试。

接口字段、权限、错误码和响应结构以 `docs/API.md` v0.1 为唯一契约；代码和测试严格按文档实现。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
python -m app.scripts.bootstrap --reset
uvicorn app.main:app --reload
```

启动后访问：

- API 文档：<http://127.0.0.1:8000/docs>
- ReDoc：<http://127.0.0.1:8000/redoc>

原型不注册为后端路由，直接打开 `prototype/index.html` 查看。

iPadOS 半透明侧栏风格的静态单文件视觉稿在 `prototype/ipados-vue.html`，仅作为视觉参考，不参与正式前端构建。

## Frontend

正式前端位于 `frontend/`，使用 Vue 3、TypeScript、Vite 和 Vue Router。界面为全屏 iPadOS 半透明侧栏布局，包含能源总览、用电分析、智能预测、报告中心和管理员控制台。

```bash
cd frontend
npm install
npm run dev
```

开发地址为 <http://127.0.0.1:5173/>。Vite 默认将 `/api` 代理到 `http://127.0.0.1:8000`。页面启动时自动恢复当前标签页中的 JWT 会话；没有有效会话时显示左侧品牌、右侧登录表单的全屏登录页。所有家庭、序列、预测、报告和管理员操作都直接调用 FastAPI，前端不包含演示数据或离线回退数据。

登录页的高级选项可修改 API Base URL；需要指向独立部署的 API 时，复制 `frontend/.env.example` 并设置 `VITE_API_BASE_URL`。

权限行为：

- `user`：只加载自己拥有的家庭，最多同时选择 5 户进行对比。
- `admin`：通过分页加载全部家庭，并显示「管理控制台」入口，可创建/停用用户、切换角色、转移家庭归属、校验或导入 CSV，并查看导入历史。
- 普通用户直接访问 `#/admin` 会被重定向回能源总览。

```bash
npm run typecheck
npm run build
```

`frontend/dist/` 是可直接部署的静态产物。`prototype/ipados-vue.html` 作为已确认的视觉参考保留，不参与正式构建。

如果数据集不在仓库默认搜索路径，显式传入：

```bash
python -m app.scripts.bootstrap --reset --csv /path/to/household_electricity_consumption.csv
```

`bootstrap` 会依次完成：

1. 只执行 `db/01_business.sql` 建库。
2. 导入 CSV，处理 Latin-1 编码、去重、质量标记和家庭画像。
3. 创建管理员与普通用户，并按平均温度分桶分配种子家庭。
4. 校验 `models/linear-v1/` 下的两级线性模型产物；运行时不训练模型。

`db/02_log.sql` 作为预留文件保留，但初始化、ORM 和运行逻辑均不使用。

## Built-in Accounts

| 用户名 | 密码 | 角色 | 家庭 |
|---|---|---|---|
| `admin` | `admin123` | `admin` | 全部 500 户 |
| `demo1` | `demo123` | `user` | 5 户 |
| `demo2` | `demo123` | `user` | 5 户 |

## Scripts

```bash
python -m app.scripts.init_db --reset
python -m app.scripts.import_csv --path /path/to/data.csv
python -m app.scripts.seed_demo
```

服务启动时仅加载 `models/linear-v1/` 下的两级线性模型并执行推理，不提供训练或重训接口。

## Tests

测试使用独立临时 SQLite 数据库与临时模型文件，不会污染本地 `app.db`。

```bash
pytest
ruff check app tests main.py
```

## Structure

```text
app/
  routers/        # auth / households / consumption / ai / reports / admin
  services/       # 聚合、导入、模型、种子数据
  scripts/        # 建库、导入、一键初始化
  models.py       # SQLAlchemy ORM
  main.py         # FastAPI 应用入口
db/               # 业务表 SQL（02 预留但不使用）
docs/             # API 文档与 ER 图
models/           # 两级线性模型产物
prototype/        # 静态界面原型
frontend/         # Vue 3 + TypeScript 正式前端
tests/            # 自包含 API 测试
```

## Data Quality

导入时按 `household_id + appliance_id + reading_date + reading_time` 去重。温度与季节明显不符的记录会标记为 `seasonal_temp_outlier`，但仍保留在业务表。家庭成员数、平均温度、日均用电等画像在导入后刷新到 `household_profiles`。

## Documentation

- [可交互数据库 ER 图](docs/ER.html)
- [API 接口文档](docs/API.md)
- [界面原型](prototype/index.html)
- [iPadOS 风格视觉参考](prototype/ipados-vue.html)

## Database

- [业务表与视图](db/01_business.sql)
- [预留审计表（当前不执行、不使用）](db/02_log.sql)

初始化数据库只执行：

```bash
sqlite3 app.db < db/01_business.sql
```

`db/02_log.sql` 先保留在仓库中，但不要执行，也不要让应用依赖其中的表。
CSV 导入同时支持管理员上传 API 和 CLI/bootstrap；导入批次记录写入业务库的 `import_batches` 表。

直接用浏览器打开 `docs/ER.html` 即可查看 ER 图；页面支持拖拽实体、缩放画布、搜索表/字段、点击查看约束与关系，以及导出 SVG。

模型采用离线预训练方案：FastAPI 服务启动时加载 `models/linear-v1/stage1_linear.joblib` 和 `stage2_linear.joblib`，只执行推理。预测接口接收家庭、室外温度、居住人口和起始月份，返回典型日均用电量、24 小时平均功率曲线，以及该家庭最近 12 个月历史与未来 6 个月预测。家庭 ID 只用于权限校验和历史取数，不是模型特征；历史总用电优先使用 `Aggregate`，缺失时才回退到分项汇总。
