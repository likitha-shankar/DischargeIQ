"""
api/

HTTP transport layer for DischargeIQ. Contains only routing and
request/response shaping - no business logic.

Modules:
    app          - create_app() factory: lifespan, CORS, router registration.
    schemas      - Pydantic request/response models for /chat.
    dependencies - FastAPI Depends() providers (db_pool).
    routes/      - One module per resource: analyze, chat, pdf, progress, health.
"""
