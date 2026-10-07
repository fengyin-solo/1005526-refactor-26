"""导出字段注册表：全平台导出的字段口径只在这里维护一份。

字段顺序与空值占位即「历史导出」口径——来源是切换前各模块 router 里的
LIST_FIELDS（已逐模块与前端列表 columns、service 关键字段、种子数据核对
一致）。各业务模块要改导出列，只改本文件；列表展示也读同一份字段。

- fields：列顺序，切换前后必须保持一致，新增列只能追加在末尾（兼容既有字段）。
- keyword_field：列表/导出共用的关键字检索列。
- statuses：状态过滤允许值，仅作文档与校验用途，过滤口径仍在 service 层。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExportSpec:
    """单个模块的导出口径：模块名、中文名、列顺序、关键字列与状态枚举。"""

    module: str
    label: str
    fields: tuple[str, ...]
    keyword_field: str
    statuses: tuple[str, ...]


REGISTRY: dict[str, ExportSpec] = {
    "alarm": ExportSpec(
        module="alarm",
        label="告警事件",
        fields=("告警编号", "告警来源", "告警类型", "触发时间", "告警阈值", "当前值", "确认人", "告警状态",),
        keyword_field="告警编号",
        statuses=("未确认", "已确认", "处理中", "已消除",),
    ),
    "boosting_station": ExportSpec(
        module="boosting_station",
        label="升压站监视",
        fields=("升压站编号", "进线电压", "出线电压", "主变容量", "母线状态", "断路器状态", "无功补偿", "运行状态",),
        keyword_field="升压站编号",
        statuses=("正常运行", "非全相运行", "保护动作", "待检修",),
    ),
    "cleaning": ExportSpec(
        module="cleaning",
        label="组件清洗",
        fields=("任务编号", "清洗区域", "清洗方式", "计划日期", "作业人员", "用水吨数", "清洗后PR值", "清洗状态",),
        keyword_field="任务编号",
        statuses=("待排期", "已排期", "作业中", "已完成",),
    ),
    "combiner_box": ExportSpec(
        module="combiner_box",
        label="汇流箱检测",
        fields=("汇流箱编号", "所属阵列", "输入路数", "熔断器状态", "防雷模块状态", "通讯状态", "箱体温度", "运行状态",),
        keyword_field="汇流箱编号",
        statuses=("运行正常", "熔断器异常", "通讯中断", "已停用",),
    ),
    "contract": ExportSpec(
        module="contract",
        label="运维合同",
        fields=("合同编号", "合同名称", "签约甲方", "签约乙方", "合同金额", "起止日期", "续签条款", "合同状态",),
        keyword_field="合同编号",
        statuses=("草稿中", "已签订", "履行中", "已到期", "已终止",),
    ),
    "defect": ExportSpec(
        module="defect",
        label="缺陷管理",
        fields=("缺陷编号", "发现日期", "缺陷设备", "缺陷类别", "严重等级", "处理方案", "整改时限", "缺陷状态",),
        keyword_field="缺陷编号",
        statuses=("待分派", "处理中", "已验收", "已关闭",),
    ),
    "dispatch": ExportSpec(
        module="dispatch",
        label="调度指令",
        fields=("指令编号", "下发单位", "指令类型", "下发时间", "执行时限", "执行人", "执行结果", "指令状态",),
        keyword_field="指令编号",
        statuses=("待执行", "执行中", "已完成", "已驳回",),
    ),
    "energy_storage": ExportSpec(
        module="energy_storage",
        label="储能电池组",
        fields=("电池组编号", "电池类型", "额定容量", "SOC上限", "充放电循环", "电池温度", "内阻变化率", "运行状态",),
        keyword_field="电池组编号",
        statuses=("充电中", "放电中", "待机", "故障停机",),
    ),
    "environment": ExportSpec(
        module="environment",
        label="环境监测站",
        fields=("站点编号", "安装位置", "辐照度", "环境温度", "风速", "风向", "积灰比", "通讯状态",),
        keyword_field="站点编号",
        statuses=("数据正常", "数据异常", "传感器故障", "已停用",),
    ),
    "inverter": ExportSpec(
        module="inverter",
        label="逆变器监视",
        fields=("逆变器编号", "品牌型号", "额定功率", "输入电压范围", "所属阵列", "运行温度", "日均发电量", "运行状态",),
        keyword_field="逆变器编号",
        statuses=("正常运行", "降容运行", "高温报警", "待检修",),
    ),
    "maintenance": ExportSpec(
        module="maintenance",
        label="检修计划",
        fields=("计划编号", "检修设备", "检修类别", "计划开始", "计划结束", "责任人", "安全措施", "计划状态",),
        keyword_field="计划编号",
        statuses=("待审批", "已批复", "执行中", "已完工",),
    ),
    "meter": ExportSpec(
        module="meter",
        label="关口计量",
        fields=("表计编号", "计量点名称", "表计精度", "正向有功电量", "反向有功电量", "上月示数", "本月示数", "通讯状态",),
        keyword_field="表计编号",
        statuses=("通讯正常", "数据异常", "通讯中断", "已停用",),
    ),
    "patrol": ExportSpec(
        module="patrol",
        label="巡视检查",
        fields=("记录编号", "巡视区域", "巡视日期", "巡视人员", "发现缺陷数", "红外测温结果", "接线端子温度", "巡视状态",),
        keyword_field="记录编号",
        statuses=("待巡视", "巡视中", "已记录", "已归档",),
    ),
    "pv_array": ExportSpec(
        module="pv_array",
        label="光伏阵列",
        fields=("阵列编号", "所属片区", "组件型号", "单块功率", "串联片数", "总装机容量", "投运日期", "阵列状态",),
        keyword_field="阵列编号",
        statuses=("运行中", "限功率", "计划停机", "故障停机",),
    ),
    "report": ExportSpec(
        module="report",
        label="运行月报",
        fields=("月报编号", "统计月份", "发电量", "等效利用小时", "综合效率PR", "设备可利用率", "故障停机时间", "月报状态",),
        keyword_field="月报编号",
        statuses=("待填写", "已填写", "已审核", "已发布",),
    ),
    "safety": ExportSpec(
        module="safety",
        label="安全措施",
        fields=("措施编号", "措施类型", "涉及设备", "签发人", "执行人", "监护人", "有效期至", "措施状态",),
        keyword_field="措施编号",
        statuses=("待签发", "已签发", "执行中", "已解除",),
    ),
    "spare_parts": ExportSpec(
        module="spare_parts",
        label="备品备件",
        fields=("备件编号", "备件名称", "规格型号", "适用设备", "安全存量", "当前存量", "存放位置", "备件状态",),
        keyword_field="备件编号",
        statuses=("存量充足", "低于安全量", "已用尽", "已废弃",),
    ),
    "transformer": ExportSpec(
        module="transformer",
        label="变压器监视",
        fields=("变压器编号", "电压等级", "额定容量", "油温上限", "绕组温度", "油位状态", "瓦斯保护状态", "运行状态",),
        keyword_field="变压器编号",
        statuses=("正常运行", "过负荷", "油温异常", "待检修",),
    ),
}


def get_spec(module: str) -> ExportSpec:
    """读取模块导出口径；未注册模块直接报错，避免静默导出一份空表。"""
    try:
        return REGISTRY[module]
    except KeyError:
        raise KeyError(f"模块 {module} 未在导出注册表登记") from None
