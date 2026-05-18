"""Streamlit interface for the crawl-backed domain categorizer."""

from __future__ import annotations

import json

import streamlit as st

from domain_classifier import classify_domain, normalize_rows, parse_crawl_file


st.set_page_config(page_title="Domain Categorizer", page_icon="🧭", layout="wide")


def main() -> None:
    st.title("Domain Categorizer")
    st.caption(
        "Upload crawl metadata so the app can classify the kind of domain from "
        "page titles, headings, descriptions, URL paths, and body text."
    )

    with st.sidebar:
        st.header("Expected upload")
        st.write("CSV or JSON crawl export with one row/object per crawled page.")
        st.write("Useful fields include:")
        st.code(
            "url, title, meta_description, h1, headings, text, status_code, content_type",
            language="text",
        )
        st.write(
            "The classifier also understands common aliases such as "
            "`address`, `page_title`, `body_text`, and `http_status`."
        )

    domain = st.text_input(
        "Domain or URL",
        placeholder="example.com",
        help="Used for the result label. If empty, the app will infer it from the crawl URLs.",
    )
    uploaded_file = st.file_uploader(
        "Upload crawl metadata",
        type=("csv", "json"),
        help="Upload a CSV or JSON export from your crawler.",
    )

    if not uploaded_file:
        _render_empty_state()
        return

    try:
        rows = parse_crawl_file(uploaded_file.name, uploaded_file.getvalue())
    except Exception as exc:  # pragma: no cover - Streamlit-facing error handling
        st.error(f"Could not read the crawl upload: {exc}")
        return

    if not rows:
        st.warning("The uploaded crawl did not contain any rows.")
        return

    normalized_pages = normalize_rows(rows)
    result = classify_domain(domain, rows)

    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Category", result.category)
    col_b.metric("Confidence", f"{result.confidence:.0%}")
    col_c.metric("Pages analyzed", result.page_count)

    st.subheader("Why this category?")
    for item in result.evidence:
        st.write(f"- {item}")

    score_col, signal_col = st.columns([1, 2])
    with score_col:
        st.subheader("Top category scores")
        if result.category_scores:
            st.dataframe(
                [{"category": name, "score": score} for name, score in result.category_scores.items()],
                hide_index=True,
                use_container_width=True,
            )
        else:
            st.info("No strong category scores were produced.")

    with signal_col:
        st.subheader("Page-level signals")
        if result.page_signals:
            st.dataframe(result.page_signals, hide_index=True, use_container_width=True)
        else:
            st.info("No page-level signals were found in the uploaded metadata.")

    with st.expander("Preview normalized crawl metadata"):
        st.dataframe(
            [
                {
                    "url": page.url,
                    "title": page.title,
                    "description": page.description,
                    "h1": page.h1,
                    "status_code": page.status_code,
                    "content_type": page.content_type,
                }
                for page in normalized_pages[:100]
            ],
            hide_index=True,
            use_container_width=True,
        )

    st.download_button(
        "Download classification JSON",
        data=json.dumps(result.as_dict(), indent=2),
        file_name="domain_classification.json",
        mime="application/json",
    )


def _render_empty_state() -> None:
    st.info("Upload crawl metadata to categorize a domain.")
    with st.expander("Example CSV"):
        st.code(
            """url,title,meta_description,h1,text,status_code
https://example.com,Example Shop,Buy products online,Online store,"Free shipping, cart, checkout",200
https://example.com/products/widget,Widget,Product page,Widget,"Add to cart and customer reviews",200
""",
            language="csv",
        )
    with st.expander("Example JSON"):
        st.code(
            json.dumps(
                {
                    "pages": [
                        {
                            "url": "https://example.com/pricing",
                            "title": "Pricing | Example Platform",
                            "meta_description": "Start a free trial of our workflow software.",
                            "h1": "Pricing for every team",
                            "text": "API integrations, dashboard, enterprise plans, book a demo.",
                            "status_code": 200,
                        }
                    ]
                },
                indent=2,
            ),
            language="json",
        )


if __name__ == "__main__":
    main()
