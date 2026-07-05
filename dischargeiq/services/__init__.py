"""
services/

Application service layer - business logic that is independent of the HTTP
transport layer. Each service has a single responsibility and is fully
testable without starting the FastAPI app.

Modules:
    session  - SessionStore: thread-safe in-memory PDF / simulator / progress state.
    chat     - ChatService: grounded patient Q&A against a discharge document.
"""
