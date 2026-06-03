#!/usr/bin/env python3
"""Schedule analysis for Primavera P6 .xer files.

Parses a schedule and computes the facts the AI layer narrates: progress,
float health, status mix, discipline breakdown and DCMA-style logic issues.
The output is a plain dict of verified facts, kept deliberately separate from
language generation so the narrative is grounded in real numbers.
"""

from __future__ import annotations
from datetime import datetime


STATUS_MAP = {"TK_NotStart": "Not Started", "TK_Active": "In Progress",
              "TK_Complete": "Completed"}
HARD_CONSTRAINTS = {"CS_MSO", "CS_MEO", "CS_MANDSTART", "CS_MANDFIN"}


def _to_float(v, default=0.0):
    try:
        return float(v)
    except (ValueError, TypeError):
        return default


def parse_xer(path):
    tables, current, fields = {}, None, None
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.rstrip("\r\n")
            if not line:
                continue
            parts = line.split("\t")
            tag = parts[0]
            if tag == "%T":
                current, fields = parts[1], None
                tables[current] = []
            elif tag == "%F":
                fields = parts[1:]
            elif tag == "%R" and current and fields:
                vals = parts[1:] + [""] * (len(fields) - len(parts[1:]))
                tables[current].append(dict(zip(fields, vals[:len(fields)])))
            elif tag == "%E":
                break
    return tables


def analyze(path):
    t = parse_xer(path)
    tasks = t.get("TASK", [])
    preds = t.get("TASKPRED", [])
    proj = t.get("PROJECT", [{}])
    proj_name = proj[0].get("proj_short_name", "P6 Project") if proj else "P6 Project"

    wbs = {w["wbs_id"]: w.get("wbs_name", "") for w in t.get("PROJWBS", [])}

    acts = []
    for r in tasks:
        status = STATUS_MAP.get(r.get("status_code", ""), "Unknown")
        pct = {"Completed": 100.0, "In Progress": 50.0,
               "Not Started": 0.0}.get(status, 0.0)
        acts.append({
            "code": r.get("task_code", ""),
            "name": r.get("task_name", ""),
            "discipline": wbs.get(r.get("wbs_id"), "General"),
            "duration_days": _to_float(r.get("target_drtn_hr_cnt")) / 8,
            "total_float_days": _to_float(r.get("total_float_hr_cnt")) / 8,
            "percent": pct,
            "status": status,
            "constraint": r.get("cstr_type", ""),
            "task_id": r.get("task_id", ""),
        })

    n = len(acts) or 1

    # progress
    avg_pct = sum(a["percent"] for a in acts) / n
    completed = sum(1 for a in acts if a["status"] == "Completed")
    in_progress = sum(1 for a in acts if a["status"] == "In Progress")
    not_started = sum(1 for a in acts if a["status"] == "Not Started")

    # float health
    neg_float = [a for a in acts if a["total_float_days"] < 0]
    high_float = [a for a in acts if a["total_float_days"] > 44]
    critical = sorted(acts, key=lambda a: a["total_float_days"])[:5]

    # logic checks
    has_pred = {p.get("task_id") for p in preds}
    has_succ = {p.get("pred_task_id") for p in preds}
    open_ends = [a for a in acts
                 if a["task_id"] not in has_pred or a["task_id"] not in has_succ]
    leads = [p for p in preds if _to_float(p.get("lag_hr_cnt")) < 0]
    hard = [a for a in acts if a["constraint"] in HARD_CONSTRAINTS]
    long_acts = [a for a in acts if a["duration_days"] > 44]

    # discipline rollup
    disc = {}
    for a in acts:
        d = disc.setdefault(a["discipline"], {"count": 0, "pct_sum": 0.0,
                                              "behind": 0})
        d["count"] += 1
        d["pct_sum"] += a["percent"]
        if a["total_float_days"] < 0:
            d["behind"] += 1
    disciplines = [{
        "name": k, "count": v["count"],
        "avg_percent": v["pct_sum"] / v["count"],
        "behind": v["behind"],
    } for k, v in disc.items()]
    disciplines.sort(key=lambda d: d["avg_percent"])

    # simple schedule health score (0-100)
    penalties = (
        len(neg_float) * 3 + len(open_ends) * 1.5 +
        len(hard) * 1 + len(high_float) * 1
    )
    health = max(0, round(100 - penalties))

    verdict = ("On Track" if health >= 80 else
               "At Risk" if health >= 55 else "Critical")

    return {
        "project_name": proj_name,
        "activity_count": len(acts),
        "relationship_count": len(preds),
        "avg_percent_complete": round(avg_pct, 1),
        "completed": completed,
        "in_progress": in_progress,
        "not_started": not_started,
        "health_score": health,
        "verdict": verdict,
        "negative_float": [_brief(a) for a in neg_float[:8]],
        "negative_float_count": len(neg_float),
        "high_float_count": len(high_float),
        "open_ends_count": len(open_ends),
        "leads_count": len(leads),
        "hard_constraints_count": len(hard),
        "long_activities_count": len(long_acts),
        "critical_activities": [_brief(a) for a in critical],
        "disciplines": disciplines,
        "generated": datetime.now().strftime("%d %b %Y %H:%M"),
    }


def _brief(a):
    return {
        "code": a["code"], "name": a["name"], "discipline": a["discipline"],
        "float": round(a["total_float_days"], 1), "status": a["status"],
    }
