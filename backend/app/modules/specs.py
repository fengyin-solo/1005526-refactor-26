"""业务模块的唯一口径注册表。

字段怎么取（fields / keyword_field）、范围怎么框（statuses / actions）、
空值怎么填（empty_placeholder）都只在这里维护一份，列表与导出共用。

本注册表由 18 个模块原有的 services / routers / 前端页面三处常量逐个核对后
合并而来，字段顺序、必填字段、状态序列、动作映射与历史行为完全一致。
"""
from __future__ import annotations

from dataclasses import dataclass, field

# 历史导出（及前端列表）对缺值单元格统一使用的占位符，不允许改动。
EMPTY_PLACEHOLDER = "—"


@dataclass(frozen=True)
class ModuleSpec:
    """一个业务模块的字段口径与状态流转口径。"""

    name: str
    """模块标识，同时是 store 表名与 /api 前缀，例如 pv_array。"""

    tag: str
    """页面/动作报错用的模块称呼，例如 逆变器监视。"""

    entity: str
    """单条记录不存在等提示用的对象称呼，例如 逆变器。"""

    created: str
    """登记成功提示里的对象称呼，例如 逆变器已登记。"""

    keyword_field: str
    """关键字检索所匹配的字段，恒为 fields 的第一个。"""

    fields: tuple[str, ...]
    """列表与导出共用的展示字段，顺序即历史导出的列顺序，不得调整。"""

    required: tuple[str, ...]
    """登记时必填的字段。"""

    statuses: tuple[str, ...]
    """允许的状态序列，第一个是新建时的初始状态，最后一个是终态。"""

    actions: dict[str, str] = field(default_factory=dict)
    """可执行动作到目标状态的映射。"""

    negative_actions: frozenset[str] = frozenset()
    """执行后应把记录标记为异常（abnormal=True）的动作。"""

    @property
    def prefix(self) -> str:
        return f"/api/{self.name}"


_MODULE_SPECS: tuple[ModuleSpec, ...] = (
    ModuleSpec(
        name="pv_array", tag="光伏阵列", entity="光伏阵列", created="光伏阵列",
        keyword_field="阵列编号",
        fields=("阵列编号", "所属片区", "组件型号", "单块功率", "串联片数", "总装机容量", "投运日期", "阵列状态"),
        required=("阵列编号", "所属片区", "组件型号"),
        statuses=("运行中", "限功率", "计划停机", "故障停机"),
        actions={"恢复全功率": "运行中", "降功率运行": "限功率", "申请停机": "计划停机"},
    ),
    ModuleSpec(
        name="inverter", tag="逆变器监视", entity="逆变器", created="逆变器",
        keyword_field="逆变器编号",
        fields=("逆变器编号", "品牌型号", "额定功率", "输入电压范围", "所属阵列", "运行温度", "日均发电量", "运行状态"),
        required=("逆变器编号", "品牌型号", "额定功率"),
        statuses=("正常运行", "降容运行", "高温报警", "待检修"),
        actions={"恢复运行": "正常运行", "降容保护": "降容运行", "安排检修": "待检修"},
    ),
    ModuleSpec(
        name="combiner_box", tag="汇流箱检测", entity="汇流箱", created="汇流箱",
        keyword_field="汇流箱编号",
        fields=("汇流箱编号", "所属阵列", "输入路数", "熔断器状态", "防雷模块状态", "通讯状态", "箱体温度", "运行状态"),
        required=("汇流箱编号", "所属阵列", "输入路数"),
        statuses=("运行正常", "熔断器异常", "通讯中断", "已停用"),
        actions={"恢复正常": "运行正常", "标记异常": "熔断器异常", "停用设备": "已停用"},
        negative_actions=frozenset({"停用设备"}),
    ),
    ModuleSpec(
        name="transformer", tag="变压器监视", entity="变压器", created="变压器",
        keyword_field="变压器编号",
        fields=("变压器编号", "电压等级", "额定容量", "油温上限", "绕组温度", "油位状态", "瓦斯保护状态", "运行状态"),
        required=("变压器编号", "电压等级", "额定容量"),
        statuses=("正常运行", "过负荷", "油温异常", "待检修"),
        actions={"恢复正常": "正常运行", "降负荷运行": "过负荷", "安排检修": "待检修"},
    ),
    ModuleSpec(
        name="energy_storage", tag="储能电池组", entity="储能电池组", created="储能电池组",
        keyword_field="电池组编号",
        fields=("电池组编号", "电池类型", "额定容量", "SOC上限", "充放电循环", "电池温度", "内阻变化率", "运行状态"),
        required=("电池组编号", "电池类型", "额定容量"),
        statuses=("充电中", "放电中", "待机", "故障停机"),
        actions={"启动充电": "充电中", "启动放电": "放电中", "切换到待机": "待机"},
    ),
    ModuleSpec(
        name="boosting_station", tag="升压站监视", entity="升压站", created="升压站",
        keyword_field="升压站编号",
        fields=("升压站编号", "进线电压", "出线电压", "主变容量", "母线状态", "断路器状态", "无功补偿", "运行状态"),
        required=("升压站编号", "进线电压", "出线电压"),
        statuses=("正常运行", "非全相运行", "保护动作", "待检修"),
        actions={"恢复正常": "正常运行", "检查保护": "非全相运行", "安排检修": "待检修"},
    ),
    ModuleSpec(
        name="meter", tag="关口计量", entity="关口表计", created="关口表计",
        keyword_field="表计编号",
        fields=("表计编号", "计量点名称", "表计精度", "正向有功电量", "反向有功电量", "上月示数", "本月示数", "通讯状态"),
        required=("表计编号", "计量点名称", "表计精度"),
        statuses=("通讯正常", "数据异常", "通讯中断", "已停用"),
        actions={"确认正常": "通讯正常", "标记异常": "数据异常", "停用表计": "已停用"},
        negative_actions=frozenset({"停用表计"}),
    ),
    ModuleSpec(
        name="environment", tag="环境监测站", entity="环境监测站", created="环境监测站",
        keyword_field="站点编号",
        fields=("站点编号", "安装位置", "辐照度", "环境温度", "风速", "风向", "积灰比", "通讯状态"),
        required=("站点编号", "安装位置", "辐照度"),
        statuses=("数据正常", "数据异常", "传感器故障", "已停用"),
        actions={"恢复正常": "数据正常", "标记异常": "数据异常", "停用站点": "已停用"},
        negative_actions=frozenset({"停用站点"}),
    ),
    ModuleSpec(
        name="cleaning", tag="组件清洗", entity="清洗任务", created="清洗任务",
        keyword_field="任务编号",
        fields=("任务编号", "清洗区域", "清洗方式", "计划日期", "作业人员", "用水吨数", "清洗后PR值", "清洗状态"),
        required=("任务编号", "清洗区域", "清洗方式"),
        statuses=("待排期", "已排期", "作业中", "已完成"),
        actions={"排期确认": "已排期", "开始作业": "作业中", "验收完成": "已完成"},
    ),
    ModuleSpec(
        name="patrol", tag="巡视检查", entity="巡视记录", created="巡视记录",
        keyword_field="记录编号",
        fields=("记录编号", "巡视区域", "巡视日期", "巡视人员", "发现缺陷数", "红外测温结果", "接线端子温度", "巡视状态"),
        required=("记录编号", "巡视区域", "巡视日期"),
        statuses=("待巡视", "巡视中", "已记录", "已归档"),
        actions={"开始巡视": "巡视中", "提交记录": "已记录", "归档记录": "已归档"},
    ),
    ModuleSpec(
        name="defect", tag="缺陷管理", entity="设备缺陷", created="设备缺陷",
        keyword_field="缺陷编号",
        fields=("缺陷编号", "发现日期", "缺陷设备", "缺陷类别", "严重等级", "处理方案", "整改时限", "缺陷状态"),
        required=("缺陷编号", "发现日期", "缺陷设备"),
        statuses=("待分派", "处理中", "已验收", "已关闭"),
        actions={"分派处理": "处理中", "提交验收": "已验收", "关闭缺陷": "已关闭"},
    ),
    ModuleSpec(
        name="maintenance", tag="检修计划", entity="检修计划", created="检修计划",
        keyword_field="计划编号",
        fields=("计划编号", "检修设备", "检修类别", "计划开始", "计划结束", "责任人", "安全措施", "计划状态"),
        required=("计划编号", "检修设备", "检修类别"),
        statuses=("待审批", "已批复", "执行中", "已完工"),
        actions={"提交审批": "已批复", "开始执行": "执行中", "确认完工": "已完工"},
    ),
    ModuleSpec(
        name="spare_parts", tag="备品备件", entity="备件物料", created="备件物料",
        keyword_field="备件编号",
        fields=("备件编号", "备件名称", "规格型号", "适用设备", "安全存量", "当前存量", "存放位置", "备件状态"),
        required=("备件编号", "备件名称", "规格型号"),
        statuses=("存量充足", "低于安全量", "已用尽", "已废弃"),
        actions={"入库登记": "存量充足", "领用出库": "低于安全量", "标记废弃": "已废弃"},
    ),
    ModuleSpec(
        name="alarm", tag="告警事件", entity="告警事件", created="告警事件",
        keyword_field="告警编号",
        fields=("告警编号", "告警来源", "告警类型", "触发时间", "告警阈值", "当前值", "确认人", "告警状态"),
        required=("告警编号", "告警来源", "告警类型"),
        statuses=("未确认", "已确认", "处理中", "已消除"),
        actions={"确认告警": "已确认", "开始处理": "处理中", "消除告警": "已消除"},
    ),
    ModuleSpec(
        name="dispatch", tag="调度指令", entity="调度指令单", created="调度指令单",
        keyword_field="指令编号",
        fields=("指令编号", "下发单位", "指令类型", "下发时间", "执行时限", "执行人", "执行结果", "指令状态"),
        required=("指令编号", "下发单位", "指令类型"),
        statuses=("待执行", "执行中", "已完成", "已驳回"),
        actions={"确认执行": "执行中", "完成回复": "已完成", "驳回指令": "已驳回"},
        negative_actions=frozenset({"驳回指令"}),
    ),
    ModuleSpec(
        name="safety", tag="安全措施", entity="安全措施票", created="安全措施票",
        keyword_field="措施编号",
        fields=("措施编号", "措施类型", "涉及设备", "签发人", "执行人", "监护人", "有效期至", "措施状态"),
        required=("措施编号", "措施类型", "涉及设备"),
        statuses=("待签发", "已签发", "执行中", "已解除"),
        actions={"签发措施": "已签发", "开始执行": "执行中", "解除措施": "已解除"},
    ),
    ModuleSpec(
        name="contract", tag="运维合同", entity="运维合同", created="运维合同",
        keyword_field="合同编号",
        fields=("合同编号", "合同名称", "签约甲方", "签约乙方", "合同金额", "起止日期", "续签条款", "合同状态"),
        required=("合同编号", "合同名称", "签约甲方"),
        statuses=("草稿中", "已签订", "履行中", "已到期", "已终止"),
        actions={"确认签订": "已签订", "开始履行": "履行中", "终止合同": "已终止"},
    ),
    ModuleSpec(
        name="report", tag="运行月报", entity="运行月报", created="运行月报",
        keyword_field="月报编号",
        fields=("月报编号", "统计月份", "发电量", "等效利用小时", "综合效率PR", "设备可利用率", "故障停机时间", "月报状态"),
        required=("月报编号", "统计月份", "发电量"),
        statuses=("待填写", "已填写", "已审核", "已发布"),
        actions={"填写月报": "已填写", "提交审核": "已审核", "发布月报": "已发布"},
    ),
)

SPECS: dict[str, ModuleSpec] = {spec.name: spec for spec in _MODULE_SPECS}
# 保持注册顺序（与路由汇总里的历史顺序一致）。
MODULE_NAMES: tuple[str, ...] = tuple(spec.name for spec in _MODULE_SPECS)


def get_spec(module: str) -> ModuleSpec:
    """按模块名取口径；模块未注册时给出明确错误，避免静默落到空表。"""
    try:
        return SPECS[module]
    except KeyError as exc:
        raise KeyError(f"未注册的业务模块：{module}") from exc
