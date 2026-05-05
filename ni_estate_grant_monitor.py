import csv
import re
import sqlite3
import warnings
from datetime import datetime, UTC
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

warnings.filterwarnings("ignore")

CSV_PATH = "colebrooke_grant_matches.csv"
DB_PATH = "seen.sqlite"

MAX_PAGES = 120

HEADERS = {
    "User-Agent": "BrockGrantFinder/1.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "identity",
}

ESTATE_TERMS = [
    "Northern Ireland", "Fermanagh", "Enniskillen", "Brookeborough",
    "Ireland", "UK", "United Kingdom", "rural", "cross-border",
    "farmer", "landowner", "land manager", "farm business", "estate"
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

GENERAL_PAGE_PHRASES = [
    "collection",
    "guidance",
    "topic",
    "policy",
    "consultation",
    "press release",
    "news article",
    "statistics",
    "research",
    "strategy",
    "framework",
    "landing page",
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

START_URLS = [
    # Northern Ireland — specific and useful sources
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

    # Aquaculture / fisheries
    "https://www.gov.uk/government/collections/marine-and-fisheries-grants",
    "https://www.gov.ie/en/department-of-agriculture-food-and-the-marine/services/fisheries-and-aquaculture/",

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


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def contains_any(text, phrases):
    text_l = text.lower()
    return any(phrase.lower() in text_l for phrase in phrases)


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
        r"£\s?\d[\d,]*(?:\.\d+)?\s?(?:million|m|k)?",
        r"€\s?\d[\d,]*(?:\.\d+)?\s?(?:million|m|k)?",
        r"\d[\d,]*(?:\.\d+)?\s?(?:per hectare|/ha|ha)",
        r"up to\s+£\s?\d[\d,]*(?:\.\d+)?\s?(?:million|m|k)?",
        r"up to\s+€\s?\d[\d,]*(?:\.\d+)?\s?(?:million|m|k)?",
    ]

    for pattern in patterns:
        for match in re.findall(pattern, text, re.IGNORECASE):
            values.append(clean(match))

    return sorted(set(values))[:12]


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


def extract_deadlines(text):
    patterns = [
        r"(closing date|deadline|closes|applications close|apply by|closing)\s.{0,140}",
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

    return sorted(set(phrases))[:8], sorted(set(parsed))


def is_open_available_grant(text, deadlines):
    text_l = text.lower()
    today = datetime.now(UTC).date()

    if contains_any(text_l, CLOSED_PHRASES):
        return False

    for deadline in deadlines:
        try:
            if datetime.fromisoformat(deadline).date() >= today:
                return True
        except Exception:
            pass

    if contains_any(text_l, OPEN_PHRASES):
        return True

    if "rolling basis" in text_l and contains_any(text_l, ["apply", "application", "grant", "funding"]):
        return True

    return False


def looks_like_specific_grant_page(title, text, url):
    title_l = title.lower()
    text_l = text.lower()
    url_l = url.lower()

    if contains_any(text_l, CLOSED_PHRASES):
        return False

    if "daera-ni.gov.uk/topics/" in url_l:
        return False

    if "gov.uk/government/collections/" in url_l:
        return False

    if title_l in ["grants and funding", "funding", "support", "guidance", "environment grants"]:
        return False

    specific_signal_count = sum(1 for signal in SPECIFIC_GRANT_SIGNALS if signal in text_l or signal in title_l or signal in url_l)

    if specific_signal_count < 2:
        return False

    if contains_any(title_l, GENERAL_PAGE_PHRASES) and not contains_any(text_l, OPEN_PHRASES):
        return False

    return True


def score_text(text, title, url, money_values):
    text_l = text.lower()
    title_l = title.lower()
    url_l = url.lower()
    score = 0

    for term in ESTATE_TERMS:
        if term.lower() in text_l or term.lower() in title_l:
            score += 3

    for category_words in CATEGORY_KEYWORDS.values():
        for word in category_words:
            if word.lower() in text_l or word.lower() in title_l:
                score += 1

    if contains_any(text_l, SPECIFIC_GRANT_SIGNALS):
        score += 10

    if contains_any(text_l, OPEN_PHRASES):
        score += 12

    if any(x in text_l for x in ["northern ireland", "fermanagh", "daera", "tourism ni", "invest ni"]):
        score += 12

    if any(x in text_l for x in ["ireland", "cross-border", "peaceplus", "interreg", "eu funding"]):
        score += 5

    if any(x in url_l for x in ["grant", "funding", "scheme", "support", "programme"]):
        score += 5

    score += grant_value_score(money_values)

    return score


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
    print("Starting Brock Grant Finder daily scraper...")

    conn = init_db()
    queue = list(START_URLS)
    visited = set()
    results = []
    new_count = 0

    while queue and len(visited) < MAX_PAGES:
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
        money_values = extract_money_values(text)
        category = classify_categories(text + " " + title)
        land_types = classify_land_type(text + " " + title)

        if not looks_like_specific_grant_page(title, text, url):
            for link in extract_links(url, soup):
                if link not in visited and link not in queue:
                    queue.append(link)
            continue

        if not is_open_available_grant(text, deadline_dates):
            for link in extract_links(url, soup):
                if link not in visited and link not in queue:
                    queue.append(link)
            continue

        score = score_text(text, title, url, money_values)
        source_region = source_region_from_url(url)

        if score >= 15:
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
                "snippet": text[:900],
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