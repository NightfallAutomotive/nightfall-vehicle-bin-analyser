const oriInput = document.getElementById("ori");
const stageInput = document.getElementById("stage1");
const button = document.getElementById("analyse-button");
const mapSelector = document.getElementById("map-selector");
const mapSelectorNote = document.getElementById("map-selector-note");

const oriName = document.getElementById("ori-name");
const stageName = document.getElementById("stage-name");
const statusText = document.getElementById("status");
const errorBox = document.getElementById("error");

function showFileName(input, label) {
    const file = input.files[0];
    label.textContent = file?.name || "No file selected";
    input.closest(".upload-box")?.classList.toggle("has-file", !!file);
}

oriInput.addEventListener("change", () => showFileName(oriInput, oriName));
stageInput.addEventListener("change", () => showFileName(stageInput, stageName));


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

    // ECUs without a torque model have nothing to review, just no graph
    const title =
        result.map_type === "no_torque_model"
            ? "No torque map"
            : "Review required";

    document.getElementById("results").style.display = "block";
    document.getElementById("map-type").textContent = title;
    document.getElementById("confidence").textContent = result.confidence || "Review";
    document.getElementById("rpm-range").textContent = "Not established";
    document.getElementById("peak-torque").textContent = "—";
    mapSelectorNote.textContent = result.message || "No graphable candidate was returned.";

    const chart = document.getElementById("chart");
    chart.innerHTML = `
        <text class="review-title" x="500" y="220" text-anchor="middle"></text>
        <text class="review-text" x="500" y="265" text-anchor="middle"></text>
    `;
    const [titleText, messageText] = chart.querySelectorAll("text");
    titleText.textContent = title;
    messageText.textContent =
        result.message || "No automatic torque graph was generated.";

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
            class="axis-title"
            x="${width / 2}"
            y="${height - 18}"
            text-anchor="middle"
        >
            ${window.binAnalyserXAxisLabel || "RPM"}
        </text>

        <text
            class="axis-title"
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

    // Shade the area under the Stage 1 line
    const last = points[points.length - 1];
    const baseline = y(0);
    const stageArea =
        pathFor("stage_torque_nm") +
        ` L ${x(xValue(last))} ${baseline} L ${x(xValue(points[0]))} ${baseline} Z`;

    svg.insertAdjacentHTML(
        "beforeend",
        `
        <defs>
            <linearGradient id="stage-area" x1="0" y1="0" x2="0" y2="1">
                <stop class="stage-area-top" offset="0" />
                <stop class="stage-area-bottom" offset="1" />
            </linearGradient>
        </defs>

        <path d="${stageArea}" fill="url(#stage-area)" />

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
                class="point ori-point"
                cx="${x(xValue(point))}"
                cy="${y(point.ori_torque_nm)}"
                r="4"
            />

            <circle
                class="point stage-point"
                cx="${x(xValue(point))}"
                cy="${y(point.stage_torque_nm)}"
                r="4"
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

            <td class="${change > 0 ? "gain-up" : change < 0 ? "gain-down" : ""}">
                ${change >= 0 ? "+" : ""}${change.toFixed(1)} Nm
            </td>
        `;

        table.appendChild(row);
    });
}


// Decoration only, so it runs last and can never stop the analyser above
new MatrixRain(document.getElementById("matrix-rain"));

new DecryptedText(document.getElementById("page-title"), {
    animateOn: "inViewHover",
    effect: "scramble",
    sequential: true,
    revealDirection: "start",
    speed: 60,
    maxIterations: 10,
    hoverRadius: 100,
    scrambleColor: "#a3be8c",
    className: "revealed",
    encryptedClassName: "encrypted",
});
