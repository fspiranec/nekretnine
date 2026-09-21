import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from app import create_app
from config import Config
from database import Database
from models import PriceHistory, Property
from scrapers.base import PropertyDTO
from scrapers.opereta import OperetaScraper
from services.sync import SyncService


class ApplicationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_sync_upserts_and_tracks_price(self) -> None:
        database = Database(f"sqlite:///{self.directory / 'test.db'}")
        database.create_all()
        original = PropertyDTO(
            portal="opereta", portal_id="123", url="https://example.test/123", title="Kuća",
            property_type="house", price=Decimal("100000"), living_area=Decimal("100"),
        )
        with database.session() as session:
            result = SyncService(session).sync([original])
            self.assertEqual(result.inserted, 1)
        changed = PropertyDTO(
            portal="opereta", portal_id="123", url="https://example.test/123", title="Kuća",
            property_type="house", price=Decimal("90000"), living_area=Decimal("100"),
        )
        with database.session() as session:
            result = SyncService(session).sync([changed])
            self.assertEqual(result.updated, 1)
            self.assertEqual(result.price_changes, 1)
            self.assertEqual(session.query(Property).count(), 1)
            self.assertEqual(session.query(PriceHistory).count(), 1)

    def test_sync_removes_records_without_any_property_facts(self) -> None:
        database = Database(f"sqlite:///{self.directory / 'invalid.db'}")
        database.create_all()
        invalid = PropertyDTO(
            portal="opereta", portal_id="property-management",
            url="https://www.opereta.hr/en/property-management",
            title="Property Management - Opereta Real Estate", property_type="house",
        )
        valid = PropertyDTO(
            portal="opereta", portal_id="house-1", url="https://example.test/house-1",
            title="Kuća", property_type="house", living_area=Decimal("120"),
        )
        with database.session() as session:
            result = SyncService(session).sync([invalid, valid])
            self.assertEqual(result.invalid_removed, 1)
            self.assertEqual(session.query(Property).count(), 1)

    def test_opereta_json_ld_parser(self) -> None:
        html = '''<html><head><script type="application/ld+json">{"@type":"Product","name":"Kuća uz more","sku":"OP-42","image":["/house.jpg"],"offers":{"price":"250000"},"address":{"addressLocality":"Zadar"},"geo":{"latitude":44.1,"longitude":15.2}}</script></head><body>Stambena površina: 120 m² Površina zemljišta: 400 m²</body></html>'''
        item = OperetaScraper.parse_detail(html, "https://www.opereta.hr/nekretnina/op-42")
        self.assertEqual(item.portal_id, "OP-42")
        self.assertEqual(item.price, Decimal("250000"))
        self.assertEqual(item.city, "Zadar")

    def test_opereta_inline_map_coordinates(self) -> None:
        html = '''<html><head><script type="application/ld+json">{"@type":"Product","name":"Kuća","sku":"OP-43"}</script></head><body><script>const map = {"lat": 45.815, "lng": 15.982};</script></body></html>'''
        item = OperetaScraper.parse_detail(html, "https://www.opereta.hr/nekretnina/op-43")

        self.assertEqual(item.latitude, 45.815)
        self.assertEqual(item.longitude, 15.982)

    def test_opereta_recognizes_current_croatian_property_urls(self) -> None:
        self.assertTrue(
            OperetaScraper._is_property_url(
                "https://www.opereta.hr/hr/nekretnine/kuca-s-pogledom"
            )
        )

    def test_opereta_rejects_property_management_page(self) -> None:
        url = "https://www.opereta.hr/en/property-management"
        html = "<html><body><h1>Property Management - Opereta Real Estate</h1></body></html>"

        self.assertFalse(OperetaScraper._is_property_url(url))
        self.assertFalse(OperetaScraper._looks_like_property_detail(html))

    def test_opereta_rejects_apartment_listing_for_house_sync(self) -> None:
        html = "<html><body><nav class='breadcrumb'>Properties / Apartments</nav></body></html>"

        self.assertFalse(OperetaScraper._looks_like_house(html, "Apartment in Zagreb"))

    def test_api_filters_local_database(self) -> None:
        app = create_app(Config(database_url=f"sqlite:///{self.directory / 'web.db'}"))
        database = app.extensions["state"].database
        with database.session() as session:
            SyncService(session).sync([PropertyDTO(
                portal="opereta", portal_id="1", url="https://example.test/1", title="Test",
                property_type="house", price=Decimal("100000"), county="Grad Zagreb",
            )])
        client = app.test_client()
        self.assertEqual(client.get("/").status_code, 200)
        payload = client.get("/api/properties?county=Grad+Zagreb&price_max=120000").get_json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(client.get("/api/properties?price_max=50000").get_json()["count"], 0)

    def test_module_exports_vercel_flask_application(self) -> None:
        from app import app

        self.assertEqual(app.name, "app")
        self.assertIn("state", app.extensions)


if __name__ == "__main__":
    unittest.main()
