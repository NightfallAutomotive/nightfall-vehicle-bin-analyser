from pathlib import Path
from analyzer import analyse

base = Path(__file__).parent
test_files = base / "test-files"

pairs = [
    ("Seat Leon", test_files / "ori.bin", test_files / "stage1.bin"),
    ("Car 2", test_files / "car2_ori.bin", test_files / "car2_stage1.bin"),
]

for name, ori_path, stage_path in pairs:
    result = analyse(
        ori_path.read_bytes(),
        stage_path.read_bytes(),
        ori_name=ori_path.name,
        stage_name=stage_path.name,
    )

    print(f"\n=== {name} ===")
    print("confidence:", result["confidence"])
    print("map_type:", result["map_type"])

    if result.get("candidate"):
        c = result["candidate"]
        print(f"top candidate: 0x{c['offset']:X}")
        print(f"layout: {c['layout']}")
        print(f"dimensions: {c['rows']} x {c['columns']}")
        print(f"score: {c['score']}")
        print(f"axis confidence: {c['axis_confidence']}%")
        print(f"map confidence: {c['map_confidence']}%")

    if result.get("graph"):
        g = result["graph"]

        print("graph range:", g.get("range"))
        print("scale:", g.get("scale"))
        print(
            "scale confidence:",
            f"{g['scale_confidence']}%"
            if g.get("scale_confidence") is not None
            else "n/a",
        )

        if g.get("x_label") is not None:
            print("x label:", g["x_label"])

        if g.get("x_key") is not None:
            print("x key:", g["x_key"])

        points = g.get("points", [])

        print("graph points:", len(points))

        if points:
            torque_points = [
                p for p in points
                if p.get("stage_torque_nm") is not None
            ]

            if torque_points:
                peak = max(
                    torque_points,
                    key=lambda p: p["stage_torque_nm"],
                )

                print(
                    "peak stage torque:",
                    peak["stage_torque_nm"],
                    "Nm at",
                    peak.get("rpm", peak.get("x")),
                    "RPM",
                )

                print(
                    "maximum torque gain:",
                    max(
                        p["gain_nm"]
                        for p in torque_points
                        if p.get("gain_nm") is not None
                    ),
                    "Nm",
                )

    print("top candidates:")

    for i, c in enumerate(result.get("candidates", [])[:5], 1):
        print(
            f"  #{i} 0x{c['offset']:X} "
            f"{c['rows']}x{c['columns']} {c['layout']} "
            f"score={c['score']}"
        )
