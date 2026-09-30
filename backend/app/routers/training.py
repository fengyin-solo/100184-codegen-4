"""养护人员资质培训台账接口。"""
from __future__ import annotations

from fastapi import APIRouter, Header, Query

from app.schemas import ActionResult, AssignmentPayload, EntryPayload, PageResult
from app.services.training import (
    REMINDER_DAYS,
    TrainingService,
)

router = APIRouter(prefix="/api/training", tags=["资质培训"])
service = TrainingService()


def _actor(
    x_user_id: str | None,
    x_user_name: str | None,
    x_user_role: str | None,
    x_user_team: str | None,
):
    return service.actor(x_user_id, x_user_name, x_user_role, x_user_team)


@router.get("/workbench")
def workbench(
    team: str | None = None,
    x_user_id: str | None = Header(default=None),
    x_user_name: str | None = Header(default=None),
    x_user_role: str | None = Header(default=None),
    x_user_team: str | None = Header(default=None),
) -> dict:
    """班组工作台待办：条数与复训到期提醒共用同一份台账口径。"""
    actor = _actor(x_user_id, x_user_name, x_user_role, x_user_team)
    return service.workbench(actor, team)


@router.get("/qualifications", response_model=PageResult[dict])
def list_qualifications(
    keyword: str | None = None,
    team: str | None = None,
    status: str | None = None,
    page: int = 1,
    size: int = 20,
    x_user_id: str | None = Header(default=None),
    x_user_name: str | None = Header(default=None),
    x_user_role: str | None = Header(default=None),
    x_user_team: str | None = Header(default=None),
) -> PageResult[dict]:
    actor = _actor(x_user_id, x_user_name, x_user_role, x_user_team)
    items, total = service.list_qualifications(
        actor,
        keyword=keyword,
        team=team,
        status=status,
        page=page,
        size=min(size, 500),
    )
    return PageResult(items=items, total=total, page=page, size=size)


@router.post("/qualifications", response_model=ActionResult)
def create_qualification(
    payload: EntryPayload,
    x_user_id: str | None = Header(default=None),
    x_user_name: str | None = Header(default=None),
    x_user_role: str | None = Header(default=None),
    x_user_team: str | None = Header(default=None),
) -> ActionResult:
    actor = _actor(x_user_id, x_user_name, x_user_role, x_user_team)
    entry = service.create_qualification(actor, payload.values)
    return ActionResult(ok=True, message="人员资质已登记", entry=entry)


@router.patch("/qualifications/{entry_id}", response_model=ActionResult)
def update_qualification(
    entry_id: int,
    payload: EntryPayload,
    x_user_id: str | None = Header(default=None),
    x_user_name: str | None = Header(default=None),
    x_user_role: str | None = Header(default=None),
    x_user_team: str | None = Header(default=None),
) -> ActionResult:
    actor = _actor(x_user_id, x_user_name, x_user_role, x_user_team)
    entry = service.update_qualification(actor, entry_id, payload.values)
    return ActionResult(ok=True, message="人员资质已更新", entry=entry)


@router.post("/qualifications/{entry_id}/verify", response_model=ActionResult)
def verify_qualification(
    entry_id: int,
    x_user_id: str | None = Header(default=None),
    x_user_name: str | None = Header(default=None),
    x_user_role: str | None = Header(default=None),
    x_user_team: str | None = Header(default=None),
) -> ActionResult:
    actor = _actor(x_user_id, x_user_name, x_user_role, x_user_team)
    entry = service.verify_qualification(actor, entry_id)
    return ActionResult(ok=True, message="管理岗已核对该资质", entry=entry)


@router.post("/qualifications/{entry_id}/leave", response_model=ActionResult)
def leave_qualification(
    entry_id: int,
    payload: EntryPayload,
    x_user_id: str | None = Header(default=None),
    x_user_name: str | None = Header(default=None),
    x_user_role: str | None = Header(default=None),
    x_user_team: str | None = Header(default=None),
) -> ActionResult:
    actor = _actor(x_user_id, x_user_name, x_user_role, x_user_team)
    entry = service.leave_qualification(actor, entry_id, payload.values)
    return ActionResult(ok=True, message="人员已离岗；资质、培训与复训历史记录均保留", entry=entry)


@router.get("/plans", response_model=PageResult[dict])
def list_plans(
    keyword: str | None = None,
    team: str | None = None,
    status: str | None = None,
    page: int = 1,
    size: int = 20,
    x_user_id: str | None = Header(default=None),
    x_user_name: str | None = Header(default=None),
    x_user_role: str | None = Header(default=None),
    x_user_team: str | None = Header(default=None),
) -> PageResult[dict]:
    actor = _actor(x_user_id, x_user_name, x_user_role, x_user_team)
    items, total = service.list_plans(actor, keyword=keyword, team=team, status=status, page=page, size=min(size, 500))
    return PageResult(items=items, total=total, page=page, size=size)


@router.post("/plans", response_model=ActionResult)
def create_plan(
    payload: EntryPayload,
    x_user_id: str | None = Header(default=None),
    x_user_name: str | None = Header(default=None),
    x_user_role: str | None = Header(default=None),
    x_user_team: str | None = Header(default=None),
) -> ActionResult:
    actor = _actor(x_user_id, x_user_name, x_user_role, x_user_team)
    entry = service.create_plan(actor, payload.values)
    return ActionResult(ok=True, message="培训计划已登记", entry=entry)


@router.patch("/plans/{entry_id}", response_model=ActionResult)
def update_plan(
    entry_id: int,
    payload: EntryPayload,
    x_user_id: str | None = Header(default=None),
    x_user_name: str | None = Header(default=None),
    x_user_role: str | None = Header(default=None),
    x_user_team: str | None = Header(default=None),
) -> ActionResult:
    actor = _actor(x_user_id, x_user_name, x_user_role, x_user_team)
    entry = service.update_plan(actor, entry_id, payload.values)
    return ActionResult(ok=True, message="培训计划已更新", entry=entry)


@router.get("/retraining", response_model=PageResult[dict])
def list_retraining(
    keyword: str | None = None,
    team: str | None = None,
    status: str | None = None,
    page: int = 1,
    size: int = 20,
    x_user_id: str | None = Header(default=None),
    x_user_name: str | None = Header(default=None),
    x_user_role: str | None = Header(default=None),
    x_user_team: str | None = Header(default=None),
) -> PageResult[dict]:
    actor = _actor(x_user_id, x_user_name, x_user_role, x_user_team)
    items, total = service.list_retraining(actor, keyword=keyword, team=team, status=status, page=page, size=min(size, 500))
    return PageResult(items=items, total=total, page=page, size=size)


@router.post("/retraining", response_model=ActionResult)
def create_retraining(
    payload: EntryPayload,
    x_user_id: str | None = Header(default=None),
    x_user_name: str | None = Header(default=None),
    x_user_role: str | None = Header(default=None),
    x_user_team: str | None = Header(default=None),
) -> ActionResult:
    actor = _actor(x_user_id, x_user_name, x_user_role, x_user_team)
    entry = service.create_retraining(actor, payload.values)
    return ActionResult(ok=True, message="复训记录已登记", entry=entry)


@router.patch("/retraining/{entry_id}", response_model=ActionResult)
def update_retraining(
    entry_id: int,
    payload: EntryPayload,
    x_user_id: str | None = Header(default=None),
    x_user_name: str | None = Header(default=None),
    x_user_role: str | None = Header(default=None),
    x_user_team: str | None = Header(default=None),
) -> ActionResult:
    actor = _actor(x_user_id, x_user_name, x_user_role, x_user_team)
    entry = service.update_retraining(actor, entry_id, payload.values)
    return ActionResult(ok=True, message="复训记录已更新", entry=entry)


@router.post("/retraining/{entry_id}/complete", response_model=ActionResult)
def complete_retraining(
    entry_id: int,
    payload: EntryPayload,
    x_user_id: str | None = Header(default=None),
    x_user_name: str | None = Header(default=None),
    x_user_role: str | None = Header(default=None),
    x_user_team: str | None = Header(default=None),
) -> ActionResult:
    actor = _actor(x_user_id, x_user_name, x_user_role, x_user_team)
    entry = service.complete_retraining(actor, entry_id, payload.values)
    return ActionResult(ok=True, message="复训已完成，待办同步消除", entry=entry)


@router.get("/reminders", response_model=PageResult[dict])
def list_reminders(
    keyword: str | None = None,
    team: str | None = None,
    days: int = Query(default=REMINDER_DAYS, ge=1, le=365),
    page: int = 1,
    size: int = 200,
    x_user_id: str | None = Header(default=None),
    x_user_name: str | None = Header(default=None),
    x_user_role: str | None = Header(default=None),
    x_user_team: str | None = Header(default=None),
) -> PageResult[dict]:
    actor = _actor(x_user_id, x_user_name, x_user_role, x_user_team)
    items, total = service.list_reminders(
        actor,
        keyword=keyword,
        team=team,
        days=days,
        page=page,
        size=min(size, 500),
    )
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/assignments", response_model=PageResult[dict])
def list_assignments(
    team: str | None = None,
    page: int = 1,
    size: int = 20,
    x_user_id: str | None = Header(default=None),
    x_user_name: str | None = Header(default=None),
    x_user_role: str | None = Header(default=None),
    x_user_team: str | None = Header(default=None),
) -> PageResult[dict]:
    actor = _actor(x_user_id, x_user_name, x_user_role, x_user_team)
    items, total = service.list_assignments(actor, team=team, page=page, size=min(size, 500))
    return PageResult(items=items, total=total, page=page, size=size)


@router.post("/assignments", response_model=ActionResult)
def create_assignment(
    payload: AssignmentPayload,
    x_user_id: str | None = Header(default=None),
    x_user_name: str | None = Header(default=None),
    x_user_role: str | None = Header(default=None),
    x_user_team: str | None = Header(default=None),
) -> ActionResult:
    actor = _actor(x_user_id, x_user_name, x_user_role, x_user_team)
    entry = service.create_assignment(
        actor,
        team=payload.team,
        assignment_no=payload.assignment_no,
        work_name=payload.work_name,
        scheduled_date=payload.scheduled_date,
        worker_ids=payload.worker_ids,
    )
    return ActionResult(ok=True, message="资质校验通过，养护作业已排入计划", entry=entry)
