#!/usr/bin/env python3
"""Classify domains from an uploaded Excel file.

The tool follows the workflow requested by the user:
- Reads sheet `citation`
- Extracts values from `parent domain`
- Removes empty values and deduplicates normalized domains
- Classifies each unique domain into a primary website category
- Produces a table and summary
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

import pandas as pd

try:
    import requests
    from bs4 import BeautifulSoup
except Exception:  # optional runtime dependency for inspection only
    requests = None
    BeautifulSoup = None


PREDEFINED_CATEGORIES = [
    "Retailer",
    "Distributor",
    "Brand",
    "Forum",
    "Marketplace",
    "Comparison Site",
    "Publisher",
    "Organization",
    "Platform",
]

SEPARATE_SERVICE_SUBDOMAINS = {
    "forum",
    "community",
    "support",
    "help",
    "docs",
    "developers",
    "app",
    "portal",
}

SECOND_LEVEL_SUFFIXES = {"co", "com", "org", "net", "gov", "ac", "edu"}


CATEGORY_PATTERNS: Dict[str, List[str]] = {
    "Forum": ["forum", "community", "thread", "discussion", "q&a", "questions"],
    "Marketplace": ["marketplace", "multi-vendor", "sellers", "listings", "buy and sell"],
    "Comparison Site": ["compare", "comparison", "vs", "best price", "price comparison"],
    "Retailer": ["shop", "store", "cart", "checkout", "buy now", "e-commerce"],
    "Distributor": ["wholesale", "distributor", "reseller", "b2b", "trade account"],
    "Publisher": ["news", "blog", "editorial", "magazine", "review", "article"],
    "Organization": ["ngo", "association", "foundation", "university", "ministry", "government", "non-profit"],
    "Platform": ["platform", "saas", "dashboard", "workspace", "tool", "service"],
    "Brand": ["official site", "our products", "about us", "company", "manufacturer"],
}


@dataclass
class Classification:
    domain: str
    category: str
    suggested_subcategory: str
    confidence: str
    reasoning: str


def clean_domain(raw: str) -> Optional[str]:
    if not isinstance(raw, str):
        return None
    value = raw.strip().lower()
    if not value:
        return None

    if not re.match(r"^[a-z]+://", value):
        value = f"http://{value}"

    parsed = urlparse(value)
    host = parsed.netloc.split("@")[(-1)].split(":")[0].strip(".")
    if not host:
        return None

    if host.startswith("www."):
        host = host[4:]

    if not re.search(r"[a-z0-9-]\.[a-z]", host):
        return None

    labels = host.split(".")
    if len(labels) <= 2:
        return host

    if labels[0] in SEPARATE_SERVICE_SUBDOMAINS:
        return host

    # best-effort eTLD+1 without external dependencies
    if len(labels) >= 3 and labels[-2] in SECOND_LEVEL_SUFFIXES:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def inspect_domain(domain: str, timeout: int = 5) -> str:
    if requests is None:
        return ""

    for scheme in ("https", "http"):
        url = f"{scheme}://{domain}"
        try:
            response = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
            if response.status_code >= 400:
                continue
            text = response.text[:200_000]
            if BeautifulSoup is None:
                return text.lower()
            soup = BeautifulSoup(text, "html.parser")
            title = (soup.title.text if soup.title else "").strip()
            description = ""
            tag = soup.find("meta", attrs={"name": re.compile(r"description", re.I)})
            if tag and tag.get("content"):
                description = tag["content"]
            body_text = " ".join([title, description])
            if not body_text.strip():
                body_text = soup.get_text(" ", strip=True)[:5_000]
            return body_text.lower()
        except Exception:
            continue
    return ""


def match_category(domain: str, text: str) -> Tuple[str, str, str, float]:
    corpus = f"{domain} {text}".lower()
    scores: Dict[str, int] = {}

    for category, patterns in CATEGORY_PATTERNS.items():
        score = 0
        for token in patterns:
            if token in corpus:
                score += 2 if token in domain else 1
        if score:
            scores[category] = score

    if not scores:
        if any(token in domain for token in ["edu", ".gov", "foundation", "org"]):
            return "Organization", "Educational/Governmental", "Medium", 0.45
        return "Software Vendor", "New category", "Low", 0.2

    category = max(scores, key=scores.get)
    best = scores[category]

    if category == "Publisher" and "review" in corpus:
        subcat = "Review Publisher"
    elif category == "Organization":
        subcat = "Association/Institution"
    elif category == "Platform":
        subcat = "SaaS Platform"
    elif category == "Retailer":
        subcat = "Direct-to-Consumer"
    elif category == "Marketplace":
        subcat = "Multi-seller Marketplace"
    else:
        subcat = "-"

    if best >= 4:
        confidence = "High"
        score = 0.9
    elif best >= 2:
        confidence = "Medium"
        score = 0.65
    else:
        confidence = "Low"
        score = 0.4

    return category, subcat, confidence, score


def classify_domain(domain: str, inspect_if_uncertain: bool = True) -> Classification:
    text = ""
    category, subcat, confidence, numeric = match_category(domain, text)

    if inspect_if_uncertain and confidence != "High":
        inspected = inspect_domain(domain)
        if inspected:
            c2, s2, conf2, n2 = match_category(domain, inspected)
            if n2 > numeric:
                category, subcat, confidence = c2, s2, conf2
                text = inspected

    reason = (
        f"Primary signals in domain/content match '{category}'."
        if category in PREDEFINED_CATEGORIES
        else "No predefined category fit clearly; suggested a new category."
    )
    if confidence != "High":
        reason += " Some ambiguity remains."

    return Classification(
        domain=domain,
        category=category,
        suggested_subcategory=subcat,
        confidence=confidence,
        reasoning=reason,
    )


def extract_unique_domains(input_file: str) -> List[str]:
    df = pd.read_excel(input_file, sheet_name="citation")

    columns_normalized = {str(c).strip().lower(): c for c in df.columns}
    if "parent domain" not in columns_normalized:
        raise ValueError("Column 'parent domain' not found in sheet 'citation'.")

    col = columns_normalized["parent domain"]
    domains = [clean_domain(v) for v in df[col].tolist()]
    unique = sorted({d for d in domains if d})
    return unique


def classify_file(input_file: str, output_file: Optional[str], inspect_if_uncertain: bool) -> pd.DataFrame:
    domains = extract_unique_domains(input_file)
    rows = [classify_domain(d, inspect_if_uncertain=inspect_if_uncertain) for d in domains]

    out_df = pd.DataFrame(
        [
            {
                "Parent Domain": r.domain,
                "Category": r.category,
                "Suggested Subcategory": r.suggested_subcategory,
                "Confidence": r.confidence,
                "Reasoning": r.reasoning,
            }
            for r in rows
        ]
    )

    if output_file:
        out_df.to_csv(output_file, index=False)
    return out_df


def print_summary(df: pd.DataFrame) -> None:
    print("\nCategory distribution")
    print(df["Category"].value_counts().to_string())

    new_categories = [c for c in df["Category"].unique() if c not in PREDEFINED_CATEGORIES]
    print("\nNewly suggested categories")
    if new_categories:
        for c in new_categories:
            print(f"- {c}")
    else:
        print("- None")

    low_conf = df[df["Confidence"] == "Low"]["Parent Domain"].tolist()
    print("\nLow-confidence domains")
    if low_conf:
        for d in low_conf:
            print(f"- {d}")
    else:
        print("- None")


def main() -> None:
    parser = argparse.ArgumentParser(description="Classify parent domains from sheet 'citation'.")
    parser.add_argument("input_file", help="Path to input Excel file")
    parser.add_argument("--output", default="classification_results.csv", help="Output CSV path")
    parser.add_argument(
        "--no-inspect",
        action="store_true",
        help="Disable website inspection for uncertain cases",
    )
    args = parser.parse_args()

    df = classify_file(args.input_file, args.output, inspect_if_uncertain=not args.no_inspect)

    print(df.to_markdown(index=False))
    print_summary(df)
    print(f"\nSaved results to: {args.output}")


if __name__ == "__main__":
    main()
