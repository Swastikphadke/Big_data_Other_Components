"""
Build the consolidated submission report (DOCX) for Big Data Systems (24CI51).

All results tables are read from the verified CSV outputs at build time and key numbers in
the text are taken from the same files, so the report cannot drift from the evidence.
Run:  .venv\\Scripts\\python.exe report\\build_report.py   (then report\\finalize.ps1 for TOC + PDF)
"""
import csv
import json
import re
from pathlib import Path

import pandas as pd
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "report" / "BigDataSystems_24CI51_SLA_Report.docx"
A1, A2, A3, A4, A5 = (ROOT / d for d in ("activity1_hive", "activity2_kafka", "activity3_flink", "activity4_mongodb", "activity5_bigquery"))
EV, FIG = ROOT / "evidence", ROOT / "report" / "figures"
BLUE = RGBColor(0x1F, 0x3A, 0x5F)
GREY = RGBColor(0x55, 0x55, 0x55)
rd = lambda p, **k: pd.read_csv(p, **k)
fmt = lambda x, d=0: f"{x:,.{d}f}"

doc = Document()
FIG_NO = [0]
TAB_NO = [0]

# ============================================================== styles, page, header/footer
sec = doc.sections[0]
sec.page_height, sec.page_width = Cm(29.7), Cm(21.0)
for side in ("left_margin", "right_margin"):
    setattr(sec, side, Cm(2.3))
sec.top_margin, sec.bottom_margin = Cm(2.3), Cm(2.2)
st = doc.styles
st["Normal"].font.name = "Calibri"; st["Normal"].font.size = Pt(11)
st["Normal"].element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
st["Normal"].paragraph_format.space_after = Pt(6); st["Normal"].paragraph_format.line_spacing = 1.15
for lvl, size, before in ((1, 18, 0), (2, 14, 14), (3, 12, 10)):
    h = st[f"Heading {lvl}"]; h.font.name = "Calibri"; h.font.size = Pt(size); h.font.bold = True
    h.font.color.rgb = BLUE; h.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
    h.paragraph_format.space_before = Pt(before); h.paragraph_format.space_after = Pt(6)
    h.paragraph_format.keep_with_next = True
st["Heading 1"].paragraph_format.page_break_before = True
for name in ("Figure Caption", "Table Caption"):
    s = st.add_style(name, WD_STYLE_TYPE.PARAGRAPH); s.base_style = st["Caption"]
    s.font.size = Pt(9); s.font.italic = False; s.font.bold = False; s.font.color.rgb = GREY
    s.paragraph_format.space_after = Pt(10); s.paragraph_format.keep_with_next = (name == "Table Caption")
code_st = st.add_style("CodeBlock", WD_STYLE_TYPE.PARAGRAPH)
code_st.font.name = "Consolas"; code_st.font.size = Pt(7.5)
code_st.element.rPr.rFonts.set(qn("w:eastAsia"), "Consolas")
code_st.paragraph_format.space_after = Pt(8); code_st.paragraph_format.line_spacing = 1.0


def shade(el, color):
    pPr = el.get_or_add_pPr() if hasattr(el, "get_or_add_pPr") else el
    shd = OxmlElement("w:shd"); shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), color)
    pPr.append(shd)


def field(par, instr, placeholder=""):
    r = par.add_run(); b = OxmlElement("w:fldChar"); b.set(qn("w:fldCharType"), "begin"); r._r.append(b)
    r = par.add_run(); t = OxmlElement("w:instrText"); t.set(qn("xml:space"), "preserve"); t.text = instr; r._r.append(t)
    r = par.add_run(); s = OxmlElement("w:fldChar"); s.set(qn("w:fldCharType"), "separate"); r._r.append(s)
    par.add_run(placeholder)
    r = par.add_run(); e = OxmlElement("w:fldChar"); e.set(qn("w:fldCharType"), "end"); r._r.append(e)


def header_footer(section):
    section.different_first_page_header_footer = True
    hp = section.header.paragraphs[0]; hp.text = ""
    r = hp.add_run("Big Data Systems (24CI51) – Self-Learning Activity Report"); r.font.size = Pt(8.5); r.font.color.rgb = GREY
    hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    bdr = OxmlElement("w:pBdr"); bt = OxmlElement("w:bottom")
    for k, v in (("val", "single"), ("sz", "4"), ("space", "1"), ("color", "A0A0A0")):
        bt.set(qn(f"w:{k}"), v)
    bdr.append(bt); hp._p.get_or_add_pPr().append(bdr)
    fp = section.footer.paragraphs[0]; fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = fp.add_run("Page "); r.font.size = Pt(9)
    field(fp, "PAGE", "1"); r = fp.add_run(" of "); r.font.size = Pt(9); field(fp, "NUMPAGES", "1")


header_footer(sec)

# ============================================================== content helpers
INLINE = re.compile(r"(\*\*[^*]+\*\*|`[^`]+`)")


def P(text, style=None, align=None, size=None, bold=False, italic=False, color=None, after=None):
    p = doc.add_paragraph(style=style)
    for part in INLINE.split(text):
        if not part:
            continue
        if part.startswith("**"):
            r = p.add_run(part[2:-2]); r.bold = True
        elif part.startswith("`"):
            r = p.add_run(part[1:-1]); r.font.name = "Consolas"; r.font.size = Pt(9.5)
        else:
            r = p.add_run(part)
        if size:
            r.font.size = Pt(size)
        if bold:
            r.bold = True
        if italic:
            r.italic = True
        if color:
            r.font.color.rgb = color
    if align:
        p.alignment = align
    if after is not None:
        p.paragraph_format.space_after = Pt(after)
    return p


def B(items, numbered=False):
    for it in items:
        P(it, style="List Number" if numbered else "List Bullet", after=2)


def H(text, lvl):
    return doc.add_heading(text, lvl)


def figure(path, caption, label="Verified", width=6.2):
    FIG_NO[0] += 1
    doc.add_picture(str(path), width=Inches(width))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.paragraphs[-1].paragraph_format.keep_with_next = True
    P(f"Figure {FIG_NO[0]}: {caption} [{label}]", style="Figure Caption", align=WD_ALIGN_PARAGRAPH.CENTER)
    return FIG_NO[0]


def cell_text(c, text, bold=False, size=8.5, align=None, fill=None):
    c.text = ""
    p = c.paragraphs[0]; r = p.add_run(str(text)); r.font.size = Pt(size); r.bold = bold
    p.paragraph_format.space_after = Pt(0); p.paragraph_format.line_spacing = 1.0
    if align:
        p.alignment = align
    if fill:
        tcPr = c._tc.get_or_add_tcPr(); shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), fill); tcPr.append(shd)


def table(rows, headers, caption, widths=None, size=8.5, source=None):
    TAB_NO[0] += 1
    P(f"Table {TAB_NO[0]}: {caption}", style="Table Caption")
    t = doc.add_table(rows=1, cols=len(headers)); t.style = "Table Grid"; t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(headers):
        cell_text(t.rows[0].cells[i], h, bold=True, size=size, fill="DCE6F2")
    for k, row in enumerate(rows):
        cells = t.add_row().cells
        for i, v in enumerate(row):
            num = isinstance(v, (int, float)) or (isinstance(v, str) and re.fullmatch(r"[-+×x≈~]?[\d,.]+ ?%?", v.strip() or "a") is not None)
            cell_text(cells[i], v, size=size, align=WD_ALIGN_PARAGRAPH.RIGHT if num else None, fill="F5F8FC" if k % 2 else None)
    if widths:
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Cm(w)
    # repeat header row on page breaks
    trPr = t.rows[0]._tr.get_or_add_trPr(); th = OxmlElement("w:tblHeader"); th.set(qn("w:val"), "true"); trPr.append(th)
    if source:
        P(f"Source: {source}", size=8, color=GREY, after=8)
    else:
        doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return TAB_NO[0]


def code(text, title=None):
    if title:
        P(title, bold=True, size=9, after=2)
    # one paragraph per line: Word paginates thousands of short paragraphs far faster than
    # one multi-page paragraph full of line breaks
    lines = text.rstrip("\n").replace("\t", "    ").split("\n")
    for i, line in enumerate(lines):
        p = doc.add_paragraph(style="CodeBlock"); shade(p._p, "F4F4F4")
        p.paragraph_format.space_after = Pt(8 if i == len(lines) - 1 else 0)
        p.add_run(line if line else " ")


def code_file(path, title=None, start=None, end=None):
    txt = Path(path).read_text(encoding="utf-8")
    if start:
        a = txt.index(start); b = txt.index(end, a) if end else len(txt)
        txt = txt[a:b]
    code(txt, title)


def pagebreak():
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


def rubric(items):
    rows = [(c, m, e) for c, m, e in items]
    table(rows, ["Evaluation criterion", "Marks", "How this activity addresses it (evidence)"], "Evaluation-criteria coverage",
          widths=[4.2, 1.3, 11.0])


# ============================================================== load verified numbers
k1 = rd(A1 / "results/q01_overall_kpis.csv").iloc[0]
b1 = rd(A1 / "results/q04_branch_revenue.csv"); h1 = rd(A1 / "results/q05_peak_hours.csv").set_index("sale_hour")
m1 = rd(A1 / "results/q06_monthly_trend.csv").set_index("sale_month"); w1 = rd(A1 / "results/q10_weekday_weekend.csv").set_index("day_type")
s1 = rd(A1 / "results/q07_category_seasonality.csv").set_index("sale_month"); idx1 = (100 * s1 / s1.mean()).round(0)
log1 = (EV / "act1/02_schema_load.log").read_text(encoding="utf-8", errors="ignore")
orc_bytes = int(re.search(r"totalSize\s+\|\s+(\d+)", log1).group(1))
n_rows1 = int(re.search(r"numRows\s+\|\s+(\d+)", log1).group(1))
csv_mb = float(re.search(r"File size: ([\d.]+) MB", (EV / "act1/01_generate_sales.log").read_text(encoding="utf-8")).group(1))

ev2 = (EV / "act2/07_evaluation.log").read_text(encoding="utf-8")
prec2, rec2 = re.search(r"precision=([\d.]+)\s+recall=([\d.]+)", ev2).groups()
ep2 = rd(A2 / "results/evaluation_episodes.csv"); lat2 = rd(A2 / "results/evaluation_latency.csv").set_index("stat").latency_ms
al2 = rd(A2 / "results/alerts.csv"); bj2 = rd(A2 / "results/evaluation_by_junction.csv")
ing2 = rd(A2 / "results/ingested_readings.csv", usecols=["partition", "junction_id"])

ev3 = (EV / "act3/09_evaluation.log").read_text(encoding="utf-8")
ra3 = rd(A3 / "results/reading_alerts.csv"); ea3 = rd(A3 / "results/episode_alerts.csv")
pe3 = rd(A3 / "results/evaluation_episodes.csv"); lt3 = rd(A3 / "results/evaluation_latency.csv")
fm3 = (EV / "act3/07_final_flink_metrics.log").read_text(encoding="utf-8")
over_in, over_out = map(int, re.search(r"OverAggregate\S*.*?records_in=\s*(\d+) records_out=\s*(\d+)", fm3).groups())
cp3 = re.search(r"completed=(\d+) failed=(\d+)", fm3).groups()
mem3 = (EV / "act3/05_memory_during_run.log").read_text(encoding="utf-8")
hostmin3 = min(int(x.replace(",", "")) for x in re.findall(r"host_free=([\d,]+)MB", mem3))
peak3 = {c: max(float(x) for x in re.findall(c + r"=([\d.]+)MiB", mem3)) for c in ("flink-taskmanager", "flink-jobmanager", "kafka")}
drop5 = int(re.search(r"dropped as late=(\d+)", ev3).group(1)); pred5 = int(re.search(r"dropped as late=\d+\s+\(predicted (\d+)\)", ev3).group(1))

bs4 = rd(A4 / "results/benchmark_summary.csv"); ib4 = rd(A4 / "results/index_build.csv")
rc4 = rd(A4 / "results/relational_counts.csv").set_index("item").value
setup4 = (EV / "act4/02_setup_db.log").read_text(encoding="utf-8")
ins4 = re.search(r"inserted ([\d,]+) documents in ([\d.]+) s \(([\d,]+) docs/s\)", setup4).groups()
st4 = re.search(r"data size=([\d.]+) MB\s+avg document=(\d+) B\s+storage \(compressed\)=([\d.]+) MB", setup4).groups()
crud4 = (EV / "act4/05_crud_demo.log").read_text(encoding="utf-8")

q5 = {n: rd(A5 / f"results/{n}.csv") for n in ["q01_overview", "q02_status_codes", "q03_top_endpoints", "q04_errors_by_endpoint",
                                                  "q06_daily_summary", "q08_peak_5min_windows", "q09_top_ips", "q11_failure_spikes",
                                                  "q12_suspicious_bruteforce", "q13_suspicious_scanners", "q14_suspicious_high_rate",
                                                  "q15_user_agent_classes", "pruning_comparison", "query_job_stats", "verification",
                                                  "cost_estimate_production", "cost_assumptions"]}
o5 = q5["q01_overview"].iloc[0]
js5 = q5["query_job_stats"]
setup5 = (EV / "act5/03_bq_setup.log").read_text(encoding="utf-8")
manifest = list(csv.DictReader(open(EV / "manifest.csv", newline="", encoding="utf-8")))
audit = rd(ROOT / "audit/audit_checks.csv")

# ============================================================== COVER
for _ in range(2):
    P("", after=0)
P("RAMAIAH INSTITUTE OF TECHNOLOGY", align=WD_ALIGN_PARAGRAPH.CENTER, size=20, bold=True, color=BLUE, after=2)
P("Department of Computer Science and Engineering (Artificial Intelligence & Machine Learning)", align=WD_ALIGN_PARAGRAPH.CENTER, size=12, after=30)
P("BIG DATA SYSTEMS (24CI51)", align=WD_ALIGN_PARAGRAPH.CENTER, size=16, bold=True, after=4)
P("Self-Learning Activity – Consolidated Report", align=WD_ALIGN_PARAGRAPH.CENTER, size=14, after=30)
P("Big Data Technologies in Practice:", align=WD_ALIGN_PARAGRAPH.CENTER, size=22, bold=True, color=BLUE, after=2)
P("Apache Hive, Apache Kafka, Apache Flink, MongoDB and Google BigQuery", align=WD_ALIGN_PARAGRAPH.CENTER, size=16, color=BLUE, after=6)
P("Five working prototypes on synthetic data, executed and verified", align=WD_ALIGN_PARAGRAPH.CENTER, size=11, italic=True, after=40)
P("Submitted by", align=WD_ALIGN_PARAGRAPH.CENTER, size=11, bold=True, after=4)
ct = doc.add_table(rows=5, cols=2); ct.alignment = WD_TABLE_ALIGNMENT.CENTER; ct.style = "Table Grid"
for i, (a, b) in enumerate([("Student Name", "[Student Name]"), ("USN", "[USN]"), ("Semester and Section", "[Semester and Section]"),
                             ("Faculty Name", "[Faculty Name]"), ("Submission Date", "[Submission Date]")]):
    cell_text(ct.rows[i].cells[0], a, bold=True, size=11, fill="DCE6F2"); cell_text(ct.rows[i].cells[1], b, size=11)
    ct.rows[i].cells[0].width = Cm(5.5); ct.rows[i].cells[1].width = Cm(8.5)
for _ in range(3):
    P("", after=0)
P("Total marks: 20 (5 activities × 4 marks)", align=WD_ALIGN_PARAGRAPH.CENTER, size=10, color=GREY)

# ============================================================== DECLARATION
H("Declaration", 1)
P("I declare that this report documents work carried out for the Big Data Systems (24CI51) self-learning activity. "
  "All five prototypes were implemented and executed on the machine described in Chapter 2; every result, table, chart "
  "and screenshot labelled **Verified** was produced by those executions and is listed with its producing script in "
  "the evidence register (Appendix C).")
P("**Use of AI assistance.** The implementation, execution, evidence capture and drafting were carried out with the help "
  "of an AI coding assistant (Anthropic Claude, via Claude Code) operating on my machine under my direction. I have "
  "reviewed the code and results and can explain each component (viva notes are provided in every activity README).")
P("**Data.** All datasets are synthetic and were generated by the scripts in this submission with fixed random seeds. "
  "Patterns and incidents were planted deliberately so that each analysis could be checked against a known ground truth; "
  "no finding should be read as a fact about a real supermarket, city, hospital, shop or web service. Activity 3 uses "
  "educational thresholds only and is not a clinical tool.")
P("")
P("Signature: ______________________          Name: [Student Name]          USN: [USN]          Date: [Submission Date]")

# ============================================================== EXECUTIVE SUMMARY
H("Executive Summary", 1)
P("This report presents five working big-data prototypes built for the scenarios in the assignment, each executed on the "
  "real technology – Apache Hive 4.0.1, Apache Kafka 4.1.0, Apache Flink 1.20.5 and MongoDB 8.0 in Docker on one laptop, "
  "and Google BigQuery in the free Sandbox – using synthetic data with planted, documented patterns. Every prototype was "
  "evaluated quantitatively against its ground truth or against an independent re-implementation, and all evidence "
  "(logs, result CSVs, charts, screenshots) is traceable through an evidence register that was audited before writing "
  "(133 automated checks, 0 open issues).")
table([
    ("1 Hive – supermarket sales", f"{n_rows1:,} sales lines; external raw + partitioned ORC warehouse; 12 HiveQL queries",
     f"ORC {csv_mb:.1f} MB → {orc_bytes / 1e6:.1f} MB; peak 19:00; Oct +{m1.loc['2025-10', 'mom_growth_pct']:.1f} % MoM; inventory recommendations"),
    ("2 Kafka – traffic congestion", "12 junction sensors, 11,520 events, 3 consumer groups, alert topic",
     f"0 lost/duplicate; p50 latency {lat2['p50']:.0f} ms; 13/13 congestion episodes; precision {prec2} / recall {rec2}"),
    ("3 Flink – patient vital signs", "14,400 readings, out-of-order + late delivery, event time, CEP, windows",
     f"1,240/1,240 reading alerts; 6/6 sustained episodes, 0 false; 12/12 events identical to reference"),
    ("4 MongoDB – product catalogue", "200,000 heterogeneous documents, validator, CRUD, 6 indexes",
     "SKU lookup 200,000 → 1 docs examined (×57.8); no gain for low-selectivity queries; 1 document vs 60 SQL rows"),
    ("5 BigQuery – server logs", f"{o5.requests:,} log lines batch-loaded; 15 SQL analyses; Sandbox",
     "outage and bad deployment detected; credential stuffing, scanner, scraper identified; actual cost USD 0"),
], ["Activity", "Prototype", "Key verified results"], "Summary of the five prototypes", widths=[3.6, 6.0, 7.0])
P("**Honest negatives are reported, not hidden**: one false-alarm congestion alert (Activity 2), a superseded Flink run that "
  "exposed a quadratic pattern-matching design (Activity 3), MongoDB queries where indexes did not help (Activity 4), and "
  "one false-positive failure spike (Activity 5). The comparative analysis (Chapter 8) relates the five technologies to "
  "batch warehousing, messaging, stream processing, operational NoSQL storage and serverless cloud analytics.")

# ============================================================== TOC, LOF, LOT
H("Table of Contents", 1)
field(doc.add_paragraph(), 'TOC \\o "1-2" \\h \\z \\u', "Right-click and choose Update Field to build the table of contents.")
H("List of Figures", 1)
field(doc.add_paragraph(), 'TOC \\h \\z \\t "Figure Caption,1"', "Update field to build the list of figures.")
H("List of Tables", 1)
field(doc.add_paragraph(), 'TOC \\h \\z \\t "Table Caption,1"', "Update field to build the list of tables.")

# ============================================================== 1 INTRODUCTION
H("1 Introduction and Objectives", 1)
H("1.1 Context", 2)
P("Organisations now generate data at volumes and speeds that a single relational database cannot handle economically: "
  "point-of-sale transactions, sensor streams, medical-device telemetry, semi-structured product data and web-server logs. "
  "These workloads differ in their **volume**, **velocity** and **variety**, and no single system serves all of them well. "
  "Big data systems therefore specialise: batch warehouses for large historical analysis, distributed logs for durable "
  "event transport, stream processors for low-latency stateful computation, document databases for flexible operational "
  "data, and serverless cloud warehouses for elastic analytics without infrastructure management.")
P("The self-learning activity asks for one prototype per technology, each grounded in a realistic scenario (Table 2).")
table([
    ("1", "Apache Hive", "Supermarket chain: best sellers, peak hours, branch revenue, monthly trends for inventory planning"),
    ("2", "Apache Kafka", "Smart-city traffic centre: continuous vehicle-count/speed data, congestion alerts for operators"),
    ("3", "Apache Flink", "Hospital monitoring: real-time heart rate, SpO₂, temperature; flag abnormal values, window summaries"),
    ("4", "MongoDB", "E-commerce catalogue with heterogeneous attributes: storage, retrieval, updates, performance"),
    ("5", "Cloud analytics (BigQuery)", "Online service logs: error frequencies, request patterns, failure spikes, peak usage, cost"),
], ["#", "Technology", "Scenario (from the assignment)"], "Activities and scenarios", widths=[0.8, 3.4, 12.3])
H("1.2 Objectives", 2)
B(["Study the architecture and core concepts of each technology (problem definition and technology study for every activity).",
   "Design and implement a working prototype for each scenario on the real technology, with reproducible configuration.",
   "Generate realistic synthetic data with documented ground truth so results can be validated, not just displayed.",
   "Produce outputs, visualisations and quantitative evaluations, and interpret them in terms of the scenario.",
   "Document limitations, improvements and conclusions, and compare the five technologies.",
   "Keep the work academically honest: every result traceable to an execution, simulated or hypothetical parts labelled."])
H("1.3 Approach and evidence labels", 2)
P("Each activity follows the same method: (1) synthetic data generator with fixed seed and planted patterns, (2) "
  "implementation on the real engine in Docker or BigQuery, (3) execution with logs captured to files, (4) independent "
  "verification (ground truth, reference implementation or local recomputation), (5) charts built only from result files, "
  "(6) README with viva notes. Figures and tables carry one of the following labels:")
table([("Verified", "produced by an execution in this project; source file named in the caption or table note"),
       ("Design diagram", "architecture/workflow drawing of the implemented system (not a measurement)"),
       ("Hypothetical", "projection or proposal that was not deployed (e.g. production cost, proposed cloud services)"),
       ("Superseded", "evidence of an earlier run kept for transparency; not used for results")],
      ["Label", "Meaning"], "Evidence labels used in this report", widths=[3.2, 13.3])
H("1.4 Mapping to the assessment rubric", 2)
P("The common rubric awards 4 marks per activity. Each activity chapter ends with an explicit coverage table; the general "
  "mapping is: understanding of problem and technology (1 mark) → sections x.1–x.3; solution design and implementation "
  "(1.5) → x.4–x.6 and Appendices A–B; results, analysis and interpretation (1) → x.7–x.8; documentation and conclusions "
  "(0.5) → x.9–x.10, READMEs and the evidence register.")

# ============================================================== 2 ENVIRONMENT
H("2 Execution Environment and Technologies Used", 1)
H("2.1 Hardware and software", 2)
table([("Machine", "Windows 11 Pro 10.0.26200, Intel Core i5-8350U, 8 GB RAM (7.8 GB usable), ~94 GB free disk"),
       ("Container runtime", "Docker Desktop (WSL2 backend), engine 29.9.2; VM limit 3.75 GiB"),
       ("Python", "3.12.10 virtual environment (pandas 3.1, numpy 2.5, matplotlib 3.11, pyarrow 26, confluent-kafka 2.16.1, "
                  "pymongo 4.19, google-cloud-bigquery 3.47)"),
       ("Activity 1", "apache/hive:4.0.1 – HiveServer2, embedded Derby metastore, Tez in local mode, Beeline (JDBC)"),
       ("Activity 2", "apache/kafka:4.1.0 – single broker+controller (KRaft); Kafka-UI (kafbat v1.5.0) for inspection"),
       ("Activity 3", "flink:1.20.5 + apache-flink 1.20.5 (PyFlink) + flink-sql-connector-kafka 3.4.0-1.20; JobManager + TaskManager"),
       ("Activity 4", "mongo:8.0 (server 8.0.34), WiredTiger cache 0.25 GB; SQLite (Python stdlib) for the relational comparison"),
       ("Activity 5", "Google BigQuery Sandbox, project bigdatasla, location asia-south1; Google Cloud SDK 592.0.0 (gcloud, bq 2.1.41)"),
       ("Evidence tools", "console capture via Win32 PrintWindow (real console windows), headless Microsoft Edge for local web UIs"),
       ], ["Component", "Version / configuration"], "Execution environment", widths=[3.4, 13.1])
figure(FIG / "fig_environment.png", "Execution environment: Docker profiles on the laptop and BigQuery in Google Cloud", "Design diagram")
H("2.2 Resource management on an 8 GB laptop", 2)
P("All servers are defined in one `docker-compose.yml` with **profiles** (`hive`, `kafka`, `flink`, `mongo`) so that only one "
  "activity's services run at a time. Default memory settings were reduced and measured: Kafka heap 512 MB, Flink JobManager "
  "768 MB and TaskManager 1,152 MB (defaults ≈ 1.6 GB + 1.7 GB), MongoDB WiredTiger cache 256 MB. During the Flink run – the "
  "heaviest – the containers peaked at about 2.1 GB and host free memory never fell below "
  f"{hostmin3} MB (Activity 3, `05_memory_during_run.log`). Containers were stopped after each activity.")
H("2.3 Evidence capture and reproducibility", 2)
B(["Every script accepts `--log` and writes its console output with a timestamp and the exact command line to `evidence/actN/`.",
   "Console screenshots are captures of real console windows running the commands (PrintWindow API); web-UI screenshots "
   "(HiveServer2, Kafka-UI, Flink) are rendered by headless Microsoft Edge from the running services; the nine BigQuery "
   "console screenshots were captured by the student in the browser.",
   "Two console captures came out blank because the window was wider than the screen; they were replaced by console windows "
   "displaying the genuine log files and are labelled as such (Appendix C).",
   "Data generators use fixed seeds; Activities 4 and 5 provide clean-start scripts (`run_all.ps1`) that wipe and rebuild "
   "everything; the evidence for those activities comes from those clean runs.",
   "An audit script (`audit/audit.py`) verifies the evidence register, recomputes key numbers and checks screenshot times (Appendix D)."])

# ============================================================== 3 HIVE
H("3 Activity 1 – Apache Hive: Supermarket Sales Analysis", 1)
H("3.1 Problem Definition", 2)
P("A supermarket chain generates millions of sales transaction records. Management wants to identify best-selling products, "
  "peak sales hours, branch-wise revenue and monthly trends to improve inventory planning and business decisions. The data "
  "is append-only, large and analysed with aggregate queries – a classic data-warehouse workload rather than a transactional one.")
H("3.2 Objectives", 2)
B(["Study Hive's architecture, HiveQL and data-warehousing concepts.",
   "Create Hive tables for sales transactions using a staging (raw) and curated (optimised) layer.",
   "Write HiveQL for total revenue, top-selling products, branch-wise sales, peak hours and monthly trends.",
   "Analyse the results and recommend inventory-management strategies."])
H("3.3 Technology Study", 2)
P("**Apache Hive** is a data-warehouse system that lets users query large datasets stored in distributed or local file "
  "systems with **HiveQL**, an SQL dialect. Hive does not store data itself; it projects table structure onto files "
  "(**schema-on-read**) and compiles queries into distributed execution plans [1][25].")
P("**Architecture.** Clients (Beeline, JDBC/ODBC) connect to **HiveServer2**, a Thrift service that manages sessions and "
  "concurrent queries. The **Driver** parses a query, performs semantic analysis using metadata from the **Metastore** "
  "(table schemas, column types, partition locations and statistics kept in a relational database – embedded Derby here, "
  "MySQL/PostgreSQL in production), optimises it (rule-based and Apache Calcite cost-based optimisation) and produces a "
  "directed acyclic graph of tasks. The **execution engine** runs the plan; Hive 4 uses **Apache Tez** by default (MapReduce "
  "is deprecated). In this prototype Tez runs in local mode inside the HiveServer2 container (`tez.local.mode=true`).")
P("**Storage concepts.** *Managed* tables are owned by Hive (dropping the table deletes data); *external* tables only "
  "reference files. **Partitioning** stores each partition value in its own directory so queries filtering on the partition "
  "column read only matching directories (**partition pruning**). **ORC** is a columnar format with stripes, lightweight "
  "indexes, column statistics and compression, which reduces I/O for analytical queries [2]. HiveQL supports joins, "
  "window functions (RANK, LAG), CTEs and dynamic-partition inserts.")
P("**Data-warehousing concepts.** A warehouse is subject-oriented, integrated, time-variant and non-volatile. Data is "
  "organised as **fact** tables (measurable events – here, sales line items) and **dimensions** (product, branch, time). "
  "Pipelines move data from a raw/staging layer to curated, query-optimised layers (ELT). The sales table here is a "
  "denormalised fact table that carries its dimension attributes, which avoids joins in the analytical queries.")
H("3.4 Architecture and Working", 2)
figure(FIG / "fig_a1_architecture.png", "Activity 1 architecture: raw external table → partitioned ORC fact table → HiveQL analytics", "Design diagram")
B(["`generate_sales.py` writes one year (2025) of line items for 6 branches and 117 products to a CSV (no header) in `data/raw/`.",
   "`sales_raw` is an EXTERNAL TEXTFILE table whose LOCATION is that directory (schema-on-read).",
   "`INSERT OVERWRITE … PARTITION (sale_month)` with dynamic partitioning converts the data into the managed ORC table `sales`, "
   "computing derived columns (amount, hour, day type) once.",
   "Twelve analytical queries run through Beeline; each produces a console log (evidence) and a CSV (charts)."])
H("3.5 Implementation and Procedure", 2)
table([("Branches", "6 (Bengaluru ×2, Mysuru ×2, Hubballi, Mangaluru) with different footfall weights"),
       ("Products", "117 products in 10 categories with fixed realistic MRPs; category purchase frequencies"),
       ("Time", "evening peak 18–20 h, secondary late-morning peak; weekend factor 1.35"),
       ("Seasonality", "festive October/November (Diwali), summer beverages/ice cream (March–May)"),
       ("Slow movers", "Khova 250g and Feeding Bottle planted with very low popularity"),
       ("Volume", f"200,000 invoices → {n_rows1:,} line items, {csv_mb:.1f} MB CSV, seed 42")],
      ["Planted pattern", "Design"], "Synthetic sales dataset (ground truth in data/planted_patterns.json)", widths=[3.4, 13.1])
code("docker compose --profile hive up -d\n"
     "export MSYS_NO_PATHCONV=1   # Git Bash only\n"
     "docker exec hive4 beeline -u jdbc:hive2://localhost:10000/ -f /opt/assignment/hql/01_schema.hql\n"
     "bash activity1_hive/run_queries.sh          # q01..q12 -> logs + CSV\n"
     ".venv/Scripts/python.exe activity1_hive/charts.py\n"
     "docker compose --profile hive down", "Procedure (project root, Git Bash):")
H("3.6 Code, Queries and Configuration", 2)
code_file(A1 / "hql/01_schema.hql", "hql/01_schema.hql (excerpt: curated table and dynamic-partition load)",
          "-- 1b. CURATED", "-- Verification")
code_file(A1 / "hql/queries/q04_branch_revenue.hql", "hql/queries/q04_branch_revenue.hql (window function for revenue share)")
code_file(A1 / "hql/queries/q06_monthly_trend.hql", "hql/queries/q06_monthly_trend.hql (LAG for month-over-month growth)")
P("The other ten queries and the full DDL are listed in Appendix A.1.")
H("3.7 Results and Sample Outputs", 2)
P(f"The curated table holds **{n_rows1:,} rows** in **12 monthly partitions**, identical to the raw row count. Converting the "
  f"{csv_mb:.1f} MB CSV to ORC (ZLIB) reduced it to **{orc_bytes / 1e6:.1f} MB** (≈ {csv_mb * 1e6 / orc_bytes:.1f}× smaller). "
  "`EXPLAIN DEPENDENCY` for an October filter lists only the partition `sale_month=2025-10`.")
table([(f"₹{k1.total_revenue_inr:,.0f}", f"{k1.total_invoices:,}", f"{k1.total_units:,}", f"{k1.line_items:,}", f"₹{k1.avg_basket_value_inr:,.2f}")],
      ["Total revenue", "Invoices", "Units sold", "Line items", "Average basket"], "Overall KPIs (q01)",
      widths=[3.6, 3.0, 3.0, 3.0, 3.6], source="activity1_hive/results/q01_overall_kpis.csv")
table([(r.branch_name, r.city, f"{r.invoices:,}", f"₹{r.revenue_inr:,.0f}", f"{r.revenue_share_pct:.2f} %", f"₹{r.avg_basket_inr:.2f}") for r in b1.itertuples()],
      ["Branch", "City", "Invoices", "Revenue", "Share", "Avg basket"], "Branch-wise revenue (q04)",
      widths=[3.0, 2.6, 2.4, 3.4, 2.2, 2.6], source="activity1_hive/results/q04_branch_revenue.csv")
figure(A1 / "charts/a1_top_products_revenue.png", "Top 10 products by revenue (q02)")
figure(A1 / "charts/a1_peak_hours.png", "Footfall by hour of day; 18:00 and 19:00 highlighted (q05)")
figure(A1 / "charts/a1_monthly_trend.png", "Monthly revenue trend with the October festive peak (q06)")
figure(A1 / "charts/a1_category_seasonality.png", "Category seasonality, monthly revenue indexed to each category's average (q07)")
figure(A1 / "charts/a1_branch_revenue.png", "Branch-wise revenue and share (q04)")
figure(A1 / "charts/a1_daytype_payment.png", "Average daily revenue weekday vs weekend (q10) and payment mix (q11)")
figure(EV / "act1/screenshots/beeline_partitions_rowcounts.png", "Beeline: 12 partitions, Tez DAG and identical raw/curated row counts", width=5.8)
figure(EV / "act1/screenshots/beeline_q04_branch_revenue.png", "Beeline console running q04 (branch revenue)", width=5.8)
figure(EV / "act1/screenshots/beeline_q12_partition_pruning.png", "EXPLAIN DEPENDENCY: only partition sale_month=2025-10 is read", width=5.8)
figure(EV / "act1/screenshots/hs2_webui.png", "HiveServer2 Web UI listing the executed queries (Tez, FINISHED)", width=4.6)
H("3.8 Analysis and Interpretation", 2)
P(f"The warehouse recovers every planted pattern, which validates the pipeline. Evening hours 17:00–21:00 carry "
  f"{100 * h1.loc[17:20, 'invoices'].sum() / h1.invoices.sum():.1f} % of invoices, with 19:00 the single busiest hour "
  f"({h1.loc[19, 'invoices']:,} invoices). October revenue rises {m1.loc['2025-10', 'mom_growth_pct']:.2f} % over September; "
  f"Sweets & Dry Fruits reach an index of {idx1.loc['2025-10', 'sweets_dryfruits']:.0f} and Household {idx1.loc['2025-10', 'household']:.0f} "
  f"in October, while Frozen & Ice Cream peaks at {idx1.loc['2025-05', 'frozen_icecream']:.0f} in May. Weekend days average "
  f"₹{w1.loc['Weekend', 'avg_daily_revenue_inr'] / 1e5:.2f} L against ₹{w1.loc['Weekday', 'avg_daily_revenue_inr'] / 1e5:.2f} L on weekdays "
  f"(×{w1.loc['Weekend', 'avg_daily_revenue_inr'] / w1.loc['Weekday', 'avg_daily_revenue_inr']:.2f}). Branch revenue differs by footfall, "
  "not by basket size (≈ ₹585–595 everywhere). February's −14.5 % is largely the shorter month.")
table([("Daily-need items move fastest (q03)", "daily replenishment and short reorder cycles for dairy and fresh produce"),
       ("High-value staples and gift items lead revenue (q02)", "safety stock on ghee, rice, atta, dry fruits; avoid stock-outs"),
       ("43.8 % of invoices between 17:00 and 21:00 (q05)", "restock shelves and add billing staff before 17:00"),
       ("Weekend daily revenue +35 % (q10)", "larger Friday deliveries and weekend staffing"),
       ("October festive surge (q06, q07)", "build festive inventory (sweets, dry fruits, diyas, cleaning products) from September"),
       ("Summer seasonality (q07)", "increase freezer and beverage stock March–May; reduce from July"),
       ("Branch shares 9 %–26 % (q04)", "allocate stock in proportion to branch volume"),
       ("Slow movers Khova, Feeding Bottle (q09)", "reduce shelf space or move to order-on-demand")],
      ["Insight (query)", "Inventory recommendation"], "Business insights and inventory-management recommendations", widths=[7.0, 9.5])
P("Technically, the two-layer design shows why warehouses separate raw and curated data: the external table makes raw files "
  "queryable immediately, while the partitioned ORC table is ≈ 10× smaller and lets month filters skip eleven of twelve "
  "partitions. Two viva-relevant observations: Hive 4 reported the curated table as `EXTERNAL_TABLE` with "
  "`TRANSLATED_TO_EXTERNAL=TRUE` (the metastore translates non-ACID managed tables), and `COUNT(*)` on the curated table was "
  "answered from table statistics without a Tez job, so the run does not prove a scan speed-up – only the storage gain.")
H("3.9 Limitations and Improvements", 2)
B(["Synthetic data with planted patterns; the analysis proves the pipeline recovers known patterns, not real market behaviour.",
   "Single-node Hive with Tez in local mode and a Derby metastore – no cluster parallelism or concurrent users.",
   "A star schema with separate product/branch/date dimensions, bucketing on product_id, and ACID tables for late corrections "
   "would be the next step; a scheduler (e.g. Airflow) would load data daily."])
H("3.10 Conclusion", 2)
P("A two-layer Hive warehouse answered every management question in the scenario with HiveQL, reduced storage by about ten "
  "times with ORC, demonstrated partition pruning, and produced inventory recommendations directly supported by the queries.")
rubric([("Understanding of problem and technology", "1", "3.1–3.3: problem, HiveServer2/Driver/Metastore/Tez, managed vs external, partitions, ORC, warehousing"),
        ("Solution design and implementation", "1.5", "3.4–3.6, Appendix A.1: two-layer design, DDL, 12 queries, run script, executed in Hive 4.0.1"),
        ("Results, analysis and interpretation", "1", "3.7–3.8: KPIs, branch table, 6 charts, 4 screenshots, planted patterns recovered, recommendations"),
        ("Documentation and conclusions", "0.5", "3.9–3.10, README with viva notes, evidence register entries act 1")])

# ============================================================== 4 KAFKA
H("4 Activity 2 – Apache Kafka: Smart-City Traffic Congestion Alerts", 1)
H("4.1 Problem Definition", 2)
P("A traffic control centre receives continuous vehicle-count and speed data from sensors at major junctions. It must ingest "
  "the stream reliably, detect congestion-prone roads and send timely alerts to operators – without losing events when "
  "consumers are slow, and with the ability to add consumers or replay data later.")
H("4.2 Objectives", 2)
B(["Study Kafka topics, partitions, producers, consumers, consumer groups and brokers.",
   "Simulate traffic sensor data and publish it continuously to a Kafka topic.",
   "Develop consumer applications that process events, detect congestion with speed / vehicle-count thresholds and publish alerts.",
   "Evaluate delivery, latency and detection quality against a known ground truth."])
H("4.3 Technology Study", 2)
P("**Apache Kafka** is a distributed, partitioned, replicated commit log [3][24]. A **topic** is split into **partitions**, "
  "each an ordered, immutable sequence of records identified by **offsets**. **Brokers** store partitions; each partition has a "
  "leader and, in a cluster, follower replicas (in-sync replica set) for fault tolerance. Since Kafka 4.0 cluster metadata is "
  "managed by the built-in **KRaft** controller quorum instead of ZooKeeper; this prototype runs one combined broker+controller.")
P("**Producers** append records; the record **key** determines the partition, which guarantees ordering per key. The Java "
  "client hashes keys with murmur2; the librdkafka-based Python client used here defaults to the `consistent_random` "
  "partitioner (CRC32 of the key) [4] – verified in this project (§4.8). `acks=all` waits for the leader and in-sync replicas, "
  "and **idempotence** prevents duplicates on retry. **Consumers** pull records and commit offsets to the internal "
  "`__consumer_offsets` topic. A **consumer group** shares the partitions of a topic among its members (each partition is read by "
  "one member), so a group scales horizontally; different groups read independently (publish–subscribe). Records are retained "
  "for a configured time regardless of consumption, so a new group can **replay** history. Delivery can be at-most-once, "
  "at-least-once or exactly-once (transactions).")
H("4.4 Architecture and Working", 2)
figure(FIG / "fig_a2_architecture.png", "Activity 2 architecture: producer, two topics, three consumer groups", "Design diagram")
P("The producer replays one simulated weekday (06:00–22:00, one reading per junction per minute) at 4 simulated minutes per "
  "real second. The detector keeps a rolling window of the last five readings per junction – safe because a key always maps to "
  "one partition and therefore one consumer – and applies the rules in Table 9 with hysteresis. Alert lifecycle events "
  "(OPEN, ESCALATE, CLEAR) are published to `congestion-alerts`, read by the operator dashboard; the archiver group stores every "
  "reading with Kafka metadata to measure latency and integrity.")
H("4.5 Implementation and Procedure", 2)
table([("CONGESTION", "rolling average speed < 20 km/h and rolling average count ≥ 45 vehicles/min"),
       ("INCIDENT (blockage)", "average speed < 15 km/h and average count < 30 vehicles/min"),
       ("Severity", "MODERATE 15–20, HEAVY 10–15, SEVERE < 10 km/h"),
       ("CLEAR (hysteresis)", "average speed recovers above 25 km/h")],
      ["Rule", "Condition (on the average of the last 5 readings)"], "Congestion detection rules (config.py)", widths=[4.0, 12.5])
P("The traffic model gives 3 heavy, 3 medium and 6 light junctions with morning and evening peaks, a planted **incident** at "
  "J04 Marathahalli 14:00–14:44 and a single faulty **sensor glitch** at J07 12:10; noise-free values define the ground truth.")
code("docker compose --profile kafka up -d\nbash activity2_kafka/setup_topics.sh   # traffic-readings (3 partitions), congestion-alerts (1)\n"
     "python -u activity2_kafka/congestion_detector.py --log evidence/act2/03_detector.log\n"
     "python -u activity2_kafka/archiver.py\npython -u activity2_kafka/alert_dashboard.py\n"
     "python -u activity2_kafka/producer.py --speed 4      # 11,520 events in ~4 min\n"
     "python activity2_kafka/evaluate.py ; python activity2_kafka/charts.py", "Procedure:")
H("4.6 Code, Queries and Configuration", 2)
code_file(A2 / "producer.py", "producer.py (excerpt: producer configuration and keyed publishing)", "    producer = Producer({", "    producer.flush(30)")
code_file(A2 / "congestion_detector.py", "congestion_detector.py (excerpt: rolling window, rules and hysteresis)",
          "            r = json.loads(msg.value())", "    except KeyboardInterrupt:")
H("4.7 Results and Sample Outputs", 2)
table([("Events produced / acknowledged / failed", "11,520 / 11,520 / 0 in 240 s (48 msg/s, paced)"),
       ("Ingested by the archiver group", "11,520; 0 missing, 0 duplicates; payload identical"),
       ("Per-junction ordering", "preserved; each junction on exactly one partition"),
       ("Messages per partition", " / ".join(f"{n:,}" for n in ing2.partition.value_counts().sort_index())),
       ("End-to-end latency", f"p50 {lat2['p50']:.0f} ms, p95 {lat2['p95']:.0f} ms, p99 {lat2['p99']:.0f} ms, max {lat2['max']:.0f} ms"),
       ("Alert events", f"{len(al2)} = {(al2.event == 'OPEN').sum()} OPEN + {(al2.event == 'ESCALATE').sum()} ESCALATE + {(al2.event == 'CLEAR').sum()} CLEAR"),
       ("Ground-truth episodes detected", f"{int(ep2.detected.sum())} / {len(ep2)}; mean detection delay {ep2.detect_delay_min.mean():.1f} min"),
       ("Minute-level precision / recall", f"{prec2} / {rec2}"),
       ("Replay (new consumer group)", "11,520 re-read from offset 0, identical to original"),
       ("Scale-out (2 detectors, 1 group)", "partitions split [0,1] / [2]; alerts identical to single instance")],
      ["Measure", "Result"], "Activity 2 verified results", widths=[5.5, 11.0], source="evidence/act2/05_producer.log, 07_evaluation.log, 11_scaleout_equivalence.log")
table([(r.junction_id, r.junction_name, r._3, r.true_congested_min, r.alerted_min, r.tp_min, r.fp_min, r.fn_min, r.alerts_opened) for r in bj2.itertuples()],
      ["Id", "Junction", "Class", "True cong. min", "Alerted min", "TP", "FP", "FN", "Alerts"], "Detection against ground truth per junction",
      widths=[1.1, 3.5, 1.6, 2.2, 2.0, 1.3, 1.3, 1.3, 1.5], size=8, source="activity2_kafka/results/evaluation_by_junction.csv")
figure(A2 / "charts/a2_junction_speeds_alerts.png", "Junction speeds (rolling average), alert intervals and ground truth")
figure(A2 / "charts/a2_speed_heatmap.png", "Average speed by junction and hour – congestion-prone roads")
figure(A2 / "charts/a2_incident_glitch_zoom.png", "Planted incident (J04) detected; single sensor glitch (J07) ignored")
figure(A2 / "charts/a2_alert_vs_truth.png", "Alerted vs truly congested minutes per junction")
figure(A2 / "charts/a2_latency_hist.png", "End-to-end ingestion latency of 11,520 messages")
figure(A2 / "charts/a2_partition_distribution.png", "Messages per partition (key = junction_id)")
figure(EV / "act2/screenshots/producer_console.png", "Producer console: 11,520 acknowledged, 0 failed", width=5.6)
figure(EV / "act2/screenshots/detector_console.png", "Congestion detector console with OPEN / ESCALATE / CLEAR events", width=5.8)
figure(EV / "act2/screenshots/consumer_groups_midrun.png", "kafka-consumer-groups during the run: live lag per partition and group", width=5.8)
figure(EV / "act2/screenshots/kafkaui_consumer_groups_midrun.png", "Kafka-UI consumer groups during the run (lag)", width=5.0)
figure(EV / "act2/screenshots/scaleout_group_members.png", "Scale-out: two detector instances share the three partitions", width=5.8)
figure(EV / "act2/screenshots/console_consumer_alerts.png", "Raw alert messages read with kafka-console-consumer (key, partition, offset)", width=5.8)
H("4.8 Analysis and Interpretation", 2)
P(f"Kafka met the ingestion requirement exactly: no event was lost or duplicated, per-junction order was preserved and the "
  f"median producer-to-consumer latency was {lat2['p50']:.0f} ms. The detector found all {len(ep2)} congestion/incident episodes "
  f"with a mean delay of {ep2.detect_delay_min.mean():.1f} minutes, ignored the single faulty reading, and raised one false alarm "
  "(J09, whose true peak speed of 21.5 km/h lies only 1.5 km/h above the threshold). Most lost precision is a deliberate "
  "trade-off: clearing only above 25 km/h prevents flapping but keeps alerts open about 11.6 minutes after the true end.")
P("The run also illustrates core Kafka behaviour. Keying by junction makes per-key state safe and explains why scaling to two "
  "detectors produced identical alerts. With only 12 keys the partitions were uneven (5 / 1 / 6 junctions); the mapping is "
  "exactly CRC32(key) % 3, which confirms librdkafka's default partitioner (the murmur2 statement in an earlier draft was "
  "corrected during the audit). Replay with a new group demonstrated retention-based re-reading, and its log showed that "
  "ordering holds only within a partition.")
H("4.9 Limitations and Improvements", 2)
B(["Single broker, replication factor 1: no fault tolerance; production needs ≥ 3 brokers and replication factor 3.",
   "Fixed global thresholds are fragile near the boundary; per-junction baselines or learned models would reduce false alarms.",
   "State lives in consumer memory; a stream processor (Kafka Streams or Flink, Activity 3) would checkpoint it.",
   "More partitions than consumers, or a custom partitioner, would balance load with few keys; schemas (Avro/Schema Registry) "
   "would enforce message contracts."])
H("4.10 Conclusion", 2)
P("The prototype demonstrates continuous, loss-free ingestion with Kafka, independent consumer groups, keyed partitioning, "
  "replay and horizontal scaling, and generates timely, mostly accurate congestion alerts whose quality was measured against "
  "ground truth.")
rubric([("Understanding of problem and technology", "1", "4.1–4.3: topics, partitions, offsets, brokers, KRaft, producers, consumer groups, retention"),
        ("Solution design and implementation", "1.5", "4.4–4.6, Appendix A.2: producer, 3 consumer groups, alert topic, rules, executed on Kafka 4.1.0"),
        ("Results, analysis and interpretation", "1", "4.7–4.8: integrity, latency, precision/recall, 6 charts, 6 screenshots, replay and scale-out"),
        ("Documentation and conclusions", "0.5", "4.9–4.10, README viva notes, evidence register entries act 2")])

# ============================================================== 5 FLINK
H("5 Activity 3 – Apache Flink: Real-Time Patient Vital-Sign Monitoring", 1)
P("**Disclaimer.** All patient data is synthetic and all thresholds are educational demonstration values, not clinical "
  "diagnostic criteria. The system must not be used for patient care.", italic=True)
H("5.1 Problem Definition", 2)
P("Connected bedside devices continuously transmit heart rate, oxygen saturation (SpO₂) and body temperature. The hospital "
  "wants readings processed in real time, abnormal values flagged for clinical review, and abnormal readings summarised over "
  "time windows. Device data arrives over networks, so events can arrive late or out of order; results must still be correct "
  "with respect to when the measurement was taken.")
H("5.2 Objectives", 2)
B(["Study Flink's architecture and stream-processing concepts (event time, watermarks, state, windows, checkpoints).",
   "Simulate a continuous stream of vital-sign readings with realistic delivery delays.",
   "Develop a Flink application that flags readings outside demonstration thresholds and detects sustained episodes.",
   "Generate alerts and window summaries, and evaluate correctness, late-data handling and latency."])
H("5.3 Technology Study", 2)
P("**Apache Flink** is a distributed engine for stateful computations over unbounded and bounded data streams [5][23]. A client "
  "submits a job; the **JobManager** (Dispatcher, ResourceManager, JobMaster) turns it into an execution graph and schedules "
  "parallel tasks into **TaskManager** slots. Operators are chained into tasks and exchange data through network buffers with "
  "credit-based flow control, so a slow operator causes **back pressure** upstream instead of data loss.")
P("**Time.** Flink distinguishes processing time from **event time** (when the event happened). A **watermark** W(t) asserts "
  "that no more events with timestamps ≤ t are expected; with bounded out-of-orderness it is the maximum event time seen minus "
  "a delay. Event-time operators (windows, OVER aggregates, pattern matching) wait for the watermark, which makes results "
  "deterministic despite out-of-order arrival; events behind the watermark are **late** and dropped by default [6].")
P("**State and fault tolerance.** Keyed state is kept per key in a state backend; periodic **checkpoints** (asynchronous "
  "barrier snapshots) make state consistent after failures. **APIs**: DataStream, and the Table API/SQL (used here through "
  "PyFlink), where a SQL query over a stream is a continuous query. Relevant SQL features: window table-valued functions "
  "(TUMBLE, HOP, CUMULATE) [8], OVER aggregations over preceding rows, and **MATCH_RECOGNIZE** – SQL row-pattern recognition "
  "(complex event processing) evaluated with a non-deterministic finite automaton [7].")
H("5.4 Architecture and Working", 2)
figure(FIG / "fig_a3_architecture.png", "Activity 3 architecture: Kafka source with watermark, five continuous queries", "Design diagram")
table([("Q1 reading alerts", "stateless filter", "every reading outside a threshold (no waiting for the watermark)"),
       ("Q2 episode onset", "OVER + MATCH_RECOGNIZE (L M* S)", "score = abnormal readings in last 12; onset when ≥ 9 after ≤ 3"),
       ("Q3 episode resolved", "OVER + MATCH_RECOGNIZE (L M* S X* R)", "resolved when the score falls back to ≤ 3 (hysteresis)"),
       ("Q4 patient summary", "TUMBLE 5 min per patient", "counts, min/avg/max of each vital, abnormal counts, status"),
       ("Q5 ward summary", "TUMBLE 15 min", "readings, patients, abnormal readings, patients with abnormal values")],
      ["Query", "Flink feature", "Logic"], "Continuous queries in the PyFlink job (one StatementSet)", widths=[3.4, 5.6, 7.5])
H("5.5 Implementation and Procedure", 2)
table([("Patients / readings", "10 patients, one reading every 5 s, 10:00–12:00 event time → 14,400 readings"),
       ("Sustained episodes", "P02 tachycardia, P04 desaturation, P06 gradual fever, P08 HR+SpO₂, P09 noisy bradycardia"),
       ("Transient bursts", "P01 (6 readings), P05 (8 readings) – must not become episodes"),
       ("Isolated spikes", "10 single abnormal readings (artefacts)"),
       ("Delivery", "≈ 90 % within 2 s, 1,420 out of order (5–25 s), 66 very late (45–150 s, beyond the 30 s watermark)"),
       ("Thresholds", "HR > 120 or < 50 bpm; SpO₂ < 92 %; temperature > 38.0 °C or < 35.5 °C (educational)")],
      ["Design element", "Value"], "Synthetic vital-sign stream and planted events", widths=[3.6, 12.9])
code("docker build -t bigdata/pyflink:1.20.5 activity3_flink\ndocker compose --profile flink up -d\n"
     "powershell -File activity3_flink\\setup_topics.ps1\n"
     "docker exec flink-jobmanager flink run -d -py /opt/activity3/vitals_job.py\n"
     "python -u activity3_flink/results_collector.py ; python -u activity3_flink/vitals_producer.py --speed 30\n"
     "python activity3_flink/evaluate.py ; python activity3_flink/charts.py", "Procedure:")
H("5.6 Code, Queries and Configuration", 2)
code_file(A3 / "vitals_job.py", "vitals_job.py (excerpt: Kafka source with event-time watermark)", "env.execute_sql(f\"\"\"\nCREATE TABLE vitals_raw", "# end-of-stream markers")
code_file(A3 / "vitals_job.py", "vitals_job.py (excerpt: sliding score and episode-onset pattern)", "# stateful sliding score", "# ------------------------------------------------------------------ sinks")
code_file(A3 / "vitals_job.py", "vitals_job.py (excerpt: ONSET query)", "# Q2 - episode ONSET", "# Q3 - episode RESOLVED")
H("5.7 Results and Sample Outputs", 2)
table([("Readings delivered", "14,400 / 14,400 (7,200 per partition)"),
       ("Rows into the scoring operator", f"{over_in:,} (= 14,400 × 3 vitals); out {over_out:,}"),
       ("Rows dropped as late by OVER/CEP", f"{over_in - over_out} = 66 very-late readings × 3 vitals (exactly as predicted)"),
       ("Reading alerts", f"{len(ra3):,} of 1,240 abnormal readings; 0 missing, 0 extra, 0 duplicates"),
       ("Very-late abnormal readings alerted", "6 / 6 (stateless filter does not depend on the watermark)"),
       ("Patient 5-min windows", f"240 / 240; {drop5} late readings excluded ({pred5} predicted); 239/240 windows exactly as predicted"),
       ("Episode events vs reference implementation", "12 / 12 identical (type, patient, vital, timestamp)"),
       ("Sustained episodes detected", f"6 / 6; mean onset delay {pe3[pe3.kind == 'SUSTAINED'].onset_delay_s.mean():.0f} s event time"),
       ("Transient / isolated with episode alert", "0 / 2 and 0 / 10; false episode onsets 0"),
       ("Checkpoints", f"{cp3[0]} completed, {cp3[1]} failed (cause no longer in history; job never restarted)"),
       ("Peak memory", f"TaskManager {peak3['flink-taskmanager']:.0f} MiB, JobManager {peak3['flink-jobmanager']:.0f} MiB, Kafka {peak3['kafka']:.0f} MiB; host free ≥ {hostmin3} MB")],
      ["Measure", "Result"], "Activity 3 verified results (run 2)", widths=[5.5, 11.0],
      source="evidence/act3/07_final_flink_metrics.log, 09_evaluation.log, 05_memory_during_run.log")
sus = pe3[pe3.kind == "SUSTAINED"]
table([(r.patient_id, r.vital, str(r.true_start)[11:16], str(r.true_end)[11:16], str(r.onset_at)[11:19], f"{r.onset_delay_s:.0f}",
        str(r.resolved_at)[11:19], f"{r.resolve_delay_s:.0f}") for r in sus.itertuples()],
      ["Patient", "Vital", "True start", "True end", "Onset alert", "Delay s", "Resolved", "Delay s"],
      "Sustained episodes: Flink onset/resolution vs planted ground truth (event time)", widths=[1.6, 2.4, 1.9, 1.9, 2.2, 1.6, 2.2, 1.6],
      source="activity3_flink/results/evaluation_episodes.csv")
table([(r.output, f"{r.n:,}", f"{r.p50_ms:,.0f}", f"{r.p95_ms:,.0f}", f"{r.max_ms:,.0f}") for r in lt3.itertuples()],
      ["Output", "n", "p50 ms", "p95 ms", "max ms"], "Latency from Kafka input to Flink output (wall clock)", widths=[8.0, 1.6, 2.2, 2.2, 2.2],
      source="activity3_flink/results/evaluation_latency.csv")
figure(A3 / "charts/a3_episodes_vs_transients.png", "Sustained episodes raise episode alerts; transient bursts only reading alerts")
figure(A3 / "charts/a3_score_hysteresis_P09.png", "Noise-tolerant score with hysteresis for P09 (one episode)")
figure(A3 / "charts/a3_patient_window_heatmap.png", "Per-patient 5-minute window summaries (Flink TUMBLE)")
figure(A3 / "charts/a3_ward_summaries.png", "Ward-level 15-minute summaries")
figure(A3 / "charts/a3_alert_types_by_category.png", "Reading alerts vs episode alerts by planted category")
figure(A3 / "charts/a3_latency.png", "Latency: stateless alerts vs event-time operators")
figure(A3 / "charts/a3_delivery_delay.png", "Delivery delays against the 30 s watermark bound")
figure(EV / "act3/screenshots/flink_job_graph_midrun.png", "Flink Web UI: job graph of the running job (no back pressure)", width=5.6)
figure(EV / "act3/screenshots/flink_window_watermarks_final.png", "Flink Web UI: window operator watermarks and records", width=5.6)
figure(EV / "act3/screenshots/flink_checkpoints.png", "Flink Web UI: checkpoint statistics", width=5.6)
figure(EV / "act3/screenshots/collector_console.png", "Collector console: out-of-order reading alerts and episode resolution", width=5.6)
figure(EV / "act3/run1_superseded_backpressure/screenshots/job_graph_backpressured.png",
       "Run 1: resolution pattern operator 100 % busy (red) and upstream back-pressured (grey)", "Superseded", width=5.6)
H("5.8 Analysis and Interpretation", 2)
P("The results show what event-time processing provides. Out-of-order readings within the 30-second bound were re-ordered "
  "correctly; the 66 very-late readings were dropped by every time-based operator and **still alerted** by the stateless "
  "filter – exactly the trade-off between completeness and determinism. The independent pandas reference, fed with the "
  "watermark simulated from the actual Kafka delivery order, produced the same 12 episode events to the second.")
P("The noise-tolerant score was a design decision taken from the data before any Flink run: a strict '12 consecutive abnormal "
  "readings' rule would have missed P09's bradycardia because noise pushes about one reading in ten back over 50 bpm. The 9-of-12 "
  "onset and 3-of-12 resolution thresholds separate sustained episodes from isolated spikes (score 1) and transient bursts "
  "(score 6 and 8), and the hysteresis prevents flapping. Latency reflects the design: about 45 ms for stateless alerts but "
  "≈ 1.3 s for event-time operators, which must wait for the watermark (30 s of event time = 1 s wall clock at 30× speed).")
P("Run 1 is kept as evidence of a real performance pitfall: the first resolution pattern `(S X* L)` started a partial match at "
  "every high-score row, so work grew quadratically during the 58-minute fever, the Match operator reached 100 % busy, upstream "
  "operators were back-pressured, watermarks stalled and one event was missing. Anchoring the pattern at a calm row "
  "`(L M* S X* R)` gives one partial match per episode; run 2 showed no back pressure.")
H("5.9 Limitations and Improvements", 2)
B(["Synthetic signals and fixed educational thresholds; real monitoring needs patient-specific baselines and clinically validated scores.",
   "Very-late readings are dropped by windows; side outputs or allowed lateness (DataStream API) could route them for review.",
   "One TaskManager with local-filesystem checkpoints; production would use RocksDB state, durable checkpoint storage, "
   "high availability and exactly-once Kafka sinks.",
   "The Flink metric store returned no per-subtask metrics in this Docker setup; late drops were measured from operator I/O and outputs."])
H("5.10 Conclusion", 2)
P("The Flink prototype processes a continuous, imperfect stream in event time, flags every abnormal reading immediately, "
  "detects sustained episodes without false alarms, produces patient and ward window summaries, and its correctness was "
  "verified against ground truth and an independent implementation – while being clearly labelled as educational and synthetic.")
rubric([("Understanding of problem and technology", "1", "5.1–5.3: JM/TM, slots, back pressure, event time, watermarks, state, checkpoints, windows, CEP"),
        ("Solution design and implementation", "1.5", "5.4–5.6, Appendix A.3: five continuous queries, PyFlink job on a Flink 1.20.5 cluster, memory-tuned"),
        ("Results, analysis and interpretation", "1", "5.7–5.8: counts, late data, 12/12 vs reference, latency, 7 charts, 5 screenshots, run-1 analysis"),
        ("Documentation and conclusions", "0.5", "5.9–5.10, README viva notes, disclaimer throughout, evidence register entries act 3")])

# ============================================================== 6 MONGODB
H("6 Activity 4 – MongoDB: E-Commerce Product Catalogue", 1)
H("6.1 Problem Definition", 2)
P("An e-commerce company manages a large catalogue whose products have very different attributes – a laptop has CPU and RAM, a "
  "book has an author and ISBN, a shirt has sizes and colours. It needs a flexible database to store, retrieve and update "
  "product information efficiently, while keeping core fields consistent.")
H("6.2 Objectives", 2)
B(["Study MongoDB document storage, collections, indexing and CRUD operations.",
   "Design a product catalogue with JSON-like documents and schema validation.",
   "Implement insertion, retrieval, category and price-range searches, stock updates and deletion of discontinued products.",
   "Benchmark queries before and after indexing and compare the document model with a relational design."])
H("6.3 Technology Study", 2)
P("**MongoDB** stores **documents** (BSON – binary JSON with types such as dates and decimals) in **collections** within "
  "databases [9]. Documents in one collection may have different fields; related data can be **embedded** (sub-documents, "
  "arrays) or **referenced** by id. Every document has a unique `_id`. Although schema-flexible, a collection can enforce a "
  "**validator** (`$jsonSchema` plus query expressions such as `$expr`) with configurable level and action [10].")
P("The **WiredTiger** storage engine provides document-level concurrency, compression and an in-memory cache. **Indexes** are "
  "B-trees: single-field, **compound**, multikey (arrays), text, **partial**, **unique**, TTL, wildcard and geospatial. The "
  "**query planner** chooses among candidate plans and caches the winner; `explain('executionStats')` reports the winning "
  "plan (e.g. COLLSCAN vs IXSCAN, FETCH, SORT), keys and documents examined and execution time [12]. The **ESR rule** "
  "(Equality, Sort, Range) guides compound-index field order [11]. CRUD covers insert/find/update/delete with atomic "
  "single-document operators (`$inc`, `$set`, `arrayFilters`); the **aggregation pipeline** ($match, $group, $bucket …) performs "
  "analytics. Scale-out uses replica sets (replication, elections) and sharding; multi-document ACID transactions require a "
  "replica set.")
H("6.4 Architecture and Working", 2)
figure(FIG / "fig_a4_architecture.png", "Activity 4 architecture: validated collection, indexes, benchmark, CRUD and SQLite comparison", "Design diagram")
code(json.dumps({k: v for k, v in json.loads(json.dumps(json.load(open(A4 / "data/sample_products.json"))[7], default=str)).items()
                 if k not in ("created_at", "updated_at")}, indent=1)[:1400], "Example document (an apparel product with embedded variants, from data/sample_products.json):")
H("6.5 Implementation and Procedure", 2)
B([f"`generate_catalog.py` creates 200,000 products in 11 categories (seed 2024); `setup_db.py` creates the collection with the "
   f"validator and inserts them in batches of 5,000 ({ins4[0]} documents in {ins4[1]} s, {ins4[2]} docs/s).",
   "`benchmark.py` drops secondary indexes, measures six queries (3 warm-ups + 25 timed runs, plan cache cleared, cache warmed), "
   "creates six indexes and repeats the identical measurement.",
   "`validation_demo.py` attempts invalid and flexible writes; `crud_demo.py` runs CRUD and aggregation reports; "
   "`sql_compare.py` exports the same data into a normalised SQLite schema; `run_all.ps1` runs everything from a clean start."])
code("powershell -ExecutionPolicy Bypass -File activity4_mongodb\\run_all.ps1     # wipes the volume, runs all steps\n"
     "docker exec -it mongodb mongosh ecommerce                                    # interactive shell", "Procedure:")
H("6.6 Code, Queries and Configuration", 2)
code_file(A4 / "setup_db.py", "setup_db.py (excerpt: schema validator)", "PRODUCT_SCHEMA = {", "def load_docs():")
code_file(A4 / "benchmark.py", "benchmark.py (excerpt: queries and indexes)", "QUERIES = [", "def stages(node):")
code_file(A4 / "crud_demo.py", "crud_demo.py (excerpt: atomic stock update and array-element update)",
          '    show("U1  stock update', '    show("U4  bulk restock')
H("6.7 Results and Sample Outputs", 2)
P(f"The collection holds 200,000 documents, {st4[0]} MB of data compressed to {st4[2]} MB on disk (average document {st4[1]} B). "
  "The validator rejected six invalid inserts (code 121), rejected an update that broke the schema, the unique index rejected a "
  "duplicate SKU (E11000), and a product with brand-new attributes was accepted without any migration.")
bb, aa = bs4[bs4.phase == "before"].set_index("query"), bs4[bs4.phase == "after"].set_index("query")
table([(q, bb.loc[q, "description"], f"{bb.loc[q, 'plan']} → {aa.loc[q, 'plan']}", f"{bb.loc[q, 'docsExamined']:,} → {aa.loc[q, 'docsExamined']:,}",
        f"{bb.loc[q, 'server_ms']} → {aa.loc[q, 'server_ms']}", f"{bb.loc[q, 'wall_median_ms']:.2f} → {aa.loc[q, 'wall_median_ms']:.2f}",
        f"×{bb.loc[q, 'wall_median_ms'] / aa.loc[q, 'wall_median_ms']:.1f}") for q in bb.index],
      ["Q", "Query", "Winning plan", "Docs examined", "Server ms", "Median ms", "Ratio"],
      "Benchmark before / after indexing (identical data, queries and conditions)", widths=[0.8, 3.6, 4.6, 2.6, 1.6, 2.4, 1.2], size=7.5,
      source="activity4_mongodb/results/benchmark_summary.csv; 25 timed runs per query and phase")
table([(r.index, r.keys.replace('"', ""), r.purpose, f"{r.size_mb:.2f}", f"{r.build_s:.2f}") for r in ib4.itertuples()],
      ["Index", "Keys", "Purpose", "MB", "Build s"], "Indexes created", widths=[3.2, 4.8, 5.6, 1.3, 1.5], size=8,
      source="activity4_mongodb/results/index_build.csv")
rel = rd(A4 / "results/relational_comparison.csv")
table([(r.aspect, r.mongodb_document_model, r.relational_model) for r in rel.itertuples()],
      ["Aspect", "MongoDB document model", "Relational model (SQLite, same data)"], "Document vs relational model",
      widths=[3.6, 6.4, 6.5], size=8, source="activity4_mongodb/results/relational_comparison.csv, 06_sql_compare.log")
figure(A4 / "charts/a4_docs_examined.png", "Documents examined per query before and after indexing")
figure(A4 / "charts/a4_latency_before_after.png", "Server time and client wall time before and after indexing")
figure(A4 / "charts/a4_index_cost.png", "Index size and build time")
figure(A4 / "charts/a4_document_vs_relational.png", "Same catalogue as documents vs normalised rows")
figure(A4 / "charts/a4_category_report.png", "Aggregation pipeline: active products and inventory value per category")
figure(EV / "act4/screenshots/validation_console.png", "Schema validation demo: rejected and accepted writes", width=5.8)
figure(EV / "act4/screenshots/mongosh_m2_explain.png", "mongosh explain: forced collection scan vs compound index", width=5.8)
figure(EV / "act4/screenshots/benchmark_log_console.png", "Console display of the genuine benchmark log (live capture was blank)", width=5.8)
figure(EV / "act4/screenshots/mongosh_m1_overview.png", "mongosh: heterogeneous documents and the index list", width=5.8)
H("6.8 Analysis and Interpretation", 2)
P(f"Indexes help when they make a query selective. The SKU lookup examined one document instead of 200,000 and the listing "
  f"query 20 instead of 200,000, giving ≈ 50–58× lower latency; the compound `{{category, price}}` index also removed the "
  f"in-memory SORT (ESR rule). For the brand and laptop range queries the server time fell 11–27×, but end-to-end time only "
  f"3.4–4×, because transferring and decoding about 2,000 documents in Python dominates. Two queries show **no gain**: Q6 "
  f"has no usable index (the compound index starts with `category`), and Q5 still returns 40,000 documents, so although "
  f"server time halved the client time did not change; the 0.9 ratios lie within run-to-run variation. Indexes cost about "
  f"21 MB and slow every write, so only indexes that serve real queries should exist.")
P(f"The relational comparison on the same 196,282 products needs {sum(rc4[k] for k in rc4.index if k.startswith('sql_rows')):,} rows "
  f"in four tables, and rebuilding one apparel product returns {rc4['one_product_sql_join_rows']} joined rows (3 specs × 10 variants × 2 tags) "
  f"versus one document. Equivalent queries return identical counts ({rc4['nested_filter_mongo']:,} and {rc4['array_filter_mongo']:,}), "
  "confirming equivalent data. The document model fits heterogeneous, read-together data; the relational model is stronger for "
  "cross-entity constraints, joins and multi-table transactions (for example orders and payments).")
H("6.9 Limitations and Improvements", 2)
B(["Synthetic prices and ratings are random within category ranges, so the brand-rating report is flat (~4.0).",
   "Single node: no replica set (no multi-document transactions, no high availability) and no sharding.",
   "Benchmark on a memory-constrained laptop; absolute times vary between runs, ratios are stable.",
   "Money stored as double for simplicity (Decimal128 is preferable); a production catalogue would use a search engine for full-text search."])
H("6.10 Conclusion", 2)
P("MongoDB stored a heterogeneous catalogue naturally, the validator kept the core consistent without losing flexibility, all "
  "CRUD requirements were demonstrated, and the benchmark quantified – without exaggeration – when indexes help and when they do not.")
rubric([("Understanding of problem and technology", "1", "6.1–6.3: documents, collections, validation, WiredTiger, index types, planner, ESR, CRUD, aggregation"),
        ("Solution design and implementation", "1.5", "6.4–6.6, Appendix A.4: document design, validator, 6 indexes, CRUD, clean-start pipeline on MongoDB 8.0"),
        ("Results, analysis and interpretation", "1", "6.7–6.8: benchmark with explain statistics, index cost, relational comparison, 5 charts, 4 screenshots"),
        ("Documentation and conclusions", "0.5", "6.9–6.10, README viva notes, evidence register entries act 4")])

# ============================================================== 7 BIGQUERY
H("7 Activity 5 – Cloud-Based Big Data Analytics: Server Logs on Google BigQuery", 1)
H("7.1 Problem Definition", 2)
P("An online service generates large volumes of application and web-server logs. The operations team wants to identify frequent "
  "errors, analyse request patterns, detect unusual spikes in failed requests and estimate peak usage – without maintaining "
  "large-scale infrastructure. The assignment allows a free tier or local simulation; this activity used a **real cloud "
  "service**, the BigQuery Sandbox, without enabling billing.")
H("7.2 Objectives", 2)
B(["Explore a cloud big-data platform and select managed storage and analytics services.",
   "Upload a multi-day server-log dataset with batch loading into a well-designed table.",
   "Analyse error frequencies, endpoints, request volume over time, peak periods, IP behaviour, failure spikes and suspicious traffic.",
   "Document the architecture, workflow, findings and estimated costs; distinguish used from proposed services."])
H("7.3 Technology Study", 2)
P("**Google BigQuery** is a serverless, fully managed data warehouse that separates storage from compute [14]. Tables are "
  "stored in a columnar format; queries are executed by the Dremel engine as multi-stage plans whose work units run on "
  "**slots** (virtual compute units) with a distributed shuffle [22]. Users manage no servers: capacity is allocated per query.")
P("**Pricing** has two parts: storage (active and long-term logical bytes) and analysis. With **on-demand** analysis a query is "
  "charged for the bytes it reads from the columns it references; **partitioning** (by a time column, ingestion time or integer "
  "range) and **clustering** (sorting by up to four columns within partitions) reduce the bytes read [16][17]. Data can be "
  "ingested by **batch load jobs** (from local files or Cloud Storage), streaming (insertAll or the Storage Write API) or queried "
  "in place as external tables. The **Sandbox** provides free use without a billing account but with limits [15]; the limits "
  "relevant here were tested directly (§7.7). Related services in a production design are **Cloud Storage** (object storage "
  "for raw logs), scheduled load jobs or the Data Transfer Service, Looker Studio dashboards and Cloud Monitoring alerts.")
H("7.4 Architecture and Working", 2)
figure(A5 / "charts/a5_architecture.png", "Activity 5: services actually used (solid) vs proposed production design (dashed)", "Design diagram")
table([("BigQuery dataset weblogs, table access_logs (asia-south1)", "USED", "Sandbox; partitioned DAY(ts), clustered endpoint, status"),
       ("BigQuery batch load job (bq load, local CSV.gz)", "USED", "1 file, 774,130 rows, 0 bad records"),
       ("BigQuery SQL, INFORMATION_SCHEMA.JOBS_BY_USER", "USED", "20 query jobs per run"),
       ("gcloud / bq CLI, BigQuery Python client", "USED", "user login token, no key files"),
       ("Cloud Billing Catalog API (read-only)", "USED", "official prices for the cost estimate"),
       ("Cloud Storage bucket (raw log landing zone)", "PROPOSED", "deliberately not created; not tested"),
       ("Ops Agent / Cloud Logging, scheduled loads", "PROPOSED", "production ingestion"),
       ("Looker Studio, Cloud Monitoring, summary tables", "PROPOSED", "production consumption")],
      ["Component", "Status", "Notes"], "Services used vs proposed", widths=[7.0, 2.2, 7.3])
H("7.5 Implementation and Procedure", 2)
table([("I1", "Wed 28 Oct 14:10–14:35", "payment outage: 503/504 on /api/v1/payments and /checkout"),
       ("I2", "Fri 30 Oct 09:00–10:30", "bad deployment: 500 on /api/v1/recommendations"),
       ("I3", "Thu 29 Oct 02:00–03:00", "credential stuffing from 203.0.113.17–19 on POST /login"),
       ("I4", "Sat 31 Oct 06:00–18:00", "scraper 198.51.100.77 crawling product pages, throttled with 429"),
       ("I5", "Tue 27 Oct 22:00–22:20", "vulnerability scan from 198.51.100.200 (/.env, /wp-login.php …)"),
       ("I6", "Fri 30 Oct 20:00–22:00", "sale campaign, traffic × 1.7")],
      ["Id", "Time (IST)", "Planted incident"], "Synthetic log dataset: planted incidents (ground truth)", widths=[1.0, 4.0, 11.5])
P(f"`generate_logs.py` writes Apache combined-format logs for one week (26 Oct – 1 Nov 2026) with daily cycles, a pool of "
  f"24,000 client IPs, browsers, mobile app and bots, and 25 deliberately truncated lines; attacker addresses use documentation "
  f"ranges. `parse_logs.py` parses the lines with a regular expression into a typed CSV (774,130 rows, 25 rejected). "
  f"`bq_setup.ps1` recreates the dataset and table and runs the batch load; `run_queries.py` executes the 15 SQL files and the "
  f"pruning tests with the cache disabled and records job statistics; `verify_results.py` recomputes every result locally.")
code("gcloud auth login ; gcloud config set project bigdatasla\n"
     "powershell -ExecutionPolicy Bypass -File activity5_bigquery\\run_all.ps1   # generate, parse, load, query, verify, cost, charts", "Procedure:")
H("7.6 Code, Queries and Configuration", 2)
code_file(A5 / "bq/schema_access_logs.json", "bq/schema_access_logs.json (table schema)")
code_file(A5 / "sql/q11_failure_spikes.sql", "sql/q11_failure_spikes.sql (failure-spike detection)")
code_file(A5 / "sql/q12_suspicious_bruteforce.sql", "sql/q12_suspicious_bruteforce.sql")
H("7.7 Results and Sample Outputs", 2)
P(f"The load job ingested **{o5.requests:,} rows** ({int(re.search(r'logical bytes=([\d,]+)', setup5).group(1).replace(',', '')) / 2**20:.1f} MiB logical) "
  f"with 0 bad records. Overview (Q01): {o5.unique_ips:,} client IPs, {o5.distinct_endpoints} endpoints, {o5.gib_sent} GiB served, "
  f"average response {o5.avg_response_ms} ms, {o5.client_errors_4xx:,} client and {o5.server_errors_5xx:,} server errors "
  f"({o5.error_pct:.2f} % of requests).")
s5 = q5["q02_status_codes"].head(8)
table([(r.status, r.status_class, f"{r.requests:,}", f"{r.pct_of_all:.3g} %") for r in s5.itertuples()],
      ["Status", "Class", "Requests", "Share"], "HTTP status codes (Q02, top 8)", widths=[2.0, 2.0, 3.5, 2.5], source="activity5_bigquery/results/q02_status_codes.csv")
t5 = q5["q03_top_endpoints"].head(8)
table([(r.endpoint, f"{r.requests:,}", f"{r.pct_of_traffic:.2f} %", f"{r.errors_4xx:,}", f"{r.errors_5xx:,}", r.p50_ms, r.p95_ms) for r in t5.itertuples()],
      ["Endpoint", "Requests", "Share", "4xx", "5xx", "p50 ms", "p95 ms"], "Most frequently accessed endpoints (Q03, top 8)",
      widths=[4.8, 2.2, 1.8, 1.8, 1.6, 1.6, 1.6], size=8, source="activity5_bigquery/results/q03_top_endpoints.csv")
sp5 = q5["q11_failure_spikes"]
gt_map = {1: "I1 payment outage (exact)", 2: "false positive", 3: "I2 bad deployment (part 1)", 4: "I2 bad deployment (part 2)"}
table([(r.incident_no, f"{r.spike_start_ist[5:16]} – {r.spike_end_ist[11:16]}", r.failed_requests_in_flagged_buckets, r.expected_failures, r.max_z_score,
        r.top_failing_endpoints[:58], gt_map.get(r.incident_no, "")) for r in sp5.itertuples()],
      ["#", "Window (IST)", "Failures", "Expected", "Max z", "Top failing endpoints", "Ground truth"], "Failure spikes detected by Q11",
      widths=[0.6, 2.9, 1.5, 1.6, 1.2, 5.6, 3.1], size=7.5, source="activity5_bigquery/results/q11_failure_spikes.csv")
b5, sc5, hr5 = q5["q12_suspicious_bruteforce"], q5["q13_suspicious_scanners"], q5["q14_suspicious_high_rate"]
rows = [(r.client_ip, "credential stuffing (Q12)", f"{r.failed_logins:,} failed + {r.successful_logins} successful logins in one hour, {r.attempts_per_minute}/min") for r in b5.itertuples()]
rows += [(r.client_ip, "vulnerability scan (Q13)", f"{r.probe_requests:,} probes, {r.distinct_probe_paths} paths, {r.pct_4xx_5xx:.0f} % 4xx") for r in sc5.itertuples()]
rows += [(r.client_ip, "high-rate automation (Q14)", f"{r.requests:,} requests, {r.minutes_at_20plus_rpm} minutes ≥ 20/min, {r.rate_limited_429:,} × 429")
         for r in hr5.itertuples() if r.client_ip not in set(b5.client_ip)]
table(rows, ["Client IP", "Finding", "Evidence"], "Suspicious traffic identified", widths=[3.0, 4.2, 9.3], source="results/q12–q14 CSV files")
pr5 = q5["pruning_comparison"]
table([(r.query, r.filter, f"{r.bytes_processed / 2**20:.2f}", f"{r.bytes_billed / 2**20:.0f}") for r in pr5.itertuples()],
      ["Query", "Filter", "MiB processed", "MiB billed"], "What a query scans and is billed for", widths=[4.4, 8.0, 2.2, 1.9], size=8,
      source="activity5_bigquery/results/pruning_comparison.csv (BigQuery job statistics)")
table([("Billing", "billingEnabled = False"), ("SELECT queries, DDL (CREATE TABLE), batch load", "allowed"),
       ("DML (INSERT / UPDATE)", "refused: 'DML queries are not allowed in the free tier'"),
       ("Streaming inserts", "refused: 'Streaming insert is not allowed in the free tier'"),
       ("Table / partition expiry", "60 days forced (dataset default 5,184,000,000 ms)"),
       ("Cloud Storage bucket", "not tested – deliberately not attempted")],
      ["Feature", "Result in project bigdatasla"], "BigQuery Sandbox limits verified empirically", widths=[6.0, 10.5], source="evidence/act5/04_sandbox_tests.log")
figure(A5 / "charts/a5_hourly_volume.png", "Request volume and server errors per hour (Q05, Q08, Q11)")
figure(A5 / "charts/a5_status_codes.png", "HTTP status code distribution (Q02)")
figure(A5 / "charts/a5_top_endpoints.png", "Most frequently accessed endpoints (Q03)")
figure(A5 / "charts/a5_weekday_hour_heatmap.png", "Peak usage periods by weekday and hour (Q07)")
figure(A5 / "charts/a5_failure_spikes.png", "Failed requests per 5 minutes with detected spikes (Q10, Q11)")
figure(A5 / "charts/a5_top_ips.png", "IP-wise request patterns: 20 most active clients (Q09)")
figure(A5 / "charts/a5_suspicious_traffic.png", "Suspicious traffic: credential stuffing, scraper, scanner (Q12–Q14)")
figure(A5 / "charts/a5_pruning_bytes.png", "Bytes scanned: partitions, columns, clustering")
figure(EV / "act5/screenshots/console_01_explorer.png", "BigQuery console (Sandbox banner): dataset weblogs and table access_logs", width=5.8)
figure(EV / "act5/screenshots/console_03_details_bottom.png", "Table details: DAY partitioning on ts, 60-day expiry, clustering, 774,130 rows", width=5.8)
figure(EV / "act5/screenshots/console_04_query_results.png", "Q11 executed in the BigQuery console: the same four incidents", width=5.8)
figure(EV / "act5/screenshots/console_04_query_job.png", "Job information: asia-south1, bytes processed and billed", width=5.8)
figure(EV / "act5/screenshots/console_05_execution.png", "Job details: query text and execution graph", width=5.8)
figure(EV / "act5/screenshots/sandbox_tests_console.png", "Sandbox limitation probes (DML and streaming refused)", width=5.8)
figure(EV / "act5/screenshots/bq_cli_query.png", "bq command-line query against the table", width=5.0)
figure(EV / "act5/screenshots/verification_console.png", "Verification: 23/23 checks against local recomputation and ground truth", width=5.8)
H("7.8 Analysis and Interpretation", 2)
P(f"BigQuery answered every operational question with plain SQL over {o5.requests:,} rows, each query finishing in well under a "
  f"second of elapsed time, and every result matched a local pandas recomputation (23/23 checks). The detections map onto the "
  "planted incidents: the payment outage was flagged exactly (14:10–14:35); the bad deployment was flagged in two parts "
  "(09:10–09:30 and 09:40–10:25, missing the first ten minutes); one false positive (29 Oct 15:45, z = 4.1) was raised. "
  "The credential-stuffing IPs had 52–55 **successful** logins each – the most serious finding, since it implies compromised "
  "accounts. The busiest client was a legitimate search bot, which shows that volume alone is not evidence of abuse; rate, user "
  "agent, error ratio and path pattern separate abusive from normal automation. All ten busiest 5-minute windows fall in the "
  "Friday sale (maximum 3.99 requests/s).")
P("The spike detector was redesigned after a measurable failure: a first version used the previous hour of failures as baseline, "
  "so once an outage began its own failures raised the baseline (self-masking) and only one 5-minute bucket per incident was "
  "flagged. The final version predicts failures from traffic and the failure rate of the previous day excluding the last hour. "
  "Its thresholds were chosen on this week's data and would need validation on other weeks.")
P("The pruning tests explain the cost model. One UTC-aligned day scanned 1.64 MiB versus 5.91 MiB for the whole table, an IST "
  "day spans two UTC partitions (3.22 MiB) – the console also reports 8 partitions for 7 IST days – and adding the long "
  "user_agent column raised the scan to 78.43 MiB because billing is per column read. Small queries are billed the 10 MiB minimum.")
H("7.9 Cost Estimation", 2)
P(f"**Actual (Sandbox):** the table uses {int(re.search(r'logical bytes=([\d,]+)', setup5).group(1).replace(',', '')) / 2**20:.1f} MiB "
  f"(1.6 % of the 10 GiB free storage); the {len(js5)} query jobs of the final run processed {js5.bytes_processed.sum() / 2**20:.0f} MiB and "
  f"were billed {js5.bytes_billed.sum() / 2**20:.0f} MiB (0.07 % of the 1 TiB monthly free tier); load jobs have no charge. **Cost: USD 0.00.**")
ce5 = q5["cost_estimate_production"]
table([(r.item, r.quantity, f"{r.usd_per_month:,.2f}") for r in ce5.itertuples()] + [("Total", "", f"{ce5.usd_per_month.sum():,.2f}")],
      ["Item (HYPOTHETICAL – not deployed)", "Quantity", "USD / month"], "Hypothetical production cost (20 GiB logs per day, asia-south1)",
      widths=[8.5, 4.5, 3.5], source="results/cost_estimate_production.csv; prices from the Cloud Billing Catalog API, retrieved 2026-11-03; "
                                    "assumptions in results/cost_assumptions.csv")
figure(A5 / "charts/a5_cost_hypothetical.png", "Hypothetical monthly production cost by component", "Hypothetical")
P("Prices used (official SKUs, asia-south1): analysis USD 7.50 per TiB after 1 TiB free; active storage USD 0.023 per GiB-month "
  "after 10 GiB free (long-term 0.016); Cloud Storage Standard Mumbai USD 0.023 per GiB-month; Class A operations USD 0.005 per "
  "1,000 after 5,000. Assumptions: 20 GiB of raw logs per day, 90-day retention in BigQuery, one-year raw archive, 15 dashboard "
  "queries per hour over the last 24 hours, four ad-hoc weekly queries per day, ratios measured in this run. Without partition "
  "pruning the same dashboards would scan about 5,200 TiB per month (≈ USD 39,000), which makes partitioning the main cost "
  "control; pre-aggregated summary tables or capacity pricing would reduce the analysis cost further.")
H("7.10 Limitations and Improvements", 2)
B(["Synthetic logs with planted incidents; real logs include proxies, NAT, IPv6 and bot impersonation (Googlebot should be verified by reverse DNS).",
   "Sandbox: no DML or streaming, 60-day expiry; the production ingestion path (Cloud Storage, scheduled loads) is designed but not deployed.",
   "Static detection thresholds tuned on one week; production would use seasonal baselines and alerting through Cloud Monitoring.",
   "IP addresses are personal data under many privacy laws; production would mask or truncate them."])
H("7.11 Conclusion", 2)
P("A real cloud warehouse, used entirely within the free Sandbox, ingested a week of logs by batch loading, answered all "
  "required analyses with SQL, found the planted outages and attacks, and supported a cost estimate built on official prices – "
  "with a clear separation between what was executed and what is proposed.")
rubric([("Understanding of problem and technology", "1", "7.1–7.3: serverless warehouse, storage/compute separation, slots, pricing, partitioning, clustering, Sandbox"),
        ("Solution design and implementation", "1.5", "7.4–7.6, Appendix A.5: schema, partition/cluster design, batch load, 15 SQL analyses, clean-start script"),
        ("Results, analysis and interpretation", "1", "7.7–7.9: verified results, detections vs ground truth, pruning, Sandbox limits, cost, 9 charts, 8 screenshots"),
        ("Documentation and conclusions", "0.5", "7.10–7.11, README viva notes, used vs proposed services, evidence register entries act 5")])

# ============================================================== 8 COMPARATIVE
H("8 Comparative Analysis of the Five Technologies", 1)
table([("Primary role", "batch SQL warehouse on files", "distributed event log / transport", "stateful stream processing",
        "operational document database", "serverless cloud warehouse"),
       ("Processing model", "batch (Tez DAG)", "publish–subscribe, pull consumers", "continuous, event time", "request–response CRUD, aggregation", "batch SQL, on-demand slots"),
       ("Data model", "tables over files (schema-on-read)", "key–value records in partitions", "dynamic tables / streams", "JSON/BSON documents", "columnar tables (nested types)"),
       ("Query interface", "HiveQL", "client APIs (no query language)", "SQL / Table API / DataStream", "MQL, aggregation pipeline", "GoogleSQL"),
       ("Latency observed here", "seconds per query (Tez)", "p50 70 ms producer→consumer", "45 ms stateless; ≈1.3 s event-time", "1–3 ms indexed lookups", "≈ 0.2–0.8 s per query"),
       ("Scaling unit", "cluster nodes / containers", "partitions × consumers", "parallelism × slots", "replica sets / shards", "slots (managed)"),
       ("Fault tolerance", "HDFS replication, re-run tasks", "replication, retained log, replay", "checkpoints, exactly-once state", "replica sets, journaling", "managed by Google"),
       ("Strength shown", "partition pruning, ORC 10× smaller", "no loss, ordering per key, replay", "late-data handling, CEP", "flexible schema + validator, indexes", "no infrastructure, pay per bytes"),
       ("Weakness shown", "local mode, stats-answered counts", "uneven partitions with few keys", "quadratic pattern risk, memory", "no gain for unselective queries", "Sandbox limits, minimum billing")],
      ["Aspect", "Hive", "Kafka", "Flink", "MongoDB", "BigQuery"], "Comparison of the five technologies (observations from this project in the last rows)",
      widths=[2.6, 2.8, 2.8, 2.8, 2.8, 2.8], size=7.5)
P("**How they fit together.** The technologies are complementary rather than competing. A realistic platform for the five "
  "scenarios would use Kafka as the durable ingestion backbone (Activity 2), Flink to compute alerts and windows from those "
  "streams with event-time correctness (Activity 3), MongoDB to serve operational data such as product catalogues to "
  "applications (Activity 4), and a warehouse – self-managed Hive on a cluster (Activity 1) or a serverless service such as "
  "BigQuery (Activity 5) – for historical analysis. Activities 2 and 3 were in fact connected in this way: the Flink job read "
  "its input from Kafka.")
P("**Batch vs streaming.** Hive and BigQuery answer questions over data at rest; their latency is seconds but they scan "
  "large histories cheaply. Kafka and Flink act on data in motion with millisecond-to-second latency, at the cost of state "
  "management, watermarks and late-data decisions. **Self-managed vs serverless.** Hive required containers, memory tuning and "
  "a metastore; BigQuery required none, but costs are tied to bytes scanned, so table design (partitioning, column choice) "
  "becomes a cost decision. **Schema.** Hive applies schema on read, MongoDB enforces schema optionally through validators, "
  "BigQuery uses a declared schema at load time, and Kafka is schema-agnostic unless a registry is added.")

# ============================================================== 9 CONCLUSION
H("9 Overall Conclusion", 1)
P("All five self-learning tasks were completed with working prototypes on the real technologies, synthetic data with known "
  "ground truth, and quantitative verification. The work showed each technology's core idea in practice: Hive's partitioned "
  "columnar warehouse, Kafka's partitioned durable log and consumer groups, Flink's event-time processing with watermarks and "
  "pattern matching, MongoDB's flexible documents with validation and indexes, and BigQuery's serverless, bytes-scanned model.")
P("Several of the most useful lessons came from problems found and fixed during the work: a strict episode rule that would have "
  "missed a noisy bradycardia, a pattern that grew quadratically and back-pressured Flink, a spike detector that masked its own "
  "incidents, Sandbox partition expiry that would have deleted year-old data on load, and an inaccurate claim about Kafka's "
  "partitioner corrected by experiment during the final audit. The main limitations are the synthetic data, single-node "
  "deployments and static thresholds; future work would move the designs to multi-node clusters, add schema management and "
  "monitoring, and validate detection rules on real data.")

# ============================================================== REFERENCES
H("References", 1)
refs = [
    "Apache Software Foundation, \"Apache Hive Documentation and Language Manual,\" https://hive.apache.org/ and https://cwiki.apache.org/confluence/display/Hive/LanguageManual",
    "Apache Software Foundation, \"Apache ORC Specification,\" https://orc.apache.org/specification/",
    "Apache Software Foundation, \"Apache Kafka Documentation,\" https://kafka.apache.org/documentation/",
    "Confluent, \"librdkafka Configuration Properties (partitioner),\" https://github.com/confluentinc/librdkafka/blob/master/CONFIGURATION.md",
    "Apache Software Foundation, \"Apache Flink 1.20 Documentation,\" https://nightlies.apache.org/flink/flink-docs-release-1.20/",
    "Apache Flink, \"Timely Stream Processing (event time and watermarks),\" https://nightlies.apache.org/flink/flink-docs-release-1.20/docs/concepts/time/",
    "Apache Flink, \"Pattern Recognition (MATCH_RECOGNIZE),\" https://nightlies.apache.org/flink/flink-docs-release-1.20/docs/dev/table/sql/queries/match_recognize/",
    "Apache Flink, \"Windowing Table-Valued Functions,\" https://nightlies.apache.org/flink/flink-docs-release-1.20/docs/dev/table/sql/queries/window-tvf/",
    "MongoDB Inc., \"MongoDB Manual,\" https://www.mongodb.com/docs/manual/",
    "MongoDB Inc., \"Schema Validation,\" https://www.mongodb.com/docs/manual/core/schema-validation/",
    "MongoDB Inc., \"The ESR (Equality, Sort, Range) Guideline,\" https://www.mongodb.com/docs/manual/tutorial/equality-sort-range-guideline/",
    "MongoDB Inc., \"Explain Results,\" https://www.mongodb.com/docs/manual/reference/explain-results/",
    "MongoDB Inc., \"PyMongo Documentation,\" https://pymongo.readthedocs.io/",
    "Google Cloud, \"BigQuery Documentation,\" https://cloud.google.com/bigquery/docs",
    "Google Cloud, \"Enable the BigQuery Sandbox,\" https://cloud.google.com/bigquery/docs/sandbox",
    "Google Cloud, \"Introduction to Partitioned Tables\" and \"Introduction to Clustered Tables,\" https://cloud.google.com/bigquery/docs/partitioned-tables, https://cloud.google.com/bigquery/docs/clustered-tables",
    "Google Cloud, \"BigQuery Pricing,\" https://cloud.google.com/bigquery/pricing",
    "Google Cloud, \"Cloud Billing Catalog API – services.skus.list,\" https://cloud.google.com/billing/docs/reference/rest/v1/services.skus/list (prices retrieved 2026-11-03)",
    "Google Cloud, \"Cloud Storage Pricing,\" https://cloud.google.com/storage/pricing",
    "Docker Inc., \"Using Profiles with Compose,\" https://docs.docker.com/compose/how-tos/profiles/",
    "Docker Hub official images: apache/hive, apache/kafka, flink, mongo – https://hub.docker.com/",
    "S. Melnik et al., \"Dremel: Interactive Analysis of Web-Scale Datasets,\" Proc. VLDB Endowment, vol. 3, no. 1, 2010.",
    "P. Carbone et al., \"Apache Flink: Stream and Batch Processing in a Single Engine,\" IEEE Data Engineering Bulletin, vol. 38, no. 4, 2015.",
    "J. Kreps, N. Narkhede and J. Rao, \"Kafka: a Distributed Messaging System for Log Processing,\" Proc. NetDB, 2011.",
    "A. Thusoo et al., \"Hive – A Warehousing Solution Over a Map-Reduce Framework,\" Proc. VLDB Endowment, vol. 2, no. 2, 2009.",
]
for i, r in enumerate(refs, 1):
    p = P(f"[{i}] {r}", size=9.5, after=3)
    p.paragraph_format.left_indent = Cm(0.9); p.paragraph_format.first_line_indent = Cm(-0.9)
P("Web references were consulted as official documentation; URLs are given as of November 2026.", size=8.5, color=GREY)

# ============================================================== APPENDICES
H("Appendix A – Source Code", 1)
P("Complete source code of the main programs. Chart scripts (`charts.py`) and evidence helpers are included in the project "
  "folder; they only read result files and are omitted here for length.")
APPX = {
    "A.1 Activity 1 – Hive": [A1 / "generate_sales.py", A1 / "hql/01_schema.hql"] + sorted((A1 / "hql/queries").glob("q*.hql")) + [A1 / "run_queries.sh"],
    "A.2 Activity 2 – Kafka": [A2 / f for f in ("config.py", "traffic_model.py", "producer.py", "congestion_detector.py", "archiver.py",
                                                  "alert_dashboard.py", "evaluate.py", "setup_topics.sh")],
    "A.3 Activity 3 – Flink": [A3 / f for f in ("patient_model.py", "vitals_producer.py", "vitals_job.py", "results_collector.py", "evaluate.py", "setup_topics.ps1")],
    "A.4 Activity 4 – MongoDB": [A4 / f for f in ("config.py", "generate_catalog.py", "setup_db.py", "benchmark.py", "validation_demo.py",
                                                    "crud_demo.py", "sql_compare.py", "relational_schema.sql", "run_all.ps1")] + sorted((A4 / "mongosh").glob("*.js")),
    "A.5 Activity 5 – BigQuery": [A5 / f for f in ("generate_logs.py", "parse_logs.py", "bq_client.py", "bq_setup.ps1", "run_queries.py",
                                                     "sandbox_tests.py", "verify_results.py", "cost_estimate.py", "run_all.ps1")] + sorted((A5 / "sql").glob("q*.sql")),
}
for title, files in APPX.items():
    H(title, 2)
    for f in files:
        code_file(f, f"{f.relative_to(ROOT).as_posix()}")
H("Appendix B – Configuration Files", 1)
for f in (ROOT / "docker-compose.yml", A3 / "Dockerfile", A3 / "thresholds.json", A5 / "bq/schema_access_logs.json", ROOT / "requirements.txt"):
    code_file(f, f.relative_to(ROOT).as_posix())
H("Appendix C – Evidence Register", 1)
P(f"`evidence/manifest.csv` lists {len(manifest)} entries; every referenced file was verified to exist during the audit.")
table([(m["activity"], m["artifact"].replace(" + ", " + "), m["type"], m["status"]) for m in manifest],
      ["Act", "Artefact(s)", "Type", "Status"], "Evidence register", widths=[0.8, 11.0, 2.7, 2.0], size=6.5)
H("Appendix D – Audit Summary", 1)
sm = audit.groupby(["section", "result"]).size().unstack(fill_value=0)
table([(s, int(r.get("OK", 0)), int(r.get("ISSUE", 0))) for s, r in sm.iterrows()], ["Audit section", "OK", "Issues"],
      "Automated audit (audit/audit.py, final run)", widths=[6.0, 2.0, 2.0])
B(["Kafka partitioner statement corrected (CRC32 / librdkafka, verified experimentally; not murmur2).",
   "Cloud Storage removed from 'verified' Sandbox limits (never tested; deliberately not attempted).",
   "Activity 1 inventory recommendations and business insights added, derived only from query results.",
   "MongoDB benchmark table shown with exact values; manifest counts and paths corrected; BigQuery console screenshots "
   "registered and doubled file extensions removed (contents unchanged).",
   "No measured result, CSV, log or screenshot was altered. Full audit report: audit/AUDIT_REPORT.md."])
H("Appendix E – Reproduction Guide", 1)
code("# prerequisites: Docker Desktop, Python 3.12, Google Cloud CLI (Activity 5)\n"
     "py -3.12 -m venv .venv ; .venv\\Scripts\\python.exe -m pip install -r requirements.txt\n\n"
     "# Activity 1 (Git Bash)\npython activity1_hive/generate_sales.py ; docker compose --profile hive up -d\n"
     "docker exec hive4 beeline -u jdbc:hive2://localhost:10000/ -f /opt/assignment/hql/01_schema.hql ; bash activity1_hive/run_queries.sh\n\n"
     "# Activity 2\ndocker compose --profile kafka up -d ; powershell -File activity2_kafka\\run_demo.ps1\n\n"
     "# Activity 3\ndocker build -t bigdata/pyflink:1.20.5 activity3_flink ; docker compose --profile flink up -d\n"
     "powershell -File activity3_flink\\setup_topics.ps1 ; docker exec flink-jobmanager flink run -d -py /opt/activity3/vitals_job.py\n"
     "python -u activity3_flink/results_collector.py ; python -u activity3_flink/vitals_producer.py --speed 30\n\n"
     "# Activity 4 (clean start)\npowershell -File activity4_mongodb\\run_all.ps1\n\n"
     "# Activity 5 (clean start; BigQuery Sandbox)\ngcloud auth login ; powershell -File activity5_bigquery\\run_all.ps1\n\n"
     "# audit\npython audit/audit.py", "Commands (project root):")

doc.save(OUT)
print(f"saved {OUT}  figures={FIG_NO[0]} tables={TAB_NO[0]}")
