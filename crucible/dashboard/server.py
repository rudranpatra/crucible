"""
Crucible Web Dashboard
Local FastAPI server: live attack feed, score history, agent graph, weakness heatmap.
Start with: crucible serve
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

# Optional imports — only available if fastapi/uvicorn are installed
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

# Add parent to path so we can import Crucible modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.trace_memory import TraceMemory


def create_app(traces_dir: str = "traces") -> "FastAPI":
    if not HAS_FASTAPI:
        raise ImportError("fastapi and uvicorn required: pip install fastapi uvicorn")

    app = FastAPI(title="Crucible Dashboard", version="0.1.0")
    memory = TraceMemory(traces_dir=traces_dir)

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        static_path = Path(__file__).parent / "static" / "index.html"
        if static_path.exists():
            return HTMLResponse(content=static_path.read_text())
        return HTMLResponse(content="<h1>Crucible Dashboard</h1><p>Static files not found.</p>")

    @app.get("/api/status")
    async def status():
        patterns = memory.get_failure_patterns()
        return JSONResponse({
            "status": "running",
            "traces": patterns.get("total_traces", 0),
            "avg_score": patterns.get("average_resilience_score", 0),
            "trend": patterns.get("score_trend", "stable"),
        })

    @app.get("/api/traces")
    async def traces(limit: int = 20):
        all_traces = memory.search()[:limit]
        return JSONResponse([
            {
                "trace_id": t.trace_id,
                "target": t.target,
                "score": t.resilience_score,
                "failures": t.failure_count,
                "attack_types": t.attack_types,
                "created_at": t.created_at,
                "blast_radius": t.blast_radius,
            }
            for t in all_traces
        ])

    @app.get("/api/traces/{trace_id}")
    async def trace_detail(trace_id: str):
        stored = memory.load(trace_id)
        if not stored:
            return JSONResponse({"error": "not found"}, status_code=404)
        return JSONResponse({
            "trace_id": stored.trace_id,
            "target": stored.target,
            "score": stored.resilience_score,
            "failures": stored.failure_count,
            "blast_radius": stored.blast_radius,
            "failure_points": stored.failure_points,
            "attack_types": stored.attack_types,
            "created_at": stored.created_at,
            "replay_command": stored.replay_command,
            "tags": stored.tags,
        })

    @app.get("/api/patterns")
    async def patterns():
        return JSONResponse(memory.get_failure_patterns())

    @app.get("/api/heatmap")
    async def heatmap():
        patterns = memory.get_failure_patterns()
        return JSONResponse({
            "vulnerable_steps": patterns.get("most_vulnerable_steps", []),
            "attack_failure_rates": patterns.get("attack_failure_rates", {}),
        })

    return app


def serve(traces_dir: str = "traces", host: str = "127.0.0.1", port: int = 7331):
    if not HAS_FASTAPI:
        print("Error: fastapi and uvicorn are required.")
        print("Install with: pip install fastapi uvicorn")
        sys.exit(1)

    app = create_app(traces_dir)
    print(f"\n🔥 Crucible Dashboard running at http://{host}:{port}\n")
    uvicorn.run(app, host=host, port=port, log_level="warning")
