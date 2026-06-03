#!/usr/bin/env python3
"""AI narrative engine for P6 schedule analysis.

Turns the verified facts from analyze.py into a written project-controls
narrative. Two modes:

    mock  - generates the narrative locally from the real metrics (no API key).
            Useful for demos and offline use.
    api   - sends the facts to a language model (Anthropic by default) with a
            controlled prompt and returns the model's narrative.

The prompt deliberately passes only computed facts, not raw schedule rows, so
the model reasons over verified numbers rather than inventing them.
"""

from __future__ import annotations
import json
import os
import textwrap


SYSTEM_PROMPT = (
    "You are a senior planning engineer writing the schedule narrative for a "
    "monthly project controls report on an EPC construction project. Write in a "
    "concise, professional tone. Base every statement only on the facts "
    "provided. Do not invent activity names or numbers. Structure the output as: "
    "(1) a one-line headline verdict, (2) a short status paragraph, (3) key "
    "concerns as bullet points, and (4) clear recommendations."
)


def build_user_prompt(facts: dict) -> str:
    return (
        "Write the schedule narrative from these facts:\n\n"
        + json.dumps(facts, indent=2)
    )


# ---------------------------------------------------------------------------
# API mode
# ---------------------------------------------------------------------------

def narrate_api(facts: dict, model: str = "claude-sonnet-4-20250514") -> str:
    """Generate the narrative with the Anthropic API. Requires ANTHROPIC_API_KEY."""
    import anthropic  # lazy import

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
    resp = client.messages.create(
        model=model,
        max_tokens=900,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_prompt(facts)}],
    )
    return "".join(block.text for block in resp.content if block.type == "text")


# ---------------------------------------------------------------------------
# Mock mode  (rule-based, reads the real numbers)
# ---------------------------------------------------------------------------

def narrate_mock(facts: dict) -> str:
    f = facts
    headline = (
        f"Schedule Health: {f['verdict']} "
        f"(score {f['health_score']}/100, {f['avg_percent_complete']}% complete)."
    )

    # status paragraph
    status = (
        f"The {f['project_name']} programme comprises {f['activity_count']} "
        f"activities and {f['relationship_count']} logic links. "
        f"{f['completed']} activities are complete, {f['in_progress']} in "
        f"progress and {f['not_started']} not yet started, giving an overall "
        f"completion of {f['avg_percent_complete']}%. "
    )
    if f["negative_float_count"]:
        status += (
            f"{f['negative_float_count']} activities currently carry negative "
            f"float, indicating the contractual completion date is at risk "
            f"unless recovery action is taken. "
        )
    else:
        status += ("No activities carry negative float, so the critical path "
                   "currently has no overrun. ")

    # concerns
    concerns = []
    if f["negative_float_count"]:
        worst = f["negative_float"][:3]
        names = ", ".join(f"{a['code']} ({a['float']}d)" for a in worst)
        concerns.append(
            f"Negative float on {f['negative_float_count']} activities — most "
            f"critical: {names}.")
    if f["open_ends_count"]:
        concerns.append(
            f"{f['open_ends_count']} activities have open ends (missing "
            f"predecessor or successor), weakening schedule logic.")
    if f["leads_count"]:
        concerns.append(
            f"{f['leads_count']} relationships use negative lag (leads), which "
            f"distorts the critical path.")
    if f["hard_constraints_count"]:
        concerns.append(
            f"{f['hard_constraints_count']} hard constraints are overriding "
            f"network logic.")
    if f["high_float_count"]:
        concerns.append(
            f"{f['high_float_count']} activities show excessive float (>44d), "
            f"suggesting missing links.")
    if not concerns:
        concerns.append("No major logic or float issues detected.")

    # discipline note
    lagging = [d for d in f["disciplines"] if d["behind"] > 0][:3]
    if lagging:
        dl = ", ".join(f"{d['name']} ({d['behind']} behind)" for d in lagging)
        concerns.append(f"Disciplines with activities behind schedule: {dl}.")

    # recommendations
    recs = []
    if f["negative_float_count"]:
        cp = f["critical_activities"][0] if f["critical_activities"] else None
        if cp:
            recs.append(
                f"Prioritise recovery on the critical path, starting with "
                f"{cp['code']} — {cp['name']} (float {cp['float']}d).")
        recs.append("Hold a recovery workshop to resequence or crash critical "
                    "activities and restore positive float.")
    if f["open_ends_count"]:
        recs.append("Close all open ends by adding the missing predecessor/"
                    "successor links before the next baseline update.")
    if f["leads_count"]:
        recs.append("Replace negative lags with explicit activities or revised "
                    "logic.")
    if f["hard_constraints_count"]:
        recs.append("Review hard constraints and convert to logic-driven dates "
                    "where possible.")
    if not recs:
        recs.append("Maintain current sequencing and continue monitoring the "
                    "critical path in weekly look-aheads.")

    parts = [headline, "", textwrap.fill(status, 100), "", "Key concerns:"]
    parts += [f"  - {c}" for c in concerns]
    parts += ["", "Recommendations:"]
    parts += [f"  - {r}" for r in recs]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate_narrative(facts: dict, mode: str = "mock",
                       model: str = "claude-sonnet-4-20250514") -> str:
    if mode == "api":
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "api mode needs ANTHROPIC_API_KEY in the environment. "
                "Run with --mode mock for an offline narrative.")
        return narrate_api(facts, model=model)
    return narrate_mock(facts)
