from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import plotly.express as px

from idamp.core.config import settings
from idamp.core.retry import chat_text


def create_report(intent: str, gold_path: str, run_id: str) -> tuple[Path, str, pd.DataFrame]:
    frame = pd.read_parquet(gold_path)
    connection = duckdb.connect(database=":memory:")
    try:
        connection.register("gold_data", frame)
        prompt = (
            f"Intent: {intent}\nTable: gold_data\nColumns: {list(frame.columns)}\n"
            "Write one read-only DuckDB SELECT query that answers the intent. Return SQL only; do not use markdown."
        )
        sql = chat_text("You write safe, read-only DuckDB SQL. Use only the provided table and columns.", prompt).strip().strip("`")
        if not sql.lower().lstrip().startswith("select") or ";" in sql.rstrip(";"):
            raise ValueError("Generated SQL must be a single SELECT statement.")
        result = connection.execute(sql).df()
        if result.empty:
            sql = "SELECT * FROM gold_data"
            result = connection.execute(sql).df()
    finally:
        connection.close()
    identifier_columns = {
        column for column in result.columns
        if column.lower().startswith("pk_") or column.lower() == "id" or column.lower().endswith("_id")
    }
    numeric = [
        column for column in result.columns
        if column not in identifier_columns and pd.api.types.is_numeric_dtype(result[column])
    ]
    dimensions = [column for column in result.columns if column not in numeric and column not in identifier_columns]
    charts = ""
    if numeric:
        chart_frame = result.copy()
        if dimensions:
            x_column = dimensions[0]
            title = f"{numeric[0]} by {x_column}"
        else:
            x_column = "_idamp_record"
            chart_frame[x_column] = [f"Record {index + 1}" for index in range(len(chart_frame))]
            title = f"{numeric[0]} by record"
        chart = px.bar(chart_frame, x=x_column, y=numeric[0], title=title)
        chart.update_traces(marker_color="#FA8232", marker_line_color="#C75B18", marker_line_width=1)
        chart.update_layout(
            paper_bgcolor="#FBFAF6",
            plot_bgcolor="#FBFAF6",
            font={"color": "#17231F", "family": "Manrope, sans-serif"},
            title={"font": {"color": "#17231F", "size": 18}},
            bargap=0.32,
            xaxis={"title_font": {"color": "#17231F"}, "tickfont": {"color": "#26352E"}, "gridcolor": "#E3E7DF", "zerolinecolor": "#9AA69C"},
            yaxis={"title_font": {"color": "#17231F"}, "tickfont": {"color": "#26352E"}, "gridcolor": "#E3E7DF", "zerolinecolor": "#9AA69C"},
        )
        charts = chart.to_html(full_html=False, include_plotlyjs=True)
    else:
        chart = px.bar(
            pd.DataFrame({"Result": ["Gold rows"], "Rows": [len(result)]}),
            x="Result",
            y="Rows",
            title="Query result size",
        )
        chart.update_traces(marker_color="#FA8232", marker_line_color="#C75B18", marker_line_width=1)
        chart.update_layout(
            paper_bgcolor="#FBFAF6",
            plot_bgcolor="#FBFAF6",
            font={"color": "#17231F", "family": "Manrope, sans-serif"},
            title={"font": {"color": "#17231F", "size": 18}},
            bargap=0.32,
            xaxis={"title_font": {"color": "#17231F"}, "tickfont": {"color": "#26352E"}, "gridcolor": "#E3E7DF", "zerolinecolor": "#9AA69C"},
            yaxis={"title_font": {"color": "#17231F"}, "tickfont": {"color": "#26352E"}, "gridcolor": "#E3E7DF", "zerolinecolor": "#9AA69C"},
        )
        charts = chart.to_html(full_html=False, include_plotlyjs=True)
    report_prompt = (
        f"Business intent: {intent}\nSQL: {sql}\nResult preview: {result.head(20).to_json(orient='records', date_format='iso')}\n"
        "Write a concise executive HTML report with a title, executive summary, key findings, and caveats. "
        "Return an HTML fragment only; do not include script tags, external assets, or charts."
    )
    narrative = chat_text("You are an executive analytics report writer. Return accessible semantic HTML only.", report_prompt)
    html = (
        "<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>IDAMP Executive Report</title><style>body{min-height:100vh;background:#fbfaf6;font:16px/1.6 system-ui,sans-serif;max-width:1100px;margin:0 auto;padding:40px 24px;color:#18211f}"
        "h1,h2{color:#163a34}section{margin:28px 0}</style></head><body><main>"
        f"{narrative}<section><h2>Data visualization</h2>{charts}</section>"
        "</main></body></html>"
    )
    settings.ensure_directories()
    report_path = settings.reports_dir / f"report_{run_id[:8]}.html"
    report_path.write_text(html, encoding="utf-8")
    return report_path, sql, result