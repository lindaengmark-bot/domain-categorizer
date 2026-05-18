"""Domain categorization from crawl metadata.

The public entry point is :func:`classify_domain`. It accepts a domain or URL
plus a crawl export represented as rows of metadata from pages on that domain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import csv
import io
import json
import math
import re
from collections import defaultdict
from typing import Any, Iterable
from urllib.parse import urlparse


FIELD_ALIASES = {
    "url": ("url", "address", "page_url", "page", "link"),
    "title": ("title", "page_title", "seo_title", "meta_title"),
    "description": (
        "description",
        "meta_description",
        "meta desc",
        "summary",
        "snippet",
    ),
    "h1": ("h1", "h1_1", "heading", "main_heading"),
    "headings": ("headings", "h2", "h3", "all_headings"),
    "text": ("text", "body", "body_text", "content", "copy", "visible_text"),
    "status_code": ("status", "status_code", "http_status", "response_code"),
    "content_type": ("content_type", "mime_type", "type"),
}


DOMAIN_TYPE_RULES = {
    "E-commerce / marketplace": {
        "keywords": (
            "add to cart",
            "basket",
            "buy now",
            "cart",
            "checkout",
            "collection",
            "delivery",
            "discount",
            "free shipping",
            "marketplace",
            "order now",
            "payment",
            "product",
            "sale",
            "shop",
            "store",
            "wishlist",
        ),
        "url_tokens": ("cart", "checkout", "collections", "product", "products", "shop"),
    },
    "SaaS / software": {
        "keywords": (
            "api",
            "book a demo",
            "cloud platform",
            "dashboard",
            "developer",
            "enterprise",
            "feature",
            "free trial",
            "integration",
            "platform",
            "pricing",
            "request a demo",
            "saas",
            "software",
            "subscription",
            "workflow",
        ),
        "url_tokens": ("api", "developers", "features", "integrations", "pricing"),
    },
    "Media / publisher": {
        "keywords": (
            "article",
            "breaking news",
            "editor",
            "headline",
            "journalist",
            "latest news",
            "magazine",
            "newsletter",
            "opinion",
            "podcast",
            "press",
            "published",
            "reporter",
            "subscribe",
        ),
        "url_tokens": ("article", "news", "opinion", "press", "stories"),
    },
    "Blog / content site": {
        "keywords": (
            "blog",
            "category",
            "guide",
            "how to",
            "insights",
            "post",
            "read more",
            "resources",
            "tips",
            "tutorial",
        ),
        "url_tokens": ("blog", "guides", "insights", "resources", "tutorials"),
    },
    "Documentation / knowledge base": {
        "keywords": (
            "changelog",
            "docs",
            "documentation",
            "faq",
            "getting started",
            "help center",
            "knowledge base",
            "release notes",
            "setup",
            "troubleshooting",
        ),
        "url_tokens": ("docs", "documentation", "faq", "help", "kb", "support"),
    },
    "Community / forum": {
        "keywords": (
            "community",
            "discussion",
            "forum",
            "members",
            "moderator",
            "post a reply",
            "thread",
            "topic",
            "user profile",
        ),
        "url_tokens": ("community", "discuss", "forum", "members", "thread", "topics"),
    },
    "Local business / services": {
        "keywords": (
            "appointment",
            "book online",
            "call us",
            "contact us",
            "hours",
            "location",
            "near me",
            "opening hours",
            "our services",
            "quote",
            "service area",
            "services",
        ),
        "url_tokens": ("appointment", "contact", "locations", "services"),
    },
    "Portfolio / agency": {
        "keywords": (
            "agency",
            "brand",
            "case study",
            "creative",
            "design",
            "portfolio",
            "project",
            "studio",
            "work",
        ),
        "url_tokens": ("case-studies", "portfolio", "projects", "work"),
    },
    "Education / institution": {
        "keywords": (
            "admissions",
            "alumni",
            "campus",
            "course",
            "curriculum",
            "degree",
            "education",
            "faculty",
            "learn",
            "school",
            "student",
            "university",
        ),
        "url_tokens": ("admissions", "courses", "faculty", "learn", "students"),
    },
    "Government / public sector": {
        "keywords": (
            "council",
            "department",
            "foia",
            "government",
            "licence",
            "license",
            "mayor",
            "municipal",
            "public service",
            "regulation",
            "tax",
        ),
        "url_tokens": ("departments", "government", "permits", "services"),
    },
    "Nonprofit / charity": {
        "keywords": (
            "advocacy",
            "charity",
            "donate",
            "foundation",
            "fundraising",
            "impact",
            "mission",
            "nonprofit",
            "volunteer",
        ),
        "url_tokens": ("donate", "impact", "mission", "volunteer"),
    },
    "Finance / fintech": {
        "keywords": (
            "account",
            "bank",
            "card",
            "credit",
            "finance",
            "fintech",
            "insurance",
            "invest",
            "loan",
            "mortgage",
            "payment",
            "wealth",
        ),
        "url_tokens": ("banking", "finance", "insurance", "loans", "payments"),
    },
    "Healthcare / medical": {
        "keywords": (
            "clinic",
            "doctor",
            "health",
            "healthcare",
            "medical",
            "patient",
            "pharmacy",
            "provider",
            "telehealth",
            "treatment",
        ),
        "url_tokens": ("clinic", "doctors", "health", "patients", "treatments"),
    },
    "App portal / authentication": {
        "keywords": (
            "account login",
            "authentication",
            "forgot password",
            "log in",
            "login",
            "password",
            "sign in",
            "single sign-on",
            "sso",
            "two-factor",
        ),
        "url_tokens": ("account", "auth", "login", "signin", "sso"),
    },
}


PARKED_OR_ERROR_TERMS = (
    "access denied",
    "bad gateway",
    "coming soon",
    "domain for sale",
    "forbidden",
    "not found",
    "parked domain",
    "server error",
    "service unavailable",
    "this domain is for sale",
    "under construction",
)


@dataclass(frozen=True)
class CrawlPage:
    """Normalized metadata for one crawled page."""

    url: str = ""
    title: str = ""
    description: str = ""
    h1: str = ""
    headings: str = ""
    text: str = ""
    status_code: int | None = None
    content_type: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def searchable_text(self) -> str:
        parts = (self.title, self.description, self.h1, self.headings, self.text)
        return " ".join(part for part in parts if part).lower()


@dataclass(frozen=True)
class ClassificationResult:
    """The aggregate classification for a domain crawl."""

    domain: str
    category: str
    confidence: float
    page_count: int
    evidence: tuple[str, ...]
    category_scores: dict[str, float]
    page_signals: tuple[dict[str, Any], ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "category": self.category,
            "confidence": self.confidence,
            "page_count": self.page_count,
            "evidence": list(self.evidence),
            "category_scores": self.category_scores,
            "page_signals": list(self.page_signals),
        }


def parse_crawl_file(file_name: str, content: bytes | str) -> list[dict[str, Any]]:
    """Parse an uploaded CSV or JSON crawl export into row dictionaries."""

    text = content.decode("utf-8-sig") if isinstance(content, bytes) else content
    suffix = file_name.lower().rsplit(".", 1)[-1] if "." in file_name else ""

    if suffix == "json" or text.lstrip().startswith(("[", "{")):
        return _rows_from_json(json.loads(text))

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV uploads must include a header row.")
    return [dict(row) for row in reader]


def classify_domain(domain_or_url: str, crawl_rows: Iterable[dict[str, Any]]) -> ClassificationResult:
    """Categorize a domain using page-level crawl metadata."""

    pages = [page for page in (_normalize_page(row) for row in crawl_rows) if _is_indexable_page(page)]
    domain = _extract_domain(domain_or_url) or _domain_from_pages(pages) or "unknown domain"

    if not pages:
        return ClassificationResult(
            domain=domain,
            category="Unknown / insufficient crawl metadata",
            confidence=0.0,
            page_count=0,
            evidence=("Upload crawl metadata with URLs, titles, headings, and page text.",),
            category_scores={},
            page_signals=(),
        )

    score_by_category: dict[str, float] = defaultdict(float)
    evidence_by_category: dict[str, set[str]] = defaultdict(set)
    page_signals: list[dict[str, Any]] = []
    parked_score = 0.0

    for page in pages:
        text = page.searchable_text
        url_tokens = _url_tokens(page.url)
        page_matches: dict[str, list[str]] = {}

        parked_matches = _matched_terms(text, PARKED_OR_ERROR_TERMS)
        if parked_matches:
            parked_score += 3 + min(len(parked_matches), 4)

        for category, rule in DOMAIN_TYPE_RULES.items():
            keyword_matches = _matched_terms(text, rule["keywords"])
            url_matches = sorted(set(url_tokens).intersection(rule["url_tokens"]))
            if not keyword_matches and not url_matches:
                continue

            title_boost = sum(1 for term in keyword_matches if term in page.title.lower())
            h1_boost = sum(1 for term in keyword_matches if term in page.h1.lower())
            score = (len(keyword_matches) * 2.0) + len(url_matches) + title_boost + h1_boost

            score_by_category[category] += _page_weight(page) * score
            for match in keyword_matches[:5]:
                evidence_by_category[category].add(match)
            for match in url_matches[:3]:
                evidence_by_category[category].add(f"url:{match}")
            page_matches[category] = keyword_matches[:5] + [f"url:{item}" for item in url_matches[:3]]

        if page_matches or parked_matches:
            page_signals.append(
                {
                    "url": page.url,
                    "title": page.title,
                    "signals": page_matches,
                    "parked_or_error_signals": parked_matches,
                }
            )

    if parked_score >= max(score_by_category.values() or [0]) and parked_score >= 3:
        score_by_category["Parked / error page"] = parked_score
        evidence_by_category["Parked / error page"].update(_parked_evidence(pages))

    if not score_by_category:
        return ClassificationResult(
            domain=domain,
            category="Unknown / needs more metadata",
            confidence=0.15,
            page_count=len(pages),
            evidence=("No strong category signals were found in the uploaded crawl metadata.",),
            category_scores={},
            page_signals=tuple(page_signals),
        )

    ranked = sorted(score_by_category.items(), key=lambda item: item[1], reverse=True)
    category, top_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0
    confidence = _confidence(top_score, second_score, len(pages))
    normalized_scores = {
        name: round(score, 2)
        for name, score in ranked
        if score >= max(1.0, top_score * 0.2)
    }
    evidence = _format_evidence(category, evidence_by_category[category], pages)

    return ClassificationResult(
        domain=domain,
        category=category,
        confidence=confidence,
        page_count=len(pages),
        evidence=tuple(evidence),
        category_scores=normalized_scores,
        page_signals=tuple(page_signals[:50]),
    )


def normalize_rows(crawl_rows: Iterable[dict[str, Any]]) -> list[CrawlPage]:
    """Expose normalized pages for previews and tests."""

    return [_normalize_page(row) for row in crawl_rows]


def _rows_from_json(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [_ensure_dict(row) for row in payload]
    if isinstance(payload, dict):
        for key in ("pages", "urls", "results", "items", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [_ensure_dict(row) for row in value]
        return [_ensure_dict(payload)]
    raise ValueError("JSON uploads must be an object or list of objects.")


def _ensure_dict(row: Any) -> dict[str, Any]:
    if isinstance(row, dict):
        return row
    raise ValueError("Crawl rows must be objects with metadata fields.")


def _normalize_page(row: dict[str, Any]) -> CrawlPage:
    lower_key_map = {_normalize_key(key): key for key in row}

    def value_for(field: str) -> str:
        for alias in FIELD_ALIASES[field]:
            source_key = lower_key_map.get(_normalize_key(alias))
            if source_key is None:
                continue
            value = row.get(source_key)
            if value is None:
                return ""
            if isinstance(value, (list, tuple)):
                return " ".join(str(item) for item in value if item is not None)
            if isinstance(value, dict):
                return " ".join(str(item) for item in value.values() if item is not None)
            return str(value)
        return ""

    return CrawlPage(
        url=value_for("url").strip(),
        title=value_for("title").strip(),
        description=value_for("description").strip(),
        h1=value_for("h1").strip(),
        headings=value_for("headings").strip(),
        text=value_for("text").strip(),
        status_code=_parse_status_code(value_for("status_code")),
        content_type=value_for("content_type").strip().lower(),
        raw=row,
    )


def _normalize_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(key).lower()).strip("_")


def _parse_status_code(value: str) -> int | None:
    if not value:
        return None
    match = re.search(r"\d{3}", value)
    return int(match.group(0)) if match else None


def _is_indexable_page(page: CrawlPage) -> bool:
    if page.status_code and page.status_code >= 500:
        return True
    if page.status_code and page.status_code >= 400:
        return True
    if page.content_type and "html" not in page.content_type and "text" not in page.content_type:
        return False
    return bool(page.searchable_text or page.url)


def _extract_domain(domain_or_url: str) -> str:
    if not domain_or_url:
        return ""
    value = domain_or_url.strip()
    parsed = urlparse(value if "://" in value else f"https://{value}")
    host = parsed.netloc or parsed.path
    return host.lower().removeprefix("www.").split("/")[0]


def _domain_from_pages(pages: Iterable[CrawlPage]) -> str:
    for page in pages:
        if page.url:
            domain = _extract_domain(page.url)
            if domain:
                return domain
    return ""


def _url_tokens(url: str) -> set[str]:
    parsed = urlparse(url if "://" in url else f"https://example.com/{url.lstrip('/')}")
    path = f"{parsed.netloc} {parsed.path}"
    return {token for token in re.split(r"[^a-z0-9]+", path.lower()) if token}


def _matched_terms(text: str, terms: Iterable[str]) -> list[str]:
    matches = []
    for term in terms:
        pattern = r"\b" + re.escape(term.lower()).replace(r"\ ", r"\s+") + r"\b"
        if re.search(pattern, text):
            matches.append(term)
    return matches


def _page_weight(page: CrawlPage) -> float:
    url = page.url.lower()
    if url.endswith("/") or re.search(r"/(home|index)(\.[a-z]+)?$", url):
        return 1.4
    if any(segment in url for segment in ("/about", "/pricing", "/products", "/services")):
        return 1.2
    return 1.0


def _parked_evidence(pages: Iterable[CrawlPage]) -> list[str]:
    found: set[str] = set()
    for page in pages:
        found.update(_matched_terms(page.searchable_text, PARKED_OR_ERROR_TERMS))
    return sorted(found) or ["error-like crawl metadata"]


def _confidence(top_score: float, second_score: float, page_count: int) -> float:
    if top_score <= 0:
        return 0.0
    separation = (top_score - second_score) / top_score
    volume = min(1.0, math.log(page_count + 1, 8))
    raw = 0.35 + (0.45 * separation) + (0.25 * volume)
    return round(max(0.2, min(raw, 0.98)), 2)


def _format_evidence(category: str, evidence_terms: set[str], pages: list[CrawlPage]) -> list[str]:
    evidence = [f"Matched {category.lower()} signals: {', '.join(sorted(evidence_terms)[:8])}."]
    high_value_pages = [page.url for page in pages if page.url][:3]
    if high_value_pages:
        evidence.append(f"Signals were found across crawl pages such as {', '.join(high_value_pages)}.")
    return evidence
