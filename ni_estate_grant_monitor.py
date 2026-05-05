import csv
import re
import sqlite3
import warnings
from datetime import datetime, UTC
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

warnings.filterwarnings("ignore")

CSV_PATH = "colebrooke_grant_matches.csv"
DB_PATH = "seen.sqlite"
MAX_PAGES = 150

HEADERS = {
    "User-Agent": "BrockGrantFinder/1.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "identity",
}

BLOCKED_URL_PARTS = [
    "/news",
    "/news/",
    "/press-release",
    "/press-releases",
    "/consultations",
    "/publications",
    "/statistics",
    "/research",
    "/search",
    "?q=",
    "search-results",
    "translation",
    "cookies",
    "privacy",
    "accessibility",
    "contact",
    "about-us",
]

BLOCKED_TITLES = [
    "news",
    "search results",
    "search",
    "publications",
    "consultations",
    "contact",
    "about us",
    "cookies",
    "privacy notice",
    "accessibility statement",
    "grants and funding",
    "environment grants",
    "funding",
    "support",
]

OPEN_PHRASES = [
    "applications open",
    "open for applications",
    "apply now",
    "you can apply",
    "currently open",
    "accepting applications",
    "call is open",
    "open call",
    "fund is open",
    "scheme is open",
    "rolling basis",
]

CLOSED_PHRASES = [
    "applications closed",
    "closed for applications",
    "scheme closed",
    "fund closed",
    "no longer accepting applications",
    "no longer open",
    "deadline has passed",
    "this scheme is now closed",
    "closed programme",
    "archived",
]

SPECIFIC_GRANT_SIGNALS = [
    "grant",
    "funding",
    "scheme",
    "programme",
    "application",
    "apply",
    "eligible",
    "eligibility",
    "deadline",
    "closing date",
    "capital grant",
    "payment",
    "support package",
    "fund",
]

CATEGORY_KEYWORDS = {
    "agriculture": [
        "agriculture", "farm", "farmer", "farming", "farm business",
        "livestock", "suckler", "beef", "sheep", "dairy", "poultry",
        "chicken", "egg", "broiler", "hen", "agri"
    ],
    "forestry": [
        "forestry", "woodland", "forest", "tree", "planting",
        "woodland creation", "native woodland", "woodland management"
    ],
    "horticulture": [
        "horticulture", "fruit", "vegetable", "glasshouse", "polytunnel",
        "market garden", "orchard", "horticultural"
    ],
    "aquaculture": [
        "aquaculture", "fish farm", "fisheries", "seafood", "marine",
        "salmon", "shellfish", "pond"
    ],
    "heritage": [
        "heritage", "historic", "listed building", "scheduled monument",
        "archaeology", "traditional farm buildings", "conservation area"
    ],
    "tourism": [
        "tourism", "visitor", "accommodation", "hotel", "glamping",
        "camping", "events", "experience", "rural tourism", "hospitality"
    ],
    "roads_access_infrastructure": [
        "road", "roads", "access", "lane", "track", "infrastructure",
        "bridge", "path", "right of way", "public access", "greenway",
        "walking", "cycling", "trail"
    ],
    "water_flood_drainage": [
        "river", "watercourse", "water quality", "flood", "drainage",
        "catchment", "wetland", "riparian", "natural flood management"
    ],
    "peatland_carbon": [
        "peat", "peatland", "bog", "carbon", "net zero", "climate",
        "emissions", "carbon farming"
    ],
    "biodiversity_conservation": [
        "biodiversity", "habitat", "species", "nature", "conservation",
        "ASSI", "SSSI", "wildlife", "rewilding", "nature recovery"
    ],
    "rural_business": [
        "business", "enterprise", "rural business", "diversification",
        "innovation", "capital grant", "productivity", "equipment"
    ],
    "energy_renewables": [
        "renewable", "solar", "wind", "biomass", "energy efficiency",
        "heat pump", "anaerobic digestion", "net zero"
    ],
    "national_lottery": [
        "national lottery", "lottery funding", "community fund",
        "heritage fund", "good causes"
    ],
}

LAND_TYPES = {
    "woodland": CATEGORY_KEYWORDS["forestry"],
    "farmland": CATEGORY_KEYWORDS["agriculture"],
    "horticulture": CATEGORY_KEYWORDS["horticulture"],
    "aquaculture": CATEGORY_KEYWORDS["aquaculture"],
    "poultry": ["poultry", "chicken", "broiler", "egg", "hen"],
    "peatland": CATEGORY_KEYWORDS["peatland_carbon"],
    "watercourses": CATEGORY_KEYWORDS["water_flood_drainage"],
    "conservation": CATEGORY_KEYWORDS["biodiversity_conservation"],
    "heritage": CATEGORY_KEYWORDS["heritage"],
    "public access": CATEGORY_KEYWORDS["roads_access_infrastructure"],
    "tourism": CATEGORY_KEYWORDS["tourism"],
    "rural business": CATEGORY_KEYWORDS["rural_business"],
    "energy": CATEGORY_KEYWORDS["energy_renewables"],
}

START_URLS = [
    "https://www.find-government-grants.service.gov.uk/grants",
    "https://www.heritagefund.org.uk/funding",
    "https://www.tnlcommunityfund.org.uk/funding",
    "https://www.national-lottery.co.uk/good-causes/funding",
    "https://www.tourismni.com/about/funding-schemes/",
    "https://www.nibusinessinfo.co.uk/content/funding-support-growing-tourism-business",
    "https://www.investni.com/support-for-business",
    "https://www.daera-ni.gov.uk/articles/daera-forestry-grants",
    "https://www.daera-ni.gov.uk/articles/agricultural-environmental-scheme-details",
    "https://www.nidirect.gov.uk/articles/private-woodlands-plant-health-grants-and-funding",
    "https://www.communities-ni.gov.uk/topics/historic-environment-funding-grants",
    "https://www.seupb.eu/funding",
    "https://www.failteireland.ie/Supports.aspx",
    "https://www.teagasc.ie/crops/forestry/grants/",
    "https://www.gov.ie/en/department-of-rural-and-community-development/",
    "https://cinea.ec.europa.eu/programmes/life_en",
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
    "failteireland.ie",
    "find-government-grants.service.gov.uk",
    "heritagefund.org.uk",
    "tnlcommunityfund.org.uk",
    "national-lottery.co.uk",
    "cinea.ec.europa.eu",
]


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def contains_any(text, phrases):
    text_l = text.lower()
    return any(phrase.lower() in text_l for phrase in phrases)


def is_blocked_url(url):
    url_l = url.lower()

    if any(part in url_l for part in BLOCKED_URL_PARTS):
        return True

    if "daera-ni.gov.uk/news" in url_l:
        return True

    if "find-government-grants.service.gov.uk/grants" == url_l.rstrip("/"):
        return True

    return False


def fetch(url):
    try:
        response = requests.get(url, timeout=20, headers=HEADERS)
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "").lower()

        if "text/html" not in content_type and "application/xhtml" not in content_type:
            print(f"Skipping non-webpage file: {url}")
            return ""

        return response.text

    except Exception as e:
        print(f"Could not open: {url}")
        print(e)
        return ""


def remove_junk(soup):
    for tag in soup([
        "script", "style", "nav", "footer", "header", "aside",
        "form", "button", "select", "option"
    ]):
        tag.decompose()

    for selector in [
        ".translation-help",
        ".language-switcher",
        ".cookie-banner",
        ".govuk-cookie-banner",
        ".site-footer",
        ".site-header",
        ".navigation",
        ".menu",
    ]:
        for element in soup.select(selector):
            element.decompose()

    return soup


def extract_main_text(soup):
    soup = remove_junk(soup)

    main = (
        soup.find("main")
        or soup.find("article")
        or soup.find("div", {"role": "main"})
        or soup.body
        or soup
    )

    return clean(main.get_text(" ", strip=True))


def extract_title(soup, url):
    h1 = soup.find("h1")

    if h1:
        return clean(h1.get_text(" ", strip=True))

    title = soup.find("title")

    if title:
        return clean(title.get_text(" ", strip=True))

    return url


def classify_categories(text):
    text_l = text.lower()
    categories = []

    for category, words in CATEGORY_KEYWORDS.items():
        if any(word.lower() in text_l for word in words):
            categories.append(category)

    return ", ".join(categories)


def classify_land_type(text):
    text_l = text.lower()
    types = []

    for land_type, words in LAND_TYPES.items():
        if any(word.lower() in text_l for word in words):
            types.append(land_type)

    return ", ".join(types)


def extract_money_values(text):
    values = []

    patterns = [
        r"up to\s+£\s?\d[\d,]*(?:\.\d+)?\s?(?:million|m|k)?",
        r"up to\s+€\s?\d[\d,]*(?:\.\d+)?\s?(?:million|m|k)?",
        r"£\s?\d[\d,]*(?:\.\d+)?\s?(?:million|m|k)?",
        r"€\s?\d[\d,]*(?:\.\d+)?\s?(?:million|m|k)?",
        r"\d[\d,]*(?:\.\d+)?\s?(?:per hectare|/ha)",
    ]

    for pattern in patterns:
        for match in re.findall(pattern, text, re.IGNORECASE):
            values.append(clean(match))

    return sorted(set(values))[:8]


def extract_deadlines(text):
    patterns = [
        r"(closing date|deadline|closes|applications close|apply by|closing)\s.{0,100}",
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
                parsed_date = dateparser.parse(phrase, fuzzy=True, dayfirst=True)
                if parsed_date:
                    parsed.append(parsed_date.date().isoformat())
            except Exception:
                pass

    return sorted(set(phrases))[:5], sorted(set(parsed))


def has_future_deadline(deadlines):
    today = datetime.now(UTC).date()

    for deadline in deadlines:
        try:
            if datetime.fromisoformat(deadline).date() >= today:
                return True
        except Exception:
            pass

    return False


def is_open_available_grant(title, text, url, deadlines):
    title_l = title.lower()
    text_l = text.lower()
    url_l = url.lower()

    if is_blocked_url(url):
        return False

    if title_l.strip() in BLOCKED_TITLES:
        return False

    if contains_any(text_l, CLOSED_PHRASES):
        return False

    specific_signal_count = sum(
        1 for signal in SPECIFIC_GRANT_SIGNALS
        if signal in title_l or signal in text_l or signal in url_l
    )

    if specific_signal_count < 3:
        return False

    has_open_signal = contains_any(text_l, OPEN_PHRASES)
    has_deadline = has_future_deadline(deadlines)

    if not has_open_signal and not has_deadline:
        return False

    if len(text_l) < 350:
        return False

    if title_l in ["search results", "news", "funding", "grants"]:
        return False

    return True


def grant_value_score(values):
    joined = " ".join(values).lower()
    score = 0

    if "million" in joined:
        score += 20
    if "£" in joined or "€" in joined:
        score += 12
    if "per hectare" in joined or "/ha" in joined:
        score += 8
    if "up to" in joined:
        score += 6

    return score


def score_text(title, text, url, money_values):
    text_l = text.lower()
    title_l = title.lower()
    url_l = url.lower()
    score = 0

    if any(x in text_l for x in ["northern ireland", "fermanagh", "daera", "tourism ni", "invest ni"]):
        score += 15

    if any(x in text_l for x in ["farmer", "farm", "landowner", "land manager", "rural business"]):
        score += 10

    if contains_any(text_l, OPEN_PHRASES):
        score += 15

    if any(x in url_l for x in ["grant", "funding", "scheme", "support", "programme"]):
        score += 8

    for category_words in CATEGORY_KEYWORDS.values():
        for word in category_words:
            if word.lower() in text_l or word.lower() in title_l:
                score += 1

    score += grant_value_score(money_values)

    return score


def source_region_from_url(url):
    if any(x in url for x in [
        "daera-ni.gov.uk", "nidirect.gov.uk", "tourismni.com",
        "investni.com", "nibusinessinfo.co.uk", "communities-ni.gov.uk"
    ]):
        return "Northern Ireland"

    if any(x in url for x in [
        "gov.ie", "teagasc.ie", "failteireland.ie"
    ]):
        return "Republic of Ireland"

    if "seupb.eu" in url:
        return "Cross-border / PEACEPLUS"

    if "cinea.ec.europa.eu" in url:
        return "EU"

    return "UK-wide / mainland UK"


def extract_links(base_url, soup):
    links = []

    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"])
        label = clean(a.get_text(" ", strip=True))
        combined = f"{label} {href}".lower()

        if is_blocked_url(href):
            continue

        if not any(domain in href for domain in ALLOWED_DOMAINS):
            continue

        if any(x in combined for x in [
            "grant", "fund", "funding", "scheme", "support", "programme",
            "application", "apply", "forestry", "woodland", "farm",
            "agriculture", "horticulture", "aquaculture", "poultry",
            "chicken", "heritage", "tourism", "lottery", "road",
            "infrastructure", "water", "flood", "peat", "business",
            "rural", "energy", "renewable"
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


def main():
    print("Starting Brock Grant Finder scraper...")

    conn = init_db()
    queue = list(START_URLS)
    visited = set()
    results = []
    new_count = 0

    while queue and len(visited) < MAX_PAGES:
        url = queue.pop(0)

        if url in visited or is_blocked_url(url):
            continue

        visited.add(url)
        print(f"Checking: {url}")

        html = fetch(url)

        if not html:
            continue

        try:
            soup = BeautifulSoup(html, "html.parser")
        except Exception as e:
            print(f"Could not parse page: {url}")
            print(e)
            continue

        title = extract_title(soup, url)
        text = extract_main_text(soup)

        deadline_phrases, deadline_dates = extract_deadlines(text)
        money_values = extract_money_values(text)

        if is_open_available_grant(title, text, url, deadline_dates):
            category = classify_categories(text + " " + title)
            land_types = classify_land_type(text + " " + title)
            score = score_text(title, text, url, money_values)
            source_region = source_region_from_url(url)

            if score >= 25:
                record = {
                    "last_checked": datetime.now(UTC).isoformat(timespec="seconds"),
                    "title": title,
                    "url": url,
                    "source_region": source_region,
                    "category": category,
                    "is_open": True,
                    "score": score,
                    "land_types": land_types,
                    "possible_grant_values": ", ".join(money_values),
                    "deadline_dates": ", ".join(deadline_dates),
                    "deadline_phrases": " | ".join(deadline_phrases),
                    "snippet": text[:750],
                }

                results.append(record)

                if is_new(conn, url):
                    new_count += 1

        for link in extract_links(url, soup):
            if link not in visited and link not in queue:
                queue.append(link)

    results.sort(key=lambda r: r["score"], reverse=True)

    fieldnames = [
        "last_checked",
        "title",
        "url",
        "source_region",
        "category",
        "is_open",
        "score",
        "land_types",
        "possible_grant_values",
        "deadline_dates",
        "deadline_phrases",
        "snippet",
    ]

    with open(CSV_PATH, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print("")
    print("Finished.")
    print(f"Pages checked: {len(visited)}")
    print(f"Open specific grant matches found: {len(results)}")
    print(f"New matches since last run: {new_count}")
    print(f"Results saved to: {CSV_PATH}")


if __name__ == "__main__":
    main()