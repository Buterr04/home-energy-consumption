# 家庭用电量分析 API 接口文档

> 版本：v0.1  
> 日期：2026-11-24  
> 状态：草稿  
> 技术栈：FastAPI + SQLite + SQLAlchemy/SQLModel + scikit-learn
> Base URL：`/api/v1`  
> 在线文档：FastAPI 启动后访问 `/docs` 和 `/redoc`

---

## 1. 概述

本接口文档对应 Technical Project - Household Electricity Consumption Analysis。

系统提供两类账户：

- `user`：可拥有一个或多个家庭；每个家庭只能有一个所有者，用户只能访问自己的家庭。
- `admin`：可访问全部家庭数据，并管理用户、家庭归属、数据导入和质量摘要。

核心约束：

- 所有业务接口除登录和健康检查外，都需要 JWT。
- 普通用户只能查询、对比自己有权访问的家庭；预测也必须指定有权限访问的家庭。
- 对比接口最多允许 5 个家庭。
- 不向普通用户暴露原始读数接口，只提供聚合结果。
- 所有日期使用 `YYYY-MM-DD`，聚合周期使用 `YYYY-MM-DD`、`YYYY-MM`、`YYYY`。
- 缺失周期不返回 0，直接省略；前端按缺失显示为空档。

---

## 2. 功能清单

| 编号 | 功能 | 角色 | 优先级 |
|---|---|---|---|
| F01 | 用户名密码登录，签发 JWT | 全部 | P0 |
| F02 | 获取当前用户信息 | 全部 | P0 |
| F03 | 查看可访问家庭列表与详情 | User / Admin | P0 |
| F04 | 默认展示单户每日用电 | User | P0 |
| F05 | 按日、月、年聚合查看 | User | P0 |
| F06 | 最多 5 户同时对比，不同颜色 | User | P0 |
| F07 | 按电器类型筛选，例如排除冰箱 | User | P0 |
| F08 | 全部家庭平均用电曲线叠加 | User / Admin | P0 |
| F09 | 选择家庭并输入月份、温度和人口，返回历史与未来连续预测曲线 | User | P0 |
| F10 | 查看预训练模型版本与离线评估指标 | User / Admin | P1 |
| F11 | 导出月度/年度汇总报告（加分项） | User | P2 |
| F12 | 管理员创建/禁用用户 | Admin | P1 |
| F13 | 管理员给用户批量设置家庭归属 | Admin | P0 |
| F14 | CSV 导入、去重、质量标记 | Admin / CLI | P1 |
| F15 | 按平均温度分桶生成演示用户 | CLI | P1 |
| F16 | 电器用电占比 breakdown | User | P1 |

优先级说明：

- `P0`：必须完成，直接影响核心需求和演示。
- `P1`：管理和完整演示需要，时间不足可简化。
- `P2`：加分项或时间允许再做。

---

## 3. 通用约定

### 3.1 认证

登录成功后返回 JWT：

```http
Authorization: Bearer <access_token>
```

JWT payload 至少包含：

```json
{
  "sub": "1",
  "role": "user",
  "exp": 1760000000
}
```

### 3.2 日期与聚合

| 参数 | 类型 | 说明 |
|---|---|---|
| `start_date` | string | 开始日期，`YYYY-MM-DD` |
| `end_date` | string | 结束日期，`YYYY-MM-DD` |
| `granularity` | string | `day`、`month`、`year`，默认 `day` |

默认日期范围：

- `day`：最近 30 天
- `month`：最近 12 个月
- `year`：最近 5 年

开始日期晚于结束日期返回 `400 INVALID_DATE_RANGE`。

### 3.3 家庭选择

`household_ids` 使用重复查询参数，不使用逗号分隔：

```http
GET /api/v1/consumption/series?household_ids=94&household_ids=435
```

规则：

- 至少 1 个，最多 5 个。
- 超过 5 个返回 `400 TOO_MANY_HOUSEHOLDS`。
- 只要有一个家庭不属于当前用户，返回 `403 FORBIDDEN_HOUSEHOLD`。
- Admin 不受家庭归属限制。

### 3.4 电器筛选

使用重复查询参数：

```http
GET /api/v1/consumption/series?exclude_appliance_ids=1&exclude_appliance_ids=2
```

| 参数 | 说明 |
|---|---|
| `include_appliance_ids` | 只包含这些电器 |
| `exclude_appliance_ids` | 排除这些电器 |

`include_appliance_ids` 和 `exclude_appliance_ids` 不能同时出现，否则返回 `400 INVALID_APPLIANCE_FILTER`。

### 3.5 分页

| 参数 | 默认 | 限制 |
|---|---|---|
| `page` | 1 | 大于等于 1 |
| `page_size` | 20 | 1–100 |

分页响应结构：

```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "page_size": 20
}
```

### 3.6 错误响应

```json
{
  "detail": {
    "code": "FORBIDDEN_HOUSEHOLD",
    "message": "One or more households are not accessible."
  }
}
```

---

## 4. 错误码

| HTTP | code | 场景 |
|---|---|---|
| 400 | `INVALID_DATE_RANGE` | 开始日期晚于结束日期 |
| 400 | `INVALID_HOUSEHOLD_ID` | 预测请求的 `household_id` 不是正整数 |
| 400 | `TOO_MANY_HOUSEHOLDS` | 对比超过 5 户 |
| 400 | `INVALID_APPLIANCE_FILTER` | include 和 exclude 同时出现 |
| 401 | `AUTH_INVALID_CREDENTIALS` | 用户名或密码错误 |
| 401 | `AUTH_TOKEN_EXPIRED` | Token 过期或无效 |
| 403 | `FORBIDDEN_HOUSEHOLD` | 访问非本人家庭 |
| 403 | `FORBIDDEN_ADMIN` | 非管理员访问管理接口 |
| 404 | `HOUSEHOLD_NOT_FOUND` | 家庭不存在 |
| 404 | `USER_NOT_FOUND` | 用户不存在 |
| 409 | `USERNAME_EXISTS` | 用户名重复 |
| 422 | `VALIDATION_ERROR` | 请求参数格式错误 |
| 503 | `MODEL_NOT_READY` | 模型未加载 |
| 500 | `IMPORT_FAILED` | CSV 导入失败 |

---

## 5. 接口总表

| Method | Path | 权限 | 说明 |
|---|---|---|---|
| POST | `/auth/login` | Public | 登录 |
| GET | `/auth/me` | User/Admin | 当前用户 |
| POST | `/auth/change-password` | User/Admin | 修改密码，P1 |
| GET | `/households` | User/Admin | 可访问家庭列表 |
| GET | `/households/{household_id}` | User/Admin | 家庭详情 |
| GET | `/appliances` | User/Admin | 电器类型列表 |
| GET | `/consumption/series` | User/Admin | 单户/多户聚合序列 |
| GET | `/consumption/average` | User/Admin | 平均曲线 |
| GET | `/consumption/breakdown` | User/Admin | 电器占比，P1 |
| GET | `/ai/model` | User/Admin | 模型信息 |
| POST | `/ai/predict` | User/Admin | 月度预测 |
| POST | `/ai/predict/batch` | User/Admin | 多月批量预测，P2 |
| GET | `/reports/summary` | User/Admin | 导出汇总，P2 |
| GET | `/admin/users` | Admin | 用户列表 |
| POST | `/admin/users` | Admin | 创建用户 |
| PATCH | `/admin/users/{user_id}` | Admin | 修改角色/状态 |
| POST | `/admin/users/{user_id}/households` | Admin | 批量设置家庭归属 |
| GET | `/admin/households` | Admin | 全部家庭 |
| POST | `/admin/imports` | Admin | 上传 CSV，P1 |
| GET | `/admin/imports` | Admin | 导入历史，P1 |

---

## 6. 接口明细

### 6.1 登录

```http
POST /api/v1/auth/login
Content-Type: application/json
```

请求：

```json
{
  "username": "demo1",
  "password": "demo123"
}
```

响应 `200`：

```json
{
  "access_token": "<jwt-token>",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": 1,
    "username": "demo1",
    "display_name": "Demo 1",
    "role": "user"
  }
}
```

错误：

- `401 AUTH_INVALID_CREDENTIALS`

### 6.2 当前用户

```http
GET /api/v1/auth/me
Authorization: Bearer <token>
```

响应 `200`：

```json
{
  "id": 1,
  "username": "demo1",
  "display_name": "Demo 1",
  "role": "user",
  "is_active": true
}
```

### 6.3 修改密码

```http
POST /api/v1/auth/change-password
Authorization: Bearer <token>
Content-Type: application/json
```

请求：

```json
{
  "current_password": "demo123",
  "new_password": "demo456"
}
```

响应 `204 No Content`。

错误：

- `400 INVALID_CURRENT_PASSWORD`
- `422 VALIDATION_ERROR`

### 6.4 家庭列表

```http
GET /api/v1/households?search=94&page=1&page_size=20
Authorization: Bearer <token>
```

查询参数：

| 参数 | 类型 | 说明 |
|---|---|---|
| `search` | string | 按家庭 ID 或显示名搜索 |
| `page` | int | 页码 |
| `page_size` | int | 每页数量 |

响应 `200`：

```json
{
  "items": [
    {
      "household_id": 94,
      "display_name": "Home 94",
      "size_median": 3,
      "avg_temp_c": 14.7,
      "avg_daily_kwh": 1.52,
      "reading_count": 201,
      "first_date": "2023-01-01",
      "last_date": "2023-12-28"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

说明：

- User 只返回 `households.owner_user_id = 当前用户` 的家庭。
- Admin 返回全部家庭。
- `size_median` 是该家庭所有读数中 `household_size` 的中位数，不是单一固定值。

### 6.5 家庭详情

```http
GET /api/v1/households/94
Authorization: Bearer <token>
```

响应 `200`：

```json
{
  "household_id": 94,
  "display_name": "Home 94",
  "size_median": 3,
  "avg_temp_c": 14.7,
  "avg_daily_kwh": 1.52,
  "reading_count": 201,
  "first_date": "2023-01-01",
  "last_date": "2023-12-28",
  "appliances": [
    {"appliance_id": 1, "appliance_name": "Fridge", "reading_count": 20},
    {"appliance_id": 2, "appliance_name": "Air Conditioning", "reading_count": 21}
  ]
}
```

错误：

- `403 FORBIDDEN_HOUSEHOLD`
- `404 HOUSEHOLD_NOT_FOUND`

### 6.6 电器列表

```http
GET /api/v1/appliances
Authorization: Bearer <token>
```

响应 `200`：

```json
{
  "items": [
    {
      "appliance_id": 1,
      "name": "Fridge",
      "reading_count": 9931,
      "avg_energy_kwh": 0.30
    },
    {
      "appliance_id": 2,
      "name": "Air Conditioning",
      "reading_count": 10067,
      "avg_energy_kwh": 3.50
    }
  ]
}
```

说明：`avg_energy_kwh` 是全局统计，可用于前端筛选器的辅助展示。

### 6.7 聚合序列

单户默认日用电：

```http
GET /api/v1/consumption/series?household_ids=94&granularity=day&start_date=2023-12-01&end_date=2023-12-31
Authorization: Bearer <token>
```

最多 5 户对比：

```http
GET /api/v1/consumption/series
  ?household_ids=94
  &household_ids=435
  &household_ids=466
  &granularity=day
  &start_date=2023-01-01
  &end_date=2023-12-31
  &exclude_appliance_ids=1
Authorization: Bearer <token>
```

响应 `200`：

```json
{
  "granularity": "day",
  "start_date": "2023-01-01",
  "end_date": "2023-12-31",
  "items": [
    {
      "household_id": 94,
      "display_name": "Home 94",
      "period": "2023-01-01",
      "kwh": 12.3,
      "reading_count": 8,
      "color_index": 0
    },
    {
      "household_id": 435,
      "display_name": "Home 435",
      "period": "2023-01-01",
      "kwh": 10.8,
      "reading_count": 7,
      "color_index": 1
    }
  ],
  "meta": {
    "unit": "kWh",
    "max_households": 5,
    "excluded_appliance_ids": [1]
  }
}
```

说明：

- `period` 格式：日 `YYYY-MM-DD`，月 `YYYY-MM`，年 `YYYY`。
- `color_index` 按请求顺序分配 `0–4`，前端用固定调色板映射。
- 缺失周期不返回记录，不返回 0。
- 单户时 `color_index` 固定为 0。

错误：

- `400 TOO_MANY_HOUSEHOLDS`
- `400 INVALID_DATE_RANGE`
- `400 INVALID_APPLIANCE_FILTER`
- `403 FORBIDDEN_HOUSEHOLD`

### 6.8 平均曲线

```http
GET /api/v1/consumption/average
  ?granularity=day
  &start_date=2023-01-01
  &end_date=2023-12-31
  &scope=all
  &exclude_appliance_ids=1
Authorization: Bearer <token>
```

查询参数：

| 参数 | 类型 | 说明 |
|---|---|---|
| `granularity` | string | `day`、`month`、`year` |
| `scope` | string | `all` 或 `accessible`，默认 `all` |
| `include_appliance_ids` | int[] | 只包含这些电器 |
| `exclude_appliance_ids` | int[] | 排除这些电器 |

响应 `200`：

```json
{
  "granularity": "day",
  "scope": "all",
  "items": [
    {
      "period": "2023-01-01",
      "avg_kwh": 1.48,
      "household_count": 498,
      "expected_households": 500
    }
  ],
  "meta": {
    "unit": "kWh",
    "excluded_appliance_ids": [1]
  }
}
```

说明：

- `scope=all`：全部家庭匿名平均，只返回聚合值，不返回户 ID。
- `scope=accessible`：只统计当前用户可访问的家庭。
- `household_count`：当天有数据的家庭数。
- `expected_households`：统计范围应有的家庭总数，用于显示覆盖率。
- 平均必须先按 `household_id + period` 汇总，再对家庭求平均，不能直接对原始行求平均。

错误：

- `400 INVALID_DATE_RANGE`
- `400 INVALID_APPLIANCE_FILTER`

### 6.9 电器占比

```http
GET /api/v1/consumption/breakdown
  ?household_id=94
  &start_date=2023-01-01
  &end_date=2023-12-31
Authorization: Bearer <token>
```

响应 `200`：

```json
{
  "household_id": 94,
  "start_date": "2023-01-01",
  "end_date": "2023-12-31",
  "total_kwh": 312.4,
  "items": [
    {
      "appliance_id": 1,
      "appliance_name": "Fridge",
      "kwh": 18.2,
      "share": 0.058
    },
    {
      "appliance_id": 2,
      "appliance_name": "Air Conditioning",
      "kwh": 120.1,
      "share": 0.384
    }
  ]
}
```

说明：`share` 保留 3 位小数；`items` 按 `kwh` 降序。

### 6.10 模型信息

```http
GET /api/v1/ai/model
Authorization: Bearer <token>
```

服务启动时加载两级线性模型产物，本接口只返回模型元数据，不触发训练或重训。

响应 `200`：

```json
{
  "version": "linear-v1",
  "trained_at": null,
  "target": "avg_daily_kwh",
  "input_fields": [
    "month",
    "household_size",
    "forecast_monthly_temp_c"
  ],
  "features": [
    "Outdoor Temperature (°C)",
    "Household Size",
    "Month"
  ],
  "metrics": {
    "mae": null,
    "rmse": null,
    "r2": null
  },
  "training_rows": 0,
  "validation_rows": 0,
  "level_model": "LinearRegression",
  "shape_model": "LinearRegression"
}
```

`trained_at`、`training_rows` 和 `validation_rows` 来自离线训练/评估阶段，只作为模型登记信息；服务运行时不训练模型。当前产物的元数据未包含训练指标，因此 `metrics` 为 `null`。

错误：

- `503 MODEL_NOT_READY`

### 6.11 月度预测

```http
POST /api/v1/ai/predict
Authorization: Bearer <token>
Content-Type: application/json
```

`household_id` 用于权限校验和历史取数，不作为模型特征；模型只使用室外温度、居住人口和月份。

```json
{
  "household_id": 1,
  "month": 8,
  "household_size": 3,
  "forecast_monthly_temp_c": 24.0
}
```

响应 `200`：

```json
{
  "household_id": 1,
  "display_name": "Home 1",
  "month": 8,
  "household_size": 3,
  "anchor_month": "2015-07",
  "forecast_start_month": "2015-08",
  "forecast_end_month": "2016-01",
  "history_basis": "aggregate",
  "history": [
    {
      "period": "2014-08",
      "actual_avg_daily_kwh": 8.166,
      "temperature_c": 15.0,
      "reading_days": 30,
      "total_kwh": 244.984
    }
  ],
  "forecast": [
    {
      "period": "2015-08",
      "predicted_avg_daily_kwh": 6.958,
      "temperature_used_c": 24.0,
      "monthly_energy_estimate_kwh": 215.7
    }
  ],
  "predicted_avg_daily_kwh": 6.958,
  "unit": "kWh/日",
  "model_version": "linear-v1",
  "average_daily_power_curve_kw": [
    0.322, 0.335, 0.326, 0.306, 0.303, 0.377,
    0.4, 0.546, 0.604, 0.522, 0.493, 0.524,
    0.531, 0.533, 0.476, 0.516, 0.646, 0.851,
    0.891, 0.76, 0.67, 0.578, 0.478, 0.363
  ],
  "monthly_energy_estimate_kwh": 215.7,
  "temperature_used_c": 24.0,
  "level_model": "LinearRegression",
  "shape_model": "LinearRegression",
  "warnings": []
}
```

说明：

- `household_id` 必须属于当前用户可访问的家庭。
- `month` 为必填的 `1–12` 整数，表示预测起始月份；年份由该家庭最后数据月之后的下一次该月份推导。
- `household_size` 为必填的 `1–20` 整数，对应前端填写的居住人口。
- `forecast_monthly_temp_c` 为必填输入，范围 `-50–60`，用于预测起始月。
- `anchor_month` 是该家庭最后一条数据所在月份；`history` 返回截至该月的最近 12 个月实际值。
- `forecast` 从 `anchor_month` 之后的下一次 `month` 开始，连续返回 6 个月；起始月使用请求温度，其余月份使用该家庭相同月份的历史平均温度。
- 历史总用电优先使用电器名为 `Aggregate` 的读数；如果该月没有 `Aggregate`，才汇总分项电器，避免重复计算。
- `average_daily_power_curve_kw` 始终包含 24 个值，对应 0–23 点；其和等于日均用电量。
- `predicted_avg_daily_kwh`、`monthly_energy_estimate_kwh` 和 24 小时曲线对应预测起始月。

错误：

- `400 INVALID_HOUSEHOLD_ID`
- `400 INVALID_MONTH`
- `400 INVALID_HOUSEHOLD_SIZE`
- `400 INVALID_TEMPERATURE`
- `403 FORBIDDEN_HOUSEHOLD`
- `503 MODEL_NOT_READY`

### 6.12 多月批量预测（P2）

```http
POST /api/v1/ai/predict/batch
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "items": [
    {
      "household_id": 1,
      "month": 1,
      "household_size": 3,
      "forecast_monthly_temp_c": 5.0
    },
    {
      "household_id": 1,
      "month": 7,
      "household_size": 5,
      "forecast_monthly_temp_c": 28.0
    }
  ]
}
```

响应 `200`：

```json
{
  "model_version": "linear-v1",
  "items": [
    {
      "month": 1,
      "predicted_avg_daily_kwh": 9.6
    },
    {
      "month": 7,
      "predicted_avg_daily_kwh": 15.2
    }
  ]
}
```

### 6.13 导出汇总报告（加分项）

```http
GET /api/v1/reports/summary
  ?granularity=month
  &household_ids=94
  &household_ids=435
  &start_date=2023-01-01
  &end_date=2023-12-31
  &format=csv
Authorization: Bearer <token>
```

查询参数：

| 参数 | 类型 | 说明 |
|---|---|---|
| `granularity` | string | `month` 或 `year` |
| `household_ids` | int[] | 1–5 个家庭 |
| `format` | string | `csv`，`xlsx` 可选 |
| `include_appliance_ids` | int[] | 只包含这些电器 |
| `exclude_appliance_ids` | int[] | 排除这些电器 |

响应头：

```http
200 OK
Content-Type: text/csv; charset=utf-8
Content-Disposition: attachment; filename="consumption_report_2023-01_2023-12.csv"
```

CSV 列：

```text
household_id,period,total_kwh,household_size_median,kwh_per_resident
94,2023-01,312.4,3,104.13
94,2023-02,298.7,3,99.57
```

说明：

- `kwh_per_resident` 使用该家庭在周期内的 `household_size` 中位数计算。
- 缺失周期不导出，或导出空值，具体在实现中固定一种并写进 SRS。

### 6.14 管理员用户列表

```http
GET /api/v1/admin/users?page=1&page_size=20
Authorization: Bearer <admin-token>
```

响应 `200`：

```json
{
  "items": [
    {
      "id": 1,
      "username": "demo1",
      "display_name": "Demo 1",
      "role": "user",
      "is_active": true,
      "household_count": 5
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

### 6.15 管理员创建用户

```http
POST /api/v1/admin/users
Authorization: Bearer <admin-token>
Content-Type: application/json
```

```json
{
  "username": "demo2",
  "password": "demo123",
  "display_name": "Demo 2",
  "role": "user"
}
```

响应 `201`：

```json
{
  "id": 2,
  "username": "demo2",
  "display_name": "Demo 2",
  "role": "user",
  "is_active": true
}
```

错误：

- `409 USERNAME_EXISTS`
- `422 VALIDATION_ERROR`

### 6.16 管理员修改用户

```http
PATCH /api/v1/admin/users/2
Authorization: Bearer <admin-token>
Content-Type: application/json
```

```json
{
  "display_name": "Demo User 2",
  "role": "user",
  "is_active": false
}
```

响应 `200`：

```json
{
  "id": 2,
  "username": "demo2",
  "display_name": "Demo User 2",
  "role": "user",
  "is_active": false
}
```

### 6.17 管理员批量设置家庭归属

```http
POST /api/v1/admin/users/2/households
Authorization: Bearer <admin-token>
Content-Type: application/json
```

```json
{
  "household_ids": [1, 2, 3, 4, 5]
}
```

响应 `200`：

```json
{
  "user_id": 2,
  "owned": [1, 2, 3, 4, 5]
}
```

说明：

- 该接口把 `households.owner_user_id` 批量设为 `user_id`。
- 一个用户可以拥有多个家庭，但每个家庭的 `owner_user_id` 只有一个值。
- 若家庭原先属于其他用户，会转移归属；原用户随即失去访问权限。
- 接口幂等，重复设置不报错。

错误：

- `404 USER_NOT_FOUND`
- `404 HOUSEHOLD_NOT_FOUND`

### 6.18 管理员家庭列表

```http
GET /api/v1/admin/households?page=1&page_size=20
Authorization: Bearer <admin-token>
```

响应结构与普通家庭列表相同，但包含全部 500 户，并额外返回 `owner_user_id`。

### 6.19 管理员导入 CSV

```http
POST /api/v1/admin/imports
Authorization: Bearer <admin-token>
Content-Type: multipart/form-data
```

表单字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `file` | file | CSV 文件 |
| `dry_run` | bool | 可选，只校验不入库 |

响应 `200`：

```json
{
 "import_id": 1,
 "status": "completed",
 "filename": "household_electricity_consumption.csv",
 "total_rows": 100000,
 "inserted_rows": 99996,
 "rejected_rows": 4,
 "duplicate_rows": 4,
 "quality_flagged_rows": 29607
}
```

说明：

- 导入阶段处理 Latin-1 编码。
- 按 `household_id + appliance_id + reading_date + reading_time` 去重。
- 10 万行同步导入可以接受；如果超过 5 秒，改成 `BackgroundTasks` 或 CLI。
- 建议同时提供 CLI：`python -m app.scripts.import_csv --path ...`。

### 6.20 管理员导入历史

```http
GET /api/v1/admin/imports?page=1&page_size=20
Authorization: Bearer <admin-token>
```

响应 `200`：

```json
{
  "items": [
    {
      "import_id": 1,
      "filename": "household_electricity_consumption.csv",
      "status": "completed",
      "total_rows": 100000,
      "inserted_rows": 99996,
      "rejected_rows": 4,
      "imported_at": "2026-11-24T14:00:00+08:00"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

---

## 7. 权限模型

### 7.1 角色

| 角色 | 权限 |
|---|---|
| `user` | 访问 `households.owner_user_id = 当前用户` 的家庭；可对比、导出；预测也必须校验家庭归属 |
| `admin` | 访问全部家庭；管理用户、家庭归属、导入、质量摘要 |

### 7.2 家庭归属校验

所有涉及 `household_ids` 的接口都要执行：

```text
requested_ids ⊆ accessible_ids
```

- Admin：`accessible_ids` 为全部家庭。
- User：`accessible_ids` 来自 `households.owner_user_id = user.id` 的家庭。
- 校验失败返回 `403 FORBIDDEN_HOUSEHOLD`。
- 错误响应不返回具体非本人家庭 ID，避免泄露数据存在性。

### 7.3 平均曲线权限

- `scope=all`：匿名聚合，只返回均值、家庭数量，不返回家庭 ID。
- `scope=accessible`：只统计当前用户可访问的家庭。
- 若课程要求严格数据隔离，可把 User 的默认 `scope` 改为 `accessible`，Admin 才允许 `all`。

### 7.4 原始数据

- 不提供普通用户的原始读数接口。
- 普通用户只能访问聚合后的序列、占比和预测结果。
- 如需要原始数据，只能通过 Admin 导入历史或后台脚本。

---

## 8. 主要数据结构

### 8.1 HouseholdSummary

```json
{
  "household_id": 94,
  "display_name": "Home 94",
  "size_median": 3,
  "avg_temp_c": 14.7,
  "avg_daily_kwh": 1.52,
  "reading_count": 201,
  "first_date": "2023-01-01",
  "last_date": "2023-12-28"
}
```

### 8.2 ConsumptionSeriesItem

```json
{
  "household_id": 94,
  "display_name": "Home 94",
  "period": "2023-01-01",
  "kwh": 12.3,
  "reading_count": 8,
  "color_index": 0
}
```

### 8.3 AveragePoint

```json
{
  "period": "2023-01-01",
  "avg_kwh": 1.48,
  "household_count": 498,
  "expected_households": 500
}
```

### 8.4 PredictRequest

```json
{
  "month": 12,
  "household_size": 3,
  "forecast_monthly_temp_c": 8.5
}
```

### 8.5 PredictResponse

```json
{
  "month": 12,
  "household_size": 3,
  "predicted_avg_daily_kwh": 12.35,
  "unit": "kWh/日",
  "model_version": "linear-v1",
  "average_daily_power_curve_kw": [
    0.322, 0.335, 0.326, 0.306, 0.303, 0.377,
    0.4, 0.546, 0.604, 0.522, 0.493, 0.524,
    0.531, 0.533, 0.476, 0.516, 0.646, 0.851,
    0.891, 0.76, 0.67, 0.578, 0.478, 0.363
  ],
  "monthly_energy_estimate_kwh": 382.9,
  "temperature_used_c": 8.5,
  "level_model": "LinearRegression",
  "shape_model": "LinearRegression",
  "warnings": []
}
```

### 8.6 ErrorResponse

```json
{
  "detail": {
    "code": "FORBIDDEN_HOUSEHOLD",
    "message": "One or more households are not accessible."
  }
}
```

---

## 9. 实现建议

### 9.1 FastAPI 依赖

- `get_current_user()`：解析 JWT，加载用户。
- `require_admin()`：校验 `role == "admin"`。
- `ensure_household_access(user, household_ids)`：执行家庭归属校验。
- `get_db()`：提供 SQLAlchemy/SQLModel session。

### 9.2 SQL 聚合

- 单户/多户序列：

```sql
SELECT household_id, reading_date, SUM(energy_kwh) AS kwh, COUNT(*) AS reading_count
FROM energy_readings
WHERE household_id IN (...)
  AND reading_date BETWEEN :start AND :end
  AND appliance_id NOT IN (...)
GROUP BY household_id, reading_date
ORDER BY reading_date, household_id;
```

- 平均曲线必须两阶段：

```sql
WITH home_daily AS (
  SELECT household_id, reading_date, SUM(energy_kwh) AS kwh
  FROM energy_readings
  WHERE reading_date BETWEEN :start AND :end
    AND appliance_id NOT IN (...)
  GROUP BY household_id, reading_date
)
SELECT reading_date, AVG(kwh) AS avg_kwh, COUNT(*) AS household_count
FROM home_daily
GROUP BY reading_date
ORDER BY reading_date;
```

### 9.3 索引

- `energy_readings (household_id, reading_date)`
- `energy_readings (reading_date, appliance_id)`
- `households (owner_user_id)`：加速“当前用户拥有哪些家庭”的过滤。

### 9.4 缓存

- 平均曲线和电器列表可以加 60 秒内存缓存或 Redis 缓存。
- 10 万行数据不强制预聚合；如果 SVVP 压测超过 500ms，再加物化日汇总表。

### 9.5 CORS 与部署

- 开发环境允许前端 `http://localhost:5173`。
- 生产/演示使用 `uvicorn app.main:app --host 0.0.0.0 --port 8000`。
- OpenAPI 文档保留 `/docs`，演示时可直接展示接口。

---

## 10. 验收清单

- [ ] User A 登录后只能看到 `owner_user_id = A` 的家庭。
- [ ] 修改 URL 中的家庭 ID 返回 `403`。
- [ ] 单户默认日用电正常显示。
- [ ] 日/月/年聚合切换正确。
- [ ] 5 户对比正常，6 户返回 `400`。
- [ ] 排除冰箱后序列和平均曲线同步变化。
- [ ] 平均曲线返回 `household_count` 和 `expected_households`。
- [ ] 预测接口接收家庭、月份、温度和人口，返回最近 12 个月历史、未来 6 个月预测和 24 小时曲线。
- [ ] 管理员可创建用户并批量设置家庭归属。
- [ ] CSV 导入 10 万行，4 条重复被拒绝，质量摘要数据一致。
- [ ] `/docs` 能展示全部接口并可直接调试。
