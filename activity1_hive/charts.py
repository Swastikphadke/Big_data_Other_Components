"""
Activity 1 - build report charts from the CSV result sets exported by
run_queries.sh (activity1_hive/results/*.csv).  Every chart is therefore
traceable to a specific HiveQL query.
"""
import sys
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import chartstyle as cs  # noqa: E402

HERE = Path(__file__).parent
RES, OUT = HERE / "results", HERE / "charts"
OUT.mkdir(exist_ok=True)
cs.apply()
lakh = FuncFormatter(lambda v, _: f"{v / 1e5:,.0f}")


def note(q):
    return f"Source: HiveQL {q} on synthetic dataset (seed 42, 559,626 line items)"


# 1. Top 10 products by revenue -------------------------------------------
d = pd.read_csv(RES / "q02_top_products_revenue.csv").iloc[::-1]
fig, ax = plt.subplots(figsize=(8, 4.2))
ax.barh(d.product_name, d.revenue_inr, color=cs.BLUE, height=0.6)
for y, v in enumerate(d.revenue_inr):
    ax.text(v, y, f" {v / 1e5:,.1f} L", va="center", fontsize=8.5, color=cs.TEXT2)
ax.xaxis.set_major_formatter(lakh); ax.grid(axis="y", visible=False)
ax.set_xlabel("Revenue (INR lakh)")
ax.set_title("Top 10 products by revenue, 2025")
cs.save(fig, OUT / "a1_top_products_revenue.png", note("q02_top_products_revenue.hql"))

# 2. Branch-wise revenue ------------------------------------------------------
d = pd.read_csv(RES / "q04_branch_revenue.csv").iloc[::-1]
labels = d.branch_name + " (" + d.city + ")"
fig, ax = plt.subplots(figsize=(8, 3.6))
ax.barh(labels, d.revenue_inr, color=cs.BLUE, height=0.6)
for y, (v, s) in enumerate(zip(d.revenue_inr, d.revenue_share_pct)):
    ax.text(v, y, f" {v / 1e5:,.0f} L  ({s:.1f}%)", va="center", fontsize=8.5, color=cs.TEXT2)
ax.xaxis.set_major_formatter(lakh); ax.grid(axis="y", visible=False)
ax.set_xlabel("Revenue (INR lakh)"); ax.set_xlim(0, d.revenue_inr.max() * 1.25)
ax.set_title("Branch-wise revenue and share of chain revenue")
cs.save(fig, OUT / "a1_branch_revenue.png", note("q04_branch_revenue.hql"))

# 3. Peak hours ---------------------------------------------------------------
d = pd.read_csv(RES / "q05_peak_hours.csv")
top2 = d.nlargest(2, "invoices").sale_hour.tolist()
colors = [cs.ORANGE if h in top2 else cs.BLUE for h in d.sale_hour]
fig, ax = plt.subplots(figsize=(8, 3.6))
ax.bar(d.sale_hour, d.invoices, color=colors, width=0.7)
ax.set_xticks(d.sale_hour, [f"{h:02d}:00" for h in d.sale_hour], rotation=45, fontsize=8.5)
ax.grid(axis="x", visible=False)
ax.set_ylabel("Invoices (bills)")
ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
ax.set_title("Footfall by hour of day - peak hours highlighted")
for h in top2:
    v = int(d.loc[d.sale_hour == h, "invoices"].iloc[0])
    ax.text(h, v, f"{v:,}", ha="center", va="bottom", fontsize=8.5, color=cs.TEXT)
cs.save(fig, OUT / "a1_peak_hours.png", note("q05_peak_hours.hql"))

# 4. Monthly trend ------------------------------------------------------------
d = pd.read_csv(RES / "q06_monthly_trend.csv")
m = pd.to_datetime(d.sale_month).dt.strftime("%b")
fig, ax = plt.subplots(figsize=(8, 3.6))
ax.plot(m, d.revenue_inr, color=cs.BLUE, marker="o", markersize=5)
i = d.revenue_inr.idxmax()
ax.annotate(f"Oct: {d.revenue_inr[i] / 1e5:,.1f} L  (+{d.mom_growth_pct[i]:.1f}% MoM, Diwali)",
            (i, d.revenue_inr[i]), xytext=(-210, -8), textcoords="offset points",
            fontsize=8.5, color=cs.TEXT, arrowprops=dict(arrowstyle="-", color=cs.MUTED))
ax.yaxis.set_major_formatter(lakh); ax.set_ylim(0, d.revenue_inr.max() * 1.15)
ax.set_ylabel("Revenue (INR lakh)"); ax.grid(axis="x", visible=False)
ax.set_title("Monthly revenue trend, Jan-Dec 2025")
cs.save(fig, OUT / "a1_monthly_trend.png", note("q06_monthly_trend.hql"))

# 5. Category seasonality: small multiples (one axis each, no colour coding) ---
d = pd.read_csv(RES / "q07_category_seasonality.csv")
m = pd.to_datetime(d.sale_month).dt.strftime("%b").str[0]
panels = [("beverages", "Beverages"), ("frozen_icecream", "Frozen & Ice Cream"),
          ("sweets_dryfruits", "Sweets & Dry Fruits"), ("household", "Household")]
fig, axes = plt.subplots(1, 4, figsize=(10, 2.8), sharey=False)
for ax, (col, title) in zip(axes, panels):
    idx = 100 * d[col] / d[col].mean()          # index: 100 = category's monthly average
    ax.axhline(100, color=cs.MUTED, lw=0.8, ls="--")
    ax.plot(range(12), idx, color=cs.BLUE, marker="o", markersize=3.5)
    ax.set_xticks(range(12), m, fontsize=7.5); ax.set_ylim(0, 300)
    ax.set_title(title, fontsize=10); ax.grid(axis="x", visible=False)
axes[0].set_ylabel("Index (100 = avg month)")
fig.suptitle("Category seasonality: monthly revenue indexed to each category's average",
             x=0.01, ha="left", fontweight="bold", fontsize=12)
cs.save(fig, OUT / "a1_category_seasonality.png", note("q07_category_seasonality.hql"))

# 6. Weekday vs weekend + payment mix (two separate panels, two different measures)
w = pd.read_csv(RES / "q10_weekday_weekend.csv")
p = pd.read_csv(RES / "q11_payment_mix.csv").iloc[::-1]
fig, (a1, a2) = plt.subplots(1, 2, figsize=(9, 3))
a1.bar(w.day_type, w.avg_daily_revenue_inr, color=cs.BLUE, width=0.5)
for x, v in enumerate(w.avg_daily_revenue_inr):
    a1.text(x, v, f"{v / 1e5:,.2f} L", ha="center", va="bottom", fontsize=9)
a1.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v / 1e5:,.1f}"))
a1.set_ylabel("INR lakh / day"); a1.grid(axis="x", visible=False)
a1.set_title("Average daily revenue", fontsize=11)
a2.barh(p.payment_mode, p.share_pct, color=cs.BLUE, height=0.5)
for y, v in enumerate(p.share_pct):
    a2.text(v, y, f" {v:.1f}%", va="center", fontsize=9)
a2.set_xlim(0, 70); a2.set_xlabel("Share of invoices (%)"); a2.grid(axis="y", visible=False)
a2.set_title("Payment mode mix", fontsize=11)
cs.save(fig, OUT / "a1_daytype_payment.png", note("q10_weekday_weekend.hql, q11_payment_mix.hql"))
