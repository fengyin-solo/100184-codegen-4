"""养护人员资质培训台账：权限、资质状态、复训提醒和排单校验统一收口在这里。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from app.store import store

QUALIFICATIONS = "training_qualifications"
PLANS = "training_plans"
RETRAINING = "training_retraining"
ASSIGNMENTS = "training_assignments"

ROLE_MANAGER = "管理岗"
ROLE_TRAINING_ADMIN = "培训管理员"
ROLE_WORKER = "作业人员"

REMINDER_DAYS = 30

QUALIFICATION_FIELDS = [
    "personnel_id",
    "personnel_name",
    "team",
    "certificate_no",
    "certificate_name",
    "certificate_issue_date",
    "certificate_expiry",
]
QUALIFICATION_UPDATABLE = {
    "personnel_id",
    "personnel_name",
    "certificate_no",
    "certificate_name",
    "certificate_level",
    "certificate_issue_date",
    "certificate_expiry",
    "suspended",
    "suspend_reason",
    "employment_status",
}
PLAN_FIELDS = [
    "plan_no",
    "team",
    "training_topic",
    "training_type",
    "personnel_id",
    "personnel_name",
    "planned_date",
]
PLAN_UPDATABLE = {
    "training_topic",
    "training_type",
    "personnel_id",
    "personnel_name",
    "planned_date",
    "trainer",
    "location",
    "hours",
    "status",
    "remark",
}
RETRAINING_FIELDS = [
    "record_no",
    "qualification_id",
    "course_name",
    "last_training_date",
    "due_date",
]
RETRAINING_UPDATABLE = {
    "course_name",
    "last_training_date",
    "due_date",
    "trainer",
    "remark",
}


class TrainingRequestError(Exception):
    """请求内容不完整或日期格式不正确。"""

    status_code = 400


class TrainingAuthError(Exception):
    """请求没有携带可识别的操作人员身份。"""

    status_code = 401


class TrainingPermissionError(Exception):
    """越权或跨班组写入被服务层拒绝。"""

    status_code = 403

    def __init__(self, message: str, *, blocked_item: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.blocked_item = blocked_item

    @property
    def detail(self) -> dict[str, Any]:
        detail: dict[str, Any] = {"message": self.message}
        if self.blocked_item:
            detail["blocked_item"] = self.blocked_item
        return detail


class TrainingNotFoundError(Exception):
    status_code = 404


class TrainingConflictError(Exception):
    """排单人员资质不满足要求，整单拒绝。"""

    status_code = 409

    def __init__(self, message: str, blockers: list[dict[str, str]]) -> None:
        super().__init__(message)
        self.message = message
        self.blockers = blockers

    @property
    def detail(self) -> dict[str, Any]:
        return {"message": self.message, "blockers": self.blockers}


@dataclass(frozen=True)
class Actor:
    user_id: str
    name: str
    role: str
    team: str

    @property
    def is_manager(self) -> bool:
        return self.role == ROLE_MANAGER

    @property
    def is_training_admin(self) -> bool:
        return self.role == ROLE_TRAINING_ADMIN


def _today() -> date:
    return date.today()


def _parse_date(value: Any, field_name: str) -> str:
    if value is None or not str(value).strip():
        raise TrainingRequestError(f"【{field_name}】不能为空")
    try:
        date.fromisoformat(str(value).strip())
    except ValueError as exc:
        raise TrainingRequestError(f"【{field_name}】必须是 YYYY-MM-DD 日期格式") from exc
    return str(value).strip()


def _text(values: dict[str, Any], key: str, label: str) -> str:
    value = str(values.get(key) or "").strip()
    if not value:
        raise TrainingRequestError(f"缺少必填字段：【{label}】")
    return value


def _next_id(rows: list[dict[str, Any]]) -> int:
    return max((int(row.get("id", 0)) for row in rows), default=0) + 1


def _paginate(rows: list[dict[str, Any]], page: int, size: int) -> tuple[list[dict[str, Any]], int]:
    total = len(rows)
    start = max(page - 1, 0) * size
    return rows[start:start + size], total


class TrainingService:
    def actor(self, user_id: str | None, name: str | None, role: str | None, team: str | None) -> Actor:
        if not user_id or not role:
            raise TrainingAuthError("缺少操作人员身份，请选择登录岗位后再提交")
        normalized_role = role.strip()
        if normalized_role not in {ROLE_MANAGER, ROLE_TRAINING_ADMIN, ROLE_WORKER}:
            raise TrainingAuthError(f"未知岗位：{normalized_role}")
        if normalized_role != ROLE_MANAGER and not (team or "").strip():
            raise TrainingAuthError("班组岗位必须携带归属班组")
        return Actor(
            user_id=user_id.strip(),
            name=(name or user_id).strip(),
            role=normalized_role,
            team=(team or "").strip(),
        )

    def _require_training_admin(self, actor: Actor) -> None:
        if not actor.is_training_admin:
            raise TrainingPermissionError(
                f"越权提交已拒绝：仅本班组培训管理员可改动资质培训与复训记录，"
                f"当前账号「{actor.name}」为{actor.role}"
            )

    def _require_same_team(self, actor: Actor, target_team: str, blocked_item: str) -> None:
        self._require_training_admin(actor)
        if actor.team != target_team:
            raise TrainingPermissionError(
                f"跨班组提交已拦下：目标记录归属「{target_team}」，当前账号归属「{actor.team}」；"
                f"请联系该班组培训管理员处理",
                blocked_item=blocked_item,
            )

    def _require_manager(self, actor: Actor, action: str) -> None:
        if not actor.is_manager:
            raise TrainingPermissionError(f"越权提交已拒绝：仅管理岗可{action}，当前岗位为{actor.role}")

    def _find(self, table: str, entry_id: int, label: str) -> dict[str, Any]:
        row = store.find(table, entry_id)
        if row is None:
            raise TrainingNotFoundError(f"{label} {entry_id} 不存在，历史记录也未检索到")
        return row

    def _find_personnel(self, personnel_id: str, team: str, label: str) -> dict[str, Any]:
        for row in store.rows(QUALIFICATIONS):
            if row.get("personnel_id") == personnel_id:
                if row.get("team") != team:
                    raise TrainingPermissionError(
                        f"跨班组提交已拦下：人员「{personnel_id}」归属「{row.get('team')}」，"
                        f"不属于当前班组「{team}」",
                        blocked_item="人员归属班组",
                    )
                return row
        raise TrainingNotFoundError(f"{label}「{personnel_id}」未在本班组资质台账建档")

    def _qualification_status(self, qualification: dict[str, Any], today: date | None = None) -> str:
        today = today or _today()
        if not qualification.get("active", True):
            return "离岗"
        if qualification.get("suspended"):
            return "已暂停"
        expiry = date.fromisoformat(str(qualification["certificate_expiry"]))
        if expiry < today:
            return "已过期"
        due_date = self._next_due_date(qualification["id"], today)
        if due_date and due_date <= today + timedelta(days=REMINDER_DAYS):
            return "待复训"
        return "正常"

    def _with_status(self, row: dict[str, Any], today: date | None = None) -> dict[str, Any]:
        item = dict(row)
        item["status"] = self._qualification_status(row, today)
        item["assignment_allowed"] = item["status"] in {"正常", "待复训"}
        return item

    def _next_due_date(self, qualification_id: int, today: date) -> date | None:
        dates: list[date] = []
        for record in store.rows(RETRAINING):
            if int(record.get("qualification_id", 0)) != qualification_id:
                continue
            if record.get("status") == "已完成" or record.get("completed_date"):
                continue
            due_date = date.fromisoformat(str(record["due_date"]))
            dates.append(due_date)
        return min(dates, default=None)

    def list_qualifications(
        self,
        actor: Actor,
        *,
        keyword: str | None = None,
        team: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = [self._with_status(row) for row in store.rows(QUALIFICATIONS)]
        rows = self._filter_people(rows, keyword=keyword, team=team, status=status)
        return _paginate(rows, page, size)

    def _filter_people(
        self,
        rows: list[dict[str, Any]],
        *,
        keyword: str | None,
        team: str | None,
        status: str | None,
    ) -> list[dict[str, Any]]:
        filtered = rows
        if team:
            filtered = [row for row in filtered if row.get("team") == team]
        if status:
            filtered = [row for row in filtered if row.get("status") == status]
        if keyword:
            key = keyword.strip()
            filtered = [
                row
                for row in filtered
                if key in str(row.get("personnel_id", ""))
                or key in str(row.get("personnel_name", ""))
                or key in str(row.get("certificate_no", ""))
            ]
        return filtered

    def create_qualification(self, actor: Actor, values: dict[str, Any]) -> dict[str, Any]:
        target_team = _text(values, "team", "归属班组")
        self._require_same_team(actor, target_team, "归属班组")
        cleaned = {field: _text(values, field, field) for field in QUALIFICATION_FIELDS}
        cleaned["certificate_issue_date"] = _parse_date(cleaned["certificate_issue_date"], "发证日期")
        cleaned["certificate_expiry"] = _parse_date(cleaned["certificate_expiry"], "证书有效期至")
        if date.fromisoformat(cleaned["certificate_expiry"]) < date.fromisoformat(cleaned["certificate_issue_date"]):
            raise TrainingRequestError("【证书有效期至】不能早于【发证日期】")
        suspended = bool(values.get("suspended", False))
        entry = {
            "id": _next_id(store.rows(QUALIFICATIONS)),
            **cleaned,
            "certificate_level": values.get("certificate_level", ""),
            "employment_status": "在岗",
            "active": True,
            "suspended": suspended,
            "suspend_reason": str(values.get("suspend_reason") or ""),
            "verified": False,
            "created_by": actor.user_id,
        }
        store.rows(QUALIFICATIONS).append(entry)
        return self._with_status(entry)

    def update_qualification(self, actor: Actor, entry_id: int, values: dict[str, Any]) -> dict[str, Any]:
        entry = self._find(QUALIFICATIONS, entry_id, "人员资质")
        self._require_same_team(actor, str(entry["team"]), "记录归属班组")
        self._apply_updates(entry, values, QUALIFICATION_UPDATABLE)
        if "certificate_expiry" in values:
            _parse_date(entry["certificate_expiry"], "证书有效期至")
        if "certificate_issue_date" in values:
            _parse_date(entry["certificate_issue_date"], "发证日期")
        if "suspended" in values:
            entry["suspended"] = bool(values["suspended"])
        return self._with_status(entry)

    def verify_qualification(self, actor: Actor, entry_id: int) -> dict[str, Any]:
        entry = self._find(QUALIFICATIONS, entry_id, "人员资质")
        self._require_manager(actor, "核对全部班组资质")
        entry["verified"] = True
        entry["verified_by"] = actor.name
        entry["verified_at"] = _today().isoformat()
        return self._with_status(entry)

    def leave_qualification(self, actor: Actor, entry_id: int, values: dict[str, Any]) -> dict[str, Any]:
        entry = self._find(QUALIFICATIONS, entry_id, "人员资质")
        self._require_same_team(actor, str(entry["team"]), "记录归属班组")
        entry["active"] = False
        entry["employment_status"] = "离岗"
        entry["left_at"] = _parse_date(values.get("left_at") or _today().isoformat(), "离岗日期")
        return self._with_status(entry)

    def list_plans(
        self,
        actor: Actor,
        *,
        keyword: str | None = None,
        team: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(PLANS)
        if team:
            rows = [row for row in rows if row.get("team") == team]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if keyword:
            key = keyword.strip()
            rows = [
                row
                for row in rows
                if key in str(row.get("plan_no", ""))
                or key in str(row.get("personnel_name", ""))
                or key in str(row.get("training_topic", ""))
            ]
        return _paginate(rows, page, size)

    def create_plan(self, actor: Actor, values: dict[str, Any]) -> dict[str, Any]:
        target_team = _text(values, "team", "归属班组")
        self._require_same_team(actor, target_team, "培训计划归属班组")
        cleaned = {field: _text(values, field, field) for field in PLAN_FIELDS}
        cleaned["planned_date"] = _parse_date(cleaned["planned_date"], "计划培训日期")
        qualification = self._find_personnel(cleaned["personnel_id"], target_team, "培训人员")
        entry = {
            "id": _next_id(store.rows(PLANS)),
            "status": "待开始",
            **cleaned,
            "personnel_name": cleaned["personnel_name"] or str(qualification["personnel_name"]),
            "trainer": str(values.get("trainer") or ""),
            "location": str(values.get("location") or ""),
            "hours": values.get("hours"),
            "remark": str(values.get("remark") or ""),
            "created_by": actor.user_id,
        }
        store.rows(PLANS).append(entry)
        return entry

    def update_plan(self, actor: Actor, entry_id: int, values: dict[str, Any]) -> dict[str, Any]:
        entry = self._find(PLANS, entry_id, "培训计划")
        self._require_same_team(actor, str(entry["team"]), "培训计划归属班组")
        self._apply_updates(entry, values, PLAN_UPDATABLE)
        if "personnel_id" in values:
            qualification = self._find_personnel(str(entry["personnel_id"]), str(entry["team"]), "培训人员")
            if not entry.get("personnel_name"):
                entry["personnel_name"] = qualification["personnel_name"]
        if "planned_date" in values:
            _parse_date(entry["planned_date"], "计划培训日期")
        return entry

    def list_retraining(
        self,
        actor: Actor,
        *,
        keyword: str | None = None,
        team: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(RETRAINING)
        if team:
            rows = [row for row in rows if row.get("team") == team]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if keyword:
            key = keyword.strip()
            rows = [
                row
                for row in rows
                if key in str(row.get("record_no", ""))
                or key in str(row.get("personnel_name", ""))
                or key in str(row.get("course_name", ""))
            ]
        return _paginate(rows, page, size)

    def create_retraining(self, actor: Actor, values: dict[str, Any]) -> dict[str, Any]:
        record_no = _text(values, "record_no", "复训记录编号")
        qualification_id_text = _text(values, "qualification_id", "关联资质ID")
        try:
            qualification_id = int(qualification_id_text)
        except ValueError as exc:
            raise TrainingRequestError("【关联资质ID】必须是数字") from exc
        qualification = store.find(QUALIFICATIONS, qualification_id)
        if qualification is None:
            raise TrainingNotFoundError(f"关联资质ID {qualification_id} 不存在")
        self._require_same_team(actor, str(qualification["team"]), "关联资质归属班组")
        course_name = _text(values, "course_name", "复训课程")
        last_training_date = _parse_date(_text(values, "last_training_date", "上次培训日期"), "上次培训日期")
        due_date = _parse_date(_text(values, "due_date", "复训到期日"), "复训到期日")
        entry = {
            "id": _next_id(store.rows(RETRAINING)),
            "status": "待复训",
            "record_no": record_no,
            "qualification_id": qualification_id,
            "personnel_id": qualification["personnel_id"],
            "personnel_name": qualification["personnel_name"],
            "team": qualification["team"],
            "course_name": course_name,
            "last_training_date": last_training_date,
            "due_date": due_date,
            "completed_date": None,
            "result": None,
            "trainer": str(values.get("trainer") or ""),
            "remark": str(values.get("remark") or ""),
            "created_by": actor.user_id,
        }
        store.rows(RETRAINING).append(entry)
        return entry

    def update_retraining(self, actor: Actor, entry_id: int, values: dict[str, Any]) -> dict[str, Any]:
        entry = self._find(RETRAINING, entry_id, "复训记录")
        self._require_same_team(actor, str(entry["team"]), "复训记录归属班组")
        self._apply_updates(entry, values, RETRAINING_UPDATABLE)
        if "due_date" in values:
            _parse_date(entry["due_date"], "复训到期日")
        if "last_training_date" in values:
            _parse_date(entry["last_training_date"], "上次培训日期")
        return entry

    def complete_retraining(self, actor: Actor, entry_id: int, values: dict[str, Any]) -> dict[str, Any]:
        entry = self._find(RETRAINING, entry_id, "复训记录")
        self._require_same_team(actor, str(entry["team"]), "复训记录归属班组")
        completed_date = _parse_date(values.get("completed_date") or _today().isoformat(), "完成日期")
        result = str(values.get("result") or "合格").strip() or "合格"
        entry["status"] = "已完成"
        entry["completed_date"] = completed_date
        entry["result"] = result
        return entry

    def _apply_updates(self, entry: dict[str, Any], values: dict[str, Any], allowed: set[str]) -> None:
        unknown = sorted(key for key in values if key not in allowed)
        if unknown:
            raise TrainingRequestError(f"字段不允许修改：{'、'.join(unknown)}")
        for key in allowed.intersection(values):
            entry[key] = values[key]

    def list_reminders(
        self,
        actor: Actor,
        *,
        team: str | None = None,
        keyword: str | None = None,
        days: int = REMINDER_DAYS,
        page: int = 1,
        size: int = 200,
    ) -> tuple[list[dict[str, Any]], int]:
        # 台账允许跨班组只读；工作台方法会先把班组范围限定为当前班组后再调用这里。
        target_team = (team or "").strip()
        today = _today()
        deadline = today + timedelta(days=days)
        qualification_by_id = {int(row["id"]): row for row in store.rows(QUALIFICATIONS)}
        reminders: list[dict[str, Any]] = []
        for record in store.rows(RETRAINING):
            qualification = qualification_by_id.get(int(record["qualification_id"]))
            if qualification is None or not qualification.get("active", True):
                continue
            if target_team and record.get("team") != target_team:
                continue
            if record.get("status") == "已完成" or record.get("completed_date"):
                continue
            due_date = date.fromisoformat(str(record["due_date"]))
            if due_date > deadline:
                continue
            qualification_status = self._qualification_status(qualification, today)
            reminders.append(
                {
                    "id": record["id"],
                    "record_no": record["record_no"],
                    "team": record["team"],
                    "personnel_id": record["personnel_id"],
                    "personnel_name": record["personnel_name"],
                    "course_name": record["course_name"],
                    "due_date": record["due_date"],
                    "days_remaining": (due_date - today).days,
                    "qualification_status": qualification_status,
                    "todo_type": "复训到期提醒",
                    "blocked_item": "复训到期日",
                }
            )
        reminders.sort(key=lambda item: (item["days_remaining"], item["team"], item["personnel_id"]))
        if keyword:
            key = keyword.strip()
            reminders = [
                item
                for item in reminders
                if key in str(item["record_no"])
                or key in str(item["personnel_id"])
                or key in str(item["personnel_name"])
                or key in str(item["course_name"])
            ]
        page_rows, total = _paginate(reminders, page, size)
        return page_rows, total

    def _workbench_team(self, actor: Actor, team: str | None) -> str:
        target_team = (team or "").strip()
        if actor.is_manager:
            return target_team
        if target_team and target_team != actor.team:
            raise TrainingPermissionError(
                f"跨班组读取工作台已拦下：当前账号归属「{actor.team}」，请求班组为「{target_team}」",
                blocked_item="工作台归属班组",
            )
        return actor.team

    def workbench(self, actor: Actor, team: str | None = None) -> dict[str, Any]:
        target_team = self._workbench_team(actor, team)
        items, total = self.list_reminders(actor, team=target_team, size=10000)
        overdue = sum(1 for item in items if item["days_remaining"] < 0)
        due_soon = total - overdue
        return {
            "team": target_team or "全部班组",
            "total": total,
            "overdue": overdue,
            "due_soon": due_soon,
            "items": items,
            "source": "training_ledger:training_retraining",
        }

    def list_assignments(
        self,
        actor: Actor,
        *,
        team: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(ASSIGNMENTS)
        target_team = (team or "").strip()
        if target_team:
            rows = [row for row in rows if row.get("team") == target_team]
        elif not actor.is_manager:
            rows = [row for row in rows if row.get("team") == actor.team]
        return _paginate(rows, page, size)

    def create_assignment(
        self,
        actor: Actor,
        *,
        team: str,
        assignment_no: str,
        work_name: str,
        scheduled_date: str,
        worker_ids: list[str],
    ) -> dict[str, Any]:
        target_team = team.strip()
        if not target_team:
            raise TrainingRequestError("缺少必填字段：【作业班组】")
        if not actor.is_manager:
            self._require_same_team(actor, target_team, "作业班组")
        if not assignment_no.strip():
            raise TrainingRequestError("缺少必填字段：【养护作业单号】")
        if not work_name.strip():
            raise TrainingRequestError("缺少必填字段：【作业名称】")
        scheduled_day = _parse_date(scheduled_date, "计划作业日期")
        if not worker_ids:
            raise TrainingRequestError("缺少必填字段：【作业人员】")
        blockers: list[dict[str, str]] = []
        worker_names: list[str] = []
        seen: set[str] = set()
        for worker_id in worker_ids:
            worker_id = str(worker_id).strip()
            if not worker_id or worker_id in seen:
                continue
            seen.add(worker_id)
            status, worker, blocked_item = self._worker_assignment_status(worker_id, target_team)
            if worker:
                worker_names.append(str(worker.get("personnel_name")))
            if not status["allowed"]:
                blockers.append(
                    {
                        "personnel_id": worker_id,
                        "personnel_name": str(worker.get("personnel_name")) if worker else "未建档人员",
                        "blocked_item": blocked_item,
                        "reason": status["reason"],
                    }
                )
        if blockers:
            raise TrainingConflictError("养护作业排单被拒绝：以下人员未通过资质校验", blockers)
        entry = {
            "id": _next_id(store.rows(ASSIGNMENTS)),
            "status": "待作业",
            "pending": True,
            "abnormal": False,
            "assignment_no": assignment_no.strip(),
            "team": target_team,
            "work_name": work_name.strip(),
            "scheduled_date": scheduled_day,
            "worker_ids": sorted(seen),
            "worker_names": worker_names,
            "created_by": actor.user_id,
            "created_at": _today().isoformat(),
        }
        store.rows(ASSIGNMENTS).append(entry)
        return entry

    def _worker_assignment_status(
        self, worker_id: str, target_team: str
    ) -> tuple[dict[str, Any], dict[str, Any] | None, str]:
        rows = [row for row in store.rows(QUALIFICATIONS) if row.get("personnel_id") == worker_id]
        if not rows:
            return {"allowed": False, "reason": "人员未在资质培训台账建档，不得排入养护作业"}, None, "人员资质建档"
        team_rows = [row for row in rows if row.get("team") == target_team]
        if not team_rows:
            row = rows[0]
            return (
                {
                    "allowed": False,
                    "reason": f"人员归属「{row.get('team')}」，不属于本次作业班组「{target_team}」",
                },
                row,
                "人员归属班组",
            )
        today = _today()
        eligible: list[dict[str, Any]] = []
        latest_reason = ""
        latest_item = ""
        for row in team_rows:
            item = self._with_status(row, today)
            status = str(item["status"])
            if not row.get("active", True):
                latest_reason = "人员已离岗，仅保留历史记录，不得排入养护作业"
                latest_item = "人员在岗状态"
            elif row.get("suspended"):
                latest_reason = f"资质已暂停：{row.get('suspend_reason') or '未说明暂停原因'}"
                latest_item = "资质暂停状态"
            elif status == "已过期":
                latest_reason = f"资质有效期至 {row['certificate_expiry']}，已过期"
                latest_item = "资质有效期"
            else:
                eligible.append(item)
        if eligible:
            return {"allowed": True, "reason": "资质有效"}, eligible[0], ""
        return {"allowed": False, "reason": latest_reason}, team_rows[0], latest_item
