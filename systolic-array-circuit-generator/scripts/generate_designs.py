#!/usr/bin/env python3
"""Generate a wrapper top module for each selected array configuration."""
from pathlib import Path
import json
import math

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "scripts" / "configs.json"
GENERATED = ROOT / "generated"
MANIFEST = GENERATED / "manifest.json"

def main():
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    GENERATED.mkdir(parents=True, exist_ok=True)
    manifest = []
    for rows, cols in cfg["array_shapes"]:
        for width in cfg["data_widths"]:
            acc_width = 2 * width + math.ceil(math.log2(cols)) if cols > 1 else 2 * width
            tag = f"sys{rows}x{cols}_w{width}"
            top = f"systolic_top_{rows}x{cols}_w{width}"
            wrapper = GENERATED / f"{tag}_top.v"
            text = "\\n".join([
                "// Auto-generated wrapper. Do not edit by hand.",
                f"module {top} (",
                "    input wire clk,",
                "    input wire rst,",
                "    input wire clear_acc,",
                f"    input wire [{rows*width-1}:0] a_in,",
                f"    input wire [{cols*width-1}:0] b_in,",
                f"    output wire [{rows*cols*acc_width-1}:0] acc_out",
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
            manifest.append({
                "run_tag": tag, "rows": rows, "cols": cols,
                "data_width": width, "acc_width": acc_width,
                "top_module": top, "wrapper": str(wrapper.relative_to(ROOT))
            })
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\\n", encoding="utf-8")
    print(f"Generated {len(manifest)} configurations in {GENERATED}")
    for item in manifest:
        print(f"  {item['run_tag']}: top={item['top_module']}, ACC_WIDTH={item['acc_width']}")

if __name__ == "__main__":
    main()
