# 🔍 AuditLens — AI Quality-Audit Scorer

> Upload a customer-service transcript and AuditLens scores it against a configurable quality rubric, classifies defects, and generates STAR-format coaching feedback as clean, structured JSON.

**Live demo:** _https://auditlens-najeeb.streamlit.app/_ · **Built by:** [Mohammed Abdul Najeeb](https://github.com/Najeeb-AI-bots)

> 💡 Open-source demonstration of a multi-metric quality-audit system I built in production at Amazon. All transcripts and rules here are synthetic / illustrative.

---

## What it does

1. **Upload** a (synthetic) support transcript
2. **Score** it against a YAML rubric — e.g. Friendliness, Understanding, Knowledge, Efficiency, Policy Adherence
3. **Classify** any defects into categories
4. **Generate** STAR-format coaching feedback (Situation · Task · Action · Result)
5. **Return** everything as validated structured JSON (with nullable fields for inapplicable criteria)

## Why it matters

Quality auditing at scale is subjective and slow. AuditLens shows how an LLM, constrained by a transparent rubric and a strict output schema, can produce consistent, explainable scores and coaching — the opposite of a black box.

## Architecture

```
transcript ──▶ Rubric Evaluator ──▶ Defect Classifier ──▶ STAR Feedback ──▶ Structured JSON
                 (rubric.yaml)         (categories)         (LLM)             (schema-validated)
```

## Tech stack

- **Claude structured output** — JSON schema, nullable fields, retry on format errors
- **YAML** — configurable scoring rubric
- **Streamlit / Gradio** — upload + scorecard UI
- **Python** — orchestration

## Design notes (applied prompt-engineering)

- **Nullable fields** so the model returns `null` for inapplicable criteria instead of fabricating a score
- **Format-error retries** separated from capability gaps (route the latter to human review)
- **Few-shot examples** with reasoning for nuanced defect categories

## Run locally

```bash
git clone https://github.com/Najeeb-AI-bots/auditlens
cd auditlens
pip install -r requirements.txt
streamlit run app.py
```

## Skills demonstrated

Structured LLM output · Rubric-based evaluation · Defect classification · Prompt engineering (nullable fields, retry boundaries, few-shot) · UI

## License

MIT — synthetic data only, no proprietary content.
