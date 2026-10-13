#!/usr/bin/env python3
"""Generate wrappers for selected systolic-array configurations."""

from pathlib import Path
import json
import math
import os

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "scripts" / "configs.json"
GENERATED = ROOT / "generated"
MANIFEST = GENERATED / "manifest.json"


def main():
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))

    rows = os.getenv("ARRAY_ROWS")
    cols = os.getenv("ARRAY_COLS")
    width = os.getenv("DATA_WIDTH")
    util = os.getenv("UTIL")
    clk = os.getenv("CLK_PERIOD")

    selected = all(v is not None and v.strip() for v in
                   [rows, cols, width, util, clk])

    if selected:
        rows, cols, width = int(rows), int(cols), int(width)
        util, clk = int(util), int(clk)

        if rows <= 0 or cols <= 0 or width <= 0:
            raise ValueError("Array dimensions and data width must be positive.")
        if not 0 < util <= 100 or clk <= 0:
            raise ValueError("Utilization must be 1–100 and clock period positive.")

        configurations = [(rows, cols, width, util, clk)]
    else:
        configurations = [
            (r, c, w, None, None)
            for r, c in cfg["array_shapes"]
            for w in cfg["data_widths"]
        ]

    GENERATED.mkdir(parents=True, exist_ok=True)
    manifest = []

    for rows, cols, width, util, clk in configurations:
        acc_width = (
            2 * width + math.ceil(math.log2(cols))
            if cols > 1 else 2 * width
        )

        if util is not None:
            tag = f"sys{rows}x{cols}_w{width}_u{util}_clk{clk}"
        else:
            tag = f"sys{rows}x{cols}_w{width}"

        top = f"systolic_top_{rows}x{cols}_w{width}"
        wrapper = GENERATED / f"{tag}_top.v"

        text = "\n".join([
            "// Auto-generated wrapper. Do not edit by hand.",
            f"module {top} (",
            "    input wire clk,",
            "    input wire rst,",
            "    input wire clear_acc,",
            f"    input wire [{rows * width - 1}:0] a_in,",
            f"    input wire [{cols * width - 1}:0] b_in,",
            f"    output wire [{rows * cols * acc_width - 1}:0] acc_out",
            ");",
            "    systolic_array #(",
            f"        .ROWS({rows}), .COLS({cols}),",
            f"        .DATA_WIDTH({width}), .ACC_WIDTH({acc_width})",
            "    ) u_array (",
            "        .clk(clk), .rst(rst), .clear_acc(clear_acc),",
            "        .a_in(a_in), .b_in(b_in), .acc_out(acc_out)",
            "    );",
            "endmodule",
            ""
        ])

        wrapper.write_text(text, encoding="utf-8")

        item = {
            "run_tag": tag,
            "rows": rows,
            "cols": cols,
            "data_width": width,
            "acc_width": acc_width,
            "top_module": top,
            "wrapper": str(wrapper.relative_to(ROOT)),
        }

        if util is not None:
            item["utilization"] = util
            item["clk_period"] = clk

        manifest.append(item)

    MANIFEST.write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Generated {len(manifest)} configuration(s) in {GENERATED}")
    for item in manifest:
        print(f"  {item['run_tag']}: top={item['top_module']}")


if __name__ == "__main__":
    main()
