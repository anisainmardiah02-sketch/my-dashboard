import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="PCB Notice Dashboard", layout="wide")

# ---- NUDE THEME STYLING ----
st.markdown("""
<style>
.stApp { background-color: #f5ede4; }
.eyebrow { color: #b5654a; font-weight: 700; font-size: 0.8rem; letter-spacing: 0.05em; }
.subtitle { color: #7a6f66; font-size: 0.95rem; margin-top: -0.5rem; }
h1, h2, h3, p, span, label, div { color: #4a3f36; }
div[data-testid="stMetric"] {
    background-color: #fbf6f0;
    border: 1px solid #e3d5c7;
    border-radius: 10px;
    padding: 1rem 1.2rem;
}
div[data-testid="stMetric"] label { color: #8a7a6d !important; }
div[data-testid="stMetricValue"] { color: #b5654a; }
.block-card {
    background-color: #fbf6f0;
    border: 1px solid #e3d5c7;
    border-radius: 10px;
    padding: 1.2rem 1.4rem;
    margin-bottom: 1rem;
}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="eyebrow">SMT MASTERLIST · ENGINEERING NOTICES</div>', unsafe_allow_html=True)
st.markdown("# PCB Notice Dashboard")
st.markdown('<div class="subtitle">Every board revision flagged with an active change notice, broken down by customer and production line.</div>', unsafe_allow_html=True)
st.write("")

# ---- 1. UPLOAD FILE ----
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

    # Build a long-format "notices" table: one row per active station flag
    records = []
    for i in range(1, 21):
        scol = f"S{i}"
        rcol = "REV" if i == 1 else f"REV.{i - 1}"
        if scol not in df.columns:
            continue
        active = df[scol].fillna(0).astype(bool)
        sub = df[active][["Customer", "Model", "PCB Board Name", "PCB P/N", "SMT P/N", "DIP P/N", "FG P/N", rcol]].copy()
        sub["Line"] = f"S{i}"
        sub = sub.rename(columns={rcol: "Rev"})
        records.append(sub)

    notices = pd.concat(records, ignore_index=True) if records else pd.DataFrame()
    return notices


notices = load_data(uploaded_file)

# Sort lines numerically (S1, S2, ... S20) instead of alphabetically
line_order = sorted(notices["Line"].unique(), key=lambda x: int(x[1:]))

# ---- 2. KPI METRICS ----
k1, k2, k3, k4 = st.columns(4)
k1.metric("Total notices", len(notices))
k2.metric("Boards affected", notices["PCB P/N"].nunique())
k3.metric("Customers", notices["Customer"].nunique())
k4.metric("Active lines", notices["Line"].nunique())

st.write("")

# ---- 3. HEATMAP + SIDE BARS ----
left, right = st.columns([2, 1])

with left:
    st.markdown('<div class="block-card">', unsafe_allow_html=True)
    st.markdown("**Notices by customer × line**")
    st.caption("Darker = more notices.")

    pivot = pd.crosstab(notices["Customer"], notices["Line"])
    pivot = pivot.reindex(columns=line_order, fill_value=0)

    fig = px.imshow(
        pivot.values,
        x=pivot.columns,
        y=pivot.index,
        text_auto=True,
        color_continuous_scale=[[0, "#fbf6f0"], [1, "#b5654a"]],
        aspect="auto",
    )
    fig.update_layout(
        plot_bgcolor="#fbf6f0", paper_bgcolor="#fbf6f0",
        font_color="#4a3f36",
        coloraxis_showscale=False,
        margin=dict(l=0, r=0, t=10, b=0),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

with right:
    st.markdown('<div class="block-card">', unsafe_allow_html=True)
    st.markdown("**Notices by customer**")
    by_cust = notices.groupby("Customer").size().sort_values(ascending=True)
    fig2 = go.Figure(go.Bar(x=by_cust.values, y=by_cust.index, orientation="h",
                             marker_color="#b5654a", text=by_cust.values, textposition="outside"))
    fig2.update_layout(
        plot_bgcolor="#fbf6f0", paper_bgcolor="#fbf6f0", font_color="#4a3f36",
        margin=dict(l=0, r=0, t=10, b=0), height=180,
        xaxis=dict(visible=False), yaxis=dict(showgrid=False),
    )
    st.plotly_chart(fig2, use_container_width=True)

    st.markdown("**Top lines by volume**")
    by_line = notices.groupby("Line").size().sort_values(ascending=False).head(8).sort_values(ascending=True)
    fig3 = go.Figure(go.Bar(x=by_line.values, y=by_line.index, orientation="h",
                             marker_color="#a68a6d", text=by_line.values, textposition="outside"))
    fig3.update_layout(
        plot_bgcolor="#fbf6f0", paper_bgcolor="#fbf6f0", font_color="#4a3f36",
        margin=dict(l=0, r=0, t=10, b=0), height=260,
        xaxis=dict(visible=False), yaxis=dict(showgrid=False),
    )
    st.plotly_chart(fig3, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ---- 4. FILTERABLE NOTICE RECORDS TABLE ----
st.markdown('<div class="block-card">', unsafe_allow_html=True)
st.markdown("**Notice records**")
st.caption("Search by board, part number, model, or rev.")

f1, f2, f3 = st.columns([1, 1, 2])
with f1:
    cust_filter = st.selectbox("Customer", ["All customers"] + sorted(notices["Customer"].unique()))
with f2:
    line_filter = st.selectbox("Line", ["All lines"] + line_order)
with f3:
    search = st.text_input("Search board, model, P/N, rev...", "")

table = notices.copy()
if cust_filter != "All customers":
    table = table[table["Customer"] == cust_filter]
if line_filter != "All lines":
    table = table[table["Line"] == line_filter]
if search:
    s = search.lower()
    mask = (
        table["PCB Board Name"].astype(str).str.lower().str.contains(s)
        | table["Model"].astype(str).str.lower().str.contains(s)
        | table["PCB P/N"].astype(str).str.lower().str.contains(s)
        | table["SMT P/N"].astype(str).str.lower().str.contains(s)
        | table["DIP P/N"].astype(str).str.lower().str.contains(s)
        | table["FG P/N"].astype(str).str.lower().str.contains(s)
        | table["Rev"].astype(str).str.lower().str.contains(s)
    )
    table = table[mask]

display_cols = ["Customer", "Model", "PCB Board Name", "PCB P/N", "SMT P/N", "DIP P/N", "FG P/N", "Line", "Rev"]
display_table = table[display_cols].rename(columns={"PCB Board Name": "Board", "PCB P/N": "P/N"})

st.download_button(
    label="⬇ Download filtered records (CSV)",
    data=display_table.to_csv(index=False).encode("utf-8"),
    file_name="notice_records.csv",
    mime="text/csv",
)

st.dataframe(display_table, use_container_width=True, hide_index=True)
st.markdown("</div>", unsafe_allow_html=True)
