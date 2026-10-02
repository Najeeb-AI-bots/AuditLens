"""
scorer.py — AuditLens quality-audit scorer.

Two modes:
  - "Heuristic" : no API key, free. Keyword/rule-based scoring so the public
    demo always works and costs nothing.
  - "Anthropic Claude" : bring-your-own-key. LLM scores each measure and
    returns strict structured JSON (schema with nullable fields).

Demonstrates the D4 prompt-engineering patterns:
  - nullable fields (null for N/A instead of a fabricated score)
  - format-error retry separated from capability gaps
  - few-shot style instruction for nuanced defect classification
"""

import json
import yaml
import os

DEFAULT_RUBRIC = {
    "measures": [
        {"id": "friendly", "label": "Associate was Friendly", "weight": 1,
         "description": "Warm, respectful, professional tone."},
        {"id": "understandable", "label": "Associate was Understandable", "weight": 1,
         "description": "Clear, jargon-free communication."},
        {"id": "knowledgeable", "label": "Associate was Knowledgeable", "weight": 2,
         "description": "Accurate product/policy knowledge."},
        {"id": "efficient", "label": "Associate was Efficient", "weight": 2,
         "description": "Resolved without unnecessary delay."},
        {"id": "policy", "label": "Agreed with Policy", "weight": 3,
         "description": "Compliant with stated policy."},
    ],
    "defect_categories": ["CHO", "PO", "RGO", "SPO"],
    "severity_bands": {"critical": 4, "high": 3, "medium": 2, "low": 1},
}


def load_rubric(path: str = "rubric.yaml") -> dict:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
        return {**DEFAULT_RUBRIC, **loaded}
    return dict(DEFAULT_RUBRIC)


# ---------- Heuristic (free, no-key) scoring ----------
_NEG_SIGNALS = {
    "friendly": ["rude", "sorry you feel", "not my problem", "calm down", "whatever"],
    "understandable": ["jargon", "as per sop", "escalation matrix", "per the tnc", "rtfm"],
    "knowledgeable": ["i'm not sure", "i don't know", "maybe", "i think", "let me guess"],
    "efficient": ["hold on", "transfer you", "call back", "repeat that", "still looking"],
    "policy": ["against policy", "exception", "i'll make an exception", "off the record"],
}
_DEFECT_MAP = {
    "friendly": "CHO", "understandable": "CHO",
    "knowledgeable": "RGO", "efficient": "PO", "policy": "SPO",
}


def _heuristic_score(transcript: str, rubric: dict) -> dict:
    text = transcript.lower()
    results = []
    for m in rubric["measures"]:
        hits = [s for s in _NEG_SIGNALS.get(m["id"], []) if s in text]
        verdict = "No" if hits else "Yes"
        results.append({
            "id": m["id"],
            "label": m["label"],
            "verdict": verdict,
            "weight": m["weight"],
            "defect": _DEFECT_MAP[m["id"]] if verdict == "No" else None,
            "evidence": (f"Detected: '{hits[0]}'" if hits else "No negative signals detected"),
        })
    return _finalize(results, rubric, transcript, mode="Heuristic")


# ---------- Claude (bring-your-own-key) scoring ----------
def _claude_score(transcript: str, rubric: dict, api_key: str) -> dict:
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        measures = [{"id": m["id"], "label": m["label"], "description": m["description"]}
                    for m in rubric["measures"]]
        schema_hint = (
            '{"scores":[{"id":"<measure id>","verdict":"Yes|No|N/A",'
            '"defect":"CHO|PO|RGO|SPO|null","evidence":"<short quote or reason>"}],'
            '"summary":"<one-line coaching summary>"}'
        )
        prompt = (
            "You are a quality auditor. Score the transcript against each measure.\n"
            f"Measures: {json.dumps(measures)}\n"
            f"Defect categories (assign only when verdict is No): {rubric['defect_categories']}\n\n"
            "Rules:\n"
            "- Return STRICT JSON only, matching this schema: " + schema_hint + "\n"
            "- Use verdict 'N/A' and defect null when a measure genuinely does not apply "
            "(do NOT fabricate a Yes/No).\n"
            "- 'evidence' must cite a short phrase from the transcript or a concrete reason.\n\n"
            f"Transcript:\n{transcript}"
        )
        msg = client.messages.create(
            model="claude-sonnet-4-5", max_tokens=1200,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        # retry-friendly parse: strip code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1].replace("json", "", 1).strip()
        data = json.loads(raw)
        by_id = {s["id"]: s for s in data.get("scores", [])}
        results = []
        for m in rubric["measures"]:
            s = by_id.get(m["id"], {})
            results.append({
                "id": m["id"], "label": m["label"],
                "verdict": s.get("verdict", "N/A"), "weight": m["weight"],
                "defect": s.get("defect") if s.get("defect") not in ("null", None) else None,
                "evidence": s.get("evidence", ""),
            })
        return _finalize(results, rubric, transcript, mode="Claude",
                         summary=data.get("summary", ""))
    except Exception as e:
        # capability gap / format error -> fall back, flag for human review
        out = _heuristic_score(transcript, rubric)
        out["note"] = f"LLM scoring unavailable ({e}); used heuristic fallback. Route to human review."
        return out


# ---------- Shared finalize ----------
def _finalize(results, rubric, transcript, mode, summary=""):
    weighted_no = sum(r["weight"] for r in results if r["verdict"] == "No")
    bands = rubric["severity_bands"]
    if weighted_no >= bands["critical"]:
        severity = "🔴 Critical"
    elif weighted_no >= bands["high"]:
        severity = "🟠 High"
    elif weighted_no >= bands["medium"]:
        severity = "🟡 Medium"
    elif weighted_no >= bands["low"]:
        severity = "🟢 Low"
    else:
        severity = "✅ Pass"

    defects = [r["defect"] for r in results if r["defect"]]
    if not summary:
        fails = [r["label"] for r in results if r["verdict"] == "No"]
        summary = ("All measures met — strong interaction." if not fails
                   else "Coaching needed on: " + ", ".join(fails))
    return {
        "mode": mode,
        "scores": results,
        "weighted_no": weighted_no,
        "severity": severity,
        "defects": defects,
        "summary": summary,
        "star_feedback": _star(results, summary),
    }


def _star(results, summary):
    fails = [r for r in results if r["verdict"] == "No"]
    if not fails:
        return ("Situation: Reviewed interaction. Task: Audit against quality rubric. "
                "Action: Scored all measures. Result: All measures met — no coaching required.")
    first = fails[0]
    return (
        f"Situation: During the interaction, '{first['label']}' was not met.\n"
        f"Task: Address the {first['defect']} defect to meet quality standards.\n"
        f"Action: Coach on — {first['evidence']}.\n"
        f"Result: {summary}"
    )


def score_transcript(transcript: str, rubric: dict, provider: str = "Heuristic",
                     api_key: str = "") -> dict:
    if provider.startswith("Anthropic") and api_key:
        return _claude_score(transcript, rubric, api_key)
    return _heuristic_score(transcript, rubric)
