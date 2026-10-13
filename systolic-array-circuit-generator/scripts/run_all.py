
#!/usr/bin/env python3
"""Generate wrappers, synthesize netlists, and create circuit visualizations."""

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


def run(cmd, check=True):
    cmd = [str(arg) for arg in cmd]
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=ROOT, check=check)


def yosys_path(path):
    """Return a project-relative path for Yosys scripts."""
    return Path(path).resolve().relative_to(ROOT).as_posix()


def main():
    yosys = shutil.which("yosys")
    dot = shutil.which("dot")

    if not yosys:
        print("ERROR: Yosys was not found on PATH.", file=sys.stderr)
        return 2

    if not dot:
        print(
            "ERROR: Graphviz was not found. Install Graphviz (dot).",
            file=sys.stderr,
        )
        return 2

    # 1. Generate wrappers and the manifest.
    run([sys.executable, ROOT / "scripts" / "generate_designs.py"])

    if not MANIFEST.exists():
        print(f"ERROR: Manifest not found: {MANIFEST}", file=sys.stderr)
        return 2

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)

    logic_dir = OUT / "visualizations" / "logic"
    logic_dir.mkdir(parents=True, exist_ok=True)

    # 2. Synthesize each design and generate a detailed schematic.
    for item in manifest:
        tag = item["run_tag"]
        top = item["top_module"]

        outdir = OUT / tag
        outdir.mkdir(parents=True, exist_ok=True)

        netlist = outdir / f"{tag}_gatelevel.v"
        stat_json = outdir / f"{tag}_stats.json"
        stat_text = outdir / f"{tag}_stats.txt"
        synth_script = outdir / "synth.ys"

        # Preserve the original generic-gate synthesis flow.
        commands = [
            f"read_verilog {yosys_path(RTL / 'pe.v')} "
            f"{yosys_path(RTL / 'systolic_array.v')} "
            f"{yosys_path(ROOT / item['wrapper'])}",
            f"hierarchy -check -top {top}",
            "proc",
            "opt",
            "check",
            f"synth -top {top} -flatten",
            "opt",
            "abc -g simple",
            "clean",
            "check",
            f"tee -o {yosys_path(stat_text)} stat",
            f"tee -o {yosys_path(stat_json)} stat -json",
            f"write_verilog -noattr -noexpr {yosys_path(netlist)}",
            "",
        ]

        synth_script.write_text(
            "\n".join(commands),
            encoding="utf-8",
        )
        run([yosys, "-s", synth_script])

        print(f"[OK] Netlist: {netlist.relative_to(ROOT)}")

        # Export a Graphviz schematic from the synthesized netlist.
        dot_file = logic_dir / f"{tag}_logic.dot"
        png_file = logic_dir / f"{tag}_logic.png"
        prefix = logic_dir / f"{tag}_logic"
        show_script = outdir / "schematic.ys"

        show_commands = [
            f"read_verilog {yosys_path(netlist)}",
            f"hierarchy -check -top {top}",
            "proc",
            "opt",
            f"show -format dot -prefix {yosys_path(prefix)}",
            "",
        ]

        show_script.write_text(
            "\n".join(show_commands),
            encoding="utf-8",
        )

        result = run([yosys, "-s", show_script], check=False)

        if result.returncode != 0:
            print(
                f"[WARN] Schematic export failed for {tag}; "
                f"inspect {show_script.relative_to(ROOT)}."
            )
            continue

        if not dot_file.exists():
            print(
                f"[WARN] Yosys did not create {dot_file.name} "
                f"for {tag}. Check the schematic log."
            )
            continue

        png_result = run(
            [dot, "-Tpng", "-Gdpi=180", dot_file, "-o", png_file],
            check=False,
        )

        if png_result.returncode == 0 and png_file.exists():
            print(f"[PNG] Logic schematic: {png_file.relative_to(ROOT)}")
        else:
            print(f"[WARN] Graphviz could not create the PNG for {tag}.")

    # 3. Generate clean architecture-level PNGs.
    visualizer = ROOT / "scripts" / "visualize_arrays.py"

    if not visualizer.exists():
        print(
            "ERROR: scripts/visualize_arrays.py is missing. "
            "Create that file before running this script.",
            file=sys.stderr,
        )
        return 2

    run([sys.executable, visualizer])

    print(f"\nCompleted {len(manifest)} designs.")
    print(f"Netlists and statistics: {OUT}")
    print(f"Logic schematics: {logic_dir}")
    print(f"Architecture PNGs: {OUT / 'visualizations' / 'architecture'}")
    print("Note: generic gate mapping is not SKY130 technology mapping.")
    print("Note: utilization and clock period are not in the current configs.json.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
