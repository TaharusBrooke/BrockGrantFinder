import csv
import io
import re
import time
import urllib.robotparser
from datetime import datetime, UTC
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser
from pypdf import PdfReader

RESULTS_CSV = "colebrooke_grant_matches.csv"
REVIEW_CSV = "grant_review_pages.csv"

MAX_PAGES = 180
RATE_LIMIT_SECONDS = 2

USER_AGENT = "BrockGrantFinder/1.0 lawful public grant research contact: colebrookeestate@outlook.com"

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.8",
}

START_URLS = [
    # Northern Ireland
    "https://www.daera-ni.gov.uk/topics/grants-and-funding",
    "https://www.daera-ni.gov.uk/articles/agricultural-environmental-scheme-details",
    "https://www.daera-ni.gov.uk/articles/daera-forestry-grants",
    "https://www.daera-ni.gov.uk/articles/rural-development-grants",
    "https://www.daera-ni.gov.uk/articles/environment-fund-water-quality-improvement-strand",
    "https://www.nidirect.gov.uk/articles/private-woodlands-plant-health-grants-and-funding",
    "https://www.tourismni.com/about/funding-schemes/",
    "https://www.nibusinessinfo.co.uk/content/funding-support-growing-tourism-business",
    "https://www.investni.com/support-for-business",
    "https://www.communities-ni.gov.uk/topics/historic-environment-funding-grants",
    "https://communityfoundationni.org/grants/",
    "https://www.ulsterwildlife.org/",
    "https://theriverstrust.org/our-work/our-projects/sustainable-catchment-programme-northern-ireland",

    # UK-wide / GB
    "https://www.find-government-grants.service.gov.uk/grants",
    "https://www.heritagefund.org.uk/funding",
    "https://www.tnlcommunityfund.org.uk/funding",
    "https://www.national-lottery.co.uk/good-causes/funding",
    "https://www.woodlandtrust.org.uk/plant-trees/trees-for-landowners-and-farmers/",
    "https://www.woodlandtrust.org.uk/plant-trees/schools-and-communities/",
    "https://www.rspb.org.uk/",
    "https://www.nationaltrust.org.uk/services/grants-and-funding",
    "https://farminginnovation.ukri.org/",
    "https://www.ukri.org/opportunity/",
    "https://www.gov.uk/guidance/funding-for-farmers",
    "https://www.gov.uk/guidance/england-woodland-creation-offer",

    # Scotland
    "https://www.ruralpayments.org/topics/all-schemes/",
    "https://www.ruralpayments.org/topics/all-schemes/agri-environment-climate-scheme/",
    "https://www.ruralpayments.org/topics/all-schemes/forestry-grant-scheme/",
    "https://forestry.gov.scot/support-regulations/forestry-grants",

    # Wales
    "https://www.gov.wales/farming-and-countryside-grants",
    "https://businesswales.gov.wales/",
    "https://www.gov.wales/woodland-creation-grant-window-6-rules-booklet-html",
    "https://www.gov.wales/sustainable-farming-scheme-2026-scheme-description-html",

    # Republic of Ireland / border relevance
    "https://www.gov.ie/en/department-of-agriculture-food-and-the-marine/collections/tams-3/",
    "https://www.gov.ie/en/department-of-agriculture-food-and-the-marine/publications/forestry-grants-and-schemes/",
    "https://www.gov.ie/en/department-of-agriculture-food-and-the-marine/collections/organic-farming-scheme/",
    "https://www.failteireland.ie/Supports.aspx",
    "https://www.catchments.ie/",
    "https://www.npws.ie/legislation/national-biodiversity-action-plan/local-biodiversity-action-fund",

    # Cross-border / EU
    "https://www.seupb.eu/funding",
    "https://www.interregeurope.eu/funding",
    "https://environment.ec.europa.eu/funding_en",
    "https://cinea.ec.europa.eu/programmes/life_en",
    "https://eu-cap-network.ec.europa.eu/publications/funding-opportunities-under-horizon-europe-calls-2026_en",
]

ALLOWED_DOMAINS = [
    "daera-ni.gov.uk",
    "nidirect.gov.uk",
    "tourismni.com",
    "nibusinessinfo.co.uk",
    "investni.com",
    "communities-ni.gov.uk",
    "communityfoundationni.org",
    "ulsterwildlife.org",
    "theriverstrust.org",
    "find-government-grants.service.gov.uk",
    "heritagefund.org.uk",
    "tnlcommunityfund.org.uk",
    "national-lottery.co.uk",
    "woodlandtrust.org.uk",
    "rspb.org.uk",
    "nationaltrust.org.uk",
    "farminginnovation.ukri.org",
    "ukri.org",
    "gov.uk",
    "ruralpayments.org",
    "forestry.gov.scot",
    "gov.wales",
    "businesswales.gov.wales",
    "gov.ie",
    "failteireland.ie",
    "catchments.ie",
    "npws.ie",
    "seupb.eu",
    "interregeurope.eu",
    "environment.ec.europa.eu",
    "cinea.ec.europa.eu",
    "eu-cap-network.ec.europa.eu",
]

NI_LOCATION_KEYWORDS = [
    "ni", "northern ireland", "fermanagh", "tyrone", "enniskillen",
    "colebrooke", "fivemiletown", "armagh", "down", "antrim",
    "derry", "londonderry", "cavan", "monaghan", "donegal",
    "leitrim", "louth", "sligo", "border counties", "cross-border",
]

CATEGORY_KEYWORDS = {
    "agriculture": ["farm", "farmer", "farming", "agriculture", "livestock", "dairy", "beef", "sheep", "poultry", "chicken", "eggs", "slurry"],
    "forestry": ["woodland", "forestry", "trees", "tree planting", "afforestation", "native woodland", "shelterbelt"],
    "biodiversity": ["biodiversity", "habitat", "species", "nature recovery", "conservation", "wildlife", "assi", "sssi"],
    "water": ["river", "water quality", "catchment", "wetland", "flood", "riparian", "drainage", "nutrients"],
    "heritage": ["heritage", "historic", "listed building", "monument", "traditional farm buildings", "archaeology"],
    "tourism": ["tourism", "visitor", "experience", "accommodation", "hospitality", "glamping", "rural tourism"],
    "rural_business": ["rural business", "enterprise", "micro-business", "diversification", "equipment", "capital grant"],
    "horticulture": ["horticulture", "fruit", "vegetable", "glasshouse", "polytunnel", "orchard"],
    "aquaculture": ["aquaculture", "fisheries", "fish farm", "shellfish", "marine"],
    "energy": ["solar", "renewable", "energy efficiency", "biomass", "heat pump", "net zero"],
}

OPEN_PHRASES = [
    "applications are open", "applications open", "open for applications",
    "apply now", "you can apply", "currently open", "accepting applications",
    "call is open", "open call", "rolling basis", "open all year",
]

CLOSED_PHRASES = [
    "applications closed", "closed for applications", "scheme closed",
    "fund closed", "no longer accepting applications", "deadline has passed",
    "this scheme is now closed", "archived",
]

GRANT_SIGNALS = [
    "grant", "funding", "fund", "scheme", "programme", "application",
    "apply", "eligible", "eligibility", "deadline", "closing date",
    "capital grant", "payment", "support",
]

SOFT_NEGATIVE_URL_PARTS = [
    "/news", "/press-release", "/press-releases", "/publications",
    "/consultations", "/statistics", "/research", "/search", "search-results",
]

HARD_BLOCKED_URL_PARTS = [
    "login", "signin", "account", "privacy", "cookies", "accessibility",
    "terms-and-conditions", "contact-us", "mailto:",
]

robots_cache = {}


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def allowed_domain(url):
    domain = urlparse(url).netloc.lower().replace("www.", "")
    return any(domain.endswith(d.replace("www.", "")) for d in ALLOWED_DOMAINS)


def robots_allowed(url):
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"

    if base not in robots_cache:
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(urljoin(base, "/robots.txt"))

        try:
            rp.read()
            robots_cache[base] = rp
        except Exception:
            return False

    return robots_cache[base].can_fetch(USER_AGENT, url)


def fetch(url):
    if not allowed_domain(url):
        return None, "domain not approved"

    if not robots_allowed(url):
        return None, "robots.txt disallows access"

    if any(part in url.lower() for part in HARD_BLOCKED_URL_PARTS):
        return None, "blocked URL"

    time.sleep(RATE_LIMIT_SECONDS)

    try:
        response = requests.get(url, timeout=25, headers=HEADERS)
        response.raise_for_status()
        return response, ""
    except Exception as e:
        return None, f"request failed: {e}"


def remove_junk(soup):
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "button", "select", "option"]):
        tag.decompose()

    return soup


def extract_html_text(response):
    soup = BeautifulSoup(response.text, "html.parser")
    soup = remove_junk(soup)

    title_tag = soup.find("h1") or soup.find("title")
    title = clean(title_tag.get_text(" ", strip=True)) if title_tag else response.url

    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = clean(main.get_text(" ", strip=True))

    meta = soup.select_one("meta[name='description']") or soup.select_one("meta[property='og:description']")
    meta_description = clean(meta.get("content")) if meta and meta.get("content") else ""

    return title, text, meta_description, soup


def extract_pdf_text(response):
    try:
        reader = PdfReader(io.BytesIO(response.content))
        pages = []

        for page in reader.pages[:12]:
            pages.append(page.extract_text() or "")

        text = clean(" ".join(pages))
        title = response.url.split("/")[-1].replace("-", " ").replace(".pdf", "")
        return title, text, "", None
    except Exception as e:
        return response.url, "", "", None


def extract_page_content(response):
    content_type = response.headers.get("Content-Type", "").lower()
    url_l = response.url.lower()

    if "pdf" in content_type or url_l.endswith(".pdf"):
        return extract_pdf_text(response)

    return extract_html_text(response)


def extract_links(base_url, soup):
    if soup is None:
        return []

    links = []

    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"])
        label = clean(a.get_text(" ", strip=True))
        combined = f"{label} {href}".lower()

        if not allowed_domain(href):
            continue

        if any(part in href.lower() for part in HARD_BLOCKED_URL_PARTS):
            continue

        if any(signal in combined for signal in GRANT_SIGNALS + list(sum(CATEGORY_KEYWORDS.values(), []))):
            links.append(href)

    return list(dict.fromkeys(links))


def extract_money_values(text):
    patterns = [
        r"up to\s+£\s?\d[\d,]*(?:\.\d+)?\s?(?:million|m|k)?",
        r"up to\s+€\s?\d[\d,]*(?:\.\d+)?\s?(?:million|m|k)?",
        r"£\s?\d[\d,]*(?:\.\d+)?\s?(?:million|m|k)?",
        r"€\s?\d[\d,]*(?:\.\d+)?\s?(?:million|m|k)?",
        r"\d[\d,]*(?:\.\d+)?\s?(?:per hectare|/ha)",
    ]

    values = []

    for pattern in patterns:
        values.extend(re.findall(pattern, text, re.IGNORECASE))

    return sorted(set(clean(v) for v in values))[:10]


def extract_deadlines(text):
    deadline_context_patterns = [
        r"(closing date|deadline|applications close|apply by|closing deadline|submission deadline|call closes)\s.{0,120}",
        r".{0,40}(closing date|deadline|applications close|apply by|call closes).{0,80}",
    ]

    parsed_dates = []
    phrases = []

    for pattern in deadline_context_patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            phrase = clean(match.group(0))
            phrase_l = phrase.lower()

            if any(bad in phrase_l for bad in ["published", "updated", "event", "webinar", "meeting"]):
                continue

            try:
                date = dateparser.parse(phrase, fuzzy=True, dayfirst=True)
                if date:
                    parsed_dates.append(date.date().isoformat())
                    phrases.append(phrase)
            except Exception:
                pass

    return sorted(set(parsed_dates)), sorted(set(phrases))[:6]


def future_deadline(deadlines):
    today = datetime.now(UTC).date()

    for d in deadlines:
        try:
            if datetime.fromisoformat(d).date() >= today:
                return True
        except Exception:
            pass

    return False


def classify(text, keyword_map):
    text_l = text.lower()
    matches = []

    for label, words in keyword_map.items():
        if any(word.lower() in text_l for word in words):
            matches.append(label)

    return ", ".join(matches)


def infer_source_region(url):
    domain = urlparse(url).netloc.lower()

    if any(d in domain for d in ["daera-ni.gov.uk", "nidirect.gov.uk", "tourismni.com", "investni.com", "communities-ni.gov.uk", "communityfoundationni.org"]):
        return "Northern Ireland"

    if any(d in domain for d in ["gov.ie", "failteireland.ie", "catchments.ie", "npws.ie"]):
        return "Republic of Ireland"

    if any(d in domain for d in ["ruralpayments.org", "forestry.gov.scot"]):
        return "Scotland"

    if "gov.wales" in domain or "businesswales" in domain:
        return "Wales"

    if any(d in domain for d in ["environment.ec.europa.eu", "cinea.ec.europa.eu", "eu-cap-network.ec.europa.eu", "interregeurope.eu"]):
        return "EU / international"

    if "seupb.eu" in domain:
        return "Cross-border"

    return "UK-wide"


def infer_eligibility_region(text, url):
    text_l = text.lower()
    regions = []

    region_terms = {
        "Northern Ireland": ["northern ireland", " ni ", "daera", "fermanagh", "tyrone", "enniskillen", "armagh", "antrim", "down", "londonderry", "derry"],
        "Republic of Ireland": ["republic of ireland", "ireland", "cavan", "monaghan", "donegal", "leitrim", "louth", "sligo"],
        "England": ["england", "defra", "rpa"],
        "Scotland": ["scotland", "scottish"],
        "Wales": ["wales", "welsh", "cymru"],
        "Cross-border": ["cross-border", "peaceplus", "interreg", "border counties"],
        "EU / international": ["european union", "horizon europe", "life programme", "eu applicants", "international"],
    }

    for region, terms in region_terms.items():
        if any(term in text_l for term in terms):
            regions.append(region)

    if not regions:
        regions.append(infer_source_region(url))

    return ", ".join(sorted(set(regions)))


def score_page(title, text, url, money_values, deadlines):
    combined = f"{title} {text} {url}".lower()
    score = 0
    reasons = []

    grant_signal_count = sum(1 for signal in GRANT_SIGNALS if signal in combined)
    category_matches = classify(combined, CATEGORY_KEYWORDS)

    if grant_signal_count:
        score += grant_signal_count * 4
        reasons.append(f"{grant_signal_count} grant signals")

    if category_matches:
        score += 15
        reasons.append(f"category keywords: {category_matches}")

    if any(term in combined for term in NI_LOCATION_KEYWORDS):
        score += 20
        reasons.append("NI / border region keywords")

    if any(phrase in combined for phrase in OPEN_PHRASES):
        score += 20
        reasons.append("matched open phrase")

    if future_deadline(deadlines):
        score += 25
        reasons.append("future deadline found")

    if money_values:
        score += 15
        reasons.append("money value found")

    if any(part in url.lower() for part in SOFT_NEGATIVE_URL_PARTS):
        score -= 15
        reasons.append("news / publication / search URL penalty")

    if any(phrase in combined for phrase in CLOSED_PHRASES):
        score -= 40
        reasons.append("closed phrase found")

    return score, "; ".join(reasons), category_matches


def short_summary(meta_description, text):
    if meta_description and len(meta_description) > 40:
        return meta_description[:700]

    sentences = re.split(r"(?<=[.!?])\s+", text)
    useful = [
        s for s in sentences
        if len(s) > 60
        and "cookie" not in s.lower()
        and "language" not in s.lower()
        and "skip to" not in s.lower()
    ]

    return clean(" ".join(useful[:3]))[:700]


def review_reason(score, reasons, deadlines, text):
    text_l = text.lower()

    if "closed phrase found" in reasons:
        return "closed phrase found"

    if score < 35:
        return "score too low"

    if not future_deadline(deadlines) and not any(p in text_l for p in OPEN_PHRASES):
        return "no future deadline or open phrase"

    if "grant signals" not in reasons:
        return "not enough grant signals"

    return "borderline / needs manual review"


def main():
    queue = list(START_URLS)
    visited = set()
    accepted = []
    review = []

    print("Starting lawful public grant monitor...")

    while queue and len(visited) < MAX_PAGES:
        url = queue.pop(0)

        if url in visited:
            continue

        visited.add(url)
        print(f"Checking: {url}")

        response, fetch_reason = fetch(url)

        if response is None:
            review.append({
                "checked_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "url": url,
                "title": "",
                "source_region": infer_source_region(url),
                "eligibility_region": "",
                "score": 0,
                "review_reason": fetch_reason,
                "reason_found": "",
                "snippet": "",
            })
            continue

        title, text, meta_description, soup = extract_page_content(response)

        if not text:
            review.append({
                "checked_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "url": response.url,
                "title": title,
                "source_region": infer_source_region(response.url),
                "eligibility_region": "",
                "score": 0,
                "review_reason": "no readable text",
                "reason_found": "",
                "snippet": "",
            })
            continue

        money_values = extract_money_values(text)
        deadlines, deadline_phrases = extract_deadlines(text)
        score, reason_found, categories = score_page(title, text, response.url, money_values, deadlines)
        eligibility_region = infer_eligibility_region(text, response.url)

        row = {
            "checked_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "title": title,
            "url": response.url,
            "source_region": infer_source_region(response.url),
            "eligibility_region": eligibility_region,
            "category": categories,
            "score": score,
            "possible_grant_values": ", ".join(money_values),
            "deadline_dates": ", ".join(deadlines),
            "deadline_phrases": " | ".join(deadline_phrases),
            "reason_found": reason_found,
            "snippet": short_summary(meta_description, text),
        }

        if score >= 55 and ("future deadline found" in reason_found or "matched open phrase" in reason_found):
            accepted.append(row)
        else:
            review_row = row.copy()
            review_row["review_reason"] = review_reason(score, reason_found, deadlines, text)
            review.append(review_row)

        for link in extract_links(response.url, soup):
            if link not in visited and link not in queue:
                queue.append(link)

    accepted.sort(key=lambda r: r["score"], reverse=True)
    review.sort(key=lambda r: r.get("score", 0), reverse=True)

    result_fields = [
        "checked_at", "title", "url", "source_region", "eligibility_region",
        "category", "score", "possible_grant_values", "deadline_dates",
        "deadline_phrases", "reason_found", "snippet"
    ]

    review_fields = result_fields + ["review_reason"]

    with open(RESULTS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=result_fields)
        writer.writeheader()
        writer.writerows(accepted)

    with open(REVIEW_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=review_fields)
        writer.writeheader()
        writer.writerows(review)

    print("")
    print("Finished.")
    print(f"Pages checked: {len(visited)}")
    print(f"Accepted grants: {len(accepted)}")
    print(f"Review pages: {len(review)}")
    print(f"Results saved to: {RESULTS_CSV}")
    print(f"Review saved to: {REVIEW_CSV}")


if __name__ == "__main__":
    main()