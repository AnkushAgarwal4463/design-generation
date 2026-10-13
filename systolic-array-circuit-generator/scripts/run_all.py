#!/usr/bin/env python3
"""Generate selected systolic-array designs, generic and SKY130 netlists,
synthesis statistics, and configuration-specific PNG visualizations.
"""

from pathlib import Path
import json
import os
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
RTL = ROOT / "rtl"
GENERATED = ROOT / "generated"
OUT = ROOT / "outputs"
MANIFEST = GENERATED / "manifest.json"

LIB_NAME = "sky130_fd_sc_hd__tt_025C_1v80.lib"


def run(cmd, check=True):
    cmd = [str(arg) for arg in cmd]
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=ROOT, check=check)


def yosys_path(path):
    """Return a project-relative path for files inside this project."""
    return Path(path).resolve().relative_to(ROOT).as_posix()


def find_sky130_lib():
    """Find the SKY130 HD typical-corner Liberty file."""
    explicit = os.environ.get("SKY130_LIB")
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if path.is_file():
            return path
        raise FileNotFoundError(
            f"SKY130_LIB was set, but the file does not exist: {path}"
        )

    roots = []

    for variable in ("PDK_ROOT", "SKY130_PDK_ROOT", "CONDA_PREFIX"):
        value = os.environ.get(variable)
        if value:
            root = Path(value).expanduser()
            if variable == "CONDA_PREFIX":
                roots.extend([
                    root / "share" / "pdk" / "sky130A",
                    root / "share" / "pdk",
                ])
            else:
                roots.extend([
                    root / "sky130A",
                    root,
                ])

    roots.extend([
        Path("/opt/pdk/sky130A"),
        Path("/usr/share/pdk/sky130A"),
    ])

    checked = set()

    for root in roots:
        if not root.exists():
            continue

        root = root.resolve()
        if root in checked:
            continue
        checked.add(root)

        direct = root / LIB_NAME
        if direct.is_file():
            return direct

        try:
            match = next(root.rglob(LIB_NAME), None)
            if match is not None and match.is_file():
                return match.resolve()
        except (OSError, PermissionError):
            continue

    raise FileNotFoundError(
        f"Could not find {LIB_NAME}. Install the SKY130 HD PDK or set "
        "SKY130_LIB to the full path of the Liberty file."
    )


def write_yosys_script(path, commands):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(commands) + "\n", encoding="utf-8")


def export_schematic(yosys, dot, tag, top, netlist, outdir,
                     schematic_dir, liberty=None):
    """Export a synthesized netlist as a Graphviz DOT file and PNG."""
    schematic_dir.mkdir(parents=True, exist_ok=True)

    prefix = schematic_dir / f"{tag}_logic"
    dot_file = prefix.with_suffix(".dot")
    png_file = prefix.with_suffix(".png")
    script = outdir / f"{tag}_schematic.ys"

    commands = []

    # Import library cell declarations so SKY130 instances are recognized.
    if liberty is not None:
        commands.append(f"read_liberty -lib {json.dumps(str(liberty))}")

    commands.extend([
        f"read_verilog {yosys_path(netlist)}",
        f"hierarchy -check -top {top}",
        f"show -format dot -prefix {yosys_path(prefix)} -colors 2",
    ])

    write_yosys_script(script, commands)
    result = run([yosys, "-s", script], check=False)

    if result.returncode != 0:
        raise RuntimeError(
            f"Yosys schematic generation failed for {tag}. "
            f"Inspect {script.relative_to(ROOT)} and the preceding log."
        )

    if not dot_file.is_file():
        raise FileNotFoundError(
            f"Yosys did not create the expected DOT file: {dot_file}"
        )

    result = run(
        [dot, "-Tpng", "-Gdpi=180", dot_file, "-o", png_file],
        check=False,
    )

    if result.returncode != 0 or not png_file.is_file():
        raise RuntimeError(f"Graphviz failed to generate {png_file}")

    print(f"[PNG] Schematic: {png_file.relative_to(ROOT)}")
    return png_file


def generate_architecture_png(item, output_path):
    """Draw a configuration-specific PE array architecture diagram."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
    except ImportError as exc:
        raise RuntimeError(
            "Matplotlib is required to generate the architecture PNG."
        ) from exc

    rows = int(item["rows"])
    cols = int(item["cols"])
    width = int(item["data_width"])
    tag = item["run_tag"]
    util = item.get("utilization")
    clk = item.get("clk_period")

    fig_w = max(8, cols * 1.8 + 3)
    fig_h = max(5, rows * 1.35 + 2.5)

    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.set_xlim(-1.6, cols + 1.4)
    ax.set_ylim(-1.4, rows + 1.2)
    ax.axis("off")

    ax.set_title(
        f"Systolic Array: {rows}x{cols}, {width}-bit\n"
        f"Configuration: {tag}",
        fontsize=13,
        pad=16,
    )

    def arrow(start, end):
        ax.add_patch(FancyArrowPatch(
            start, end,
            arrowstyle="-|>",
            mutation_scale=11,
            linewidth=1.2,
        ))

    # Draw each processing element (PE).
    for r in range(rows):
        y = rows - 1 - r

        for c in range(cols):
            x = c

            block = FancyBboxPatch(
                (x + 0.12, y + 0.12),
                0.76, 0.66,
                boxstyle="round,pad=0.04",
                linewidth=1.3,
                facecolor="white",
                edgecolor="black",
            )
            ax.add_patch(block)
            ax.text(
                x + 0.5, y + 0.45,
                f"PE[{r},{c}]",
                ha="center", va="center", fontsize=8,
            )

            # Horizontal operand flow.
            if c < cols - 1:
                arrow((x + 0.9, y + 0.45), (x + 1.1, y + 0.45))
            else:
                arrow((x + 0.9, y + 0.45), (x + 1.15, y + 0.45))
                ax.text(
                    x + 1.18, y + 0.45,
                    f"A{r}", ha="left", va="center", fontsize=8,
                )

            # Vertical operand flow.
            if r < rows - 1:
                arrow((x + 0.5, y + 0.1), (x + 0.5, y - 0.08))
            else:
                arrow((x + 0.5, y + 0.1), (x + 0.5, y - 0.23))
                ax.text(
                    x + 0.5, y - 0.35,
                    f"B{c}", ha="center", va="top", fontsize=8,
                )

    # Input labels on the top and left boundaries.
    for c in range(cols):
        x = c + 0.5
        arrow((x, rows + 0.55), (x, rows + 0.05))
        ax.text(
            x, rows + 0.65,
            f"B_in[{c}]",
            ha="center", va="bottom", fontsize=8,
        )

    for r in range(rows):
        y = rows - 1 - r + 0.45
        arrow((-1.15, y), (0.08, y))
        ax.text(
            -1.2, y,
            f"A_in[{r}]",
            ha="right", va="center", fontsize=8,
        )

    metadata = []
    if util is not None:
        metadata.append(f"Utilization: {util}%")
    if clk is not None:
        metadata.append(f"Clock period: {clk} ns")

    if metadata:
        ax.text(
            0.5, -0.95,
            " | ".join(metadata),
            transform=ax.transAxes,
            ha="center", va="center", fontsize=9,
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)

    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise RuntimeError(f"Architecture PNG was not created: {output_path}")

    print(f"[PNG] Architecture: {output_path.relative_to(ROOT)}")


def main():
    yosys = shutil.which("yosys")
    dot = shutil.which("dot")

    if not yosys:
        print("ERROR: Yosys was not found on PATH.", file=sys.stderr)
        return 2

    if not dot:
        print("ERROR: Graphviz 'dot' was not found on PATH.", file=sys.stderr)
        return 2

    # Locate the PDK before synthesis so missing dependencies fail clearly.
    try:
        liberty = find_sky130_lib()
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(f"[PDK] SKY130 HD Liberty: {liberty}")

    # 1. Generate wrappers and the selected configuration manifest.
    run([sys.executable, ROOT / "scripts" / "generate_designs.py"])

    if not MANIFEST.is_file():
        print(f"ERROR: Manifest not found: {MANIFEST}", file=sys.stderr)
        return 2

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if not manifest:
        print("ERROR: The generated manifest is empty.", file=sys.stderr)
        return 2

    OUT.mkdir(parents=True, exist_ok=True)

    logic_dir = OUT / "visualizations" / "logic"
    sky130_dir = OUT / "visualizations" / "sky130"
    architecture_dir = OUT / "visualizations" / "architecture"

    logic_dir.mkdir(parents=True, exist_ok=True)
    sky130_dir.mkdir(parents=True, exist_ok=True)

    architecture_dir.mkdir(parents=True, exist_ok=True)

    # Process each generated configuration.
    for item in manifest:
        tag = item["run_tag"]
        top = item["top_module"]

        outdir = OUT / tag
        outdir.mkdir(parents=True, exist_ok=True)

        wrapper = ROOT / item["wrapper"]
        if not wrapper.is_file():
            raise FileNotFoundError(f"Generated wrapper missing: {wrapper}")

        # ---------------------------------------------------------
        # 1. GENERIC GATE-LEVEL SYNTHESIS
        # ---------------------------------------------------------
        generic_netlist = outdir / f"{tag}_gatelevel.v"
        generic_stats = outdir / f"{tag}_stats.txt"
        generic_json = outdir / f"{tag}_stats.json"
        generic_script = outdir / "generic_synth.ys"

        generic_commands = [
            f"read_verilog {yosys_path(RTL / 'pe.v')} "
            f"{yosys_path(RTL / 'systolic_array.v')} "
            f"{yosys_path(wrapper)}",
            f"hierarchy -check -top {top}",
            f"synth -top {top} -flatten",
            "clean",
            "check",
            f"tee -o {yosys_path(generic_stats)} stat",
            f"tee -o {yosys_path(generic_json)} stat -json",
            f"write_verilog -noattr -noexpr "
            f"{yosys_path(generic_netlist)}",
        ]

        write_yosys_script(generic_script, generic_commands)
        run([yosys, "-s", generic_script])

        print(f"[OK] Generic netlist: {generic_netlist.relative_to(ROOT)}")

        # ---------------------------------------------------------
        # 2. SKY130 HD TECHNOLOGY-MAPPED SYNTHESIS
        # ---------------------------------------------------------
        sky_netlist = outdir / f"{tag}_sky130_gatelevel.v"
        sky_stats = outdir / f"{tag}_sky130_stats.txt"
        sky_json = outdir / f"{tag}_sky130_stats.json"
        sky_script = outdir / "sky130_synth.ys"

        lib_arg = json.dumps(str(liberty))

        sky_commands = [
            f"read_liberty -lib {lib_arg}",
            f"read_verilog {yosys_path(RTL / 'pe.v')} "
            f"{yosys_path(RTL / 'systolic_array.v')} "
            f"{yosys_path(wrapper)}",
            f"hierarchy -check -top {top}",
            f"synth -top {top} -flatten -noabc",
            f"dfflibmap -liberty {lib_arg}",
            f"abc -liberty {lib_arg}",
            "clean",
            "check",
            f"tee -o {yosys_path(sky_stats)} "
            f"stat -liberty {lib_arg}",
            f"tee -o {yosys_path(sky_json)} "
            f"stat -json -liberty {lib_arg}",
            f"write_verilog -noattr -noexpr "
            f"{yosys_path(sky_netlist)}",
        ]

        write_yosys_script(sky_script, sky_commands)
        run([yosys, "-s", sky_script])

        print(f"[OK] SKY130 netlist: {sky_netlist.relative_to(ROOT)}")

        # ---------------------------------------------------------
        # 3. GENERIC LOGIC SCHEMATIC PNG
        # ---------------------------------------------------------
        export_schematic(
            yosys, dot, tag, top, generic_netlist,
            outdir, logic_dir
        )

        # ---------------------------------------------------------
        # 4. SKY130 CELL SCHEMATIC PNG
        # ---------------------------------------------------------
        export_schematic(
            yosys, dot, tag, top, sky_netlist,
            outdir, sky130_dir, liberty=liberty
        )

        # ---------------------------------------------------------
        # 5. CONFIGURATION-SPECIFIC ARCHITECTURE PNG
        # ---------------------------------------------------------
        architecture_png = architecture_dir / f"{tag}_architecture.png"
        generate_architecture_png(item, architecture_png)

    print(f"\nCompleted {len(manifest)} configuration(s).")
    print(f"Generated RTL: {GENERATED}")
    print(f"Netlists and statistics: {OUT}")
    print(f"Generic schematics: {logic_dir}")
    print(f"SKY130 schematics: {sky130_dir}")
    print(f"Architecture diagrams: {architecture_dir}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, FileNotFoundError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)

