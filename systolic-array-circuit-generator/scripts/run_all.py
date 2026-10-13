#!/usr/bin/env python3
"""Generate wrappers and synthesize generic gate-level netlists with Yosys."""
from pathlib import Path
import json
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
RTL = ROOT / "rtl"
GENERATED = ROOT / "generated"
OUT = ROOT / "outputs"
MANIFEST = GENERATED / "manifest.json"

def run(cmd):
    print("+", " ".join(map(str, cmd)), flush=True)
    subprocess.run(list(map(str, cmd)), cwd=ROOT, check=True)

def main():
    yosys = shutil.which("yosys")
    if not yosys:
        print("ERROR: yosys was not found on PATH. Install Yosys and retry.", file=sys.stderr)
        return 2

    run([sys.executable, ROOT / "scripts" / "generate_designs.py"])
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)

    for item in manifest:
        tag, top = item["run_tag"], item["top_module"]
        outdir = OUT / tag
        outdir.mkdir(parents=True, exist_ok=True)
        netlist = outdir / f"{tag}_gatelevel.v"
        stat_json = outdir / f"{tag}_stats.json"
        stat_text = outdir / f"{tag}_stats.txt"
        yosys_script = outdir / "synth.ys"

        # This maps to generic simple gates, not a foundry-specific cell library.
        script = "\\n".join([
            f"read_verilog {RTL / 'pe.v'} {RTL / 'systolic_array.v'} {ROOT / item['wrapper']}",
            f"hierarchy -check -top {top}",
            "proc", "opt", "check",
            f"synth -top {top} -flatten",
            "opt", "abc -g simple", "clean", "check",
            f"tee -o {stat_text} stat",
            f"tee -o {stat_json} stat -json",
            f"write_verilog -noattr -noexpr {netlist}",
            ""
        ])
        yosys_script.write_text(script, encoding="utf-8")
        run([yosys, "-s", yosys_script])
        print(f"[OK] {tag}: {netlist.relative_to(ROOT)}")

    print(f"\\nCompleted {len(manifest)} designs.")
    print(f"Outputs: {OUT}")
    print("Note: generic gate mapping is not SKY130 technology mapping.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
