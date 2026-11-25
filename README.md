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

## Documentation

- [可交互数据库 ER 图](docs/ER.html)
- [API 接口文档](docs/API.md)
- [界面原型](prototype/index.html)

## Database

- [业务表与视图](db/01_business.sql)
- [导入/模型/推理审计表](db/02_log.sql)

初始化数据库时按顺序执行：

```bash
sqlite3 app.db < db/01_business.sql
sqlite3 app.db < db/02_log.sql
```

直接用浏览器打开 `docs/ER.html` 即可查看 ER 图；页面支持拖拽实体、缩放画布、搜索表/字段、点击查看约束与关系，以及导出 SVG。

模型采用离线预训练方案：FastAPI 服务只加载模型文件执行推理，不提供训练或重训接口。预测接口接收月份、房屋和居住人口，返回该房屋在指定月份的平均日用电量。
