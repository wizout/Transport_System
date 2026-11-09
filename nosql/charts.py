# графіки і таблиця з results.csv
import csv
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

COLORS = {"MongoDB": "#4caf50", "PostgreSQL (таблиці)": "#336791", "PostgreSQL (jsonb)": "#9fb7d0"}


def build(path):
    path = Path(path)
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    by_scen = defaultdict(list)
    for r in rows:
        by_scen[r["scenario"]].append(r)
    scales = sorted({int(r["trips"]) for r in rows})
    scenarios = sorted(by_scen, key=lambda s: (s[0].isdigit() is False, s))

    cols = 3
    nrows = (len(scenarios) + cols - 1) // cols
    fig, axes = plt.subplots(nrows, cols, figsize=(15, 4 * nrows))
    for ax, scen in zip(axes.flat, scenarios):
        engines = [e for e in COLORS if any(r["engine"] == e for r in by_scen[scen])]
        w = 0.8 / len(engines)
        for k, eng in enumerate(engines):
            vals = []
            for s in scales:
                v = [r for r in by_scen[scen] if r["engine"] == eng and int(r["trips"]) == s]
                val = float(v[0]["median_ms"]) if v else 0
                if scen.startswith("0."):
                    val /= 1000  # секунди
                vals.append(val)
            xs = [i + k * w for i in range(len(scales))]
            ax.bar(xs, vals, w, label=eng, color=COLORS[eng])
        ax.set_xticks([i + w * (len(engines) - 1) / 2 for i in range(len(scales))])
        ax.set_xticklabels([f"{s} рейсів" for s in scales], fontsize=8)
        ax.set_title(scen, fontsize=10)
        if scen.startswith("0."):
            ax.set_ylabel("секунди")
        elif scen.startswith("Розмір"):
            ax.set_ylabel("МБ")
        else:
            ax.set_ylabel("медіана, мс (лог. шкала)")
            ax.set_yscale("log")
        ax.grid(axis="y", alpha=0.3)
    for ax in list(axes.flat)[len(scenarios):]:
        ax.axis("off")
    handles, labels = axes.flat[0].get_legend_handles_labels()
    for ax in axes.flat:
        h, l = ax.get_legend_handles_labels()
        if len(h) > len(handles):
            handles, labels = h, l
    fig.legend(handles, labels, loc="upper center", ncol=3)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(path.parent / "charts.png", dpi=110)

    # таблиця для звіту
    out = ["| Сценарій | Рейсів | " + " | ".join(COLORS) + " |", "|---|---|" + "---|" * len(COLORS)]
    for scen in scenarios:
        for s in scales:
            cells = []
            for eng in COLORS:
                v = [r for r in by_scen[scen] if r["engine"] == eng and int(r["trips"]) == s]
                if not v:
                    cells.append("—")
                elif scen.startswith("0."):
                    cells.append(f"{float(v[0]['median_ms']) / 1000:.1f} с")
                elif scen.startswith("Розмір"):
                    cells.append(f"{v[0]['median_ms']} МБ")
                else:
                    cells.append(f"{float(v[0]['median_ms']):.2f} мс (p95 {float(v[0]['p95_ms']):.2f})")
            out.append(f"| {scen} | {s} | " + " | ".join(cells) + " |")
    (path.parent / "results.md").write_text("\n".join(out) + "\n", encoding="utf-8")


if __name__ == "__main__":
    build(Path(__file__).resolve().parent / "results" / "results.csv")
