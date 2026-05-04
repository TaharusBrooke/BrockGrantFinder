import csv
import re
import smtplib
import sqlite3
import warnings
from datetime import datetime, UTC
from email.message import EmailMessage
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

warnings.filterwarnings("ignore")

# =========================
# EMAIL SETTINGS - GMAIL
# =========================
EMAIL_FROM = "archiebrooke528@gmail.com"
EMAIL_TO = "colebrookeestate@outlook.com"

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

# Replace this with your NEW Outlook password or Outlook app password
SMTP_PASSWORD = "yvqjthbccglfpdwl"

# Change to today's day if testing immediately.
# Then change back to "Monday" afterwards.
SUMMARY_DAY = "Friday"

CSV_PATH = "colebrooke_grant_matches.csv"
DB_PATH = "seen.sqlite"

HEADERS = {
    "User-Agent": "ColebrookeEstateGrantMonitor/1.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "identity",
}

ESTATE_PROFILE = {
    "name": "Colebrooke Estate",
    "location_terms": [
        "Northern Ireland", "Fermanagh", "Enniskillen", "Brookeborough",
        "Ireland", "UK", "United Kingdom", "rural", "cross-border"
    ],
    "interest_terms": [
        "woodland", "forestry", "tree", "native woodland",
        "farm", "farming", "agriculture", "land manager",
        "peat", "peatland", "bog", "carbon",
        "river", "water", "watercourse", "flood", "catchment",
        "biodiversity", "habitat", "ASSI", "SSSI", "conservation",
        "heritage", "historic", "listed building", "monument",
        "public access", "recreation", "footpath", "walking", "cycling",
        "tourism", "visitor", "accommodation", "events", "rural tourism"
    ],
}

LAND_TYPES = {
    "woodland": ["woodland", "forestry", "tree", "forest", "native woodland"],
    "farmland": ["farm", "farming", "agriculture", "farmer", "land manager"],
    "peatland": ["peat", "bog", "peatland", "carbon"],
    "watercourses": ["river", "watercourse", "water quality", "flood", "catchment"],
    "conservation": ["assi", "sssi", "habitat", "biodiversity", "conservation", "nature"],
    "heritage": ["heritage", "historic", "listed building", "monument", "archaeology"],
    "public access": ["public access", "recreation", "footpath", "walking", "cycling"],
    "tourism": ["tourism", "visitor", "accommodation", "events", "rural tourism", "experience"],
}

START_URLS = [
    # Northern Ireland
    "https://www.daera-ni.gov.uk/topics/grants-and-funding",
    "https://www.daera-ni.gov.uk/articles/daera-forestry-grants",
    "https://www.daera-ni.gov.uk/articles/agricultural-environmental-scheme-details",
    "https://www.daera-ni.gov.uk/topics/environment-grants",
    "https://www.daera-ni.gov.uk/articles/sap-payment-schemes",
    "https://www.nidirect.gov.uk/articles/private-woodlands-plant-health-grants-and-funding",
    "https://www.tourismni.com/about/funding-schemes/",
    "https://www.nibusinessinfo.co.uk/content/funding-support-growing-tourism-business",
    "https://www.investni.com/support-for-business",
    "https://www.communities-ni.gov.uk/topics/historic-environment-funding-grants",

    # Cross-border / PEACEPLUS
    "https://www.seupb.eu/funding",

    # Republic of Ireland
    "https://www.gov.ie/en/department-of-agriculture-food-and-the-marine/publications/forestry-grants-and-schemes/",
    "https://www.teagasc.ie/crops/forestry/grants/",
    "https://www.citizensinformation.ie/en/environment/land/farming-grants-and-schemes/",
    "https://www.gov.ie/en/department-of-rural-and-community-development/",
    "https://www.failteireland.ie/Supports.aspx",
    "https://www.naturacommunities.ie/community-resources/funding-opportunities/",

    # UK-wide / mainland UK
    "https://www.find-government-grants.service.gov.uk/grants",
    "https://www.gov.uk/government/collections/find-government-grants",
    "https://www.heritagefund.org.uk/funding",
    "https://www.heritagefundingdirectoryuk.org/",
    "https://www.tnlcommunityfund.org.uk/funding",
    "https://www.national-lottery.co.uk/good-causes/funding",
    "https://historicengland.org.uk/advice/caring-for-heritage/rural-heritage/support-and-funding/",
    "https://www.woodlandtrust.org.uk/",
    "https://www.rspb.org.uk/",
    "https://www.rivers-trust.org/",
    "https://www.wildlifetrusts.org/",

    # EU
    "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/home",
    "https://cinea.ec.europa.eu/programmes/life_en",
    "https://commission.europa.eu/funding-tenders/find-funding/eu-funding-programmes_en",
    "https://transition-pathways.europa.eu/tourism/funding-mechanisms",
]

ALLOWED_DOMAINS = [
    "daera-ni.gov.uk",
    "nidirect.gov.uk",
    "tourismni.com",
    "nibusinessinfo.co.uk",
    "investni.com",
    "communities-ni.gov.uk",
    "seupb.eu",
    "gov.ie",
    "teagasc.ie",
    "citizensinformation.ie",
    "failteireland.ie",
    "naturacommunities.ie",
    "find-government-grants.service.gov.uk",
    "gov.uk",
    "heritagefund.org.uk",
    "heritagefundingdirectoryuk.org",
    "tnlcommunityfund.org.uk",
    "national-lottery.co.uk",
    "historicengland.org.uk",
    "woodlandtrust.org.uk",
    "rspb.org.uk",
    "rivers-trust.org",
    "wildlifetrusts.org",
    "ec.europa.eu",
    "commission.europa.eu",
    "cinea.ec.europa.eu",
    "transition-pathways.europa.eu",
]


def fetch(url):
    try:
        r = requests.get(url, timeout=20, headers=HEADERS)
        r.raise_for_status()

        content_type = r.headers.get("Content-Type", "").lower()
        if "text/html" not in content_type and "application/xhtml" not in content_type:
            print(f"Skipping non-webpage file: {url}")
            return ""

        return r.text

    except Exception as e:
        print(f"Could not open: {url}")
        print(e)
        return ""


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def extract_money_values(text):
    values = []

    patterns = [
        r"£\s?\d[\d,]*(?:\.\d+)?\s?(?:million|m|k)?",
        r"€\s?\d[\d,]*(?:\.\d+)?\s?(?:million|m|k)?",
        r"\d[\d,]*(?:\.\d+)?\s?(?:per hectare|/ha|ha)",
    ]

    for pattern in patterns:
        for match in re.findall(pattern, text, re.IGNORECASE):
            values.append(clean(match))

    return sorted(set(values))[:10]


def grant_value_score(values):
    score = 0
    joined = " ".join(values).lower()

    if "million" in joined or " m" in joined:
        score += 20
    if "£" in joined or "€" in joined:
        score += 10
    if "per hectare" in joined or "/ha" in joined:
        score += 8

    return score


def score_text(text, url=""):
    text_l = text.lower()
    url_l = url.lower()
    score = 0

    for term in ESTATE_PROFILE["location_terms"]:
        if term.lower() in text_l:
            score += 4

    for term in ESTATE_PROFILE["interest_terms"]:
        if term.lower() in text_l:
            score += 2

    if any(x in text_l for x in ["grant", "funding", "scheme", "support", "programme", "call for applications"]):
        score += 6

    if any(x in text_l for x in ["apply now", "applications open", "open for applications", "currently open"]):
        score += 6

    if any(x in text_l for x in ["tourism", "visitor", "rural tourism", "accommodation", "events"]):
        score += 8

    if any(x in text_l for x in ["northern ireland", "fermanagh", "daera", "tourism ni", "invest ni"]):
        score += 10

    if any(x in text_l for x in ["ireland", "cross-border", "peaceplus", "interreg", "eu funding"]):
        score += 4

    if any(x in url_l for x in ["funding", "grant", "scheme", "support"]):
        score += 4

    if any(x in text_l for x in ["applications closed", "scheme closed", "closed for applications"]):
        score -= 12

    money_values = extract_money_values(text)
    score += grant_value_score(money_values)

    return score


def extract_deadlines(text):
    patterns = [
        r"(closing date|deadline|closes|applications close|apply by|closing)\s.{0,120}",
        r"\b\d{1,2}\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b",
        r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",
    ]

    phrases = []
    parsed = []

    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            phrase = clean(match.group(0))
            phrases.append(phrase)

            try:
                d = dateparser.parse(phrase, fuzzy=True, dayfirst=True)
                if d:
                    parsed.append(d.date().isoformat())
            except Exception:
                pass

    return sorted(set(phrases))[:8], sorted(set(parsed))


def is_open(text, deadlines):
    text_l = text.lower()
    today = datetime.now(UTC).date()

    closed_phrases = [
        "applications closed",
        "scheme closed",
        "closed for applications",
        "no longer open",
        "deadline has passed",
        "this scheme is now closed",
    ]

    open_phrases = [
        "applications open",
        "apply now",
        "open for applications",
        "currently open",
        "you can apply",
        "call is open",
        "accepting applications",
    ]

    if any(phrase in text_l for phrase in closed_phrases):
        return False

    for d in deadlines:
        try:
            if datetime.fromisoformat(d).date() >= today:
                return True
        except Exception:
            pass

    if any(phrase in text_l for phrase in open_phrases):
        return True

    return False


def classify_land_type(text):
    text_l = text.lower()
    types = []

    for land_type, words in LAND_TYPES.items():
        if any(word in text_l for word in words):
            types.append(land_type)

    return ", ".join(types)


def extract_links(base_url, soup):
    links = []

    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"])
        label = clean(a.get_text(" ", strip=True))
        combined = f"{label} {href}".lower()

        if not any(domain in href for domain in ALLOWED_DOMAINS):
            continue

        if any(x in combined for x in [
            "grant", "fund", "funding", "scheme", "support", "programme",
            "forestry", "woodland", "farm", "tourism", "heritage",
            "environment", "biodiversity", "rural", "water", "peat",
            "application", "apply"
        ]):
            links.append(href)

    return list(dict.fromkeys(links))


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS seen(url TEXT PRIMARY KEY)")
    conn.commit()
    return conn


def is_new(conn, url):
    cur = conn.execute("SELECT 1 FROM seen WHERE url=?", (url,))
    if cur.fetchone():
        return False

    conn.execute("INSERT INTO seen VALUES(?)", (url,))
    conn.commit()
    return True


def source_region_from_url(url):
    if any(x in url for x in [
        "daera-ni.gov.uk", "nidirect.gov.uk", "tourismni.com",
        "investni.com", "nibusinessinfo.co.uk", "communities-ni.gov.uk"
    ]):
        return "Northern Ireland"

    if any(x in url for x in [
        "gov.ie", "teagasc.ie", "citizensinformation.ie",
        "failteireland.ie", "naturacommunities.ie"
    ]):
        return "Republic of Ireland"

    if any(x in url for x in [
        "ec.europa.eu", "commission.europa.eu",
        "cinea.ec.europa.eu", "transition-pathways.europa.eu"
    ]):
        return "EU"

    if "seupb.eu" in url:
        return "Cross-border / PEACEPLUS"

    return "UK-wide / mainland UK"


def send_weekly_email(results):
    today_name = datetime.now(UTC).strftime("%A")

    if today_name != SUMMARY_DAY:
        print(f"Today is {today_name}. Weekly email only sends on {SUMMARY_DAY}.")
        return

    if not results:
        print("No results to email.")
        return

    if not SMTP_PASSWORD or SMTP_PASSWORD == "PUT_YOUR_NEW_OUTLOOK_PASSWORD_HERE":
        print("Email not sent: please add your Outlook password/app password in the script.")
        return

    top_results = results[:25]

    msg = EmailMessage()
    msg["Subject"] = f"Weekly Colebrooke Estate grant summary - {len(results)} matches"
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO

    lines = [
        "Weekly grant and funding summary for Colebrooke Estate",
        "",
        f"Total open relevant matches found: {len(results)}",
        "",
        "Top opportunities, prioritised by relevance and possible grant value:",
        "",
    ]

    for i, m in enumerate(top_results, start=1):
        lines.append(f"{i}. {m['title']}")
        lines.append(f"   Source region: {m['source_region']}")
        lines.append(f"   Relevance score: {m['score']}")
        lines.append(f"   Land / tourism type: {m['land_types'] or 'Not clearly classified'}")
        lines.append(f"   Possible grant value: {m['possible_grant_values'] or 'Not clearly found'}")
        lines.append(f"   Deadline: {m['deadline_dates'] or 'Not clearly found'}")
        lines.append(f"   URL: {m['url']}")
        lines.append("")

    msg.set_content("\n".join(lines))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.starttls()
            s.login(EMAIL_FROM, SMTP_PASSWORD)
            s.send_message(msg)

        print("Weekly summary email sent.")

    except Exception as e:
        print("Email failed to send.")
        print("Most likely causes: wrong password, Outlook blocking SMTP, or needing an app password.")
        print(e)


def main():
    print("Starting expanded Colebrooke Estate grant search...")

    conn = init_db()
    queue = list(START_URLS)
    visited = set()
    results = []
    new_matches = []

    while queue and len(visited) < 300:
        url = queue.pop(0)

        if url in visited:
            continue

        visited.add(url)
        print(f"Checking: {url}")

        html = fetch(url)
        if not html:
            continue

        try:
            soup = BeautifulSoup(html, "html.parser")
        except Exception as e:
            print(f"Could not read page properly, skipping: {url}")
            print(e)
            continue

        text = clean(soup.get_text(" ", strip=True))

        title_tag = soup.find("h1") or soup.find("title")
        title = clean(title_tag.get_text(" ", strip=True)) if title_tag else url

        deadline_phrases, deadline_dates = extract_deadlines(text)
        open_flag = is_open(text, deadline_dates)
        money_values = extract_money_values(text)
        score = score_text(text + " " + title, url)
        land_types = classify_land_type(text + " " + title)
        source_region = source_region_from_url(url)

        if score >= 12 and open_flag:
            record = {
                "checked_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "title": title,
                "url": url,
                "source_region": source_region,
                "is_open": open_flag,
                "score": score,
                "land_types": land_types,
                "possible_grant_values": ", ".join(money_values),
                "deadline_dates": ", ".join(deadline_dates),
                "deadline_phrases": " | ".join(deadline_phrases),
                "snippet": text[:800],
            }

            results.append(record)

            if is_new(conn, url):
                new_matches.append(record)

        for link in extract_links(url, soup):
            if link not in visited and link not in queue:
                queue.append(link)

    results.sort(key=lambda r: r["score"], reverse=True)

    fieldnames = [
        "checked_at",
        "title",
        "url",
        "source_region",
        "is_open",
        "score",
        "land_types",
        "possible_grant_values",
        "deadline_dates",
        "deadline_phrases",
        "snippet",
    ]

    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    send_weekly_email(results)

    print("")
    print("Finished.")
    print(f"Pages checked: {len(visited)}")
    print(f"Open relevant matches found: {len(results)}")
    print(f"New matches found since last run: {len(new_matches)}")
    print(f"Results saved to: {CSV_PATH}")


if __name__ == "__main__":
    main()