from __future__ import annotations

import traceback
from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from analyzer import ANALYSER_VERSION, analyse as analyse_bin


STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(
    title="Nightfall BIN Analyser",
    version=ANALYSER_VERSION,
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/health")
def health():
    return {
        "ok": True,
        "service": "nightfall-bin-analyser",
        "version": ANALYSER_VERSION,
    }


# A plain (non-async) endpoint: analysis is CPU-bound, so FastAPI runs it in
# its thread pool rather than blocking the event loop for every other request.
@app.post("/analyse")
def analyse(
    ori: UploadFile = File(...),
    stage1: UploadFile = File(...),
):
    try:
        result = analyse_bin(
            ori.file.read(),
            stage1.file.read(),
            ori.filename or "",
            stage1.filename or "",
        )
        return JSONResponse(result)

    except ValueError as exc:
        return JSONResponse(
            {"ok": False, "message": str(exc)},
            status_code=400,
        )

    except Exception as exc:
        traceback.print_exc()

        return JSONResponse(
            {
                "ok": False,
                "message": (
                    "BIN analysis failed: "
                    f"{type(exc).__name__}: {exc}"
                ),
            },
            status_code=500,
        )


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(STATIC_DIR / "index.html")
