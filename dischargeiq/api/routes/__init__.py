"""
api/routes/

One FastAPI APIRouter per resource. Registered in api/app.py.

    health.py   - GET /health
    analyze.py  - POST /analyze
    chat.py     - POST /chat
    pdf.py      - GET /pdf/{session_id}, GET /simulator/{session_id}
    progress.py - GET /progress/{session_id}
"""
