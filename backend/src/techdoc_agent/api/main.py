"""Punto de entrada de la API: ``uvicorn techdoc_agent.api.main:app``.

La aplicación se ensambla en ``app.py``; los endpoints viven en ``routers/``, las dependencias en
``deps.py``, los modelos de entrada en ``schemas.py`` y la frontera de seguridad en ``security.py``.
"""

from __future__ import annotations

from techdoc_agent.api.app import STATIC_DIR, create_app
from techdoc_agent.api.deps import Core
from techdoc_agent.api.security import CSP, safe_filename

__all__ = ["CSP", "STATIC_DIR", "Core", "app", "create_app", "safe_filename"]

app = create_app()
