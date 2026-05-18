# AGENTS.md

## Cursor Cloud specific instructions

This is a pure Python Streamlit application with no external service dependencies (no database, no Docker, no Node.js).

### Services

| Service | Command | Port |
|---------|---------|------|
| Streamlit App | `streamlit run streamlit_app.py --server.headless true --server.port 8501` | 8501 |

### Quick reference

- **Install deps:** `pip install -r requirements.txt`
- **Run tests:** `python3 -m unittest discover`
- **Run app:** `streamlit run streamlit_app.py --server.headless true`
- **Lint:** No linter configured in the repo; use `python3 -m py_compile domain_classifier.py streamlit_app.py` for syntax checks

### Notes

- The only pip dependency is `streamlit`; all classification logic uses the Python standard library.
- The app runs entirely in-memory on uploaded files — no persistent state or database.
- Pass `--server.headless true` when running Streamlit in a headless/cloud environment to suppress the "Email:" prompt on first launch.
- The feature branch `cursor/add-crawl-metadata-categorizer-a957` contains all implementation; `main` has empty placeholder files.
