from __future__ import annotations

import traceback
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from analyzer import ANALYSER_VERSION, analyse as analyse_bin
from changes import OriLibrary, analyse_single, describe_changes


STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(
    title="Nightfall BIN Analyser",
    version=ANALYSER_VERSION,
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Stock originals used when only one file is uploaded
LIBRARY = OriLibrary()

# ECU flash reads are a few MB at most; refuse anything far bigger so a
# public server can't be swamped
MAX_UPLOAD_BYTES = 16 * 1024 * 1024


class UploadTooLarge(Exception):
    pass


def read_upload(upload):
    data = upload.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise UploadTooLarge(upload.filename or "file")
    return data


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
    stage1: UploadFile | None = File(None),
    save_original: bool = Form(True),
):
    try:
        data = read_upload(ori)

        # Only one file: find its original in the library, or fall back to
        # pattern checks
        if stage1 is None:
            return JSONResponse(analyse_single(data, ori.filename or "", LIBRARY))

        modified = read_upload(stage1)
        result = analyse_bin(
            data,
            modified,
            ori.filename or "",
            stage1.filename or "",
        )
        result["comparison"] = {"mode": "original"}
        result["changes"] = describe_changes(data, modified)

        # The page tells people their original is kept, and lets them opt
        # out. Identical files mean the "original" may not be one.
        if not save_original:
            result["library"] = {"saved": False, "reason": "not saved, as requested"}
        elif data == modified:
            result["library"] = {"saved": False, "reason": "both files are the same"}
        else:
            result["library"] = LIBRARY.add(data)
        return JSONResponse(result)

    except UploadTooLarge as exc:
        return JSONResponse(
            {"ok": False, "message": f"{exc} is larger than 16 MB, too big to be an ECU read."},
            status_code=413,
        )

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
