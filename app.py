import os
import pandas as pd
import streamlit as st
from datetime import datetime

CSV_PATH = "colebrooke_grant_matches.csv"
SUBSCRIBERS_PATH = "subscribers.csv"

APP_PASSWORD = "brockgrantfinder123"

POSSIBLE_LOGO_FILES = [
    "Brockgrantfinder logo.png",   # ✅ primary (best)
    "Brockgrantfinder_logo.png",  # fallback
    "logo.png",
]


def find_logo():
    for file in POSSIBLE_LOGO_FILES:
        if os.path.exists(file):
            return file
    return None


LOGO_PATH = find_logo()

st.set_page_config(
    page_title="Brock Grant Finder",
    page_icon="🌿",
    layout="wide"
)

st.markdown("""
<style>
    .stApp {
        background-color: #f6f2e8;
        color: #173b2c;
    }

    section[data-testid="stSidebar"] {
        background-color: #e7efe1;
    }

    h1, h2, h3 {
        color: #123d2b;
    }

    .hero {
        background: #ffffff;
        padding: 28px;
        border-radius: 22px;
        border: 1px solid #d6dfd0;
        box-shadow: 0 4px 16px rgba(0,0,0,0.05);
        margin-bottom: 25px;
    }

    .grant-card {
        background: #ffffff;
        padding: 22px;
        border-radius: 18px;
        border: 1px solid #d5dfd1;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        margin-bottom: 18px;
    }

    .tag {
        display: inline-block;
        padding: 4px 10px;
        margin: 3px;
        background-color: #dce9d6;
        color: #123d2b;
        border-radius: 999px;
        font-size: 13px;
    }

    .small-muted {
        color: #6f786d;
        font-size: 14px;
    }

    .big-title {
        font-size: 44px;
        font-weight: 800;
        color: #123d2b;
        margin-bottom: 0px;
    }

    .subtitle {
        font-size: 18px;
        color: #6f786d;
        margin-top: 4px;
    }
</style>
""", unsafe_allow_html=True)


def save_subscriber(email):
    email = email.strip().lower()

    if not email or "@" not in email:
        return False, "Please enter a valid email address."

    existing = pd.DataFrame()

    if os.path.exists(SUBSCRIBERS_PATH):
        existing = pd.read_csv(SUBSCRIBERS_PATH)

        if "email" in existing.columns and email in existing["email"].astype(str).str.lower().values:
            return False, "This email is already subscribed."

    new_row = pd.DataFrame([{
        "email": email,
        "subscribed_at": datetime.utcnow().isoformat(timespec="seconds")
    }])

    combined = pd.concat([existing, new_row], ignore_index=True)
    combined.to_csv(SUBSCRIBERS_PATH, index=False)

    return True, "You have been added to the grant alert list."


def login():
    st.markdown("<div class='hero'>", unsafe_allow_html=True)

    col1, col2 = st.columns([1, 2])

    with col1:
        if LOGO_PATH:
            st.image(LOGO_PATH, width=260)
        else:
            st.warning("Logo not found. Upload: Brockgrantfinder logo.png")

    with col2:
        st.markdown("<div class='big-title'>Brock Grant Finder</div>", unsafe_allow_html=True)
        st.markdown(
            "<div class='subtitle'>GrantBurrow — funding intelligence for farms, estates and rural businesses.</div>",
            unsafe_allow_html=True
        )

    st.markdown("</div>", unsafe_allow_html=True)

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


st.sidebar.title("Brock Grant Finder")

if LOGO_PATH:
    st.sidebar.image(LOGO_PATH, use_container_width=True)
else:
    st.sidebar.warning("Logo missing")

st.sidebar.success("Logged in")

if st.sidebar.button("Log out"):
    st.session_state["logged_in"] = False
    st.rerun()


st.markdown("<div class='hero'>", unsafe_allow_html=True)

col_logo, col_title = st.columns([1, 4])

with col_logo:
    if LOGO_PATH:
        st.image(LOGO_PATH, width=170)

with col_title:
    st.markdown("<div class='big-title'>Farm & Estate Grant Dashboard</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='subtitle'>Open funding opportunities matched to agriculture, forestry, heritage, tourism, land, water and rural business assets.</div>",
        unsafe_allow_html=True
    )

st.markdown("</div>", unsafe_allow_html=True)


st.subheader("📩 Get grant alerts by email")

with st.form("email_signup"):
    email = st.text_input("Enter your email address")
    submitted = st.form_submit_button("Subscribe to grant alerts")

    if submitted:
        success, message = save_subscriber(email)
        if success:
            st.success(message)
        else:
            st.warning(message)

st.info("This dashboard reads the latest saved grant results. The scraper should run separately each day.")

if not os.path.exists(CSV_PATH):
    st.warning("No grant results found yet. Run the scraper first to create colebrooke_grant_matches.csv.")
    st.stop()

df = pd.read_csv(CSV_PATH)

if df.empty:
    st.warning("No open relevant grants found in the latest search.")
    st.stop()

df["score"] = pd.to_numeric(df["score"], errors="coerce").fillna(0)

for col in [
    "title",
    "url",
    "source_region",
    "category",
    "land_types",
    "possible_grant_values",
    "deadline_dates",
    "snippet",
    "last_checked"
]:
    if col not in df.columns:
        df[col] = ""

last_updated = df["last_checked"].dropna().max() if "last_checked" in df.columns else "Unknown"

st.caption(f"Last updated: {last_updated}")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Open grants", len(df))
col2.metric("Top score", int(df["score"].max()))
col3.metric("Regions", df["source_region"].nunique())
col4.metric("Categories", df["category"].nunique())

st.divider()

st.sidebar.header("Filters")

regions = sorted(df["source_region"].dropna().unique())
selected_regions = st.sidebar.multiselect("Source region", regions, default=regions)

categories = sorted(
    set(
        item.strip()
        for row in df["category"].dropna()
        for item in str(row).split(",")
        if item.strip()
    )
)

selected_categories = st.sidebar.multiselect("Category", categories)

land_types = sorted(
    set(
        item.strip()
        for row in df["land_types"].dropna()
        for item in str(row).split(",")
        if item.strip()
    )
)

selected_land_types = st.sidebar.multiselect("Land / business type", land_types)

min_score = st.sidebar.slider(
    "Minimum relevance score",
    min_value=0,
    max_value=int(max(100, df["score"].max())),
    value=20
)

keyword = st.sidebar.text_input("Keyword search")

filtered = df.copy()

if selected_regions:
    filtered = filtered[filtered["source_region"].isin(selected_regions)]

filtered = filtered[filtered["score"] >= min_score]

if selected_categories:
    filtered = filtered[
        filtered["category"].fillna("").apply(
            lambda x: any(cat.lower() in x.lower() for cat in selected_categories)
        )
    ]

if selected_land_types:
    filtered = filtered[
        filtered["land_types"].fillna("").apply(
            lambda x: any(land.lower() in x.lower() for land in selected_land_types)
        )
    ]

if keyword:
    keyword_l = keyword.lower()
    filtered = filtered[
        filtered.apply(
            lambda row: keyword_l in " ".join(row.astype(str)).lower(),
            axis=1
        )
    ]

st.subheader("💰 Top Opportunities")

top = filtered.sort_values("score", ascending=False).head(8)

if top.empty:
    st.warning("No grants match the current filters.")
else:
    for _, row in top.iterrows():
        category_tags = ""

        for tag in str(row.get("category", "")).split(","):
            tag = tag.strip()
            if tag:
                category_tags += f"<span class='tag'>{tag}</span>"

        st.markdown(f"""
        <div class="grant-card">
            <h3>{row.get("title", "Untitled grant")}</h3>
            <p><strong>Region:</strong> {row.get("source_region", "Unknown")}</p>
            <p><strong>Score:</strong> {int(row.get("score", 0))}</p>
            <p><strong>Category:</strong><br>{category_tags}</p>
            <p><strong>Land / business type:</strong> {row.get("land_types", "Not clearly classified")}</p>
            <p><strong>Possible grant value:</strong> {row.get("possible_grant_values", "Not clearly found") or "Not clearly found"}</p>
            <p><strong>Deadline:</strong> {row.get("deadline_dates", "Not clearly found") or "Not clearly found"}</p>
            <p class="small-muted">{str(row.get("snippet", ""))[:420]}</p>
            <p><a href="{row.get("url", "#")}" target="_blank">Open grant page</a></p>
        </div>
        """, unsafe_allow_html=True)

st.divider()

st.subheader("📊 All Matching Grants")

display_cols = [
    "title",
    "source_region",
    "category",
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