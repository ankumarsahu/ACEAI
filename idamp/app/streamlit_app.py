from __future__ import annotations

import json
import importlib
import ast
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
from langgraph.types import Command

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from idamp.agents.auditor import get_recent_runs, get_stage_events
from idamp.agents.sttm_generator import generate_sttm
from idamp.app.components import export_session, inject_styles, render_mapping, render_processing_loader, render_stepper
import idamp.app.components as components_module
from idamp.core.config import settings
from idamp.core.quality import validate_sttm
import idamp.agents.silver_agent as silver_agent_module
import idamp.agents.sttm_generator as sttm_generator_module
import idamp.agents.gold_agent as gold_agent_module
import idamp.agents.reporter as reporter_module
import idamp.graph.nodes as graph_nodes_module
import idamp.graph.pipeline as pipeline_module


st.set_page_config(page_title="IDAMP | Agentic Medallion Pipeline", page_icon="◈", layout="wide", initial_sidebar_state="collapsed")

importlib.reload(components_module)
importlib.reload(reporter_module)
importlib.reload(graph_nodes_module)
importlib.reload(pipeline_module)
export_session = components_module.export_session
inject_styles = components_module.inject_styles
render_mapping = components_module.render_mapping
render_processing_loader = components_module.render_processing_loader
render_stepper = components_module.render_stepper

GRAPH_VERSION = "orange-visible-report-chart-v1"
THEME_VERSION = "offwhite-v1"


@st.cache_resource
def get_graph(version: str = GRAPH_VERSION):
    return pipeline_module.build_pipeline()


if st.session_state.get("theme_version") != THEME_VERSION:
    st.session_state.light_mode = True
    st.session_state.theme_version = THEME_VERSION
inject_styles(st.session_state.light_mode)
graph = get_graph()


def thread_config(run_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": run_id}}


def set_business_intent(value: str) -> None:
    st.session_state.intent_input = value


def canonical_data_type(value: object) -> str:
    normalized = str(value).strip().lower().replace("_", "")
    if normalized in {"int64", "int", "integer", "long", "int32", "int16", "int8"}:
        return "int64"
    if normalized in {"float64", "float", "double", "decimal", "number", "numeric"}:
        return "float64"
    if any(token in normalized for token in ("datetime", "timestamp", "date", "time")):
        return "datetime64"
    return "str"


def canonical_source_column(value: object) -> str:
    parsed = value
    if isinstance(value, str) and value.lstrip().startswith(("[", "(")):
        try:
            parsed = ast.literal_eval(value)
        except (SyntaxError, ValueError):
            parsed = value
    if isinstance(parsed, (list, tuple)):
        parsed = next((item for item in parsed if isinstance(item, str) and item.strip()), "")
    return str(parsed).strip() if parsed is not None else ""


def persist_uploads(uploaded: list[Any]) -> list[dict[str, Any]]:
    settings.ensure_directories()
    run_id = str(uuid.uuid4())
    infos: list[dict[str, Any]] = []
    for file in uploaded:
        path = settings.landing_dir / f"{run_id}_{Path(file.name).name}"
        path.write_bytes(file.getvalue())
        preview_frame = pd.read_csv(path, nrows=8, low_memory=False)
        infos.append({"name": file.name, "path": str(path), "size": file.size, "rows_preview": len(preview_frame), "columns": list(preview_frame.columns)})
    return infos


def run_until_pause(run_id: str, initial: dict[str, Any] | None = None) -> dict[str, Any]:
    config = thread_config(run_id)
    result = graph.invoke(initial, config=config) if initial is not None else graph.invoke(None, config=config)
    state = dict(result)
    if st.session_state.get("auto_approve"):
        for _ in range(4):
            snapshot = graph.get_state(config)
            next_nodes = snapshot.next
            current = dict(snapshot.values)
            if not next_nodes or current.get("error") or current.get("current_step") == "complete":
                state = current
                break
            waiting = next_nodes[0].replace("_hitl_node", "") if next_nodes[0].endswith("_hitl_node") else ""
            if not waiting:
                state = current
                break
            graph.update_state(config, {"approved_stage": waiting, "current_step": f"{waiting}_load"})
            state = dict(graph.invoke(None, config=config))
            if st.session_state.get("error"):
                break
    return state


def reload_pipeline_agents() -> None:
    importlib.reload(silver_agent_module)
    importlib.reload(gold_agent_module)
    importlib.reload(sttm_generator_module)
    importlib.reload(reporter_module)
    importlib.reload(graph_nodes_module)


def restart_pipeline_from_sources(state: dict[str, Any]) -> dict[str, Any]:
    global graph
    reload_pipeline_agents()
    importlib.reload(pipeline_module)
    get_graph.clear()
    graph = get_graph()
    files = state["uploaded_files_info"]
    columns = set().union(*(set(info.get("columns", [])) for info in files))
    run_id = str(uuid.uuid4())
    initial = {
        "run_id": run_id,
        "business_intent": state["business_intent"],
        "uploaded_files_info": files,
        "profile": {"columns": {column: {} for column in sorted(columns)}},
        "current_step": "profile",
        "retry_counts": {},
        "max_gold_rows": state.get("max_gold_rows", 8),
        "strict_validation": state.get("strict_validation", True),
        "uploaded_column_count": max((len(info.get("columns", [])) for info in files), default=0),
    }
    return run_until_pause(run_id, initial)


def review_current_sttm(state: dict[str, Any], stage: str, config: dict[str, Any]) -> None:
    key = f"{stage}_sttm"
    mapping = [
        {
            **entry,
            "source_column": canonical_source_column(entry.get("source_column", "")),
            "data_type": canonical_data_type(entry.get("data_type", "str")),
        }
        for entry in state.get(key, [])
    ]
    if mapping != state.get(key, []):
        state = {**state, key: mapping}
        st.session_state.pipeline_state = state
    checkpoint = graph.get_state(config)
    if not checkpoint.values or checkpoint.values.get("run_id") != state.get("run_id"):
        st.warning("This graph checkpoint is no longer available. Restart from the saved source files to continue.")
        if st.button("Restart from source files", key=f"restore_{stage}"):
            st.session_state.pipeline_state = restart_pipeline_from_sources(state)
            st.session_state.started_at = time.time()
            st.rerun()
        return
    st.subheader(f"{stage.title()} source-to-target mapping")
    if not mapping:
        st.error("The model did not produce a mapping.")
        return
    edited = render_mapping(mapping, f"mapping_{stage}_{state['run_id']}_schema_v3")
    if stage == "bronze":
        available = set(state.get("profile", {}).get("columns", {}))
    else:
        available = {str(entry.get("target_column", "")) for entry in state.get("bronze_sttm", [])}
        available.update({"_load_timestamp", "_source_file"})
    errors = validate_sttm(edited, available)
    if errors:
        st.warning("Mapping checks: " + " · ".join(errors))
    else:
        st.caption(f"{len(edited)} mapped fields · no mapping errors")
    left, middle, right = st.columns([1, 1, 1])
    with left:
        approval_key = f"mapping_approved_{state['run_id']}_{stage}"
        already_approved = st.session_state.get(approval_key, False)
        button_label = "Mapping approved" if already_approved else "Approve mapping"
        if st.button(button_label, type="primary", disabled=bool(errors) or already_approved, key=f"approve_{stage}_{state['run_id']}"):
            st.session_state[approval_key] = True
            reload_pipeline_agents()
            with st.status(f"Applying {stage.title()} mapping", expanded=True) as status:
                render_processing_loader(stage)
                graph.update_state(config, {key: edited, "approved_stage": stage, "current_step": f"{stage}_load"})
                st.session_state.pipeline_state = run_until_pause(state["run_id"])
                next_state = st.session_state.pipeline_state
                if next_state.get("error"):
                    status.update(label=f"{stage.title()} processing needs attention", state="error", expanded=True)
                else:
                    status.update(label=f"{stage.title()} layer completed", state="complete", expanded=False)
            st.toast(f"{stage.title()} mapping approved")
            st.rerun()
    with middle:
        if st.button("Regenerate", key=f"regen_{stage}"):
            st.session_state[f"regen_open_{stage}"] = True
    with right:
        st.download_button("Download mapping JSON", json.dumps(edited, indent=2), file_name=f"{stage}_sttm.json", mime="application/json", key=f"download_{stage}")
    st.download_button("Download mapping CSV", pd.DataFrame(edited).to_csv(index=False), file_name=f"{stage}_sttm.csv", mime="text/csv", key=f"csv_{stage}")
    if st.session_state.get(f"regen_open_{stage}"):
        with st.form(f"regenerate_form_{stage}"):
            hint = st.text_input("Refinement instruction", key=f"hint_{stage}", placeholder="Preserve all fields; group revenue by month")
            submitted = st.form_submit_button("Generate revised mapping", type="primary")
        if submitted:
            try:
                regen_profile = dict(state.get("profile", {}))
                if stage != "bronze":
                    regen_profile["silver_columns"] = {name: {} for name in sorted(available)}
                revised = generate_sttm(stage, state["business_intent"], regen_profile, hint)
                graph.update_state(config, {key: revised})
                st.session_state.pipeline_state = {**state, key: revised}
                st.session_state[f"regen_open_{stage}"] = False
                st.toast("Revised mapping generated")
                st.rerun()
            except Exception as exc:
                st.error(f"Could not regenerate mapping: {exc}")
    with st.expander("Column lineage"):
        for entry in edited:
            st.markdown(f"<div class='lineage'><b>{entry.get('source_column')}</b> → <b>{entry.get('target_column')}</b><br><small>{entry.get('transformation')} · {entry.get('data_type')}</small></div>", unsafe_allow_html=True)


st.markdown("<div class='hero'><div class='eyebrow'>IDAMP / INTENT-DRIVEN DATA ENGINEERING</div><h1>From business question to trusted data.</h1><p>Review every mapping. Keep every transformation auditable.</p></div>", unsafe_allow_html=True)
st.markdown("<div class='flow'><span>CSV sources</span><b>→</b><span>BRONZE · source fidelity</span><b>→</b><span>SILVER · data quality</span><b>→</b><span>GOLD · business-ready</span><b>→</b><span>EXECUTIVE REPORT</span></div>", unsafe_allow_html=True)

left, main, right = st.columns([1.2, 3.5, 1.3], gap="medium")
with left:
    st.markdown("<div class='eyebrow'>01 / SOURCE & INTENT</div>", unsafe_allow_html=True)
    current = st.session_state.get("pipeline_state", {})
    if not current:
        uploads = st.file_uploader("Drop CSV files", type=["csv"], accept_multiple_files=True)
        if uploads:
            for item in uploads:
                with st.expander(f"{item.name} · {item.size / 1024:.1f} KB", expanded=False):
                    st.dataframe(pd.read_csv(item, nrows=5), use_container_width=True)
        intent = st.text_area("Business intent", placeholder="Analyse Q1 sales by region", height=100, key="intent_input", max_chars=500)
        suggestions = ["Analyse sales by region", "Find monthly revenue trends", "Compare customer segments", "Summarise product performance"]
        for index, suggestion in enumerate(suggestions):
            st.button(
                suggestion,
                key=f"suggest_{index}",
                use_container_width=True,
                on_click=set_business_intent,
                args=(suggestion,),
            )
        st.caption(f"{len(intent)} / 500 characters")
        with st.expander("Pipeline settings"):
            st.toggle("Auto-approve generated mappings", key="auto_approve", value=False)
            st.toggle("Strict validation", key="strict_validation", value=True)
            st.slider("Maximum gold output rows", 4, 12, 8, key="max_gold_rows")
        if st.button("Start pipeline", type="primary", disabled=not uploads or not intent.strip(), use_container_width=True):
            try:
                infos = persist_uploads(uploads)
                frame_columns = set().union(*(set(info["columns"]) for info in infos))
                profile_shell = {"columns": {column: {} for column in sorted(frame_columns)}}
                initial = {
                    "run_id": str(uuid.uuid4()), "business_intent": intent.strip(), "uploaded_files_info": infos,
                    "profile": profile_shell, "current_step": "profile", "retry_counts": {},
                    "max_gold_rows": st.session_state.get("max_gold_rows", 8),
                    "strict_validation": st.session_state.get("strict_validation", True),
                    "uploaded_column_count": max((len(info["columns"]) for info in infos), default=0),
                }
                st.session_state.pipeline_state = run_until_pause(initial["run_id"], initial)
                st.session_state.started_at = time.time()
                st.toast("Pipeline started")
                st.rerun()
            except Exception as exc:
                st.error(f"Could not start pipeline: {exc}")
    else:
        st.markdown(f"<div class='glass'><div class='eyebrow'>BUSINESS INTENT</div><p>“{current.get('business_intent', '')}”</p></div>", unsafe_allow_html=True)
        for info in current.get("uploaded_files_info", []):
            st.caption(f"▤ {info['name']} · {info['size'] / 1024:.1f} KB")
        elapsed = max(0, int(time.time() - st.session_state.get("started_at", time.time())))
        st.metric("Elapsed", f"{elapsed // 60:02d}:{elapsed % 60:02d}")
        st.caption("Pipeline health: " + ("Needs attention" if current.get("error") else "Operational"))
        with st.expander("Pipeline settings"):
            st.toggle("Auto-approve generated mappings", key="auto_approve", value=False)
            st.toggle("Strict validation", key="strict_validation", value=True)
            st.slider("Maximum gold output rows", 4, 12, current.get("max_gold_rows", 8), key="max_gold_rows")
    if st.button("Reset session", use_container_width=True):
        st.session_state.confirm_reset = True
    if st.session_state.get("confirm_reset"):
        st.warning("Clear the current pipeline from this screen?")
        yes, no = st.columns(2)
        if yes.button("Confirm", key="confirm_reset_yes"):
            st.session_state.pop("pipeline_state", None)
            st.session_state.confirm_reset = False
            st.rerun()
        if no.button("Keep", key="confirm_reset_no"):
            st.session_state.confirm_reset = False
    if current:
        st.download_button("Export session JSON", export_session(current), file_name=f"idamp_{current['run_id'][:8]}.json", mime="application/json", use_container_width=True)

with main:
    state = st.session_state.get("pipeline_state", {})
    step = state.get("current_step", "profile")
    render_stepper(step)
    if not state:
        feature_cols = st.columns(3)
        feature_data = [("01 / PROFILE", "Understand the source", "Column statistics and data-quality signals."), ("02 / REVIEW", "Approve each mapping", "Human control at Bronze, Silver, and Gold."), ("03 / DELIVER", "Share the outcome", "Parquet layers, audit history, and an executive report.")]
        for column, (eyebrow, title, detail) in zip(feature_cols, feature_data):
            with column:
                st.markdown(f"<div class='glass'><div class='eyebrow'>{eyebrow}</div><h3>{title}</h3><p style='color:var(--muted)'>{detail}</p></div>", unsafe_allow_html=True)
        st.info("Add one or more CSV files and describe the business question to begin.")
    elif state.get("error"):
        st.error(state["error"])
        if st.button("Restart pipeline from source files"):
            st.session_state.pipeline_state = restart_pipeline_from_sources(state)
            st.session_state.started_at = time.time()
            st.rerun()
    elif step in {"bronze_hitl", "silver_hitl", "gold_hitl"}:
        stage = step.split("_")[0]
        review_current_sttm(state, stage, thread_config(state["run_id"]))
    elif step == "complete":
        st.success("All medallion layers validated and the executive report is ready.")
        tabs = st.tabs(["Report", "Raw Data", "Pipeline Summary"])
        with tabs[0]:
            report_path = Path(state["report_path"])
            report_html = report_path.read_text(encoding="utf-8")
            report_html = report_html.replace("<style>body{", "<style>body{min-height:100vh;background:#fbfaf6;")
            st.components.v1.html(report_html, height=650, scrolling=True)
            st.download_button("Download HTML report", report_path.read_bytes(), file_name=report_path.name, mime="text/html")
        with tabs[1]:
            report_result = state["report_result_df"]
            result = pd.DataFrame(report_result["records"], columns=report_result["columns"])
            st.dataframe(result, use_container_width=True)
            st.download_button("Download results CSV", result.to_csv(index=False), file_name="idamp_results.csv", mime="text/csv")
            st.selectbox("Quick chart", [column for column in result.columns if pd.api.types.is_numeric_dtype(result[column])] or ["No numeric fields"])
        with tabs[2]:
            st.json({layer: state.get(f"{layer}_validation") for layer in ["bronze", "silver", "gold"]})
            st.code(state.get("report_sql", ""), language="sql")
            custom_sql = st.text_area("Edit SQL", value=state.get("report_sql", ""), key="custom_sql")
            if st.button("Run custom SQL") and custom_sql.strip().lower().startswith("select"):
                import duckdb
                connection = duckdb.connect(database=":memory:")
                connection.register("gold_data", pd.read_parquet(state["gold_paths"][0]))
                st.dataframe(connection.execute(custom_sql).df(), use_container_width=True)
                connection.close()
        st.download_button("Download pipeline log JSON", json.dumps(get_stage_events(state["run_id"]), indent=2), file_name="pipeline_log.json", mime="application/json")
    else:
        st.markdown(f"<div class='glass'><div class='eyebrow'>PIPELINE RUN / {state.get('run_id', '')[:8]}</div><h3>{step.replace('_', ' ').title()}</h3><p>Stage is processing or waiting for its next checkpoint.</p></div>", unsafe_allow_html=True)
        if step.endswith("validate"):
            layer = step.split("_")[0]
            result = state.get(f"{layer}_validation", {})
            if result:
                cols = st.columns(3)
                for col, label, value in zip(cols, ["Rows", "Quality", "Validation"], [result.get("rows", 0), f"{result.get('quality_score', 0):.1f}%", "Passed" if result.get("valid") else "Needs retry"]):
                    with col:
                        st.markdown(f"<div class='kpi'><strong>{value}</strong><small>{label}</small></div>", unsafe_allow_html=True)
                for check in result.get("checks", []):
                    st.write(("✓" if check["valid"] else "✕") + f"  {check['name']} · {check['detail']}")
        if st.button("Continue pipeline"):
            st.session_state.pipeline_state = run_until_pause(state["run_id"])
            st.rerun()

with right:
    st.markdown("<div class='eyebrow'>LIVE AUDIT / LAST 5 RUNS</div>", unsafe_allow_html=True)
    state = st.session_state.get("pipeline_state", {})
    if state.get("run_id"):
        events = get_stage_events(state["run_id"])
        if not events:
            st.caption("Stage events appear as pipeline steps complete.")
        for event in reversed(events[-8:]):
            marker = "✓" if event["status"] == "completed" else "!"
            with st.expander(f"{marker} {event['stage']} · {event['status']}", expanded=False):
                st.caption(f"Rows: {event.get('rows_out') or '—'} · Quality: {event.get('quality_score') or '—'}")
                if event.get("error_message"):
                    st.error(event["error_message"])
                    if st.button("Retry stage", key=f"retry_{event['event_id']}"):
                        st.session_state.pipeline_state = run_until_pause(state["run_id"])
                        st.rerun()
    for run in get_recent_runs(5):
        with st.expander(f"{run['status']} · {run['started_at'][:16]}"):
            st.write(run["business_intent"])
            st.caption(run["run_id"])
    if st.button("☼ / ◐", help="Toggle light and dark appearance"):
        st.session_state.light_mode = not st.session_state.light_mode
        st.rerun()