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

## 统一导出通道

所有模块的导出都收拢在 `backend/app/exporting/`，各模块不再各写一份：

| 文件 | 职责 |
| --- | --- |
| `app/exporting/registry.py` | 字段口径唯一来源：每个模块的列顺序、关键字列、状态枚举 |
| `app/exporting/pipeline.py` | 公共通道：复用各模块 `service.list_entries` 取数 → 按口径投影 → CSV 落盘 |
| `app/exporting/writer.py` | 列投影与 CSV 渲染，空值统一占位 `—`（与列表一致），带 UTF-8 BOM |
| `app/exporting/routes.py` | 导出端点工厂，各模块 `/api/<模块>/export` 都由它生成 |
| `app/exporting/runner.py` | 全量导出编排，逐模块报告成败，单模块故障不影响其它模块 |

约定：

- 下载入口不变：仍是 `GET /api/<模块>/export`，前端按钮无需改动。
- 导出与列表读同一份数据：同一套 `keyword/status` 参数、同一个 `list_entries`，
  导出条数必然等于列表 `total`；分页导出（`?page=&size=`）与全量导出走同一函数，
  分页不落盘，全量才写文件。
- 字段顺序与空值占位以 `registry.py` 为准（来自切换前各模块清单，已逐模块核对），
  新增列只能追加在末尾；`?format=json` 保留老的 `{module,total,items}` 响应。
- 全量导出固定写入 `backend/exports/export_<模块>.csv`，重复导出只覆盖不追加；
  带过滤条件的导出写入带范围指纹的独立文件，不会冲掉全量文件。
- 一键全量导出：`POST /api/exports/run`（可带 `?only=a,b` 只跑部分模块），
  返回逐模块的 `ok/total/path/error` 与失败堆栈，起服务后可直接验证是哪个模块坏了。

测试：`make backend-test`（或 `cd backend && .venv/bin/python -m unittest discover -s tests`）。
