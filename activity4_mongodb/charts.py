"""Activity 4 - report charts from results/*.csv (benchmark, aggregations, relational comparison)."""
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import chartstyle as cs  # noqa: E402

HERE = Path(__file__).parent
RES, OUT = HERE / "results", HERE / "charts"
OUT.mkdir(exist_ok=True)
cs.apply()
NOTE = "Synthetic catalog (seed 2024). Source: MongoDB 8.0 run 2026-11-03 - {}"
BEFORE, AFTER = cs.MUTED, cs.BLUE

s = pd.read_csv(RES / "benchmark_summary.csv")
b, a = s[s.phase == "before"].set_index("query"), s[s.phase == "after"].set_index("query")
qs = list(b.index)
SHORT = {"Q1": "SKU lookup", "Q2": "Laptops 50-80k|+ sort", "Q3": "brand =|Sennheiser", "Q4": "top-20 phones|< 20k",
         "Q5": "all Apparel|(20 %)", "Q6": "price >= 500|(~85 %)"}
lab = [f"{q}: " + SHORT[q].replace("|", chr(10)) for q in qs]
x = np.arange(len(qs)); w = 0.38

# 1. documents examined ------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(10, 3.8))
ax.bar(x - w / 2, b.docsExamined.clip(lower=1), w, color=BEFORE, label="before (only _id index)")
ax.bar(x + w / 2, a.docsExamined.clip(lower=1), w, color=AFTER, label="after (6 secondary indexes)")
for i, q in enumerate(qs):
    ax.text(i + w / 2, max(a.loc[q, "docsExamined"], 1) * 1.3, f"{a.loc[q, 'docsExamined']:,}", ha="center", fontsize=8)
ax.set_yscale("log"); ax.set_xticks(x, lab, fontsize=7.5); ax.set_ylabel("documents examined (log)")
ax.set_title("Documents examined per query - from explain('executionStats')")
ax.legend(fontsize=8.5, loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=2); ax.set_ylim(0.5, 2e6)
ax.grid(axis="x", visible=False)
cs.save(fig, OUT / "a4_docs_examined.png", NOTE.format("benchmark_summary.csv (identical result counts before/after)"))

# 2. server time vs client wall time --------------------------------------------------------------
raw = pd.read_csv(RES / "benchmark_raw.csv")
fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 3.9), sharey=True)
a1.bar(x - w / 2, b.server_ms.clip(lower=0.5), w, color=BEFORE, label="before")
a1.bar(x + w / 2, a.server_ms.clip(lower=0.5), w, color=AFTER, label="after")
a1.set_title("Server executionTimeMillis (explain)", fontsize=10)
for ph, off, col in (("before", -w / 2, BEFORE), ("after", w / 2, AFTER)):
    g = raw[raw.phase == ph].groupby("query").wall_ms
    med, p95 = g.median().reindex(qs), g.quantile(.95).reindex(qs)
    a2.bar(x + off, med, w, color=col, label=ph)
    a2.errorbar(x + off, med, yerr=[np.zeros(len(qs)), p95 - med], fmt="none", ecolor=cs.TEXT, lw=0.8, capsize=2)
a2.set_title("Client wall time, median of 25 runs (whisker = p95)", fontsize=10)
for ax in (a1, a2):
    ax.set_yscale("log"); ax.set_xticks(x, qs); ax.grid(axis="x", visible=False)
a1.set_ylabel("milliseconds (log)"); a1.legend(fontsize=8)
for i, q in enumerate(qs):
    a2.text(i, max(b.loc[q, "wall_median_ms"], a.loc[q, "wall_median_ms"]) * 1.9,
            f"x{b.loc[q, 'wall_median_ms'] / a.loc[q, 'wall_median_ms']:.1f}", ha="center", fontsize=8.5)
fig.suptitle("Index effect: large for selective queries, none for Q5/Q6 where transfer of many documents dominates",
             x=0.01, ha="left", fontweight="bold", fontsize=11)
cs.save(fig, OUT / "a4_latency_before_after.png", NOTE.format("benchmark_summary.csv, benchmark_raw.csv; server 0 ms drawn at 0.5 ms (log axis)"))

# 3. index cost ---------------------------------------------------------------------------------------
ib = pd.read_csv(RES / "index_build.csv")
fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 3.2))
a1.barh(ib["index"][::-1], ib.size_mb[::-1], color=cs.BLUE, height=0.55)
a2.barh(ib["index"][::-1], ib.build_s[::-1], color=cs.BLUE, height=0.55)
for ax, col, unit in ((a1, "size_mb", "MB"), (a2, "build_s", "s")):
    for i, v in enumerate(ib[col][::-1]):
        ax.text(v, i, f" {v:.2f} {unit}", va="center", fontsize=8.5)
    ax.grid(axis="y", visible=False); ax.tick_params(axis="y", labelsize=8.5)
a1.set_title("Index size on disk", fontsize=10); a2.set_title("Index build time (200,000 docs)", fontsize=10)
a1.set_xlim(0, ib.size_mb.max() * 1.3); a2.set_xlim(0, ib.build_s.max() * 1.3); a2.set_yticklabels([])
cs.save(fig, OUT / "a4_index_cost.png", NOTE.format("index_build.csv; indexes also add work to every write"))

# 4. category report (aggregation pipeline) -----------------------------------------------------------
cr = pd.read_csv(RES / "agg_category_report.csv").sort_values("products")
fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 3.8))
a1.barh(cr.category, cr.products, color=cs.BLUE, height=0.6); a1.set_title("Active products", fontsize=10)
cr2 = cr.sort_values("inventory_value")
a2.barh(cr2.category, cr2.inventory_value / 1e7, color=cs.BLUE, height=0.6)
a2.set_title("Inventory value (INR crore) = sum(price x stock)", fontsize=10)
for ax in (a1, a2):
    ax.grid(axis="y", visible=False); ax.tick_params(axis="y", labelsize=8.5)
cs.save(fig, OUT / "a4_category_report.png", NOTE.format("agg_category_report.csv ($match + $group pipeline, after CRUD demo)"))

# 5. document vs relational representation -------------------------------------------------------------
rc = pd.read_csv(RES / "relational_counts.csv").set_index("item").value
fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 3.2))
parts = ["sql_rows_products", "sql_rows_product_specs", "sql_rows_product_variants", "sql_rows_product_tags"]
names = ["products", "product_specs (EAV)", "product_variants", "product_tags"]
left = 0
for p, n, c in zip(parts, names, [cs.BLUE, cs.ORANGE, cs.AQUA, cs.YELLOW]):
    a1.barh(["SQL (4 tables)"], [rc[p] / 1e6], left=left / 1e6, color=c, height=0.5, label=f"{n}: {rc[p]:,}",
            edgecolor="white", linewidth=1.5)
    left += rc[p]
a1.barh(["MongoDB (1 collection)"], [rc["mongodb_documents"] / 1e6], color=cs.BLUE, height=0.5)
a1.text(rc["mongodb_documents"] / 1e6, 1, f"  {rc['mongodb_documents']:,} documents", va="center", fontsize=8.5)
a1.text(left / 1e6, 0, f"  {left:,} rows", va="center", fontsize=8.5)
a1.set_xlim(0, left / 1e6 * 1.6); a1.set_xlabel("millions of records"); a1.legend(fontsize=7.5, loc="upper right")
a1.set_title("Same catalog, two representations", fontsize=10); a1.grid(axis="y", visible=False)
a2.bar(["MongoDB find_one", "SQL 3 LEFT JOINs"], [rc["one_product_mongo_docs"], rc["one_product_sql_join_rows"]],
       color=[cs.BLUE, cs.ORANGE], width=0.5)
for i, v in enumerate([rc["one_product_mongo_docs"], rc["one_product_sql_join_rows"]]):
    a2.text(i, v, f"{v}", ha="center", va="bottom", fontsize=9)
a2.set_title("Records to rebuild ONE apparel product", fontsize=10); a2.grid(axis="x", visible=False)
cs.save(fig, OUT / "a4_document_vs_relational.png", NOTE.format("relational_counts.csv (SQLite export of the same collection)"))
