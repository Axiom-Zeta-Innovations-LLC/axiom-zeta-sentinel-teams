# Copyright (C) 2026 Axiom Zeta Innovations LLC
# SPDX-License-Identifier: AGPL-3.0-only
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, version 3 of the License.

from fastapi import FastAPI

from gateway.api.routes_team import router as team_router
from gateway.api.routes_stabilize import router as stabilize_router
from gateway.core.config import load_settings

app = FastAPI(title="Axiom Zeta Sentinel Teams Gateway", version="0.1.0")
app.include_router(stabilize_router)
app.include_router(team_router)
settings = load_settings()


@app.get("/v1/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "deterministic_mode": settings.deterministic_mode,
        "engine_seed": settings.default_seed,
    }

from pathlib import Path

from fastapi.responses import FileResponse

_STATIC_DIR = Path(__file__).parent / "static"


@app.get("/ui", include_in_schema=False)
def ui():
    return FileResponse(_STATIC_DIR / "index.html")


@app.get("/", include_in_schema=False)
def root():
    return FileResponse(_STATIC_DIR / "index.html")
