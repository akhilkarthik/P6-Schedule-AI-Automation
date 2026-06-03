#!/usr/bin/env python3
"""
generate_sample_xer.py
-----------------------
Generates a realistic Primavera P6 .xer file with intentional schedule
defects so the health checker has something meaningful to flag.

Usage:
    python generate_sample_xer.py [output.xer]
"""

import sys
import random
from datetime import datetime, timedelta

random.seed(11)


def fmt(dt):
    return dt.strftime("%Y-%m-%d %H:%M") if dt else ""


def build_xer():
    proj_start = datetime(2024, 1, 1, 8, 0)

    disciplines = ["Civil", "Structural", "Mechanical", "Piping",
                   "Electrical", "Instrumentation", "Insulation", "Painting"]

    tasks = []
    task_id = 1001
    for d_i, disc in enumerate(disciplines):
        for n in range(1, 9):  # 8 activities per discipline = 64 total
            start = proj_start + timedelta(days=random.randint(0, 300))
            dur = random.randint(3, 60)
            finish = start + timedelta(days=dur)

            # default healthy values
            total_float = random.randint(0, 30)
            constraint_type = ""
            constraint_date = ""
            task_type = "TT_Task"
            status = random.choice(["TK_NotStart", "TK_Active", "TK_Complete"])

            # ---- inject intentional defects ----
            r = random.random()
            if r < 0.08:                      # negative float
                total_float = -random.randint(1, 15)
            elif r < 0.16:                    # high float (>44d)
                total_float = random.randint(45, 120)

            if random.random() < 0.10:        # hard constraint
                constraint_type = random.choice(
                    ["CS_MSO", "CS_MEO"])      # Mandatory Start / Finish On
                constraint_date = fmt(start)
            elif random.random() < 0.12:      # soft constraint
                constraint_type = random.choice(
                    ["CS_MSOA", "CS_MEOB", "CS_ALAP"])
                constraint_date = fmt(start)

            if dur > 44:
                pass  # high-duration defect occurs naturally sometimes

            tasks.append({
                "task_id": task_id,
                "task_code": f"{disc[:3].upper()}-{1000 + n}",
                "task_name": f"{disc} Activity {n:02d}",
                "task_type": task_type,
                "status_code": status,
                "duration": dur,
                "start": start,
                "finish": finish,
                "total_float": total_float,
                "constraint_type": constraint_type,
                "constraint_date": constraint_date,
                "wbs_id": 100 + d_i,
                "rsrc_assigned": random.random() > 0.25,  # 25% have no resource
            })
            task_id += 1

    # ---- relationships ----
    preds = []
    rel_id = 5001
    # chain most tasks; intentionally leave some open ends
    for i in range(1, len(tasks)):
        if random.random() < 0.12:
            continue  # skip link -> creates an open end (missing predecessor)
        pred = tasks[i - 1]
        succ = tasks[i]

        rel_type = "PR_FS"
        if random.random() < 0.12:
            rel_type = random.choice(["PR_SS", "PR_FF", "PR_SF"])  # non-FS

        lag = 0
        rr = random.random()
        if rr < 0.10:
            lag = random.randint(1, 10) * 8   # positive lag (in hours, 8h/day)
        elif rr < 0.16:
            lag = -random.randint(1, 5) * 8   # negative lag (lead) -> defect

        preds.append({
            "rel_id": rel_id,
            "task_id": succ["task_id"],
            "pred_task_id": pred["task_id"],
            "pred_type": rel_type,
            "lag_hr_cnt": lag,
        })
        rel_id += 1

    return tasks, preds


def write_xer(tasks, preds, path):
    lines = []
    today = datetime.now().strftime("%Y-%m-%d")
    lines.append(
        f"ERMHDR\t19.12\t{today}\tProject\tadmin\tAkhil\tHEALTH_DEMO\t"
        f"USD\tDD/MM/YYYY\t1\t0\t0")

    # PROJECT table
    lines.append("%T\tPROJECT")
    lines.append("%F\tproj_id\tproj_short_name\tplan_start_date\tplan_end_date")
    lines.append("%R\t1\tBOROUGE4_DEMO\t2024-01-01 08:00\t2025-12-31 17:00")

    # PROJWBS table
    lines.append("%T\tPROJWBS")
    lines.append("%F\twbs_id\tproj_id\twbs_name")
    wbs_seen = set()
    for t in tasks:
        if t["wbs_id"] not in wbs_seen:
            lines.append(f"%R\t{t['wbs_id']}\t1\t{t['task_name'].split(' Activity')[0]}")
            wbs_seen.add(t["wbs_id"])

    # TASK table
    lines.append("%T\tTASK")
    lines.append("%F\ttask_id\tproj_id\twbs_id\ttask_code\ttask_name\ttask_type\t"
                 "status_code\ttarget_drtn_hr_cnt\ttarget_start_date\t"
                 "target_end_date\ttotal_float_hr_cnt\tcstr_type\tcstr_date")
    for t in tasks:
        dur_hr = t["duration"] * 8
        tf_hr = t["total_float"] * 8
        lines.append(
            f"%R\t{t['task_id']}\t1\t{t['wbs_id']}\t{t['task_code']}\t"
            f"{t['task_name']}\t{t['task_type']}\t{t['status_code']}\t"
            f"{dur_hr}\t{fmt(t['start'])}\t{fmt(t['finish'])}\t{tf_hr}\t"
            f"{t['constraint_type']}\t{t['constraint_date']}")

    # TASKPRED table
    lines.append("%T\tTASKPRED")
    lines.append("%F\ttask_pred_id\ttask_id\tpred_task_id\tpred_type\tlag_hr_cnt")
    for p in preds:
        lines.append(
            f"%R\t{p['rel_id']}\t{p['task_id']}\t{p['pred_task_id']}\t"
            f"{p['pred_type']}\t{p['lag_hr_cnt']}")

    # TASKRSRC table (resource assignments)
    lines.append("%T\tTASKRSRC")
    lines.append("%F\ttaskrsrc_id\ttask_id\trsrc_id")
    rid = 9001
    for t in tasks:
        if t["rsrc_assigned"]:
            lines.append(f"%R\t{rid}\t{t['task_id']}\t1")
            rid += 1

    lines.append("%E")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "sample_schedule.xer"
    tasks, preds = build_xer()
    write_xer(tasks, preds, out)
    print(f"Sample XER written to {out} "
          f"({len(tasks)} activities, {len(preds)} relationships)")
