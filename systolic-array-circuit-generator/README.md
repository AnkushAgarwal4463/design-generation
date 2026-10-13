# Systolic Array Circuit Generator

Independent RTL-generation and Yosys-synthesis project for eight rectangular
systolic MAC-array configurations. It does not run OpenROAD, placement, routing,
congestion extraction, timing analysis, or ML aggregation.

## Configurations

| Array rows × columns | Data widths |
|---|---|
| 2×2 | 4-bit and 8-bit |
| 2×4 | 4-bit and 8-bit |
| 4×2 | 4-bit and 8-bit |
| 4×4 | 4-bit and 8-bit |

Total: 8 designs.

## Files

- `rtl/pe.v`: registered unsigned multiply-accumulate processing element.
- `rtl/systolic_array.v`: parameterized rectangular array.
- `scripts/configs.json`: list of configurations.
- `scripts/generate_designs.py`: creates a top wrapper for each design.
- `scripts/run_all.py`: synthesizes all generated designs with Yosys.
- `scripts/synth.ys`: reference manual synthesis recipe.
- `generated/`: generated wrappers and manifest (created at runtime).
- `outputs/<run_tag>/`: gate-level Verilog, synthesis statistics and exact Yosys script.

## Requirements

- Python 3.9+
- Yosys available on `PATH`
- No PDK or Liberty file is needed for generic-gate synthesis.

### Ubuntu / WSL

```bash
sudo apt update
sudo apt install yosys python3
```

Then run from the project root:

```bash
python3 --version
yosys -V
python3 scripts/run_all.py
```

`run_all.py` automatically runs the wrapper generator first. You can run
`python3 scripts/generate_designs.py` separately if you only want generated RTL
wrappers without synthesis.

## Output example

```text
outputs/
  sys2x2_w4/
    sys2x2_w4_gatelevel.v
    sys2x2_w4_stats.txt
    sys2x2_w4_stats.json
    synth.ys
```

The other seven configurations have equivalent output folders.

## Circuit interface

Each generated top module has:
- `clk`: rising-edge clock.
- `rst`: synchronous active-high reset.
- `clear_acc`: synchronous accumulator clear.
- `a_in`: packed operand inputs, one DATA_WIDTH slice per row.
- `b_in`: packed operand inputs, one DATA_WIDTH slice per column.
- `acc_out`: packed accumulators, in row-major order.

Slices:
- row `r` A input: `a_in[r*DATA_WIDTH +: DATA_WIDTH]`
- column `c` B input: `b_in[c*DATA_WIDTH +: DATA_WIDTH]`
- PE `(r,c)` accumulator: `acc_out[(r*COLS+c)*ACC_WIDTH +: ACC_WIDTH]`

A moves right and B moves down, one registered PE hop per cycle. Each PE
accumulates the current product on each active cycle. Assert `clear_acc` for a
cycle before starting a new accumulation window. Operands are unsigned.
Accumulator overflow wraps modulo 2**ACC_WIDTH.

The selected accumulator width is `2*DATA_WIDTH + ceil(log2(COLS))`, providing
additional accumulation headroom. This is a simple design rule, not a proof
that overflow is impossible for every possible accumulation length.

## What "gate-level" means here

The default synthesis uses `abc -g simple`, which maps the logic to generic
simple gates. It is not a SKY130 standard-cell netlist. Technology mapping to
SKY130 requires a compatible Liberty file and a separate `abc -liberty` setup.
That is intentionally excluded so this project remains portable.

## Validation

1. Confirm `yosys -V` succeeds.
2. Run `python3 scripts/run_all.py`.
3. Confirm eight output folders are generated.
4. Inspect the `.txt` statistics for each configuration and check there are no
   unresolved modules or synthesis errors.
5. For functional verification, add a testbench and compare outputs against a
   software reference model. This starter project focuses on generation and
   synthesis; it does not include a simulation testbench.

## Excluded by design

- OpenROAD floorplanning, placement and routing.
- Physical timing, congestion and DRC extraction.
- ML feature extraction and CSV aggregation.
- Technology-specific standard-cell mapping by default.
