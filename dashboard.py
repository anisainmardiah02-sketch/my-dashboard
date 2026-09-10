import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="SMT Masterlist Dashboard", layout="wide")
st.title("🏭 SMT Masterlist Dashboard")

# ---- 1. UPLOAD FILE (not stored on GitHub, kept private) ----
uploaded_file = st.file_uploader("Upload your PCBA Notice Information Excel file", type=["xlsx"])

if not uploaded_file:
    st.info("Upload your Excel file above to see the dashboard. Nothing is saved — it stays only in this session.")
    st.stop()


@st.cache_data
def load_data(file):
    xls = pd.ExcelFile(file)
    sheet_name = next(s for s in xls.sheet_names if s.strip().lower() == "smt masterlist")
    df = pd.read_excel(xls, sheet_name=sheet_name)

    cut_idx = df.index[df["Customer"] == "REV"]
    if len(cut_idx) > 0:
        df = df.loc[: cut_idx[0] - 1]

    for col in ["Customer", "Model", "PCB Board Name", "PCB P/N", "PCB REV", "Side"]:
        df[col] = df[col].ffill()

    df = df.dropna(subset=["SMT P/N"])

    station_cols = []
    for i in range(1, 21):
        scol = f"S{i}"
        rcol = "REV" if i == 1 else f"REV.{i - 1}"
        if scol in df.columns:
            station_cols.append((scol, rcol))

    return df, station_cols


df, station_cols = load_data(uploaded_file)

# ---- 2. SIDEBAR FILTERS ----
st.sidebar.header("Filters")
customers = st.sidebar.multiselect("Customer", sorted(df["Customer"].dropna().unique()),
                                    default=sorted(df["Customer"].dropna().unique()))
models = st.sidebar.multiselect("Model", sorted(df["Model"].dropna().unique()),
                                 default=sorted(df["Model"].dropna().unique()))

filtered = df[df["Customer"].isin(customers) & df["Model"].isin(models)]

# ---- 3. KPI METRICS ----
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Parts", len(filtered))
col2.metric("Customers", filtered["Customer"].nunique())
col3.metric("Models", filtered["Model"].nunique())
col4.metric("Unique Boards", filtered["PCB P/N"].nunique())

st.divider()

# ---- 4. OVERVIEW CHARTS ----
left, right = st.columns(2)

with left:
    by_customer = filtered.groupby("Customer").size().reset_index(name="Parts")
    fig1 = px.bar(by_customer, x="Customer", y="Parts", title="Parts by Customer")
    st.plotly_chart(fig1, use_container_width=True)

with right:
    by_model = filtered.groupby("Model").size().reset_index(name="Parts").sort_values("Parts", ascending=False).head(15)
    fig2 = px.bar(by_model, x="Model", y="Parts", title="Parts by Model (Top 15)")
    fig2.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig2, use_container_width=True)

# ---- 5. STATION USAGE ----
st.subheader("Station Usage (S1–S20)")

usage_rows = []
for scol, rcol in station_cols:
    active = filtered[scol].fillna(0).astype(bool)
    usage_rows.append({"Station": scol, "Active Parts": int(active.sum())})

usage_df = pd.DataFrame(usage_rows)
fig3 = px.bar(usage_df, x="Station", y="Active Parts", title="Number of Parts Using Each Station")
st.plotly_chart(fig3, use_container_width=True)

# ---- 6. DETAIL TABLE ----
st.subheader("Part Details")
display_cols = ["Customer", "Model", "PCB Board Name", "PCB P/N", "PCB REV", "Side",
                 "SMT P/N", "DIP P/N", "FG P/N", "PCS/PANEL", "Line Summary"]
display_cols = [c for c in display_cols if c in filtered.columns]
st.dataframe(filtered[display_cols], use_container_width=True)
