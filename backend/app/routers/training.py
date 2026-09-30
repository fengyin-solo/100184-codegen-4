"""养护人员资质培训台账接口。

身份通过 X-Operator-Id 请求头识别（演示环境无登录态，正式环境换成鉴权中间件）。
路由层只做参数解析与 HTTP 状态映射，权限/资质/提醒规则都在 services/training.py。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.training import TrainingService

router = APIRouter(prefix="/api/training", tags=["养护人员资质培训台账"])

service = TrainingService()

QUALIFICATION_STATES = ["有效", "已过期", "暂停"]


def _operator(operator_id: int | None) -> dict[str, Any]:
    return service.resolve_operator(operator_id)


@router.get("/operators")
def get_operators() -> dict[str, Any]:
    """可选操作人员：前端身份切换下拉用。"""
    return {"items": service.list_operators()}


@router.get("/staff")
def list_staff(
    crew: str | None = Query(default=None, description="按班组过滤"),
    x_operator_id: int | None = Header(default=None),
) -> dict[str, Any]:
    """作业人员花名册：离岗人员同样返回（历史记录保留），用在岗状态区分。"""
    _operator(x_operator_id)
    return {"items": service.list_staff(crew)}


@router.get("/entries", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按人员姓名/资质名称/证书编号检索"),
    crew: str | None = Query(default=None, description="按所属班组过滤"),
    qualification: str | None = Query(default=None, description="有效、已过期、暂停"),
    only_due: bool = Query(default=False, description="只看待复训提醒中的台账"),
    include_left: bool = Query(default=True, description="是否包含已离岗人员的历史记录"),
    page: int = 1,
    size: int = 50,
    x_operator_id: int | None = Header(default=None),
) -> PageResult[dict]:
    """培训台账列表。所有登录身份都可看；班组范围由前端按身份收窄，服务端不强制。"""
    _operator(x_operator_id)
    rows = service.list_entries(
        keyword=keyword,
        crew=crew,
        qualification=qualification,
        only_due=only_due,
        include_left=include_left,
    )
    total = len(rows)
    start = max(page - 1, 0) * size
    return PageResult(items=rows[start:start + size], total=total, page=page, size=size)


@router.get("/entries/stats")
def entry_stats(
    crew: str | None = Query(default=None),
    x_operator_id: int | None = Header(default=None),
) -> dict[str, Any]:
    """台账统计卡片。"""
    _operator(x_operator_id)
    return service.stats(crew)


@router.get("/entries/{entry_id}", response_model=dict)
def get_entry(
    entry_id: int,
    x_operator_id: int | None = Header(default=None),
) -> dict[str, Any]:
    _operator(x_operator_id)
    entry = service.get_entry(entry_id)
    if entry is None:
        return {"message": f"台账 {entry_id} 不存在", "entry": None}
    return entry


@router.post("/entries", response_model=ActionResult)
def create_plan(
    payload: EntryPayload,
    x_operator_id: int | None = Header(default=None),
) -> ActionResult:
    """登记培训计划：本班组培训管理员可用，跨班组被逐项拦下，其余身份越权拒绝。"""
    operator = _operator(x_operator_id)
    entry = service.create_plan(payload.values, operator)
    return ActionResult(ok=True, message="培训计划已登记", entry=entry)


@router.post("/entries/{entry_id}/retrain", response_model=ActionResult)
def add_retrain(
    entry_id: int,
    payload: EntryPayload,
    x_operator_id: int | None = Header(default=None),
) -> ActionResult:
    """登记一次复训记录；合格复训会续期并关闭对应到期提醒。"""
    operator = _operator(x_operator_id)
    entry = service.add_retrain(entry_id, payload.values, operator)
    tip = entry.pop("提示", None)
    message = tip or "复训记录已登记"
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/entries/{entry_id}/suspend", response_model=ActionResult)
def suspend_entry(
    entry_id: int,
    payload: EntryPayload,
    x_operator_id: int | None = Header(default=None),
) -> ActionResult:
    """暂停资质：暂停期间该人员不能排进养护作业。"""
    operator = _operator(x_operator_id)
    entry = service.suspend(entry_id, str(payload.values.get("暂停原因") or ""), operator)
    return ActionResult(ok=True, message="资质已暂停，排班已同步拦截", entry=entry)


@router.post("/entries/{entry_id}/resume", response_model=ActionResult)
def resume_entry(
    entry_id: int,
    payload: EntryPayload,
    x_operator_id: int | None = Header(default=None),
) -> ActionResult:
    """恢复资质：过期资质不能直接恢复，需先补合格复训。"""
    operator = _operator(x_operator_id)
    entry = service.resume(entry_id, operator)
    return ActionResult(ok=True, message="资质已恢复", entry=entry)


@router.post("/entries/{entry_id}/verify", response_model=ActionResult)
def verify_entry(
    entry_id: int,
    payload: EntryPayload,
    x_operator_id: int | None = Header(default=None),
) -> ActionResult:
    """管理岗位核对：可核对全部班组台账，但不改动培训/复训内容。"""
    operator = _operator(x_operator_id)
    entry = service.verify_entry(entry_id, operator)
    return ActionResult(ok=True, message="台账已核对", entry=entry)


@router.post("/staff/{staff_id}/leave", response_model=ActionResult)
def leave_staff(
    staff_id: int,
    payload: EntryPayload,
    x_operator_id: int | None = Header(default=None),
) -> ActionResult:
    """人员离岗：只改在岗状态，台账与复训历史完整保留。"""
    operator = _operator(x_operator_id)
    staff = service.leave_staff(staff_id, operator, payload.values.get("离岗日期"))
    return ActionResult(ok=True, message="已登记离岗，培训历史记录保留", entry=staff)


@router.get("/assignments")
def list_assignments(x_operator_id: int | None = Header(default=None)) -> dict[str, Any]:
    """已生成的养护作业排班。"""
    _operator(x_operator_id)
    return {"items": service.list_assignments()}


@router.post("/assignments/check")
def check_assignment(
    payload: EntryPayload,
    x_operator_id: int | None = Header(default=None),
) -> dict[str, Any]:
    """只校验不落单：前端排班表单提交前预检查，返回逐项卡控原因。"""
    _operator(x_operator_id)
    person_ids = payload.values.get("人员ids") or []
    try:
        ids = [int(pid) for pid in person_ids]
    except (ValueError, TypeError):
        ids = []
    passed, blocked = service.check_assignment(ids)
    return {"passed": passed, "blocked": blocked, "ok": not blocked}


@router.post("/assignments", response_model=ActionResult)
def create_assignment(
    payload: EntryPayload,
    x_operator_id: int | None = Header(default=None),
) -> ActionResult:
    """提交养护作业排班：资质过期、暂停、离岗、无资质逐项拦截，整体不落单。"""
    operator = _operator(x_operator_id)
    assignment = service.create_assignment(payload.values, operator)
    return ActionResult(ok=True, message="排班已生成，人员资质校验全部通过", entry=assignment)


@router.get("/workbench")
def workbench(
    crew: str | None = Query(default=None, description="管理岗位可指定班组；班组身份强制本班组"),
    x_operator_id: int | None = Header(default=None),
) -> dict[str, Any]:
    """班组工作台待办：待办条数与培训台账「待复训」同口径一致。"""
    operator = _operator(x_operator_id)
    return service.workbench(operator, crew)


@router.get("/reminders")
def list_reminders(
    crew: str | None = Query(default=None),
    x_operator_id: int | None = Header(default=None),
) -> dict[str, Any]:
    """复训到期提醒清单（待处理）。"""
    operator = _operator(x_operator_id)
    effective_crew = crew
    if operator["角色"] != "管理岗位":
        effective_crew = operator["所属班组"]
    return {"items": service.open_reminders(effective_crew)}
