from __future__ import annotations

import html
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse

from analyzer import analyse as analyse_bin


app = FastAPI(
    title="Nightfall BIN Analyser",
    version="0.3.0",
)


@app.get("/health")
def health():
    return {
        "ok": True,
        "service": "nightfall-bin-analyser",
        "version": "0.3.0",
    }


@app.post("/analyse")
async def analyse(
    ori: UploadFile = File(...),
    stage1: UploadFile = File(...),
):
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)

            ori_path = temp / "ori.bin"
            stage_path = temp / "stage1.bin"

            ori_bytes = await ori.read()
            stage_bytes = await stage1.read()

            ori_path.write_bytes(ori_bytes)
            stage_path.write_bytes(stage_bytes)

            result = analyse_bin(
                ori_bytes,
                stage_bytes,
                ori.filename or "",
                stage1.filename or "",
            )

        return JSONResponse(result)

    except Exception as exc:
        import traceback

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


@app.get("/", response_class=HTMLResponse)
def home():
    return HTMLResponse(
        """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<title>Nightfall BIN Analyser</title>

<style>
    :root {
        --background: #2e3440;
        --surface: #3b4252;
        --surface-2: #434c5e;
        --border: #4c566a;
        --text: #eceff4;
        --muted: #d8dee9;
        --blue: #81a1c1;
        --green: #a3be8c;
        --red: #bf616a;
    }

    * {
        box-sizing: border-box;
    }

    body {
        margin: 0;
        min-height: 100vh;
        background: var(--background);
        color: var(--text);
        font-family:
            Inter,
            ui-sans-serif,
            system-ui,
            -apple-system,
            BlinkMacSystemFont,
            "Segoe UI",
            sans-serif;
    }

    .container {
        width: min(1200px, calc(100% - 32px));
        margin: 0 auto;
        padding: 40px 0;
    }

    .header {
        margin-bottom: 28px;
    }

    .eyebrow {
        margin: 0 0 8px;
        color: var(--blue);
        font-size: 12px;
        font-weight: 800;
        letter-spacing: 0.2em;
        text-transform: uppercase;
    }

    h1 {
        margin: 0;
        font-size: clamp(28px, 5vw, 42px);
        line-height: 1.1;
    }

    .subtitle {
        margin: 12px 0 0;
        color: var(--muted);
        font-size: 15px;
    }

    .card {
        border: 1px solid var(--border);
        background: var(--surface);
        border-radius: 20px;
        padding: 24px;
        box-shadow: 0 10px 30px rgb(0 0 0 / 0.25);
    }

    .upload-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 16px;
    }

    .upload-box {
        border: 1px dashed var(--border);
        background: var(--surface-2);
        border-radius: 16px;
        padding: 20px;
    }

    .upload-label {
        display: block;
        margin-bottom: 8px;
        font-size: 13px;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }

    .file-name {
        margin-top: 10px;
        color: var(--muted);
        font-size: 13px;
        word-break: break-all;
    }

    input[type="file"] {
        width: 100%;
        color: var(--muted);
    }

    .actions {
        margin-top: 20px;
        display: flex;
        align-items: center;
        gap: 12px;
        flex-wrap: wrap;
    }

    button {
        border: 0;
        border-radius: 12px;
        background: var(--green);
        color: var(--background);
        padding: 13px 20px;
        font-size: 14px;
        font-weight: 800;
        cursor: pointer;
    }

    button:hover {
        filter: brightness(1.08);
    }

    button:disabled {
        opacity: 0.5;
        cursor: not-allowed;
    }

    .status {
        color: var(--muted);
        font-size: 13px;
    }

    .error {
        margin-top: 16px;
        border: 1px solid rgb(191 97 106 / 0.4);
        background: rgb(191 97 106 / 0.1);
        border-radius: 12px;
        padding: 14px;
        color: #bf616a;
        display: none;
    }

    #results {
        display: none;
        margin-top: 24px;
    }

    .summary {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 12px;
        margin-bottom: 20px;
    }

    .stat {
        border: 1px solid var(--border);
        background: var(--surface-2);
        border-radius: 14px;
        padding: 16px;
    }

    .stat-label {
        color: var(--muted);
        font-size: 11px;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }

    .stat-value {
        margin-top: 6px;
        font-size: 20px;
        font-weight: 800;
    }

    .verified {
        color: var(--green);
    }

    .chart-card {
        border: 1px solid var(--border);
        background: var(--surface);
        border-radius: 20px;
        padding: 20px;
    }

    .chart-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 16px;
        flex-wrap: wrap;
        margin-bottom: 16px;
    }

    .chart-title {
        margin: 0;
        font-size: 20px;
    }

    .chart-note {
        margin: 6px 0 0;
        color: var(--muted);
        font-size: 13px;
    }

    .legend {
        display: flex;
        gap: 16px;
        flex-wrap: wrap;
        color: var(--muted);
        font-size: 13px;
        font-weight: 700;
    }

    .legend-item {
        display: flex;
        align-items: center;
        gap: 7px;
    }

    .legend-line {
        width: 26px;
        height: 3px;
        border-radius: 99px;
    }

    .ori-line {
        background: var(--blue);
    }

    .stage-line {
        background: var(--green);
    }

    .map-selector-wrap {
        margin: 22px 0 16px;
        padding: 16px;
        background: var(--surface-2);
        border: 1px solid var(--border);
        border-radius: 12px;
    }

    .map-selector-wrap label {
        display: block;
        margin-bottom: 8px;
        font-weight: 700;
    }

    #map-selector {
        width: 100%;
        padding: 11px 12px;
        border-radius: 8px;
        border: 1px solid var(--border);
        background: var(--surface);
        color: var(--text);
        font-size: 15px;
    }

    .selector-note {
        margin-top: 8px;
        color: var(--muted);
        font-size: 13px;
    }

    .chart-wrap {
        width: 100%;
        overflow-x: auto;
    }

    svg {
        width: 100%;
        min-width: 760px;
        height: auto;
        display: block;
    }

    .axis {
        stroke: var(--border);
        stroke-width: 1;
    }

    .grid-line {
        stroke: var(--border);
        stroke-width: 1;
        opacity: 0.45;
    }

    .axis-text {
        fill: var(--muted);
        font-size: 11px;
    }

    .ori-path {
        fill: none;
        stroke: var(--blue);
        stroke-width: 4;
        stroke-linejoin: round;
        stroke-linecap: round;
    }

    .stage-path {
        fill: none;
        stroke: var(--green);
        stroke-width: 4;
        stroke-linejoin: round;
        stroke-linecap: round;
    }

    .point {
        stroke: var(--surface);
        stroke-width: 2;
    }

    .table-wrap {
        margin-top: 20px;
        overflow-x: auto;
    }

    table {
        width: 100%;
        border-collapse: collapse;
        font-size: 13px;
    }

    th,
    td {
        padding: 10px 12px;
        border-bottom: 1px solid var(--border);
        text-align: right;
    }

    th:first-child,
    td:first-child {
        text-align: left;
    }

    th {
        color: var(--muted);
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.06em;
    }

    @media (max-width: 800px) {
        .upload-grid,
        .summary {
            grid-template-columns: 1fr;
        }

        .container {
            padding: 24px 0;
        }

        .card {
            padding: 18px;
        }
    }
</style>
</head>

<body>

<div class="container">

    <div class="header">
        <p class="eyebrow">Nightfall Automotive</p>
        <h1>BIN Analyser</h1>
        <p class="subtitle">
            Compare an original calibration with a Stage 1 calibration
            and detect torque limiter changes.
        </p>
    </div>

    <div class="card">

        <div class="upload-grid">

            <div class="upload-box">
                <label class="upload-label" for="ori">
                    Original BIN
                </label>

                <input
                    id="ori"
                    type="file"
                    accept=".bin,.BIN"
                >

                <div id="ori-name" class="file-name">
                    No file selected
                </div>
            </div>

            <div class="upload-box">
                <label class="upload-label" for="stage1">
                    Stage 1 BIN
                </label>

                <input
                    id="stage1"
                    type="file"
                    accept=".bin,.BIN"
                >

                <div id="stage-name" class="file-name">
                    No file selected
                </div>
            </div>

        </div>

        <div class="actions">

            <button id="analyse-button">
                Analyse BINs
            </button>

            <span id="status" class="status"></span>

        </div>

        <div id="error" class="error"></div>

    </div>

    <div id="results">

        <div class="summary">

            <div class="stat">
                <div class="stat-label">
                    Map
                </div>

                <div
                    id="map-type"
                    class="stat-value"
                >
                    —
                </div>
            </div>

            <div class="stat">
                <div class="stat-label">
                    Confidence
                </div>

                <div
                    id="confidence"
                    class="stat-value verified"
                >
                    —
                </div>
            </div>

            <div class="stat">
                <div class="stat-label">
                    RPM Range
                </div>

                <div
                    id="rpm-range"
                    class="stat-value"
                >
                    —
                </div>
            </div>

            <div class="stat">
                <div class="stat-label">
                    Peak Stage 1 Torque
                </div>

                <div
                    id="peak-torque"
                    class="stat-value"
                >
                    —
                </div>
            </div>

        </div>

        <div class="chart-card">

            <div class="chart-header">

                <div>
                    <h2 class="chart-title">
                        Torque Limiter Comparison
                    </h2>

                    <p class="chart-note">
                        Original calibration vs Stage 1 torque limiter.
                    </p>
                </div>

                <div class="legend">

                    <div class="legend-item">
                        <span class="legend-line ori-line"></span>
                        ORI
                    </div>

                    <div class="legend-item">
                        <span class="legend-line stage-line"></span>
                        Stage 1
                    </div>

                </div>

            </div>

            <div class="map-selector-wrap">
                <label for="map-selector">Map candidates — compare alternatives</label>
                <select id="map-selector">
                    <option value="">Run analysis first</option>
                </select>
                <div id="map-selector-note" class="selector-note"></div>
            </div>

            <div class="chart-wrap">
                <svg
                    id="chart"
                    viewBox="0 0 1000 520"
                    preserveAspectRatio="xMidYMid meet"
                ></svg>
            </div>

            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th id="x-axis-table-heading">RPM</th>
                            <th>ORI Nm</th>
                            <th>Stage 1 Nm</th>
                            <th>Change</th>
                        </tr>
                    </thead>

                    <tbody id="data-table"></tbody>
                </table>
            </div>

        </div>

    </div>

</div>

<script>

const oriInput = document.getElementById("ori");
const stageInput = document.getElementById("stage1");
const button = document.getElementById("analyse-button");
const mapSelector = document.getElementById("map-selector");
const mapSelectorNote = document.getElementById("map-selector-note");

const oriName = document.getElementById("ori-name");
const stageName = document.getElementById("stage-name");
const statusText = document.getElementById("status");
const errorBox = document.getElementById("error");

oriInput.addEventListener("change", () => {
    oriName.textContent =
        oriInput.files[0]?.name ||
        "No file selected";
});

stageInput.addEventListener("change", () => {
    stageName.textContent =
        stageInput.files[0]?.name ||
        "No file selected";
});


button.addEventListener("click", async () => {

    errorBox.style.display = "none";

    if (!oriInput.files[0]) {
        showError("Please select the original BIN.");
        return;
    }

    if (!stageInput.files[0]) {
        showError("Please select the Stage 1 BIN.");
        return;
    }

    button.disabled = true;
    statusText.textContent = "Analysing BINs...";

    try {

        const formData = new FormData();

        formData.append(
            "ori",
            oriInput.files[0]
        );

        formData.append(
            "stage1",
            stageInput.files[0]
        );

        const response = await fetch(
            "/analyse",
            {
                method: "POST",
                body: formData,
            }
        );

        const rawResponse =
            await response.text();

        let result;

        try {
            result =
                JSON.parse(rawResponse);
        } catch (parseError) {
            throw new Error(
                `Server returned an invalid response (${response.status}). ` +
                `${rawResponse.slice(0, 300)}`
            );
        }

        if (!response.ok || !result.ok) {
            throw new Error(
                result.message ||
                `Analysis failed (HTTP ${response.status}).`
            );
        }

        renderResults(result);

        statusText.textContent =
            "Analysis complete.";

    } catch (error) {

        showError(
            error.message ||
            "Something went wrong."
        );

        statusText.textContent = "";

    } finally {

        button.disabled = false;
    }
});


function showError(message) {

    errorBox.textContent = message;
    errorBox.style.display = "block";
}


function renderResults(result) {

    window.binAnalyserResult = result;

    const options =
        result.map_options || [];

    mapSelector.innerHTML = "";

    options.forEach(
        (option, index) => {
            const item =
                document.createElement("option");

            item.value = String(index);

            const candidate =
                option.candidate || {};

            const score =
                Number(option.score ?? candidate.score ?? 0).toFixed(1);

            const rows =
                candidate.rows ?? "?";

            const columns =
                candidate.columns ?? "?";

            const offset =
                Number.isFinite(candidate.table_offset)
                    ? `0x${candidate.table_offset.toString(16).toUpperCase()}`
                    : "unknown offset";

            item.textContent =
                `${index + 1}. ${option.label || "Map candidate"} — ` +
                `${rows}×${columns} — ${offset} — score ${score}`;

            mapSelector.appendChild(item);
        }
    );

    if (!options.length) {
        mapSelector.innerHTML =
            '<option value="">No map candidates</option>';
        mapSelector.disabled = true;
        renderReviewState(result);
        return;
    }

    mapSelector.disabled = false;
    mapSelector.value = "0";
    renderSelectedMap(result, 0);
}


function renderSelectedMap(result, index) {

    const option =
        (result.map_options || [])[index];

    if (!option || !option.graph) {
        renderReviewState(result);
        return;
    }

    const graph =
        option.graph;

    const points =
        graph.points || [];

    const candidate =
        option.candidate || {};

    const axisLabel =
        graph.x_label ||
        (graph.x_key === "injection_speed" ? "Injection speed" : "RPM");

    const rangeLabel =
        document.querySelector(
            "#rpm-range"
        )?.parentElement?.querySelector(
            ".stat-label"
        );

    if (rangeLabel) {
        rangeLabel.textContent =
            axisLabel + " Range";
    }

    document.getElementById("results").style.display = "block";

    document.getElementById("map-type").textContent =
        option.recommended ? "Torque limiter" : "Torque limiter candidate";

    document.getElementById("confidence").textContent =
        option.recommended
            ? (result.confidence || "high")
            : (candidate.scale_source === "ecu_profile"
                ? "profile-scaled candidate"
                : "manual selection");

    const start =
        graph.range?.start_rpm ?? graph.range?.start_x;
    const end =
        graph.range?.end_rpm ?? graph.range?.end_x;

    document.getElementById("rpm-range").textContent =
        Number.isFinite(start) && Number.isFinite(end)
            ? `${start.toLocaleString()}–${end.toLocaleString()}`
            : "Not established";

    if (!points.length) {
        document.getElementById("peak-torque").textContent = "—";
    } else {
        const peakStage = Math.max(
            ...points.map(point => point.stage_torque_nm)
        );
        document.getElementById("peak-torque").textContent =
            `${peakStage.toFixed(1)} Nm`;
    }

    window.binAnalyserXAxisLabel = axisLabel;

    const tableHeading =
        document.getElementById("x-axis-table-heading");

    if (tableHeading) {
        tableHeading.textContent = axisLabel;
    }

    const scaleText =
        Number.isFinite(Number(candidate.scale))
            ? ` Scale ${Number(candidate.scale)} Nm/count.`
            : "";

    mapSelectorNote.textContent =
        `${option.note || "Candidate selected"}. ` +
        `Score ${Number(option.score ?? candidate.score ?? 0).toFixed(1)}.` +
        scaleText;

    drawChart(points);
    renderTable(points);
}


function renderReviewState(result) {

    document.getElementById("results").style.display = "block";
    document.getElementById("map-type").textContent = "Review required";
    document.getElementById("confidence").textContent = result.confidence || "Review";
    document.getElementById("rpm-range").textContent = "Not established";
    document.getElementById("peak-torque").textContent = "—";
    mapSelectorNote.textContent = result.message || "No graphable candidate was returned.";

    document.getElementById("chart").innerHTML = `
        <text x="500" y="220" text-anchor="middle" font-size="28" fill="#eceff4">Review required</text>
        <text x="500" y="265" text-anchor="middle" font-size="17" fill="#d8dee9">${result.message || "No automatic torque graph was generated."}</text>
    `;

    document.getElementById("data-table").innerHTML = `
        <tr><td colspan="4">Select a map candidate above if one is available.</td></tr>
    `;
}


mapSelector.addEventListener(
    "change",
    () => {
        const index = Number(mapSelector.value);
        if (!Number.isNaN(index) && window.binAnalyserResult) {
            renderSelectedMap(window.binAnalyserResult, index);
        }
    }
);


function drawChart(points) {

    const svg =
        document.getElementById("chart");

    svg.innerHTML = "";

    if (!points.length) {
        return;
    }

    const width = 1000;
    const height = 520;

    const margin = {
        top: 30,
        right: 40,
        bottom: 65,
        left: 75,
    };

    const chartWidth =
        width -
        margin.left -
        margin.right;

    const chartHeight =
        height -
        margin.top -
        margin.bottom;

    const xValue =
        point =>
            point.x ?? point.rpm;

    const minRpm =
        Math.min(
            ...points.map(
                xValue
            )
        );

    const maxRpm =
        Math.max(
            ...points.map(
                xValue
            )
        );

    const maxTorque =
        Math.max(
            ...points.flatMap(
                p => [
                    p.ori_torque_nm,
                    p.stage_torque_nm,
                ]
            )
        );

    const yMax =
        Math.ceil(
            maxTorque / 50
        ) * 50;

    const x =
        rpm =>
            margin.left +
            (
                (rpm - minRpm) /
                (maxRpm - minRpm)
            ) *
            chartWidth;

    const y =
        torque =>
            margin.top +
            chartHeight -
            (
                torque / yMax
            ) *
            chartHeight;

    // Horizontal grid
    for (
        let value = 0;
        value <= yMax;
        value += 50
    ) {

        const yy = y(value);

        svg.insertAdjacentHTML(
            "beforeend",
            `
            <line
                class="grid-line"
                x1="${margin.left}"
                y1="${yy}"
                x2="${width - margin.right}"
                y2="${yy}"
            />

            <text
                class="axis-text"
                x="${margin.left - 12}"
                y="${yy + 4}"
                text-anchor="end"
            >
                ${value}
            </text>
            `
        );
    }

    // Axes
    svg.insertAdjacentHTML(
        "beforeend",
        `
        <line
            class="axis"
            x1="${margin.left}"
            y1="${margin.top}"
            x2="${margin.left}"
            y2="${height - margin.bottom}"
        />

        <line
            class="axis"
            x1="${margin.left}"
            y1="${height - margin.bottom}"
            x2="${width - margin.right}"
            y2="${height - margin.bottom}"
        />

        <text
            class="axis-text"
            x="${width / 2}"
            y="${height - 18}"
            text-anchor="middle"
        >
            ${window.binAnalyserXAxisLabel || "RPM"}
        </text>

        <text
            class="axis-text"
            x="18"
            y="${height / 2}"
            text-anchor="middle"
            transform="rotate(-90 18 ${height / 2})"
        >
            Torque (Nm)
        </text>
        `
    );

    // X labels
    const labelEvery =
        Math.max(
            1,
            Math.ceil(points.length / 8)
        );

    points.forEach(
        (point, index) => {

            if (
                index % labelEvery !== 0 &&
                index !== points.length - 1
            ) {
                return;
            }

            svg.insertAdjacentHTML(
                "beforeend",
                `
                <text
                    class="axis-text"
                    x="${x(xValue(point))}"
                    y="${height - margin.bottom + 22}"
                    text-anchor="middle"
                >
                    ${(point.x ?? point.rpm).toLocaleString()}
                </text>
                `
            );
        }
    );

    function pathFor(key) {

        return points
            .map(
                (point, index) => {

                    const command =
                        index === 0
                            ? "M"
                            : "L";

                    return `
                        ${command}
                        ${x(xValue(point))}
                        ${y(point[key])}
                    `;
                }
            )
            .join(" ");
    }

    svg.insertAdjacentHTML(
        "beforeend",
        `
        <path
            class="ori-path"
            d="${pathFor("ori_torque_nm")}"
        />

        <path
            class="stage-path"
            d="${pathFor("stage_torque_nm")}"
        />
        `
    );

    // Data points
    points.forEach(point => {

        svg.insertAdjacentHTML(
            "beforeend",
            `
            <circle
                class="point"
                cx="${x(xValue(point))}"
                cy="${y(point.ori_torque_nm)}"
                r="4"
                fill="#81a1c1"
            />

            <circle
                class="point"
                cx="${x(xValue(point))}"
                cy="${y(point.stage_torque_nm)}"
                r="4"
                fill="#a3be8c"
            />
            `
        );
    });
}


function renderTable(points) {

    const table =
        document.getElementById(
            "data-table"
        );

    table.innerHTML = "";

    points.forEach(point => {

        const change =
            point.stage_torque_nm -
            point.ori_torque_nm;

        const row =
            document.createElement("tr");

        row.innerHTML = `
            <td>
                ${(point.x ?? point.rpm).toLocaleString()}
            </td>

            <td>
                ${point.ori_torque_nm.toFixed(1)}
            </td>

            <td>
                ${point.stage_torque_nm.toFixed(1)}
            </td>

            <td>
                ${change >= 0 ? "+" : ""}
                ${change.toFixed(1)} Nm
            </td>
        `;

        table.appendChild(row);
    });
}

</script>

</body>
</html>
        """
    )