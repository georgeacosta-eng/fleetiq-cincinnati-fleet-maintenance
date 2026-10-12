"""Data-quality audit and exploratory analysis of the City of Cincinnati
Fleet Preventative Maintenance & Repair Work Orders dataset (2013-2023).

Usage:  python analysis/fleet_audit_and_eda.py <path-to-xlsx-or-csv> [output_dir]
Outputs: charts (PNG) in <output_dir>/ and metrics.json
Only columns that are structurally consistent across the whole file are used
(see README, "Data-quality findings").
"""
import json, sys
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

src = Path(sys.argv[1]); out = Path(sys.argv[2] if len(sys.argv) > 2 else "assets"); out.mkdir(exist_ok=True)
raw = pd.read_excel(src) if src.suffix.lower().startswith(".xls") else pd.read_csv(src, low_memory=False)

# ---------- 1. Audit ----------
m = {"rows_in_file": len(raw)}
df = raw.dropna(how="all").copy()
m["fully_empty_rows"] = m["rows_in_file"] - len(df)
m["work_orders"] = len(df)
m["duplicate_work_order_numbers"] = int(df["UNIQUE_WORK_ORDER_NO"].duplicated().sum())
m["distinct_vehicles"] = int(df["EQ_EQUIP_NO"].nunique())
# two column layouts: standard rows have YES/NO in WARRANTY; shifted rows do not
m["rows_with_shifted_columns"] = int((~df["WARRANTY"].astype(str).isin(["YES", "NO"])).sum())
m["rows_with_shifted_columns_pct"] = round(100 * m["rows_with_shifted_columns"] / len(df), 1)

# ---------- 2. Parse (columns that are consistent in every row) ----------
fmt = "%Y %b %d %I:%M:%S %p"
for c in ["CREATE_DATE", "DATETIME_FINISHED", "DATETIME_DUE"]:
    df[c] = pd.to_datetime(df[c], format=fmt, errors="coerce")
df["year"] = df["CREATE_DATE"].dt.year
df["days_to_finish"] = (df["DATETIME_FINISHED"] - df["CREATE_DATE"]).dt.days
m["date_range"] = [str(df["CREATE_DATE"].min().date()), str(df["CREATE_DATE"].max().date())]
m["pm_share_pct"] = round(100 * (df["JOB_TYPE"] == "PM").mean(), 1)
m["status_counts"] = df["WORK_ORDER_STATUS"].value_counts().to_dict()
ok = df[df["days_to_finish"] >= 0]
m["negative_duration_rows"] = int((df["days_to_finish"] < 0).sum())
m["days_to_finish_median"] = ok.groupby("JOB_TYPE")["days_to_finish"].median().to_dict()
m["days_to_finish_p90"] = ok.groupby("JOB_TYPE")["days_to_finish"].quantile(.9).to_dict()
fin = df.dropna(subset=["DATETIME_FINISHED", "DATETIME_DUE"])
m["finished_after_due_pct"] = round(100 * (fin["DATETIME_FINISHED"] > fin["DATETIME_DUE"]).mean(), 1)
vc = df["EQ_EQUIP_NO"].value_counts()
m["top20pct_vehicles_share_of_orders_pct"] = round(100 * vc.head(int(len(vc) * .2)).sum() / len(df), 1)
m["top_shops"] = df["LOC_WORK_ORDER_LOC_NAME"].value_counts().head(10).to_dict()
Path(out / "metrics.json").write_text(json.dumps(m, indent=2, default=str))

# ---------- 3. Charts ----------
plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False, "figure.dpi": 150})
C = {"REPAIR": "#d9822b", "PM": "#2a7f9e"}

fig, ax = plt.subplots(figsize=(9, 4.6))
t = df.pivot_table(index="year", columns="JOB_TYPE", values="UNIQUE_WORK_ORDER_NO", aggfunc="count")
t = t.drop(index=[y for y in [2014] if y in t.index], errors="ignore")
t[["REPAIR", "PM"]].plot.bar(stacked=True, ax=ax, color=[C["REPAIR"], C["PM"]], width=.75)
ax.set_title("Work orders per year by job type (2014 absent in source; 2023 partial to Aug 9)", loc="left", fontsize=12)
ax.set_xlabel(""); ax.set_ylabel("Work orders"); ax.legend(frameon=False, title="")
plt.xticks(rotation=0); fig.tight_layout(); fig.savefig(out / "orders_per_year.png"); plt.close(fig)

fig, ax = plt.subplots(figsize=(9, 4.2))
days = pd.DataFrame({k: [m["days_to_finish_median"][k], m["days_to_finish_p90"][k]] for k in ["PM", "REPAIR"]}, index=["Median", "90th percentile"])
days.plot.bar(ax=ax, color=[C["PM"], C["REPAIR"]], width=.65)
for p in ax.patches: ax.annotate(f"{p.get_height():.0f}", (p.get_x() + p.get_width() / 2, p.get_height()), ha="center", va="bottom", fontsize=10)
ax.set_title("Days from creation to completion", loc="left", fontsize=12); ax.set_ylabel("Days"); ax.legend(frameon=False, title="")
plt.xticks(rotation=0); fig.tight_layout(); fig.savefig(out / "days_to_finish.png"); plt.close(fig)

fig, ax = plt.subplots(figsize=(9, 4.8))
s = df["LOC_WORK_ORDER_LOC_NAME"].value_counts().head(10)[::-1]
ax.barh(s.index, s.values, color="#2a7f9e")
for i, v in enumerate(s.values): ax.text(v, i, f" {v:,}", va="center", fontsize=10)
ax.set_title("Top 10 work locations by order volume", loc="left", fontsize=12); ax.set_xlabel("Work orders")
fig.tight_layout(); fig.savefig(out / "top_shops.png"); plt.close(fig)

fig, ax = plt.subplots(figsize=(9, 3.4))
parts = {"Usable work orders": m["work_orders"], "Fully empty rows": m["fully_empty_rows"]}
ax.barh(["Rows in file"], [parts["Usable work orders"]], color="#2a7f9e", label=f"Usable work orders ({m['work_orders']:,})")
ax.barh(["Rows in file"], [parts["Fully empty rows"]], left=[parts["Usable work orders"]], color="#c9c9c9", label=f"Fully empty rows ({m['fully_empty_rows']:,})")
ax.set_title(f"{m['rows_in_file']:,} rows in source file", loc="left", fontsize=12); ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(.5, -.25), ncol=2)
ax.set_xlabel("")
fig.tight_layout(); fig.savefig(out / "row_audit.png"); plt.close(fig)
print(json.dumps(m, indent=2, default=str))
