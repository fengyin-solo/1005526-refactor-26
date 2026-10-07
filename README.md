# 光伏电站运维管理平台

面向光伏组件、逆变器、汇流箱、变压器、储能与升压站运行监视的集中式电站运维后台。

这是一个前后端分离的管理平台：前端 Vue 3 + Vite + TypeScript，后端 FastAPI（Python）。
两边各自独立启动，前端 dev server 已关掉自动打开页面，启动后按终端打印的地址手工打开。

## 目录结构

```text
.
├── frontend/                 Vue 3 + Vite + TypeScript 前端
│   ├── src/views/            每个业务模块一个页面
│   ├── src/api/              统一请求封装
│   ├── src/stores/           会话与筛选状态
│   └── vite.config.ts        dev server 配置（open: false）
├── backend/                  FastAPI（Python） 后端
│   ├── app/routers/          每个业务模块一组接口
│   ├── app/services/         业务规则与状态流转
│   └── app/store.py          内存数据仓库与示例数据
├── .gitignore
└── docker-compose.yml
```

## 启动

### 后端

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
./run.sh
```

健康检查：`curl http://127.0.0.1:8000/api/health`

### 前端

```bash
cd frontend
npm install
npm run dev
```

前端默认监听 `http://127.0.0.1:5173/`，dev server 不会自动打开浏览器，
需要自己访问。`/api` 由 vite 代理到后端 `http://127.0.0.1:8000`。

## 业务模块

| 模块 | 目录 | 业务对象 | 主要字段 |
| --- | --- | --- | --- |
| 光伏阵列 | `pv_array` | 光伏阵列 | 阵列编号、所属片区、组件型号 |
| 逆变器监视 | `inverter` | 逆变器 | 逆变器编号、品牌型号、额定功率 |
| 汇流箱检测 | `combiner_box` | 汇流箱 | 汇流箱编号、所属阵列、输入路数 |
| 变压器监视 | `transformer` | 变压器 | 变压器编号、电压等级、额定容量 |
| 储能电池组 | `energy_storage` | 储能电池组 | 电池组编号、电池类型、额定容量 |
| 升压站监视 | `boosting_station` | 升压站 | 升压站编号、进线电压、出线电压 |
| 关口计量 | `meter` | 关口表计 | 表计编号、计量点名称、表计精度 |
| 环境监测站 | `environment` | 环境监测站 | 站点编号、安装位置、辐照度 |
| 组件清洗 | `cleaning` | 清洗任务 | 任务编号、清洗区域、清洗方式 |
| 巡视检查 | `patrol` | 巡视记录 | 记录编号、巡视区域、巡视日期 |
| 缺陷管理 | `defect` | 设备缺陷 | 缺陷编号、发现日期、缺陷设备 |
| 检修计划 | `maintenance` | 检修计划 | 计划编号、检修设备、检修类别 |
| 备品备件 | `spare_parts` | 备件物料 | 备件编号、备件名称、规格型号 |
| 告警事件 | `alarm` | 告警事件 | 告警编号、告警来源、告警类型 |
| 调度指令 | `dispatch` | 调度指令单 | 指令编号、下发单位、指令类型 |
| 安全措施 | `safety` | 安全措施票 | 措施编号、措施类型、涉及设备 |
| 运维合同 | `contract` | 运维合同 | 合同编号、合同名称、签约甲方 |
| 运行月报 | `report` | 运行月报 | 月报编号、统计月份、发电量 |

## 约定

- 每个模块的前端页面在 `frontend/src/views/<模块>/index.vue`，后端接口在
  `backend/app/routers/<模块>.py`，业务规则在 `backend/app/services/<模块>.py`。
- 列表接口统一返回 `{ items, total, page, size }`，动作接口统一返回 `{ ok, message }`。
- 状态流转只允许在 `app/services` 里改，路由层不做业务判断。

## 统一导出

各模块不再各自实现导出：字段口径（取哪些字段、列顺序、空值占位）、取数范围
（关键字、状态）统一维护在 `backend/app/modules/`：

- `app/modules/specs.py`：每个模块唯一的字段/状态/动作口径注册表，是字段顺序与
  空值占位的唯一维护点。存量字段已按收拢前的 services / routers / 前端页面三处
  定义逐模块核对合并（凭据见 `backend/tests/expected_specs.json`）。
- `app/modules/base.py`：通用 service，`query_rows` 是列表与导出唯一共用的取数通道。
- `app/modules/exporting.py`：统一导出，负责字段投影、空值占位（`—`）、落盘覆盖。
- `app/modules/router.py`：按注册表为每个模块生成路由，`app/services`、`app/routers`
  下的模块文件只保留薄壳，兼容历史 import 路径。

行为约定：

- **同一份数据**：导出与列表走同一个 `query_rows`，支持与列表相同的 `keyword`、
  `status` 过滤；导出条数恒等于列表 `total`（通道内置自检，结果里带 `matched`）。
- **入口不变**：`GET /api/<模块>/export` 原样保留，响应里 `module/total/items`
  键不变；默认 JSON，加 `fmt=csv` 下载带 BOM 的 CSV。前端仍是原按钮，
  统一走 `openExport(endpoint, filters)`，并带上当前列表过滤条件。
- **列顺序与空值不变**：投影列顺序按注册表，缺值（None/空串/空白）统一补 `—`；
  行里多余字段不进导出、缺失字段补占位，原始数据不被修改。
- **覆盖不追加**：同一模块 + 同一范围固定写同一文件（全量为 `<模块>.all.json`），
  重复导出只覆盖。落盘目录默认 `backend/var/exports/`，可用 `EXPORT_DIR` 覆盖。
- **全量导出与失败定位**：`GET /api/exports`（可选 `modules=a,b&fmt=csv`）一次导出
  全部模块，单个模块失败会被隔离并在 `failures` 里给出模块名与原因。
  也可用脚本自检：`.venv/bin/python -m scripts.export_all`。

