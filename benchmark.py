"""
benchmark.py - measure how long the cleaning engine takes on large CSV files.

Run from the project root:
    .venv\\Scripts\\python.exe benchmark.py

It writes three synthetic messy CSV files into benchmarks/ (100k, 250k and
500k data rows), then runs each one through the same pipeline the GUI uses:

    load_csv()  -> happens when the user picks a file in the GUI
    clean()     -> happens when the user clicks Clean
    save_csv()  -> happens right after clean()
    build_summary()

All cleaning options are switched on. Each file is processed twice:
  * a timing pass with no memory tracing (tracemalloc slows Python down a lot,
    so timing it would overstate how long the GUI freezes), and
  * a memory pass with tracemalloc on, to get the peak memory.
"""

import os
import random
import sys
import time
import tracemalloc

from app.cleaner import CleanOptions, build_summary, clean, load_csv, save_csv

ROOT = os.path.dirname(os.path.abspath(__file__))
BENCH_DIR = os.path.join(ROOT, "benchmarks")
TIERS = [100_000, 250_000, 500_000]
SEED = 42

HEADER = ["order_id", "customer", "email", "sku", "quantity", "amount", "status", "notes"]
FIRST = ["Ana", "Ben", "Chen", "Dana", "Eli", "Fatima", "Goro", "Hana", "Ivan", "Jo"]
LAST = ["Smith", "Lopez", "Tanaka", "Okafor", "Novak", "Kim", "Silva", "Brown"]
STATUSES = ["paid", "pending", "refunded", "shipped"]
FORMULAS = ["=+10.00", "=SUM(A1:A3)", "+44 20 7946 0000", "-15.50", "@admin", "=HYPERLINK(\"x\")"]


def _messy(value: str, rng: random.Random) -> str:
    """Add leading/trailing spaces to roughly 1 in 5 cells."""
    roll = rng.random()
    if roll < 0.10:
        return "  " + value
    if roll < 0.20:
        return value + "   "
    return value


def _csv_cell(value: str) -> str:
    if any(ch in value for ch in ',"\n\r'):
        return '"' + value.replace('"', '""') + '"'
    return value


def generate(path: str, n_rows: int) -> None:
    """Write n_rows data rows: ~5% blank, ~10% exact duplicates, ~3% formula-like."""
    rng = random.Random(SEED + n_rows)
    written: list[str] = []
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(",".join(HEADER) + "\r\n")
        for i in range(n_rows):
            roll = rng.random()
            if roll < 0.05:
                line = ",".join([""] * len(HEADER)) if rng.random() < 0.5 else ",".join(["  "] * len(HEADER))
            elif roll < 0.15 and written:
                line = rng.choice(written)  # exact duplicate of an earlier row
            else:
                first, last = rng.choice(FIRST), rng.choice(LAST)
                qty = rng.randint(1, 50)
                amount = f"{qty * rng.uniform(1, 200):.2f}"
                notes = rng.choice(["", "gift", "rush order", "call before delivery, thanks"])
                if rng.random() < 0.03:
                    amount = rng.choice(FORMULAS)
                if rng.random() < 0.01:
                    notes = rng.choice(FORMULAS)
                cells = [
                    f"{i + 1:07d}", f"{first} {last}",
                    f"{first.lower()}.{last.lower()}{i % 997}@example.com",
                    f"SKU-{rng.randint(100, 999)}", str(qty), amount,
                    rng.choice(STATUSES), notes,
                ]
                line = ",".join(_csv_cell(_messy(c, rng)) for c in cells)
                if len(written) < 5000:
                    written.append(line)
                elif rng.random() < 0.05:
                    written[rng.randrange(5000)] = line
            f.write(line + "\r\n")


def run_pipeline(src: str, out: str):
    """Run the GUI's pipeline once; return per-stage times and the result."""
    if os.path.exists(out):
        os.remove(out)
    t0 = time.perf_counter()
    data = load_csv(src)
    t1 = time.perf_counter()
    result = clean(data, CleanOptions(trim_spaces=True, remove_empty_rows=True, remove_duplicates=True))
    t2 = time.perf_counter()
    save_csv(result, out, src, replace_existing=True)
    summary = build_summary(result, out)
    t3 = time.perf_counter()
    return {"load": t1 - t0, "clean": t2 - t1, "save": t3 - t2, "total": t3 - t0}, result, summary


def main() -> None:
    os.makedirs(BENCH_DIR, exist_ok=True)
    print(f"Python {sys.version.split()[0]}  |  all cleaning options ON\n")
    rows_out = []
    for n in TIERS:
        src = os.path.join(BENCH_DIR, f"messy_{n // 1000}k.csv")
        out = os.path.join(BENCH_DIR, f"cleaned_{n // 1000}k.csv")
        print(f"Generating {src} ...", flush=True)
        generate(src, n)
        size_mb = os.path.getsize(src) / (1024 * 1024)

        times, result, _ = run_pipeline(src, out)  # timing pass (no tracing)

        tracemalloc.start()                          # memory pass
        run_pipeline(src, out)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        rows_out.append((n, size_mb, times, peak / (1024 * 1024), result))

    print()
    hdr = (f"{'Tier':>6} {'File MB':>8} {'Read':>8} {'Written':>8} {'Load s':>7} "
           f"{'Clean s':>8} {'Save s':>7} {'Total s':>8} {'Clean+Save':>10} {'Peak MB':>8}")
    print(hdr)
    print("-" * len(hdr))
    for n, size_mb, t, peak_mb, r in rows_out:
        print(f"{n // 1000:>5}k {size_mb:>8.1f} {r.rows_read:>8} {r.rows_written:>8} "
              f"{t['load']:>7.2f} {t['clean']:>8.2f} {t['save']:>7.2f} {t['total']:>8.2f} "
              f"{t['clean'] + t['save']:>10.2f} {peak_mb:>8.0f}")
    print()
    for n, _, _, _, r in rows_out:
        print(f"{n // 1000}k: trimmed={r.cells_trimmed}  empty_removed={r.empty_rows_removed}  "
              f"dupes_removed={r.duplicates_removed}  formula_warnings={len(r.formula_warnings)}")


if __name__ == "__main__":
    main()
