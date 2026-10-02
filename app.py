"""
AuditLens — AI Quality-Audit Scorer (Streamlit demo)

Paste or upload a (synthetic) support transcript. AuditLens scores it against
a configurable quality rubric, classifies defects, assigns a severity, and
generates STAR-format coaching feedback — returned as structured JSON.

All data is synthetic. No proprietary content.
"""

import json
import streamlit as st

from scorer import load_rubric, score_transcript

st.set_page_config(page_title="AuditLens", page_icon="🔍", layout="wide")

st.title("🔍 AuditLens — AI Quality-Audit Scorer")
st.caption(
    "Scores a support transcript against a configurable rubric, classifies "
    "defects, and generates STAR-format coaching feedback as structured JSON. "
    "Open-source demo · synthetic data only."
)

SAMPLES = {
    "Strong interaction": (
        "Customer: My refund hasn't arrived.\n"
        "Associate: I completely understand the concern, happy to help. I can see the "
        "refund was approved on the 2nd and banks take 3-5 business days. I've emailed "
        "you the reference number so you can track it. Anything else I can do?"
    ),
    "Weak interaction": (
        "Customer: My refund hasn't arrived.\n"
        "Associate: I'm not sure, maybe check with your bank. As per the TnC it's not my "
        "problem. Let me transfer you. Hold on. Actually, call back later."
    ),
    "Policy issue": (
        "Customer: Can you waive the fee?\n"
        "Associate: Sure, I'll make an exception off the record, don't tell anyone. "
        "It's against policy but I'll do it this once."
    ),
}

with st.sidebar:
    st.header("⚙️ Configuration")
    rubric = load_rubric()
    st.write("**Rubric measures:**")
    for m in rubric["measures"]:
        st.caption(f"• {m['label']} (weight {m['weight']})")

    st.subheader("Scoring engine")
    provider = st.selectbox(
        "Provider",
        ["Heuristic (no key, free)", "Anthropic Claude (bring your own key)"],
    )
    api_key = ""
    if provider.startswith("Anthropic"):
        api_key = st.text_input("Anthropic API key", type="password",
                                help="Used only in this session, never stored.")

st.subheader("📝 Transcript")
sample_choice = st.selectbox("Load a sample (or paste your own below)",
                             ["— none —"] + list(SAMPLES.keys()))
default_text = SAMPLES.get(sample_choice, "")
transcript = st.text_area("Support transcript (synthetic)", value=default_text, height=200)

if st.button("🔎 Score transcript", type="primary") and transcript.strip():
    with st.spinner("Scoring…"):
        result = score_transcript(transcript, rubric, provider=provider, api_key=api_key)

    # Severity + summary
    c1, c2, c3 = st.columns(3)
    c1.metric("Severity", result["severity"])
    c2.metric("Weighted defects", result["weighted_no"])
    c3.metric("Defect types", ", ".join(set(result["defects"])) or "None")

    if result.get("note"):
        st.warning(result["note"])

    # Scorecard
    st.subheader("📊 Scorecard")
    for r in result["scores"]:
        icon = {"Yes": "✅", "No": "❌", "N/A": "⚪"}.get(r["verdict"], "•")
        defect = f" · **{r['defect']}**" if r["defect"] else ""
        st.markdown(f"{icon} **{r['label']}** — {r['verdict']}{defect}  \n"
                    f"<span style='color:#888;font-size:0.9em'>{r['evidence']}</span>",
                    unsafe_allow_html=True)

    # STAR feedback
    st.subheader("⭐ STAR Coaching Feedback")
    st.text(result["star_feedback"])

    # Raw structured JSON
    with st.expander("🧩 Structured JSON output"):
        st.json(result)
    st.download_button("Download result (.json)",
                       json.dumps(result, indent=2),
                       file_name="auditlens_result.json")

st.markdown("---")
st.caption(
    "Built by Mohammed Abdul Najeeb · open-source demonstration of a multi-metric "
    "quality-audit system built in production at Amazon. Synthetic data only."
)
