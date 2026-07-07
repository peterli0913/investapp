# AGENTS.md

## Cursor Cloud specific instructions

This is a single-process **Python/Streamlit** stock assistant app (炒股助手). No external database servers or Docker containers are needed.

### Quick Reference

| Action | Command |
|--------|---------|
| Install deps | `pip install -r requirements.txt` |
| Run app | `streamlit run streamlit_app.py` (serves on port 8501) |
| Run tests | `pytest tests/ -v` |
| Config | Copy `.env.example` → `.env`; LLM key is optional (heuristic fallback exists) |

### Non-obvious notes

- **PATH**: `streamlit` and other pip-installed scripts land in `~/.local/bin`. Ensure `export PATH="$HOME/.local/bin:$PATH"` is active before running `streamlit`.
- **No lint tool configured**: The project has no dedicated linter (flake8/ruff/mypy) in requirements or config. Code style is ad-hoc.
- **SQLite embedded**: The DB file `app/storage/stocks.db` is auto-created on first run by `init_db()`. No migration step needed.
- **LLM optional**: Without `OPENAI_API_KEY` in `.env`, all AI modules fall back to keyword-based heuristic analysis. The app is fully functional without an API key.
- **Scheduler**: APScheduler runs an in-process background job at 06:30 Beijing time daily. No external cron is required.
- **Data sources require internet**: `akshare` (A/HK stocks) and `yfinance` (US stocks) fetch live market data. RSS feeds provide news. If network is unavailable, the app gracefully uses cached snapshots.
- **Tests are self-contained**: `pytest tests/` uses synthetic data and monkeypatching; no network or API keys needed.
