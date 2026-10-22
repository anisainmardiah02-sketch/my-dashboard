import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="My Dashboard", layout="wide")
st.title("📊 Sales Dashboard")

@st.cache_data
def load_data():
    import numpy as np
    dates = pd.date_range("2024-01-01", periods=180)
    df = pd.DataFrame({
        "Date": dates,
        "Category": np.random.choice(["Electronics", "Clothing", "Food", "Books"], len(dates)),
        "Region": np.random.choice(["North", "South", "East", "West"], len(dates)),
        "Sales": np.random.randint(100, 1000, len(dates)),
    })
    return df

df = load_data()

st.sidebar.header("Filters")
region = st.sidebar.selectbox("Region", ["All"] + sorted(df["Region"].unique().tolist()))
category = st.sidebar.multiselect("Category", df["Category"].unique(), default=df["Category"].unique())

filtered = df.copy()
if region != "All":
    filtered = filtered[filtered["Region"] == region]
filtered = filtered[filtered["Category"].isin(category)]

col1, col2, col3 = st.columns(3)
col1.metric("Total Sales", f"${filtered['Sales'].sum():,.0f}")
col2.metric("Average Sale", f"${filtered['Sales'].mean():,.0f}")
col3.metric("Records", len(filtered))

fig1 = px.bar(filtered.groupby("Category")["Sales"].sum().reset_index(),
              x="Category", y="Sales", title="Sales by Category")
st.plotly_chart(fig1, use_container_width=True)

fig2 = px.line(filtered.groupby("Date")["Sales"].sum().reset_index(),
               x="Date", y="Sales", title="Sales Over Time")
st.plotly_chart(fig2, use_container_width=True)

st.subheader("Raw Data")
st.dataframe(filtered)
