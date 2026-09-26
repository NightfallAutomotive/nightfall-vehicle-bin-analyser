from pathlib import Path
from analyzer_v2 import analyse

base = Path(__file__).parent

pairs = [
    ("Seat Leon", base / "ori.bin", base / "stage1.bin"),
    ("Car 2", base / "car2_ori.bin", base / "car2_stage1.bin"),
]

for name, ori_path, stage_path in pairs:
    result = analyse(ori_path.read_bytes(), stage_path.read_bytes())

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
        print("graph row:", g["row_index"])
        print("row axis:", g["row_axis_value"])
        print("range:", g["range"])
        print("peak stage torque:", g["peak_stage_torque_nm"], "Nm")

    print("top candidates:")
    for i, c in enumerate(result.get("candidates", [])[:5], 1):
        print(
            f"  #{i} 0x{c['offset']:X} "
            f"{c['rows']}x{c['columns']} {c['layout']} "
            f"score={c['score']}"
        )
