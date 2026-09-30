"""养护人员资质培训台账业务规则。

权限模型：
- 培训管理员：只能改动本班组归属的培训计划与复训记录；跨班组提交按业务卡控拦下，
  并在「卡控项」里逐项说明卡在哪；
- 作业人员：只读，任何改动都按越权直接拒绝（403）；
- 管理岗位：可查看全部班组、可核对全部班组的台账，但不能改动培训与复训内容。

资质卡控：资质过期或被暂停（或已离岗）的人员不允许排进养护作业。

复训提醒：由台账唯一口径计算（到期/逾期/临期 30 天内），同步进 training_reminders
表；班组工作台待办直接数这张表，台账页的「待复训」也数这张表，两边条数天然一致。
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from fastapi import HTTPException

from app.store import store
from app.training_seed import TODAY

T_OPERATORS = "training_operators"
T_STAFF = "training_staff"
T_ENTRIES = "training_entries"
T_REMINDERS = "training_reminders"
T_ASSIGNMENTS = "training_assignments"

ROLE_ADMIN_CREW = "培训管理员"
ROLE_WORKER = "作业人员"
ROLE_MANAGER = "管理岗位"

RETRAIN_WARN_DAYS = 30

PLAN_REQUIRED = ["人员id", "所属班组", "资质名称", "初训日期", "初训有效期至", "计划复训日"]
RETRAIN_REQUIRED = ["复训日期", "培训内容", "学时", "考核结果", "下次复训日", "复训有效期至"]
ASSIGN_REQUIRED = ["作业名称", "作业日期", "人员ids"]


def _parse_day(value: Any, field: str) -> date:
    try:
        return date.fromisoformat(str(value).strip())
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(
            status_code=422,
            detail={
                "message": "日期格式不正确，提交未生效",
                "卡控项": [{"项": field, "提交值": value, "原因": "日期需为 YYYY-MM-DD 格式"}],
            },
        )


def _block(message: str, items: list[dict[str, Any]]) -> HTTPException:
    """业务卡控（含跨班组、字段缺失、资质不符）：422 并逐项说明卡点。"""
    return HTTPException(status_code=422, detail={"message": message, "卡控项": items})


def _deny(message: str, items: list[dict[str, Any]] | None = None) -> HTTPException:
    """越权提交：直接拒绝，不落任何数据。"""
    return HTTPException(status_code=403, detail={"message": message, "卡控项": items or []})


class TrainingService:
    def __init__(self) -> None:
        self.today = date.fromisoformat(TODAY)
        self.sync_reminders()

    # ---------- 身份与权限 ----------

    def resolve_operator(self, operator_id: int | None) -> dict[str, Any]:
        if operator_id is None:
            raise _deny("未识别到操作人员身份（缺少 X-Operator-Id），提交已拒绝")
        operator = store.find(T_OPERATORS, int(operator_id))
        if operator is None:
            raise _deny(f"操作人员 {operator_id} 不存在，提交已拒绝")
        return operator

    def list_operators(self) -> list[dict[str, Any]]:
        return [dict(row) for row in store.rows(T_OPERATORS)]

    def require_role(self, operator: dict[str, Any], roles: list[str], action: str) -> None:
        if operator["角色"] not in roles:
            raise _deny(
                f"越权提交已拒绝：{action}仅由{'、'.join(roles)}执行，"
                f"当前身份「{operator['姓名']}（{operator['角色']}）」无权操作"
            )

    def require_crew(self, operator: dict[str, Any], crew: str, field: str, value: Any) -> None:
        """培训管理员的班组归属校验：跨班组在这里被拦下并指出卡在哪一项。"""
        if operator["角色"] == ROLE_ADMIN_CREW and operator["所属班组"] != crew:
            raise _block(
                "跨班组提交被拦下：只能维护本班组归属的资质培训记录",
                [{
                    "项": field,
                    "提交值": value,
                    "原因": (
                        f"当前培训管理员归属「{operator['所属班组']}」，"
                        f"该记录归属「{crew}」，班组不一致"
                    ),
                }],
            )

    # ---------- 基础查询 ----------

    def list_staff(self, crew: str | None = None) -> list[dict[str, Any]]:
        rows = store.rows(T_STAFF)
        if crew:
            rows = [row for row in rows if row["所属班组"] == crew]
        return [dict(row) for row in rows]

    def find_staff(self, staff_id: int) -> dict[str, Any] | None:
        return store.find(T_STAFF, staff_id)

    def qualification_view(self, entry: dict[str, Any]) -> dict[str, Any]:
        """台账行视图：资质状态按今天实时判定，待复训标记与提醒表同口径。"""
        view = dict(entry)
        valid_to = _parse_day(entry["初训有效期至"], "初训有效期至")
        if entry.get("暂停"):
            view["资质状态"] = "暂停"
        elif valid_to < self.today:
            view["资质状态"] = "已过期"
        else:
            view["资质状态"] = "有效"
        open_reminder = next(
            (r for r in store.rows(T_REMINDERS)
             if r["台账id"] == entry["id"] and r["状态"] == "待处理"),
            None,
        )
        view["待复训"] = open_reminder is not None
        view["提醒级别"] = open_reminder["提醒级别"] if open_reminder else None
        view["到期天数"] = open_reminder["到期天数"] if open_reminder else None
        staff = store.find(T_STAFF, int(entry["人员id"]))
        view["在岗状态"] = staff["在岗状态"] if staff else "人员缺失"
        return view

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        crew: str | None = None,
        qualification: str | None = None,
        only_due: bool = False,
        include_left: bool = True,
    ) -> list[dict[str, Any]]:
        rows = store.rows(T_ENTRIES)
        if crew:
            rows = [row for row in rows if row["所属班组"] == crew]
        if keyword:
            rows = [
                row for row in rows
                if keyword in str(row["人员姓名"])
                or keyword in str(row["资质名称"])
                or keyword in str(row["证书编号"])
            ]
        views = [self.qualification_view(row) for row in rows]
        if qualification:
            views = [row for row in views if row["资质状态"] == qualification]
        if only_due:
            views = [row for row in views if row["待复训"]]
        if not include_left:
            views = [row for row in views if row["在岗状态"] != "已离岗"]
        return views

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(T_ENTRIES, entry_id)
        return self.qualification_view(entry) if entry else None

    def stats(self, crew: str | None = None) -> dict[str, int]:
        views = self.list_entries(crew=crew)
        staff = self.list_staff(crew)
        return {
            "台账总数": len(views),
            "资质有效": sum(1 for row in views if row["资质状态"] == "有效"),
            "资质过期": sum(1 for row in views if row["资质状态"] == "已过期"),
            "资质暂停": sum(1 for row in views if row["资质状态"] == "暂停"),
            "待复训": sum(1 for row in views if row["待复训"]),
            "离岗人员历史": sum(1 for row in staff if row["在岗状态"] == "已离岗"),
        }

    # ---------- 培训计划 ----------

    def create_plan(self, values: dict[str, Any], operator: dict[str, Any]) -> dict[str, Any]:
        # 第一层：角色。作业人员/管理岗位动台账一律按越权直接拒绝。
        self.require_role(operator, [ROLE_ADMIN_CREW], "培训计划登记")

        missing = [field for field in PLAN_REQUIRED if not str(values.get(field) or "").strip()]
        if missing:
            raise _block(
                "培训计划登记被拦下：存在未填写的必填项",
                [{"项": field, "提交值": values.get(field), "原因": "必填项缺失"} for field in missing],
            )

        crew = str(values["所属班组"]).strip()
        # 第二层：班组归属。跨班组提交在这里被拦下，并指明卡在「所属班组」。
        self.require_crew(operator, crew, "所属班组", crew)

        staff_id = int(values["人员id"])
        staff = self.find_staff(staff_id)
        blocks: list[dict[str, Any]] = []
        if staff is None:
            blocks.append({"项": "人员id", "提交值": staff_id, "原因": "作业人员档案不存在，无法按人登记"})
        elif staff["所属班组"] != crew:
            blocks.append({
                "项": "人员id",
                "提交值": staff_id,
                "原因": f"该人员归属「{staff['所属班组']}」，与提交班组「{crew}」不一致",
            })
        elif staff["在岗状态"] == "已离岗":
            blocks.append({"项": "人员id", "提交值": staff_id, "原因": "人员已离岗，不再登记新的培训计划（历史记录保留）"})

        train_date = _parse_day(values["初训日期"], "初训日期")
        valid_to = _parse_day(values["初训有效期至"], "初训有效期至")
        plan_day = _parse_day(values["计划复训日"], "计划复训日")
        if valid_to < train_date:
            blocks.append({"项": "初训有效期至", "提交值": values["初训有效期至"], "原因": "有效期不能早于初训日期"})
        if plan_day < train_date:
            blocks.append({"项": "计划复训日", "提交值": values["计划复训日"], "原因": "计划复训日不能早于初训日期"})
        if blocks:
            raise _block("培训计划登记被拦下，请按卡控项修正后重新提交", blocks)

        assert staff is not None
        entry = {
            "id": store.next_id(T_ENTRIES),
            "人员id": staff_id,
            "人员姓名": staff["姓名"],
            "所属班组": crew,
            "资质名称": str(values["资质名称"]).strip(),
            "证书编号": str(values.get("证书编号") or "").strip(),
            "初训日期": values["初训日期"],
            "初训有效期至": values["初训有效期至"],
            "计划复训日": values["计划复训日"],
            "下次复训日": values["计划复训日"],
            "暂停": False,
            "暂停原因": None,
            "核对状态": "未核对",
            "核对人": None,
            "登记人": operator["姓名"],
            "历史复训": [],
        }
        store.rows(T_ENTRIES).append(entry)
        self.sync_reminders()
        return self.qualification_view(entry)

    # ---------- 复训记录 ----------

    def add_retrain(self, entry_id: int, values: dict[str, Any], operator: dict[str, Any]) -> dict[str, Any]:
        self.require_role(operator, [ROLE_ADMIN_CREW], "复训记录登记")
        entry = store.find(T_ENTRIES, entry_id)
        if entry is None:
            raise _block(f"台账 {entry_id} 不存在", [{"项": "台账id", "提交值": entry_id, "原因": "记录不存在或已删除"}])
        # 改的是已存在的记录：按记录归属班组卡控，跨班组管理员在这里被拦。
        self.require_crew(operator, entry["所属班组"], "记录所属班组", entry["所属班组"])

        missing = [field for field in RETRAIN_REQUIRED if not str(values.get(field) or "").strip()]
        if missing:
            raise _block(
                "复训记录登记被拦下：存在未填写的必填项",
                [{"项": field, "提交值": values.get(field), "原因": "必填项缺失"} for field in missing],
            )

        blocks: list[dict[str, Any]] = []
        retrain_day = _parse_day(values["复训日期"], "复训日期")
        next_day = _parse_day(values["下次复训日"], "下次复训日")
        valid_to = _parse_day(values["复训有效期至"], "复训有效期至")
        try:
            hours = float(values["学时"])
            if hours <= 0:
                raise ValueError
        except (ValueError, TypeError):
            blocks.append({"项": "学时", "提交值": values["学时"], "原因": "学时需为大于 0 的数字"})
        result = str(values["考核结果"]).strip()
        if result not in ("合格", "不合格"):
            blocks.append({"项": "考核结果", "提交值": result, "原因": "只接受「合格 / 不合格」"})
        if next_day <= retrain_day:
            blocks.append({"项": "下次复训日", "提交值": values["下次复训日"], "原因": "下次复训日必须晚于本次复训日期"})
        if valid_to <= retrain_day:
            blocks.append({"项": "复训有效期至", "提交值": values["复训有效期至"], "原因": "复训有效期必须晚于本次复训日期"})
        if blocks:
            raise _block("复训记录登记被拦下，请按卡控项修正后重新提交", blocks)

        record = {
            "复训日期": values["复训日期"],
            "培训内容": str(values["培训内容"]).strip(),
            "学时": hours,
            "考核结果": result,
            "复训有效期至": values["复训有效期至"],
            "下次复训日": values["下次复训日"],
            "登记人": operator["姓名"],
        }
        entry.setdefault("历史复训", []).append(record)
        entry["下次复训日"] = values["下次复训日"]
        if result == "合格":
            # 合格复训续期：解除过期/暂停口径，资质恢复为有效。
            entry["初训有效期至"] = values["复训有效期至"]
            entry["暂停"] = False
            entry["暂停原因"] = None
        # 内容发生变化，需要管理岗位重新核对。
        entry["核对状态"] = "未核对"
        entry["核对人"] = None
        self.sync_reminders()
        view = self.qualification_view(entry)
        if result != "合格":
            view["提示"] = "复训考核不合格，记录已留存；该资质在考核合格前仍不允许排进养护作业"
        return view

    # ---------- 暂停 / 恢复 / 离岗 ----------

    def _find_entry_for_crew_admin(self, entry_id: int, operator: dict[str, Any], action: str) -> dict[str, Any]:
        self.require_role(operator, [ROLE_ADMIN_CREW], action)
        entry = store.find(T_ENTRIES, entry_id)
        if entry is None:
            raise _block(f"台账 {entry_id} 不存在", [{"项": "台账id", "提交值": entry_id, "原因": "记录不存在"}])
        self.require_crew(operator, entry["所属班组"], "记录所属班组", entry["所属班组"])
        return entry

    def suspend(self, entry_id: int, reason: str, operator: dict[str, Any]) -> dict[str, Any]:
        entry = self._find_entry_for_crew_admin(entry_id, operator, "资质暂停")
        if not reason.strip():
            raise _block("资质暂停被拦下", [{"项": "暂停原因", "提交值": reason, "原因": "暂停资质必须填写原因"}])
        entry["暂停"] = True
        entry["暂停原因"] = reason.strip()
        entry["核对状态"] = "未核对"
        self.sync_reminders()
        return self.qualification_view(entry)

    def resume(self, entry_id: int, operator: dict[str, Any]) -> dict[str, Any]:
        entry = self._find_entry_for_crew_admin(entry_id, operator, "资质恢复")
        view = self.qualification_view(entry)
        if view["资质状态"] == "已过期":
            raise _block(
                "资质恢复被拦下：过期资质不能直接恢复",
                [{"项": "初训有效期至", "提交值": entry["初训有效期至"], "原因": "资质已过期，需先登记合格复训续期后才能恢复排班"}],
            )
        entry["暂停"] = False
        entry["暂停原因"] = None
        entry["核对状态"] = "未核对"
        self.sync_reminders()
        return self.qualification_view(entry)

    def leave_staff(self, staff_id: int, operator: dict[str, Any], leave_day: str | None) -> dict[str, Any]:
        self.require_role(operator, [ROLE_ADMIN_CREW], "人员离岗登记")
        staff = self.find_staff(staff_id)
        if staff is None:
            raise _block("人员离岗登记被拦下", [{"项": "人员id", "提交值": staff_id, "原因": "作业人员档案不存在"}])
        self.require_crew(operator, staff["所属班组"], "人员所属班组", staff["所属班组"])
        if staff["在岗状态"] == "已离岗":
            raise _block(
                "人员离岗登记被拦下",
                [{"项": "在岗状态", "提交值": "已离岗", "原因": f"{staff['姓名']}已于 {staff['离岗日期']} 离岗，历史培训记录继续保留"}],
            )
        day = leave_day.strip() if leave_day else TODAY
        _parse_day(day, "离岗日期")
        staff["在岗状态"] = "已离岗"
        staff["离岗日期"] = day
        # 离岗不删台账、不删复训历史，只把该人的到期待办关闭留痕。
        self.sync_reminders()
        return dict(staff)

    # ---------- 管理岗位核对 ----------

    def verify_entry(self, entry_id: int, operator: dict[str, Any]) -> dict[str, Any]:
        self.require_role(operator, [ROLE_MANAGER], "台账核对")
        entry = store.find(T_ENTRIES, entry_id)
        if entry is None:
            raise _block(f"台账 {entry_id} 不存在", [{"项": "台账id", "提交值": entry_id, "原因": "记录不存在"}])
        entry["核对状态"] = "已核对"
        entry["核对人"] = operator["姓名"]
        return self.qualification_view(entry)

    # ---------- 排班资质卡控 ----------

    def check_assignment(self, person_ids: list[int]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """返回（可排班人员及资质, 卡控项）。任一人员不合格，调用方应整体拒绝。"""
        passed: list[dict[str, Any]] = []
        blocked: list[dict[str, Any]] = []
        for staff_id in person_ids:
            staff = self.find_staff(staff_id)
            if staff is None:
                blocked.append({"项": "人员id", "提交值": staff_id, "原因": "作业人员档案不存在"})
                continue
            if staff["在岗状态"] == "已离岗":
                blocked.append({
                    "项": "人员资质",
                    "提交值": f"{staff['姓名']}（{staff['所属班组']}）",
                    "原因": f"该人员已于 {staff['离岗日期']} 离岗，不能排进养护作业",
                })
                continue
            entries = [row for row in store.rows(T_ENTRIES) if int(row["人员id"]) == staff_id]
            if not entries:
                blocked.append({
                    "项": "人员资质",
                    "提交值": staff["姓名"],
                    "原因": "培训台账中没有该人员的资质登记，无资质不得排班",
                })
                continue
            # 取该人员最近一份资质做判定；存在任一暂停/过期且没有有效资质即拦截。
            views = [self.qualification_view(row) for row in entries]
            valid = [view for view in views if view["资质状态"] == "有效"]
            if not valid:
                view = views[0]
                reason = {
                    "暂停": f"资质「{view['资质名称']}」已被暂停（{view.get('暂停原因') or '见台账'}），暂停期间不得排班",
                    "已过期": f"资质「{view['资质名称']}」已于 {view['初训有效期至']} 过期，未完成合格复训前不得排班",
                }[view["资质状态"]]
                blocked.append({"项": "人员资质", "提交值": staff["姓名"], "原因": reason})
                continue
            best = valid[0]
            item = {
                "人员id": staff["id"],
                "姓名": staff["姓名"],
                "所属班组": staff["所属班组"],
                "资质名称": best["资质名称"],
                "证书编号": best["证书编号"],
                "有效期至": best["初训有效期至"],
            }
            if best["待复训"]:
                item["提醒"] = f"该资质{best['提醒级别']}（下次复训日 {best['下次复训日']}），本次可排班，请尽快安排复训"
            passed.append(item)
        return passed, blocked

    def create_assignment(self, values: dict[str, Any], operator: dict[str, Any]) -> dict[str, Any]:
        # 排班属于调度动作：作业人员无调度权；培训管理员与管理岗位可提交，资质按人逐项卡控。
        self.require_role(operator, [ROLE_ADMIN_CREW, ROLE_MANAGER], "养护作业排班")
        missing = [field for field in ASSIGN_REQUIRED if not str(values.get(field) or "").strip()
                   and not (field == "人员ids" and isinstance(values.get(field), list))]
        if missing:
            raise _block(
                "排班提交被拦下：存在未填写的必填项",
                [{"项": field, "提交值": values.get(field), "原因": "必填项缺失"} for field in missing],
            )
        raw_ids = values["人员ids"]
        if not isinstance(raw_ids, list) or not raw_ids:
            raise _block("排班提交被拦下", [{"项": "人员ids", "提交值": raw_ids, "原因": "至少选择一名作业人员"}])
        try:
            person_ids = [int(pid) for pid in raw_ids]
        except (ValueError, TypeError):
            raise _block("排班提交被拦下", [{"项": "人员ids", "提交值": raw_ids, "原因": "人员id必须为数字"}])
        if len(set(person_ids)) != len(person_ids):
            raise _block("排班提交被拦下", [{"项": "人员ids", "提交值": raw_ids, "原因": "同一人员在本次排班中重复出现"}])

        work_day = _parse_day(values["作业日期"], "作业日期")
        if work_day < self.today:
            raise _block(
                "排班提交被拦下",
                [{"项": "作业日期", "提交值": values["作业日期"], "原因": "作业日期不能早于今天"}],
            )

        passed, blocked = self.check_assignment(person_ids)
        if blocked:
            raise _block(
                "排班提交被拦下：以下人员资质不符合要求，已整体拒绝本次排班（未生成作业单）",
                blocked,
            )

        assignment = {
            "id": store.next_id(T_ASSIGNMENTS),
            "作业名称": str(values["作业名称"]).strip(),
            "作业日期": values["作业日期"],
            "班组": "、".join(sorted({item["所属班组"] for item in passed})),
            "人员": passed,
            "排单人": operator["姓名"],
            "状态": "已排班",
        }
        store.rows(T_ASSIGNMENTS).append(assignment)
        return assignment

    def list_assignments(self) -> list[dict[str, Any]]:
        return [dict(row) for row in store.rows(T_ASSIGNMENTS)]

    # ---------- 复训到期提醒（台账与工作台唯一口径） ----------

    def _desired_reminders(self) -> dict[int, dict[str, Any]]:
        """按当前台账计算应处于待处理状态的提醒：在岗、未暂停、下次复训日逾期或 30 天内。"""
        desired: dict[int, dict[str, Any]] = {}
        for entry in store.rows(T_ENTRIES):
            staff = store.find(T_STAFF, int(entry["人员id"]))
            if staff is None or staff["在岗状态"] == "已离岗" or entry.get("暂停"):
                continue
            due = _parse_day(entry["下次复训日"], "下次复训日")
            days_left = (due - self.today).days
            if days_left > RETRAIN_WARN_DAYS:
                continue
            desired[int(entry["id"])] = {
                "台账id": int(entry["id"]),
                "人员id": int(entry["人员id"]),
                "人员姓名": entry["人员姓名"],
                "所属班组": entry["所属班组"],
                "资质名称": entry["资质名称"],
                "下次复训日": entry["下次复训日"],
                "到期天数": days_left,
                "提醒级别": "已逾期" if days_left < 0 else "临期",
            }
        return desired

    def sync_reminders(self) -> None:
        """以台账为准对齐提醒表：新到期的开提醒，解除/离岗/复训后的关提醒（记录保留）。"""
        rows = store.rows(T_REMINDERS)
        by_entry = {int(row["台账id"]): row for row in rows}
        desired = self._desired_reminders()

        for entry_id, item in desired.items():
            existing = by_entry.get(entry_id)
            if existing is None:
                rows.append({
                    "id": store.next_id(T_REMINDERS),
                    **item,
                    "状态": "待处理",
                    "关闭原因": None,
                    "处理人": None,
                    "处理时间": None,
                })
            else:
                existing.update(item)
                existing["状态"] = "待处理"
                existing["关闭原因"] = None
                existing["处理人"] = None
                existing["处理时间"] = None

        for entry_id, existing in by_entry.items():
            if entry_id in desired or existing["状态"] != "待处理":
                continue
            entry = store.find(T_ENTRIES, entry_id)
            staff = store.find(T_STAFF, int(existing["人员id"]))
            if staff is not None and staff["在岗状态"] == "已离岗":
                reason = f"人员于 {staff['离岗日期']} 离岗，待办关闭，历史记录保留"
            elif entry is not None and entry.get("暂停"):
                reason = "资质被暂停，待办关闭（恢复或复训合格后再评估）"
            else:
                reason = "已登记合格复训，到期提醒关闭"
            existing["状态"] = "已关闭"
            existing["关闭原因"] = reason
            existing["处理时间"] = TODAY

    def open_reminders(self, crew: str | None = None) -> list[dict[str, Any]]:
        rows = [dict(row) for row in store.rows(T_REMINDERS) if row["状态"] == "待处理"]
        if crew:
            rows = [row for row in rows if row["所属班组"] == crew]
        rows.sort(key=lambda row: row["到期天数"])
        return rows

    def workbench(self, operator: dict[str, Any], crew: str | None = None) -> dict[str, Any]:
        """班组工作台：待办直接取培训提醒表；台账侧用同一函数计数，条数必然一致。"""
        if operator["角色"] in (ROLE_ADMIN_CREW, ROLE_WORKER):
            # 班组身份固定，看不了别的班组待办。
            crew = operator["所属班组"]
        todos = self.open_reminders(crew)
        ledger_due = len(self.list_entries(crew=crew, only_due=True))
        return {
            "班组": crew or "全部班组",
            "待办": todos,
            "待办条数": len(todos),
            "台账待复训条数": ledger_due,
            "条数一致": len(todos) == ledger_due,
            "统计": self.stats(crew),
        }
