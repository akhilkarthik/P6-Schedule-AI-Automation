# P6 Schedule AI Automation

Reads a Primavera P6 `.xer` schedule, analyses it, and uses an AI layer to write
the **project-controls narrative a planner would normally write by hand** — then
outputs a professional PDF report.

It separates the analysis from the language generation: the tool computes the
hard facts (progress, float health, logic issues), and the AI layer turns those
verified facts into commentary and recommendations. The model never sees raw
schedule rows, only computed metrics, so it reasons over real numbers instead of
inventing them.

```
.xer schedule
   -> parse + analyse        (progress, float, DCMA-style logic checks)
   -> verified facts (dict)
   -> AI layer writes narrative
   -> PDF report + terminal output
```

## Two modes

| Mode | What it does | Needs |
|------|--------------|-------|
| `mock` (default) | Generates the narrative offline from the metrics | nothing |
| `api` | Calls a language model for the narrative | `ANTHROPIC_API_KEY` |

`mock` mode is fully functional and produces a genuine, data-driven narrative —
useful for demos and offline use. `api` mode swaps in a real model with one flag.

## Quick start

```bash
pip install reportlab            # add 'anthropic' only for api mode

# generate a sample schedule (optional)
python generate_sample_xer.py sample_schedule.xer

# offline narrative
python p6_ai_report.py sample_schedule.xer

# with a real model
export ANTHROPIC_API_KEY=sk-ant-...
python p6_ai_report.py sample_schedule.xer --mode api -o report.pdf
```

## Files

| File | Purpose |
|------|---------|
| `p6_ai_report.py` | Main CLI — parse, analyse, narrate, build PDF |
| `analyze.py` | XER parser + schedule metrics and logic checks |
| `ai_engine.py` | AI narrative engine (mock + api modes) |
| `generate_sample_xer.py` | Creates a sample schedule for testing |
| `sample_schedule.xer` | Example schedule |

## Design notes

- The AI prompt receives only the computed facts as JSON, never raw rows — this
  keeps the narrative grounded and avoids hallucinated activities or numbers.
- `mock` mode mirrors the same fact structure, so switching to `api` changes only
  the language, not the inputs.
- The PDF always shows the supporting metrics alongside the narrative, so a
  reviewer can check the AI's commentary against the numbers.
