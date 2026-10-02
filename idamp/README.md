# IDAMP

Intent-Driven Agentic Medallion Pipeline turns uploaded CSV files and a business question into reviewed Bronze, Silver, and Gold Parquet layers plus an executive HTML report.

## Run locally

1. Use Python 3.11 or later.
2. From this directory, install `requirements.txt`.
3. Copy `.env.example` to `.env` and set `GROQ_API_KEY`. The key must be a fresh key; keys exposed in chat or source control should be revoked.
4. Start the interface with `streamlit run app/streamlit_app.py`.

The graph pauses before each mapping approval and persists its checkpoint in memory for the lifetime of the Streamlit process. Parquet artifacts and SQLite audit events are stored under this project directory. The application only accepts CSV uploads and generated report SQL is restricted to a single SELECT statement.