
#!/usr/bin/env python3
"""Generate clean architecture PNGs for the configured systolic arrays."""

from pathlib import Path
import json
import re
import sys

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = ROOT / "scripts" / "configs.json"
MANIFEST_FILE = ROOT / "generated" / "manifest.json"
OUTPUT_DIR = ROOT / "outputs" / "visualizations" / "architecture"


def get_design_info(item, fallback):
    """Read shape and width from the manifest tag, or use config order."""
    tag = str(item.get("run_tag", item.get("tag", "")))

    match = re.search(
        r"(?:sys)?(\d+)x(\d+).*?(?:w|width)(\d+)",
        tag,
        re.IGNORECASE,
    )
    if match:
        return int(match.group(1)), int(match.group(2)), int(match.group(3))

    match = re.search(
        r"(?:sys)?(\d+).*?(?:w|width)(\d+)",
        tag,
        re.IGNORECASE,
    )
    if match:
        size, width = map(int, match.groups())
        return size, size, width

    return fallback


def arrow(ax, start, end, color, linewidth=1.2):
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=11,
            linewidth=linewidth,
            color=color,
            shrinkA=0,
            shrinkB=0,
        )
    )


def draw_array(tag, rows, cols, width):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(
        figsize=(max(7, cols * 2.0 + 3), max(5, rows * 1.7 + 2.5)),
        dpi=180,
    )

    ax.set_xlim(-1.5, cols + 1.1)
    ax.set_ylim(-1.2, rows + 1.5)
    ax.set_aspect("equal")
    ax.axis("off")

    # Processing-element blocks.
    for r in range(rows):
        for c in range(cols):
            x = c + 0.12
            y = rows - 1 - r + 0.12

            block = FancyBboxPatch(
                (x, y),
                0.76,
                0.66,
                boxstyle="round,pad=0.04,rounding_size=0.06",
                linewidth=1.3,
                edgecolor="#29445f",
                facecolor="#eaf2fb",
            )
            ax.add_patch(block)
            ax.text(
                x + 0.38, y + 0.42, f"PE[{r},{c}]",
                ha="center", va="center", fontsize=8, weight="bold",
            )
            ax.text(
                x + 0.38, y + 0.20, "MAC",
                ha="center", va="center", fontsize=7, color="#29445f",
            )

    # A inputs move horizontally across each row.
    for r in range(rows):
        y = rows - 1 - r + 0.45
        arrow(ax, (-0.75, y), (0.08, y), "#1675a9")
        ax.text(
            -0.82, y + 0.16, f"A{r}",
            ha="left", va="bottom", fontsize=8, color="#1675a9",
        )

        for c in range(cols - 1):
            arrow(
                ax,
                (c + 0.90, y),
                (c + 1.10, y),
                "#1675a9",
                linewidth=1.0,
            )

    # B inputs move vertically through each column.
    for c in range(cols):
        x = c + 0.50
        arrow(ax, (x, rows + 0.80), (x, rows - 0.02), "#b05a18")
        ax.text(
            x, rows + 0.90, f"B{c}",
            ha="center", va="bottom", fontsize=8, color="#b05a18",
        )

        for r in range(rows - 1):
            y_start = rows - 1 - r + 0.10
            y_end = rows - 2 - r + 0.80
            arrow(
                ax, (x, y_start), (x, y_end),
                "#b05a18", linewidth=1.0,
            )

    # Result/accumulator output indicators.
    for c in range(cols):
        x = c + 0.50
        arrow(ax, (x, 0.08), (x, -0.35), "#4f783d", linewidth=1.0)

    ax.text(
        cols / 2, -0.56, "Accumulator / result outputs",
        ha="center", va="center", fontsize=8, color="#4f783d",
    )

    ax.set_title(
        f"Systolic Array — {rows} × {cols}, {width}-bit data",
        fontsize=13,
        weight="bold",
        pad=18,
    )

    ax.text(
        cols / 2,
        -0.94,
        f"Configuration: {tag}  |  Rows: {rows}  |  Columns: {cols}"
        f"  |  Data width: {width} bit",
        ha="center",
        va="center",
        fontsize=8,
    )

    fig.tight_layout()

    output_file = OUTPUT_DIR / f"{tag}_architecture.png"
    fig.savefig(
        output_file,
        dpi=240,
        bbox_inches="tight",
        facecolor="white",
    )
    plt.close(fig)

    print(f"[PNG] {output_file.relative_to(ROOT)}")


def main():
    if not CONFIG_FILE.exists() or not MANIFEST_FILE.exists():
        print(
            "ERROR: configs.json or generated/manifest.json is missing. "
            "Run scripts/run_all.py first.",
            file=sys.stderr,
        )
        return 2

    config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))

    shapes = config["array_shapes"]
    widths = config["data_widths"]

    expected = [
        (int(shape[0]), int(shape[1]), int(width))
        for shape in shapes
        for width in widths
    ]

    if len(manifest) != len(expected):
        print(
            f"WARNING: manifest has {len(manifest)} designs; "
            f"configuration describes {len(expected)} designs."
        )

    for index, item in enumerate(manifest):
        tag = str(item.get("run_tag", item.get("tag", f"design_{index + 1}")))

        if index < len(expected):
            fallback = expected[index]
        else:
            fallback = (2, 2, 4)

        rows, cols, width = get_design_info(item, fallback)
        draw_array(tag, rows, cols, width)

    print(f"Architecture images saved in: {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
