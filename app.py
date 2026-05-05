import os
from datetime import datetime

import pandas as pd
import streamlit as st

CSV_PATH = "colebrooke_grant_matches.csv"
SUBSCRIBERS_PATH = "subscribers.csv"

APP_PASSWORD = "brockgrantfinder123"

POSSIBLE_LOGO_FILES = [
    "brockgrantfinder_logo.png",
    "Brockgrantfinder logo.png",
    "Brockgrantfinder_logo.png",
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
    page_icon="",
    layout="wide",
)

st.markdown("""
<style>
    .stApp {
        background: #f5f1e7;
        color: #1f3a2d;
        font-family: Georgia, 'Times New Roman', serif;
    }

    section[data-testid="stSidebar"] {
        background: #e8ecdf;
        border-right: 1px solid #c9c3ae;
    }

    .block-container {
        max-width: 1180px;
        padding-top: 2rem;
        padding-bottom: 4rem;
    }

    h1, h2, h3 {
        color: #173b2c;
        font-family: Georgia, 'Times New Roman', serif;
        letter-spacing: 0.2px;
    }

    .top-bar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 14px 0 24px 0;
        border-bottom: 1px solid #cfc7b2;
        margin-bottom: 28px;
    }

    .brand-name {
        font-size: 18px;
        letter-spacing: 2px;
        text-transform: uppercase;
        color: #173b2c;
        font-weight: 600;
    }

    .nav-text {
        font-size: 13px;
        letter-spacing: 1.4px;
        text-transform: uppercase;
        color: #6f6a59;
    }

    .hero {
        background:
            linear-gradient(rgba(245, 241, 231, 0.88), rgba(245, 241, 231, 0.92)),
            linear-gradient(135deg, #f9f4e8, #e6eddd);
        padding: 46px 52px;
        border-radius: 4px;
        border: 1px solid #cfc7b2;
        box-shadow: 0 12px 32px rgba(42, 56, 41, 0.08);
        margin-bottom: 34px;
    }

    .hero-title {
        font-size: 52px;
        line-height: 1.05;
        font-weight: 500;
        color: #173b2c;
        margin: 0 0 12px 0;
    }

    .hero-subtitle {
        font-size: 19px;
        line-height: 1.65;
        color: #665f4d;
        max-width: 780px;
    }

    .section-kicker {
        font-size: 12px;
        letter-spacing: 2px;
        text-transform: uppercase;
        color: #8a7a55;
        margin-bottom: 6px;
        font-weight: 600;
    }

    .estate-panel {
        background: #fffdf7;
        border: 1px solid #d6ceb9;
        padding: 26px;
        border-radius: 3px;
        box-shadow: 0 6px 18px rgba(42, 56, 41, 0.055);
        margin-bottom: 22px;
    }

    .grant-card {
        background: #fffdf7;
        padding: 28px 30px;
        border-radius: 3px;
        border: 1px solid #d6ceb9;
        box-shadow: 0 6px 20px rgba(42, 56, 41, 0.06);
        margin-bottom: 22px;
    }

    .grant-card h3 {
        font-size: 26px;
        font-weight: 500;
        margin-bottom: 12px;
    }

    .tag {
        display: inline-block;
        padding: 5px 12px;
        margin: 4px 5px 4px 0;
        background-color: #e7eadc;
        color: #173b2c;
        border: 1px solid #cbd4bd;
        border-radius: 999px;
        font-size: 13px;
        font-family: Arial, sans-serif;
    }

    .small-muted {
        color: #6f6a59;
        font-size: 15px;
        line-height: 1.65;
    }

    .muted-rule {
        height: 1px;
        background: #d4ccb7;
        margin: 20px 0;
    }

    a {
        color: #315f3c !important;
        font-weight: 600;
        text-decoration: none;
    }

    a:hover {
        text-decoration: underline;
    }

    .stButton > button {
        background-color: #315f3c;
        color: white;
        border-radius: 2px;
        border: 1px solid #315f3c;
        padding: 0.55rem 1.1rem;
        font-family: Georgia, 'Times New Roman', serif;
    }

    .stButton > button:hover {
        background-color: #24482e;
        color: white;
        border: 1px solid #24482e;
    }

    div[data-testid="stMetric"] {
        background: #fffdf7;
        border: 1px solid #d6ceb9;
        padding: 18px;
        border-radius: 3px;
        box-shadow: 0 4px 12px rgba(42, 56, 41, 0.04);
    }

    input, textarea {
        border-radius: 2px !important;
    }
</style>
""", unsafe_allow_html=True)


def save_subscriber(email):
    email = email.strip().lower()

    if not email or "@" not in email:
        return False, "Please enter a valid email address."

    if os.path.exists(SUBSCRIBERS_PATH):
        existing = pd.read_csv(SUBSCRIBERS_PATH)
        if "email" in existing.columns:
            if email in existing["email"].astype(str).str.lower().values:
                return False, "This email is already subscribed."
    else:
        existing = pd.DataFrame()

    new_row = pd.DataFrame([{
        "email": email,
        "subscribed_at": datetime.utcnow().isoformat(timespec="seconds"),
    }])

    pd.concat([existing, new_row], ignore_index=True).to_csv(
        SUBSCRIBERS_PATH,
        index=False,
    )

    return True, "You have been added to the grant alert list."


def login():
    st.markdown("""
    <div class="top-bar">
        <div class="brand-name">Brock Grant Finder</div>
        <div class="nav-text">Farms · Estates · Rural Business</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div class='hero'>", unsafe_allow_html=True)

    col1, col2 = st.columns([1, 2.4])

    with col1:
        if LOGO_PATH:
            st.image(LOGO_PATH, width=260)
        else:
            st.warning("Logo not found. Upload brockgrantfinder_logo.png or Brockgrantfinder logo.png.")

    with col2:
        st.markdown("<div class='section-kicker'>Private grant intelligence</div>", unsafe_allow_html=True)
        st.markdown("<div class='hero-title'>Funding routes for land, nature and rural enterprise.</div>", unsafe_allow_html=True)
        st.markdown(
            "<div class='hero-subtitle'>A curated monitor for public grants relevant to farmers, landowners, estates and countryside businesses.</div>",
            unsafe_allow_html=True,
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


st.markdown("""
<div class="top-bar">
    <div class="brand-name">Brock Grant Finder</div>
    <div class="nav-text">GrantBurrow · Public funding monitor</div>
</div>
""", unsafe_allow_html=True)

st.markdown("<div class='hero'>", unsafe_allow_html=True)

col_logo, col_title = st.columns([1, 4])

with col_logo:
    if LOGO_PATH:
        st.image(LOGO_PATH, width=170)

with col_title:
    st.markdown("<div class='section-kicker'>Farm & Estate Grant Dashboard</div>", unsafe_allow_html=True)
    st.markdown("<div class='hero-title'>Public funding, matched to countryside assets.</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='hero-subtitle'>Specific public funding opportunities for agriculture, forestry, heritage, tourism, water, biodiversity and rural business.</div>",
        unsafe_allow_html=True,
    )

st.markdown("</div>", unsafe_allow_html=True)


st.markdown("<div class='estate-panel'>", unsafe_allow_html=True)
st.markdown("<div class='section-kicker'>Grant alerts</div>", unsafe_allow_html=True)
st.subheader("Receive updates by email")

with st.form("email_signup"):
    email = st.text_input("Enter your email address")
    submitted = st.form_submit_button("Subscribe")

    if submitted:
        success, message = save_subscriber(email)
        if success:
            st.success(message)
        else:
            st.warning(message)

st.markdown("</div>", unsafe_allow_html=True)

st.info("This dashboard reads the latest saved grant results. The grant monitor should run separately each day.")

if not os.path.exists(CSV_PATH):
    st.warning("No grant results found yet. Run the grant monitor first to create colebrooke_grant_matches.csv.")
    st.stop()

df = pd.read_csv(CSV_PATH)

if df.empty:
    st.warning("No matching grants found in the latest search.")
    st.stop()

required_cols = [
    "checked_at",
    "last_checked",
    "title",
    "url",
    "source_region",
    "eligibility_region",
    "category",
    "score",
    "land_types",
    "possible_grant_values",
    "deadline_dates",
    "deadline_phrases",
    "reason_found",
    "snippet",
]

for col in required_cols:
    if col not in df.columns:
        df[col] = ""

df["score"] = pd.to_numeric(df["score"], errors="coerce").fillna(0)

if df["last_checked"].dropna().astype(str).str.len().sum() > 0:
    last_updated = df["last_checked"].dropna().max()
elif df["checked_at"].dropna().astype(str).str.len().sum() > 0:
    last_updated = df["checked_at"].dropna().max()
else:
    last_updated = "Unknown"

st.caption(f"Last updated: {last_updated}")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Matching grants", len(df))
col2.metric("Top score", int(df["score"].max()))
col3.metric("Source regions", df["source_region"].nunique())
col4.metric("Eligibility regions", df["eligibility_region"].nunique())

st.divider()

st.sidebar.header("Filters")

source_regions = sorted(df["source_region"].dropna().astype(str).unique())
eligibility_regions = sorted(df["eligibility_region"].dropna().astype(str).unique())

st.sidebar.markdown("### Source region")

selected_source_regions = st.sidebar.multiselect(
    "Include source regions",
    source_regions,
    default=source_regions,
)

excluded_source_regions = st.sidebar.multiselect(
    "Exclude source regions",
    source_regions,
)

st.sidebar.markdown("### Eligibility region")

selected_eligibility_regions = st.sidebar.multiselect(
    "Include eligibility regions",
    eligibility_regions,
    default=eligibility_regions,
)

excluded_eligibility_regions = st.sidebar.multiselect(
    "Exclude eligibility regions",
    eligibility_regions,
)

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
    value=20,
)

keyword = st.sidebar.text_input("Keyword search")

filtered = df.copy()

if selected_source_regions:
    filtered = filtered[filtered["source_region"].isin(selected_source_regions)]

if excluded_source_regions:
    filtered = filtered[~filtered["source_region"].isin(excluded_source_regions)]

if selected_eligibility_regions:
    filtered = filtered[
        filtered["eligibility_region"].fillna("").apply(
            lambda x: any(region.lower() in str(x).lower() for region in selected_eligibility_regions)
        )
    ]

if excluded_eligibility_regions:
    filtered = filtered[
        ~filtered["eligibility_region"].fillna("").apply(
            lambda x: any(region.lower() in str(x).lower() for region in excluded_eligibility_regions)
        )
    ]

filtered = filtered[filtered["score"] >= min_score]

if selected_categories:
    filtered = filtered[
        filtered["category"].fillna("").apply(
            lambda x: any(cat.lower() in str(x).lower() for cat in selected_categories)
        )
    ]

if selected_land_types:
    filtered = filtered[
        filtered["land_types"].fillna("").apply(
            lambda x: any(land.lower() in str(x).lower() for land in selected_land_types)
        )
    ]

if keyword:
    keyword_l = keyword.lower()
    filtered = filtered[
        filtered.apply(
            lambda row: keyword_l in " ".join(row.astype(str)).lower(),
            axis=1,
        )
    ]

st.markdown("<div class='section-kicker'>Curated opportunities</div>", unsafe_allow_html=True)
st.subheader("Top Opportunities")

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
            <div class="muted-rule"></div>
            <p><strong>Source region:</strong> {row.get("source_region", "Unknown")}</p>
            <p><strong>Eligibility region:</strong> {row.get("eligibility_region", "Unknown")}</p>
            <p><strong>Score:</strong> {int(row.get("score", 0))}</p>
            <p><strong>Category:</strong><br>{category_tags}</p>
            <p><strong>Land / business type:</strong> {row.get("land_types", "Not clearly classified")}</p>
            <p><strong>Possible grant value:</strong> {row.get("possible_grant_values", "Not clearly found") or "Not clearly found"}</p>
            <p><strong>Deadline:</strong> {row.get("deadline_dates", "Not clearly found") or "Not clearly found"}</p>
            <p><strong>Why included:</strong> {row.get("reason_found", "Not specified") or "Not specified"}</p>
            <p class="small-muted">{str(row.get("snippet", ""))[:420]}</p>
            <p><a href="{row.get("url", "#")}" target="_blank">Open grant page</a></p>
        </div>
        """, unsafe_allow_html=True)

st.divider()

st.markdown("<div class='section-kicker'>Full register</div>", unsafe_allow_html=True)
st.subheader("All Matching Grants")

display_cols = [
    "title",
    "source_region",
    "eligibility_region",
    "category",
    "score",
    "land_types",
    "possible_grant_values",
    "deadline_dates",
    "reason_found",
    "url",
]

available_cols = [col for col in display_cols if col in filtered.columns]

st.dataframe(
    filtered[available_cols].sort_values("score", ascending=False),
    use_container_width=True,
    hide_index=True,
)