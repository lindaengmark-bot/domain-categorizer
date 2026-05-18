# Domain Categorizer

A Streamlit app that categorizes a domain type from uploaded crawl metadata.

Instead of relying on a bare domain name, the app reads page-level crawl exports
and uses metadata such as URLs, titles, descriptions, headings, body text, status
codes, and content types to infer the domain category.

## Supported categories

- E-commerce / marketplace
- SaaS / software
- Media / publisher
- Blog / content site
- Documentation / knowledge base
- Community / forum
- Local business / services
- Portfolio / agency
- Education / institution
- Government / public sector
- Nonprofit / charity
- Finance / fintech
- Healthcare / medical
- App portal / authentication
- Parked / error page
- Unknown / insufficient crawl metadata

## Upload format

Upload either CSV or JSON with one crawled page per row/object.

Recommended fields:

```text
url, title, meta_description, h1, headings, text, status_code, content_type
```

Common aliases are supported, including `address`, `page_url`, `page_title`,
`seo_title`, `description`, `body_text`, `content`, `http_status`, and
`response_code`.

### CSV example

```csv
url,title,meta_description,h1,text,status_code
https://example.com,Example Shop,Buy products online,Online store,"Free shipping, cart, checkout",200
https://example.com/products/widget,Widget,Product page,Widget,"Add to cart and customer reviews",200
```

### JSON example

```json
{
  "pages": [
    {
      "url": "https://example.com/pricing",
      "title": "Pricing | Example Platform",
      "meta_description": "Start a free trial of our workflow software.",
      "h1": "Pricing for every team",
      "text": "API integrations, dashboard, enterprise plans, book a demo.",
      "status_code": 200
    }
  ]
}
```

## Run locally

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Test

```bash
python3 -m unittest discover
```
