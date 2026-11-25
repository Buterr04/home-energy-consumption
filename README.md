<div align="center"> 
<h1>home-energy-consumption</h1>
<p>
  <img src="https://img.shields.io/github/stars/Buterr04/home-energy-consumption.svg?style=social">
  <img src="https://img.shields.io/github/issues/Buterr04/home-energy-consumption.svg">
  <img src="https://img.shields.io/github/license/Buterr04/home-energy-consumption.svg">
  <img src="https://img.shields.io/badge/Language-Python-blue?logo=python&logoColor=white">
  <img src="https://img.shields.io/badge/Framework-FastAPI-green?logo=fastapi&logoColor=white">
  <img src="https://img.shields.io/badge/Frontend-Vite%20%2B%20React-pink?logo=react&logoColor=white">
  <img src="https://img.shields.io/badge/Database-SQLite-lightgrey?logo=sqlite&logoColor=white">
  <img src="https://img.shields.io/badge/Animation%20Library-ReactBits-blueviolet?logo=react&logoColor=white">
  
  </p>
  <img src=https://socialify.git.ci/Buterr04/home-energy-consumption/image?custom_language=Python&issues=1&language=1&name=1&owner=1&stargazers=1&theme=Light />
</div>

## Quick Start

当前仓库已完成第一阶段初始化：FastAPI 服务、SQLite 建表、CSV 导入、演示账号、离线模型训练与推理、核心 P0/P1 接口和自包含测试均可运行。

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

如果数据集不在仓库默认搜索路径，显式传入：

```bash
python -m app.scripts.bootstrap --reset --csv /path/to/household_electricity_consumption.csv
```

`bootstrap` 会依次完成：

1. 只执行 `db/01_business.sql` 建库。
2. 导入 CSV，处理 Latin-1 编码、去重、质量标记和家庭画像。
3. 创建管理员与演示用户，并按平均温度分桶分配演示家庭。
4. 离线训练 `models/rf-v1.joblib`，模型元数据只保存在模型文件中。

`db/02_log.sql` 作为预留文件保留，但初始化、ORM 和运行逻辑均不使用。

## Demo Accounts

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
python -m app.scripts.train_model
```

模型训练只发生在离线脚本中；服务启动时仅加载模型文件并执行推理，不在线训练或重训。

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
  services/       # 聚合、导入、模型、演示数据
  scripts/        # 建库、导入、训练、一键初始化
  models.py       # SQLAlchemy ORM
  main.py         # FastAPI 应用入口
db/               # 业务表 SQL（02 预留但不使用）
docs/             # API 文档与 ER 图
models/           # 离线模型产物（默认 gitignore）
prototype/        # 静态界面原型
tests/            # 自包含 API 测试
```

## Data Quality

导入时按 `household_id + appliance_id + reading_date + reading_time` 去重。温度与季节明显不符的记录会标记为 `seasonal_temp_outlier`，但仍保留在业务表；离线训练视图 `training_readings` 只读取 `quality_flag = 'ok'` 的记录。家庭成员数、平均温度、日均用电等画像在导入后刷新到 `household_profiles`。

## Documentation

- [可交互数据库 ER 图](docs/ER.html)
- [API 接口文档](docs/API.md)
- [界面原型](prototype/index.html)

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

模型采用离线预训练方案：FastAPI 服务只加载模型文件执行推理，不提供训练或重训接口。预测接口接收月份、房屋和居住人口，返回该房屋在指定月份的平均日用电量。
