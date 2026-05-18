import unittest

from domain_classifier import classify_domain, normalize_rows, parse_crawl_file


class DomainClassifierTest(unittest.TestCase):
    def test_classifies_ecommerce_from_crawl_metadata(self):
        result = classify_domain(
            "shop.example",
            [
                {
                    "url": "https://shop.example/",
                    "title": "Example Store",
                    "meta_description": "Buy products online with free shipping.",
                    "h1": "Shop our latest collection",
                    "text": "Add to cart, checkout, delivery, sale, wishlist.",
                    "status_code": "200",
                    "content_type": "text/html",
                },
                {
                    "url": "https://shop.example/products/widget",
                    "title": "Widget product page",
                    "text": "Product reviews and add to cart button.",
                    "status_code": "200",
                },
            ],
        )

        self.assertEqual(result.category, "E-commerce / marketplace")
        self.assertGreaterEqual(result.confidence, 0.7)
        self.assertIn("E-commerce / marketplace", result.category_scores)

    def test_classifies_saas_from_csv_upload(self):
        csv_content = """address,page_title,meta_description,h1,body_text,http_status
https://example.app/pricing,Pricing | Example Platform,Start a free trial,Plans for every team,"API integrations, dashboard, workflow software, book a demo",200
https://example.app/integrations,Integrations,Connect your stack,Integrations,"Enterprise platform for developers",200
"""

        rows = parse_crawl_file("crawl.csv", csv_content)
        result = classify_domain("", rows)

        self.assertEqual(result.domain, "example.app")
        self.assertEqual(result.category, "SaaS / software")

    def test_parses_json_wrapped_pages(self):
        rows = parse_crawl_file(
            "crawl.json",
            b'{"pages":[{"url":"https://docs.example/help","title":"Help Center","text":"Documentation, FAQ, troubleshooting and getting started"}]}',
        )

        result = classify_domain("docs.example", rows)

        self.assertEqual(len(rows), 1)
        self.assertEqual(result.category, "Documentation / knowledge base")

    def test_normalizes_common_field_aliases(self):
        pages = normalize_rows(
            [
                {
                    "Address": "https://example.org/about",
                    "Page Title": "About our charity",
                    "Response Code": "HTTP 200",
                    "Meta Desc": "Donate and volunteer for our mission.",
                }
            ]
        )

        self.assertEqual(pages[0].url, "https://example.org/about")
        self.assertEqual(pages[0].status_code, 200)
        self.assertIn("Donate", pages[0].description)

    def test_returns_unknown_for_empty_metadata(self):
        result = classify_domain("example.com", [])

        self.assertEqual(result.category, "Unknown / insufficient crawl metadata")
        self.assertEqual(result.confidence, 0.0)


if __name__ == "__main__":
    unittest.main()
