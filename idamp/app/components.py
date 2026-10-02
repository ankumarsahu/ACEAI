from __future__ import annotations

import json
from typing import Any

import pandas as pd
import streamlit as st


def inject_styles(light_mode: bool) -> None:
    background = "#f7f6f0" if light_mode else "#101716"
    surface = "rgba(255,255,255,.82)" if light_mode else "rgba(255,255,255,.055)"
    foreground = "#17231f" if light_mode else "#e7efeb"
    muted = "#5f6e67" if light_mode else "#93a39d"
    canvas = "radial-gradient(ellipse at 8% 0%,rgba(91,143,116,.10),transparent 32%),linear-gradient(135deg,#fbfaf6,#f1f3ec 72%)" if light_mode else "radial-gradient(ellipse at 8% 0%,rgba(112,214,190,.10),transparent 32%),linear-gradient(135deg,#101716,#111b19 72%)"
    sidebar = "rgba(247,246,240,.98)" if light_mode else "rgba(12,19,17,.96)"
    st.markdown(
        f"""<style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Manrope:wght@400;500;600;700;800&display=swap');
        :root{{--bg:{background};--surface:{surface};--fg:{foreground};--muted:{muted};--lime:#c5ef6b;--teal:#70d6be}}
        .stApp{{background:{canvas};color:var(--fg);font-family:'Manrope',sans-serif}}
        [data-testid="stSidebar"]{{background:{sidebar}}}
        .stButton>button,.stDownloadButton>button,[data-testid="stBaseButton"],button[kind]{{color:#111!important;background-color:#e8eee4;border:1px solid #b8c6b9}}
        .stButton>button:hover,.stDownloadButton>button:hover,[data-testid="stBaseButton"]:hover{{color:#000!important;background-color:#dce8d8;border-color:#738d79}}
        .stButton>button:disabled{{color:#111!important;opacity:.58}}
        .stButton>button p,.stDownloadButton>button p,.stButton>button span,.stDownloadButton>button span,[data-testid="stBaseButton"] *{{color:#111!important}}
        [data-testid="stBaseButton-primary"]{{background-color:#c5ef6b!important;border-color:#8ba83d!important;color:#111!important}}
        .st-key-suggest_0 button,.st-key-suggest_1 button,.st-key-suggest_2 button,.st-key-suggest_3 button{{min-height:36px;padding:4px 12px;justify-content:flex-start;text-align:left;white-space:nowrap;font-size:13px}}
        .st-key-suggest_0 button p,.st-key-suggest_1 button p,.st-key-suggest_2 button p,.st-key-suggest_3 button p{{text-align:left;white-space:nowrap;font-size:13px}}
        h1,h2,h3,p,span,label{{font-family:'Manrope',sans-serif}}
        .glass{{background:var(--surface);border:1px solid rgba(182,218,200,.15);border-radius:12px;padding:20px;backdrop-filter:blur(16px);box-shadow:0 12px 36px rgba(0,0,0,.12)}}
        .eyebrow{{font:500 11px 'DM Mono',monospace;color:var(--teal);text-transform:uppercase;letter-spacing:1px}}
        .hero{{padding:30px 34px;border-radius:14px;border:1px solid rgba(83,119,88,.22);background:linear-gradient(115deg,#e7eee2,#f4f4e9 55%,#e9eee7);animation:rise .7s ease-out both}}
        .hero h1{{font-size:34px;margin:8px 0;color:#18372f}} .hero p{{color:#4e6258;margin:0}}
        .flow{{display:flex;align-items:center;justify-content:center;gap:10px;padding:18px 8px;color:#354a40;font:12px 'DM Mono',monospace}}
        .flow span{{padding:9px 12px;border:1px solid rgba(112,214,190,.25);background:rgba(112,214,190,.08);border-radius:7px}}.flow b{{color:var(--lime)}}
        .stepper{{display:flex;gap:5px;margin:8px 0 20px}}.step{{flex:1;height:4px;border-radius:8px;background:rgba(255,255,255,.12)}}.step.done{{background:#70d6be}}.step.active{{background:#c5ef6b;box-shadow:0 0 12px #c5ef6b;animation:pulse 1.3s infinite}}
        .kpi{{padding:17px 16px;border:1px solid rgba(112,214,190,.2);border-radius:10px;background:rgba(112,214,190,.055)}}.kpi strong{{display:block;font-size:24px;color:var(--lime)}}.kpi small{{color:var(--muted)}}
        .lineage{{border-left:2px solid #70d6be;padding:9px 12px;margin:8px 0;background:rgba(112,214,190,.045);border-radius:0 7px 7px 0}}
        .event{{border-left:2px solid #70d6be;padding:8px 10px;margin:7px 0;background:rgba(255,255,255,.04);border-radius:0 8px 8px 0;font-size:12px}}
        .pipeline-loader{{display:flex;align-items:center;gap:16px;padding:18px 20px;margin:12px 0;border:1px solid rgba(83,119,88,.2);border-radius:12px;background:linear-gradient(110deg,#fffefa,#edf2e9);color:#17231f;box-shadow:0 10px 28px rgba(37,57,43,.08)}}
        .loader-orbit{{position:relative;flex:0 0 48px;width:48px;height:48px;border:3px solid #dce5d9;border-top-color:#fa8232;border-right-color:#fa8232;border-radius:50%;animation:loader-spin .9s linear infinite}}
        .loader-orbit:before{{content:'';position:absolute;width:10px;height:10px;border-radius:50%;background:#fa8232;top:2px;left:4px;box-shadow:0 0 12px rgba(250,130,50,.55)}}
        .loader-copy strong{{display:block;font-size:14px;color:#173a31}}.loader-copy small{{display:block;margin-top:3px;color:#607168;font-size:12px}}
        .loader-dots{{display:inline-flex;gap:4px;margin-left:4px;vertical-align:middle}}.loader-dots i{{width:5px;height:5px;border-radius:50%;background:#fa8232;animation:loader-dot 1.1s infinite ease-in-out}}.loader-dots i:nth-child(2){{animation-delay:.15s}}.loader-dots i:nth-child(3){{animation-delay:.3s}}
        @keyframes loader-spin{{to{{transform:rotate(360deg)}}}}@keyframes loader-dot{{0%,60%,100%{{opacity:.3;transform:translateY(0)}}30%{{opacity:1;transform:translateY(-3px)}}}}
        @keyframes pulse{{50%{{opacity:.45}}}}@keyframes rise{{from{{opacity:0;transform:translateY(8px)}}to{{opacity:1;transform:translateY(0)}}}}
        </style>""",
        unsafe_allow_html=True,
    )


def render_stepper(active: str) -> None:
    steps = ["Upload", "Profile", "Bronze", "Silver", "Gold", "Report", "Review", "Export"]
    active_group = {"bronze_sttm": "Bronze", "bronze_hitl": "Bronze", "bronze_load": "Bronze", "silver_sttm": "Silver", "silver_hitl": "Silver", "silver_load": "Silver", "gold_sttm": "Gold", "gold_hitl": "Gold", "gold_load": "Gold", "complete": "Export"}.get(active, "Profile")
    index = steps.index(active_group)
    st.markdown('<div class="stepper">' + "".join(f'<div class="step {"done" if i < index else "active" if i == index else ""}" title="{step}"></div>' for i, step in enumerate(steps)) + "</div>", unsafe_allow_html=True)


def render_mapping(mapping: list[dict[str, object]], key: str) -> list[dict[str, object]]:
    frame = pd.DataFrame(mapping)
    if "source_column" in frame:
        frame["source_column"] = frame["source_column"].astype(str)
    if "validation" not in frame:
        frame["validation"] = ""
    edited = st.data_editor(
        frame,
        key=key,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        disabled=["source_column", "validation"],
        column_config={
            "source_column": st.column_config.TextColumn("Source", help="Source fields are preserved from the profiler."),
            "target_column": st.column_config.TextColumn("Target", required=True),
            "transformation": st.column_config.TextColumn("Transformation", width="large"),
            "data_type": st.column_config.SelectboxColumn("Type", options=["str", "int64", "float64", "datetime64"], required=True),
            "notes": st.column_config.TextColumn("Notes", width="medium"),
            "validation": st.column_config.TextColumn("Validation"),
        },
    )
    return edited.drop(columns=["validation"], errors="ignore").fillna("").to_dict(orient="records")


def render_processing_loader(stage: str) -> None:
    st.markdown(
        f"""<div class="pipeline-loader" role="status" aria-live="polite">
        <div class="loader-orbit"></div><div class="loader-copy">
        <strong>Applying {stage.title()} mapping<span class="loader-dots"><i></i><i></i><i></i></span></strong>
        <small>Writing the medallion layer and running its validation checks</small>
        </div></div>""",
        unsafe_allow_html=True,
    )


def export_session(state: dict[str, Any]) -> str:
    clean = {key: value for key, value in state.items() if key != "report_result_df"}
    return json.dumps(clean, indent=2, default=str)