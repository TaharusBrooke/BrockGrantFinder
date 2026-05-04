import os
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Farm & Estate Grant Finder",
    page_icon="🌿",
    layout="wide"
)

APP_PASSWORD = "colebrooke123"  # Change this


def login():
    st.title("🌿 Farm & Estate Grant Finder")
    st.write("Grant intelligence for farms, estates, woodland, heritage, tourism and nature recovery.")

    password = st.text_input("Enter password", type="password")

    if password == APP_PASSWORD:
        st.session_state["logged_in"] = True
        st.rerun()
    elif password:
        st.error("Incorrect password")


if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    login()
    st.stop()


st.sidebar.title("🌿 Grant Finder")
st.sidebar.success("Logged in")

if st.sidebar.button("Log out"):
    st.session_state["logged_in"] = False
    st.rerun()

st.title("Farm & Estate Grant Dashboard")
st.caption("Funding opportunities matched to land, tourism, heritage and environmental assets.")

if st.button("🔍 Run Grant Search"):
    with st.spinner("Searching funding sources..."):
        import ni_estate_grant_monitor
        ni_estate_grant_monitor.main()
    st.success("Search complete.")

if not os.path.exists("colebrooke_grant_matches.csv"):
    st.warning("No results yet. Click 'Run Grant Search'.")
    st.stop()

df = pd.read_csv("colebrooke_grant_matches.csv")

if df.empty:
    st.warning("No open relevant grants found yet.")
    st.stop()

df["score"] = pd.to_numeric(df["score"], errors="coerce").fillna(0)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Open matches", len(df))
col2.metric("Top score", int(df["score"].max()))
col3.metric("Regions", df["source_region"].nunique())
col4.metric("Land categories", df["land_types"].nunique())

st.divider()

st.sidebar.header("Filters")

regions = sorted(df["source_region"].dropna().unique())
selected_regions = st.sidebar.multiselect("Source region", regions, default=regions)

land_options = sorted(
    set(
        item.strip()
        for row in df["land_types"].dropna()
        for item in str(row).split(",")
        if item.strip()
    )
)

selected_land = st.sidebar.multiselect("Land type", land_options)

min_score = st.sidebar.slider(
    "Minimum relevance score",
    min_value=0,
    max_value=int(max(50, df["score"].max())),
    value=12
)

filtered = df[df["source_region"].isin(selected_regions)]
filtered = filtered[filtered["score"] >= min_score]

if selected_land:
    filtered = filtered[
        filtered["land_types"].fillna("").apply(
            lambda x: any(item in x for item in selected_land)
        )
    ]

st.subheader("💰 Top Opportunities")

top = filtered.sort_values("score", ascending=False).head(5)

for _, row in top.iterrows():
    with st.container(border=True):
        st.markdown(f"### {row['title']}")
        c1, c2, c3 = st.columns(3)
        c1.write(f"**Region:** {row['source_region']}")
        c2.write(f"**Score:** {int(row['score'])}")
        c3.write(f"**Type:** {row['land_types'] or 'Not classified'}")

        st.write(f"**Possible grant value:** {row['possible_grant_values'] or 'Not clearly found'}")
        st.write(f"**Deadline:** {row['deadline_dates'] or 'Not clearly found'}")
        st.write(row["snippet"])
        st.link_button("Open grant page", row["url"])

st.divider()

st.subheader("📊 All Matching Grants")

display_cols = [
    "title",
    "source_region",
    "score",
    "land_types",
    "possible_grant_values",
    "deadline_dates",
    "url",
]

st.dataframe(
    filtered[display_cols].sort_values("score", ascending=False),
    use_container_width=True,
    hide_index=True
)