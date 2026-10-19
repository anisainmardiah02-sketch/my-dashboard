import streamlit as st
import pandas as pd
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
st.markdown('<div class="subtitle">Every board revision flagged with an active change notice, broken down by customer and production line. Click any number or bar to see the notices behind it.</div>', unsafe_allow_html=True)
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

    # Process flow (which SMT/DIP steps each board uses), from the Direction Board tab
    flow = pd.read_excel(xls, sheet_name="Direction Board", header=2)
    process_cols = ["Loader", "Printer", "SPI/Pre-AOI/Post AOI", "Mounter", "Side Insert",
                     "Reflow", "Router", "Auto-Insertion", "Wave solder", "Press-fit", "AXI", "Final-AOI"]
    flow = flow[["PCB P/N"] + process_cols].drop_duplicates(subset="PCB P/N")

    notices = notices.merge(flow, on="PCB P/N", how="left")
    return notices, process_cols


notices, process_cols = load_data(uploaded_file)

line_order = sorted(notices["Line"].unique(), key=lambda x: int(x[1:]))
customers = sorted(notices["Customer"].unique())

# ---- 2. KPI METRICS ----
k1, k2, k3, k4 = st.columns(4)
k1.metric("Total notices", len(notices))
k2.metric("Boards affected", notices["PCB P/N"].nunique())
k3.metric("Customers", notices["Customer"].nunique())
k4.metric("Active lines", notices["Line"].nunique())

st.write("")

# ---- 3. CLICKABLE CHARTS ----
# Each chart has a "version" number in its key. Bumping it gives the chart a fresh key,
# which is how we clear a chart's selection.
for k in ("grid", "cust", "line"):
    st.session_state.setdefault(f"ver_{k}", 0)

# The data behind each chart. The ORDER here matters: a click comes back as a position,
# and we use that position to look up which customer / line was clicked.
cells = notices.groupby(["Customer", "Line"]).size().reset_index(name="Count")
cells["_cu"] = cells["Customer"].map({c: i for i, c in enumerate(customers)})
cells["_ln"] = cells["Line"].map({l: i for i, l in enumerate(line_order)})
cells = cells.sort_values(["_cu", "_ln"], kind="stable").reset_index(drop=True)

by_cust = notices.groupby("Customer").size().sort_values(ascending=True, kind="stable")
by_line = (
    notices.groupby("Line").size()
    .sort_values(ascending=False, kind="stable").head(8)
    .sort_values(ascending=True, kind="stable")
)

CHART_BG = "#fbf6f0"
CHART_TEXT = "#4a3f36"
PLOT_CONFIG = {"displayModeBar": False}

left, right = st.columns([2, 1])

with left:
    st.markdown("**Notices by customer × line**")
    st.caption("Darker = more notices. Click a number to list its notices below.")

    max_count = cells["Count"].max()
    fig_grid = go.Figure(go.Scatter(
        x=cells["Line"], y=cells["Customer"],
        mode="markers+text",
        text=cells["Count"].astype(str),
        textposition="middle center",
        textfont=dict(size=12, color=["#ffffff" if c > 0.55 * max_count else CHART_TEXT for c in cells["Count"]]),
        marker=dict(
            symbol="square", size=34, color=cells["Count"],
            colorscale=[[0, "#f1ddcc"], [1, "#b5654a"]], showscale=False, line=dict(width=0),
        ),
        hovertemplate="%{y} · %{x}<br>%{text} notices<extra></extra>",
        selected=dict(marker=dict(opacity=1)),
        unselected=dict(marker=dict(opacity=0.5), textfont=dict(color=CHART_TEXT)),
    ))
    fig_grid.update_xaxes(
        categoryorder="array", categoryarray=line_order, side="top",
        showgrid=False, zeroline=False, fixedrange=True,
    )
    fig_grid.update_yaxes(
        categoryorder="array", categoryarray=customers, autorange="reversed",
        showgrid=False, zeroline=False, fixedrange=True, automargin=True,
    )
    fig_grid.update_layout(
        plot_bgcolor=CHART_BG, paper_bgcolor=CHART_BG, font_color=CHART_TEXT,
        margin=dict(l=0, r=0, t=10, b=0), dragmode=False,
        height=max(200, 90 + 60 * len(customers)),
    )
    ev_grid = st.plotly_chart(
        fig_grid, use_container_width=True, theme=None, on_select="rerun",
        selection_mode="points", key=f"chart_grid_{st.session_state.ver_grid}", config=PLOT_CONFIG,
    )

with right:
    st.markdown("**Notices by customer**")
    st.caption("Click a bar to list that customer's notices.")
    fig_cust = go.Figure(go.Bar(
        x=by_cust.values, y=by_cust.index, orientation="h", marker_color="#b5654a",
        text=by_cust.values, textposition="auto", cliponaxis=False,
        insidetextfont=dict(color="#ffffff"), outsidetextfont=dict(color=CHART_TEXT),
        hovertemplate="%{y}<br>%{x} notices<extra></extra>",
        selected=dict(marker=dict(opacity=1)), unselected=dict(marker=dict(opacity=0.4)),
    ))
    fig_cust.update_layout(
        plot_bgcolor=CHART_BG, paper_bgcolor=CHART_BG, font_color=CHART_TEXT,
        margin=dict(l=0, r=0, t=10, b=0), dragmode=False,
        height=max(140, 50 + 45 * len(by_cust)),
        xaxis=dict(visible=False, fixedrange=True), yaxis=dict(showgrid=False, fixedrange=True, automargin=True),
    )
    ev_cust = st.plotly_chart(
        fig_cust, use_container_width=True, theme=None, on_select="rerun",
        selection_mode="points", key=f"chart_cust_{st.session_state.ver_cust}", config=PLOT_CONFIG,
    )

    st.markdown("**Top lines by volume**")
    st.caption("Click a bar to list that line's notices.")
    fig_line = go.Figure(go.Bar(
        x=by_line.values, y=by_line.index, orientation="h", marker_color="#a68a6d",
        text=by_line.values, textposition="auto", cliponaxis=False,
        insidetextfont=dict(color="#ffffff"), outsidetextfont=dict(color=CHART_TEXT),
        hovertemplate="%{y}<br>%{x} notices<extra></extra>",
        selected=dict(marker=dict(opacity=1)), unselected=dict(marker=dict(opacity=0.4)),
    ))
    fig_line.update_layout(
        plot_bgcolor=CHART_BG, paper_bgcolor=CHART_BG, font_color=CHART_TEXT,
        margin=dict(l=0, r=0, t=10, b=0), dragmode=False,
        height=max(140, 40 + 27 * len(by_line)),
        xaxis=dict(visible=False, fixedrange=True), yaxis=dict(showgrid=False, fixedrange=True, automargin=True),
    )
    ev_line = st.plotly_chart(
        fig_line, use_container_width=True, theme=None, on_select="rerun",
        selection_mode="points", key=f"chart_line_{st.session_state.ver_line}", config=PLOT_CONFIG,
    )


def picked(event):
    """Positions of the points that are currently selected in a chart."""
    try:
        points = event["selection"]["points"]
    except Exception:
        return ()
    return tuple(sorted({p["point_index"] for p in points if p.get("curve_number", 0) == 0}))


current = {"grid": picked(ev_grid), "cust": picked(ev_cust), "line": picked(ev_line)}
previous = st.session_state.get("prev_sel", {"grid": (), "cust": (), "line": ()})

# Whichever chart was clicked most recently decides what the list below shows.
changed = [k for k in current if current[k] and current[k] != previous.get(k, ())]
if changed:
    newest = changed[-1]
    others = [k for k in current if k != newest and current[k]]
    st.session_state["active"] = newest
    st.session_state["prev_sel"] = {k: (current[k] if k == newest else ()) for k in current}
    if others:
        # Clear the other charts' highlights so only one selection is visible at a time
        for k in others:
            st.session_state[f"ver_{k}"] += 1
        st.rerun()
else:
    st.session_state["prev_sel"] = current
    active = st.session_state.get("active")
    if not active or not current.get(active):
        nonempty = [k for k in current if current[k]]
        st.session_state["active"] = nonempty[-1] if nonempty else None

active = st.session_state.get("active")


def clear_selection():
    for k in ("grid", "cust", "line"):
        st.session_state[f"ver_{k}"] += 1
    st.session_state["prev_sel"] = {"grid": (), "cust": (), "line": ()}
    st.session_state["active"] = None


# ---- 3b. NOTICES BEHIND THE CLICKED NUMBER / BAR ----
if not active:
    st.markdown("**Selected notices**")
    st.caption("👆 Click a number in the customer × line grid, or a bar, to see the models, revisions and part numbers behind it.")
else:
    if active == "grid":
        pairs = [(cells.iloc[i]["Customer"], cells.iloc[i]["Line"]) for i in current["grid"]]
        mask = pd.MultiIndex.from_frame(notices[["Customer", "Line"]]).isin(pairs)
        title = ", ".join(f"{c} × {l}" for c, l in pairs) if len(pairs) <= 4 else f"{len(pairs)} cells"
    elif active == "cust":
        names = [by_cust.index[i] for i in current["cust"]]
        mask = notices["Customer"].isin(names)
        title = ", ".join(names)
    else:
        names = [by_line.index[i] for i in current["line"]]
        mask = notices["Line"].isin(names)
        title = ", ".join(names)

    picked_rows = notices[mask].copy()
    picked_rows["_ln"] = picked_rows["Line"].map({l: i for i, l in enumerate(line_order)})
    picked_rows = picked_rows.sort_values(["Customer", "Model", "_ln", "Rev"], kind="stable")

    head_l, head_r = st.columns([4, 1])
    with head_l:
        st.markdown(f"**Selected notices — {title}**")
        st.caption(
            f"{len(picked_rows)} notices · {picked_rows['PCB P/N'].nunique()} boards · "
            f"{picked_rows['Model'].nunique()} models"
        )
    with head_r:
        st.button("✕ Clear selection", on_click=clear_selection, key="clear_sel")

    detail = picked_rows[["Customer", "Model", "Rev", "PCB Board Name", "PCB P/N",
                           "Line", "SMT P/N", "DIP P/N", "FG P/N"]].rename(
        columns={"PCB Board Name": "Board", "PCB P/N": "P/N"})

    st.download_button(
        label="⬇ Download these notices (CSV)",
        data=detail.to_csv(index=False).encode("utf-8"),
        file_name="selected_notices.csv",
        mime="text/csv",
        key="download_selected",
    )
    st.dataframe(detail, use_container_width=True, hide_index=True)

# ---- 4. PROCESS FLOW (SMT & DIP) ----
st.markdown('<div class="block-card">', unsafe_allow_html=True)
st.markdown("**Process flow — SMT & DIP**")
st.caption("Which process steps this board runs through.")

board_options = notices[["PCB P/N", "PCB Board Name"]].drop_duplicates()
board_options["label"] = board_options["PCB P/N"] + " — " + board_options["PCB Board Name"]
chosen_label = st.selectbox("Choose a board", board_options["label"].tolist())
chosen_pn = chosen_label.split(" — ")[0]

board_row = notices[notices["PCB P/N"] == chosen_pn].iloc[0]

smt_steps = ["Loader", "Printer", "SPI/Pre-AOI/Post AOI", "Mounter", "Side Insert", "Reflow"]
dip_steps = ["Router", "Auto-Insertion", "Wave solder", "Press-fit", "AXI", "Final-AOI"]


def render_flow(steps, row):
    pills = []
    for step in steps:
        is_active = bool(row.get(step, False))
        color = "#b5654a" if is_active else "#d8cfc6"
        bg = "#fbf6f0" if is_active else "#f0eae3"
        weight = "700" if is_active else "400"
        pills.append(
            f'<span style="display:inline-block;margin:4px;padding:6px 12px;'
            f'border-radius:20px;border:2px solid {color};background:{bg};'
            f'color:{color};font-weight:{weight};font-size:0.85rem;">{step}</span>'
        )
    return " → ".join(pills)


st.markdown("*SMT:*  " + render_flow(smt_steps, board_row), unsafe_allow_html=True)
st.write("")
st.markdown("*DIP:*  " + render_flow(dip_steps, board_row), unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

# ---- 4b. FIND BOARDS BY PROCESS STEP ----
st.markdown('<div class="block-card">', unsafe_allow_html=True)
st.markdown("**Find boards by process step**")
st.caption("Pick a process step to see every model/board that runs through it.")

step_choice = st.selectbox("Process step", process_cols)

step_boards = (
    notices[notices[step_choice] == True]
    [["Customer", "Model", "PCB Board Name", "PCB P/N"]]
    .drop_duplicates()
    .rename(columns={"PCB Board Name": "Board", "PCB P/N": "P/N"})
    .sort_values(["Customer", "Model"])
)

st.write(f"**{len(step_boards)}** board(s) use **{step_choice}**")

st.download_button(
    label=f"⬇ Download boards using {step_choice} (CSV)",
    data=step_boards.to_csv(index=False).encode("utf-8"),
    file_name=f"boards_using_{step_choice.replace('/', '-')}.csv",
    mime="text/csv",
    key="download_by_step",
)

st.dataframe(step_boards, use_container_width=True, hide_index=True)
st.markdown("</div>", unsafe_allow_html=True)

# ---- 5. FILTERABLE NOTICE RECORDS TABLE ----
st.markdown('<div class="block-card">', unsafe_allow_html=True)
st.markdown("**Notice records**")
st.caption("Search by board, part number, model, or rev.")

f1, f2, f3 = st.columns([1, 1, 2])
with f1:
    cust_filter = st.selectbox("Customer", ["All customers"] + customers)
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
