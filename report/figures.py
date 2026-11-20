"""Design diagrams for the report (architecture / workflow). These are ILLUSTRATIVE design figures
drawn from the implemented components; they are not measurement results."""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import chartstyle as cs  # noqa: E402

OUT = Path(__file__).parent / "figures"
OUT.mkdir(exist_ok=True)
cs.apply()
FILL = {"data": "#eef4fb", "engine": "#e3eefc", "out": "#f1f8f4", "store": "#fdf6e8", "cloud": "#eef4fb"}
EDGE = {"data": cs.MUTED, "engine": cs.BLUE, "out": cs.AQUA, "store": cs.YELLOW, "cloud": cs.BLUE}


def canvas(w, h, title):
    fig, ax = plt.subplots(figsize=(w, h)); ax.set_xlim(0, w); ax.set_ylim(0, h); ax.axis("off")
    ax.set_title(title, loc="left", fontsize=12, fontweight="bold")
    return fig, ax


def box(ax, x, y, w, h, text, kind="engine", dashed=False, fs=8.5):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.03,rounding_size=0.08", fc=FILL[kind],
                                ec=EDGE[kind], lw=1.5, ls="--" if dashed else "-"))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, color=cs.TEXT)


def group(ax, x, y, w, h, label):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.1", fc="none", ec=cs.MUTED, lw=1, ls=":"))
    ax.text(x + 0.08, y + h - 0.08, label, ha="left", va="top", fontsize=8, color=cs.TEXT2, style="italic")


def arrow(ax, p1, p2, text=None, curve=0.0):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle="-|>", mutation_scale=12, lw=1.2, color=cs.TEXT2,
                                 connectionstyle=f"arc3,rad={curve}"))
    if text:
        ax.text((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2 + 0.12, text, ha="center", fontsize=7.5, color=cs.TEXT2)


def save(fig, name):
    fig.savefig(OUT / name, dpi=200, bbox_inches="tight"); plt.close(fig); print("saved", name)


# ---- overall environment ----------------------------------------------------------------------------
fig, ax = canvas(12, 5.6, "Execution environment: one laptop, Docker profiles, and BigQuery in Google Cloud")
group(ax, 0.2, 0.3, 8.4, 4.9, "Windows 11 laptop (8 GB RAM, i5-8350U)")
NL = chr(10)
box(ax, 0.5, 3.4, 2.4, 1.3, NL.join(["Python 3.12 venv", "generators, producers,", "consumers, analysis,", "charts, evidence capture"]), "data")
box(ax, 0.5, 0.55, 2.4, 1.1, NL.join(["Google Cloud CLI", "(gcloud, bq)", "user login token"]), "data")
group(ax, 3.2, 1.25, 5.1, 3.65, "Docker Desktop (WSL2 VM, 3.75 GiB) - one profile at a time")
box(ax, 3.5, 3.55, 2.2, 0.85, NL.join(["profile hive", "Hive 4.0.1 (HS2, Tez local)"]), "engine")
box(ax, 5.9, 3.55, 2.2, 0.85, NL.join(["profile kafka", "Kafka 4.1.0 + Kafka-UI"]), "engine")
box(ax, 3.5, 2.45, 2.2, 0.85, NL.join(["profile flink", "Kafka + Flink 1.20.5 JM/TM"]), "engine")
box(ax, 5.9, 2.45, 2.2, 0.85, NL.join(["profile mongo", "MongoDB 8.0"]), "engine")
box(ax, 3.5, 1.45, 4.6, 0.75, "evidence: logs, CSV results, console and web-UI screenshots", "out")
group(ax, 9.0, 0.3, 2.8, 4.9, "Google Cloud (asia-south1)")
box(ax, 9.2, 3.0, 2.4, 1.5, NL.join(["Cloud Billing", "Catalog API", "(read-only prices,", "same gcloud token)"]), "cloud")
box(ax, 9.2, 0.55, 2.4, 1.6, NL.join(["BigQuery Sandbox", "project bigdatasla", "dataset weblogs", "(no billing)"]), "cloud")
arrow(ax, (2.9, 4.0), (3.5, 3.95))
arrow(ax, (2.9, 1.0), (9.2, 1.0)); ax.text(6.0, 0.72, "batch load jobs + SQL queries over HTTPS", ha="center", fontsize=7.5, color=cs.TEXT2)
save(fig, "fig_environment.png")

# ---- Activity 1 -------------------------------------------------------------------------------------------
fig, ax = canvas(12, 4.6, "Activity 1 - Hive data warehouse for supermarket sales")
box(ax, 0.2, 2.9, 2.0, 1.1, "generate_sales.py\n559,626 line items\nCSV (57 MB)", "data")
group(ax, 2.6, 0.4, 6.6, 3.9, "HiveServer2 container (apache/hive:4.0.1)")
box(ax, 2.9, 2.9, 2.3, 1.0, "sales_raw\nEXTERNAL TEXTFILE\nschema-on-read", "store")
box(ax, 6.6, 2.9, 2.3, 1.0, "sales\nORC (ZLIB), PARTITIONED\nBY sale_month (12)", "store")
box(ax, 2.9, 1.0, 2.3, 1.1, "Metastore\n(embedded Derby):\nschemas, partitions, stats", "engine")
box(ax, 6.6, 1.0, 2.3, 1.1, "Driver: parse, optimise,\nplan -> Tez DAG\n(local mode)", "engine")
arrow(ax, (2.2, 3.45), (2.9, 3.4), "bind mount")
arrow(ax, (5.2, 3.4), (6.6, 3.4), "INSERT OVERWRITE\ndynamic partitions")
box(ax, 9.6, 2.9, 2.2, 1.0, "Beeline (JDBC)\n12 HiveQL queries", "engine")
box(ax, 9.6, 1.0, 2.2, 1.1, "results/*.csv ->\ncharts, insights,\nrecommendations", "out")
arrow(ax, (9.6, 3.4), (8.9, 3.4)); arrow(ax, (10.7, 2.9), (10.7, 2.1))
save(fig, "fig_a1_architecture.png")

# ---- Activity 2 ---------------------------------------------------------------------------------------------
fig, ax = canvas(12, 5.0, "Activity 2 - Kafka traffic-congestion alerting")
box(ax, 0.2, 2.2, 2.1, 1.3, "producer.py\n12 junction sensors\nkey = junction_id\nacks=all, idempotent", "data")
group(ax, 2.7, 0.5, 3.8, 4.1, "Kafka broker (KRaft, apache/kafka:4.1.0)")
box(ax, 3.0, 2.0, 3.2, 1.8, "topic traffic-readings\npartition 0 | partition 1 | partition 2\n(CRC32(key) % 3)", "store")
box(ax, 3.0, 0.8, 3.2, 0.9, "topic congestion-alerts (1 partition)", "store")
box(ax, 7.0, 3.2, 2.5, 1.0, "group congestion-detector\nrolling window (5) +\nrules + hysteresis", "engine")
box(ax, 7.0, 1.9, 2.5, 1.0, "group traffic-archiver\nall readings + latency", "engine")
box(ax, 7.0, 0.6, 2.5, 1.0, "group operator-dashboard\ncontrol-room view", "engine")
box(ax, 9.9, 1.9, 1.9, 2.3, "results/\nalerts.csv\ningested_readings.csv\nevaluation vs\nground truth", "out")
arrow(ax, (2.3, 2.85), (3.0, 2.9))
arrow(ax, (6.2, 3.2), (7.0, 3.7)); arrow(ax, (6.2, 2.6), (7.0, 2.4))
arrow(ax, (7.0, 3.45), (6.25, 1.62)); ax.text(6.45, 2.0, "alerts", fontsize=7.5, color=cs.TEXT2, rotation=68)
arrow(ax, (6.2, 1.1), (7.0, 1.1))
arrow(ax, (9.5, 3.7), (9.9, 3.4)); arrow(ax, (9.5, 2.4), (9.9, 2.4))
save(fig, "fig_a2_architecture.png")

# ---- Activity 3 ----------------------------------------------------------------------------------------------
fig, ax = canvas(12, 5.4, "Activity 3 - Flink event-time processing of patient vital signs (synthetic, educational)")
box(ax, 0.2, 2.4, 1.9, 1.3, "vitals_producer.py\n10 patients, 5 s\narrival order:\nout-of-order + late", "data")
box(ax, 2.4, 2.4, 1.6, 1.3, "Kafka topic\npatient-vitals\n(2 partitions)", "store")
group(ax, 4.3, 0.3, 5.3, 4.7, "Flink 1.20.5 session cluster: JobManager + TaskManager (2 slots), PyFlink job")
box(ax, 4.5, 2.4, 1.5, 1.3, "Kafka source\nWATERMARK\nts - 30 s", "engine")
box(ax, 6.3, 3.9, 3.1, 0.75, "Q1 filter -> reading alerts", "engine")
box(ax, 6.3, 2.9, 3.1, 0.8, "unpivot -> OVER (last 12 rows)\nabnormal score per vital", "engine")
box(ax, 6.3, 1.8, 3.1, 0.8, "Q2/Q3 MATCH_RECOGNIZE\nepisode onset / resolved", "engine")
box(ax, 6.3, 0.55, 3.1, 0.95, "Q4 TUMBLE 5 min per patient\nQ5 TUMBLE 15 min ward\n(local + global aggregation)", "engine")
box(ax, 9.9, 2.0, 1.9, 2.2, "4 output topics\n-> results_collector\n-> CSV\n-> evaluate.py\n(reference impl.)", "out")
arrow(ax, (2.1, 3.05), (2.4, 3.05)); arrow(ax, (4.0, 3.05), (4.5, 3.05))
for y in (4.27, 3.3, 1.0):
    arrow(ax, (6.0, 3.05), (6.3, y))
arrow(ax, (7.85, 2.9), (7.85, 2.6))
for y in (4.27, 2.2, 1.0):
    arrow(ax, (9.4, y), (9.9, 3.1))
ax.text(4.5, 0.05, "checkpoints every 10 s; memory: JM 768 MB, TM 1152 MB", fontsize=7.5, color=cs.TEXT2)
save(fig, "fig_a3_architecture.png")

# ---- Activity 4 ------------------------------------------------------------------------------------------------
fig, ax = canvas(12, 4.6, "Activity 4 - MongoDB product catalogue: design, indexing benchmark and relational comparison")
box(ax, 0.2, 2.8, 2.0, 1.2, "generate_catalog.py\n200,000 products\n11 categories", "data")
group(ax, 2.6, 0.4, 5.6, 3.9, "MongoDB 8.0 container (WiredTiger cache 256 MB)")
box(ax, 2.9, 2.6, 2.4, 1.3, "collection products\nvalidator: $jsonSchema\n+ $expr (mrp >= price)", "store")
box(ax, 5.6, 2.6, 2.3, 1.3, "indexes: sku unique,\nbrand, category+price,\ntext, partial, rating", "store")
box(ax, 2.9, 0.8, 5.0, 1.2, "query engine: planner, explain(executionStats)\nCRUD, aggregation pipeline, text search", "engine")
box(ax, 8.6, 2.9, 3.2, 1.0, "benchmark.py: 6 queries x 25 runs\nbefore / after indexing", "out")
box(ax, 8.6, 1.6, 3.2, 1.0, "validation_demo.py, crud_demo.py\n(PyMongo)", "out")
box(ax, 8.6, 0.3, 3.2, 1.0, "sql_compare.py: same data in\nSQLite (4 normalised tables)", "out")
arrow(ax, (2.2, 3.4), (2.9, 3.3)); arrow(ax, (5.3, 3.25), (5.6, 3.25))
for y in (3.4, 2.1, 0.8):
    arrow(ax, (8.6, y), (7.9, 1.4))
save(fig, "fig_a4_architecture.png")
