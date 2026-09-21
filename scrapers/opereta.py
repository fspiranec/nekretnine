"""Opereta house listing adapter.

The parser prefers schema.org JSON-LD and has conservative HTML fallbacks so a
minor presentation redesign does not silently corrupt persisted values.
"""

from __future__ import annotations

import json
import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup, Tag

from scrapers.base import BaseScraper, PropertyDTO

LOGGER = logging.getLogger(__name__)


class OperetaScraper(BaseScraper):
    """Collect house listings from Opereta and emit normalized DTOs."""

    def __init__(self, listing_url: str, base_url: str, timeout: int = 20, max_pages: int = 30) -> None:
        self.listing_url = listing_url
        self.base_url = base_url
        self.timeout = timeout
        self.max_pages = max_pages
        self._sitemap_links: list[str] = []
        self.http = requests.Session()
        self.http.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (compatible; NekretnineHR/1.0; +local-property-index)",
                # Opereta redirects clients without a language preference to an
                # English URL that currently returns 404 for the Croatian slug.
                "Accept-Language": "hr-HR,hr;q=0.9,en;q=0.5",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        )

    def scrape(self) -> list[PropertyDTO]:
        links = self._collect_links()
        LOGGER.info("Found %d Opereta house links", len(links))
        properties: list[PropertyDTO] = []
        for index, link in enumerate(links, 1):
            try:
                response = self.http.get(link, timeout=self.timeout)
                response.raise_for_status()
                properties.append(self.parse_detail(response.text, response.url))
            except (requests.RequestException, ValueError) as exc:
                LOGGER.warning("Skipping Opereta listing %s (%d/%d): %s", link, index, len(links), exc)
        return properties

    def _collect_links(self) -> list[str]:
        links: set[str] = set()
        next_url: str | None = self._working_listing_url()
        if next_url == "sitemap://opereta":
            return list(self._sitemap_links)
        for _ in range(self.max_pages):
            if not next_url:
                break
            response = self.http.get(next_url, timeout=self.timeout)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            for anchor in soup.select("a[href]"):
                href = str(anchor.get("href", ""))
                absolute = urljoin(response.url, href).split("#")[0]
                if self._is_property_link(absolute, anchor):
                    links.add(absolute)
            next_anchor = soup.select_one("a[rel='next'], .next.page-numbers, .pagination-next a")
            candidate = urljoin(response.url, str(next_anchor.get("href"))) if next_anchor else None
            next_url = candidate if candidate and candidate != response.url else None
        if links:
            return sorted(links)
        sitemap_links = self._links_from_sitemaps()
        if sitemap_links:
            return sitemap_links
        raise requests.RequestException(
            f"Opereta stranica {next_url or self.listing_url} nije sadržavala poveznice na oglase."
        )

    def _working_listing_url(self) -> str:
        """Resolve a live listing page instead of depending on one fragile slug."""
        base = self.base_url.rstrip("/")
        candidates = list(
            dict.fromkeys(
                (
                    self.listing_url,
                    f"{base}/hr/nekretnine?vrsta=kuce",
                    f"{base}/hr/nekretnine",
                    f"{base}/nekretnine",
                    f"{base}/en/properties",
                    f"{base}/properties",
                )
            )
        )
        failures: list[str] = []
        for candidate in candidates:
            try:
                response = self.http.get(candidate, timeout=self.timeout)
                if response.ok and self._looks_like_listing_page(response.text):
                    LOGGER.info("Using Opereta listing page %s", response.url)
                    return response.url
                failures.append(f"{candidate} -> HTTP {response.status_code}")
            except requests.RequestException as exc:
                failures.append(f"{candidate} -> {exc}")

        sitemap_links = self._links_from_sitemaps()
        if sitemap_links:
            # Detail links from the sitemap can be consumed by _collect_links
            # through a synthetic in-memory page while preserving one code path.
            LOGGER.info("Opereta listing page unavailable; using %d sitemap links", len(sitemap_links))
            return self._cache_sitemap_page(sitemap_links)
        raise requests.RequestException(
            "Nije pronađena dostupna Opereta stranica oglasa. " + "; ".join(failures)
        )

    @staticmethod
    def _looks_like_listing_page(html: str) -> bool:
        lowered = html.lower()
        return len(html) > 500 and any(
            token in lowered for token in ("nekretnin", "property", "real-estate", "listing")
        )

    def _links_from_sitemaps(self) -> list[str]:
        """Use public sitemaps as a last-resort discovery mechanism."""
        sitemap_urls = [urljoin(self.base_url, "/sitemap.xml")]
        try:
            robots = self.http.get(urljoin(self.base_url, "/robots.txt"), timeout=self.timeout)
            if robots.ok:
                sitemap_urls.extend(
                    match.strip() for match in re.findall(r"(?im)^sitemap:\s*(\S+)", robots.text)
                )
        except requests.RequestException:
            pass

        property_links: set[str] = set()
        visited: set[str] = set()
        while sitemap_urls and len(visited) < 20:
            sitemap_url = sitemap_urls.pop(0)
            if sitemap_url in visited:
                continue
            visited.add(sitemap_url)
            try:
                response = self.http.get(sitemap_url, timeout=self.timeout)
                response.raise_for_status()
                root = ElementTree.fromstring(response.content)
            except (requests.RequestException, ElementTree.ParseError):
                continue
            locations = [node.text.strip() for node in root.iter() if node.tag.endswith("loc") and node.text]
            for location in locations:
                if location.lower().endswith(".xml"):
                    sitemap_urls.append(location)
                elif self._is_property_url(location):
                    property_links.add(location)
        return sorted(property_links)

    @staticmethod
    def _is_property_url(url: str) -> bool:
        lowered = url.lower()
        path_parts = [part for part in urlparse(lowered).path.split("/") if part]
        return len(path_parts) >= 2 and any(
            part in lowered
            for part in ("/nekretnina/", "/nekretnine/", "/property/", "/properties/")
        )

    def _cache_sitemap_page(self, links: list[str]) -> str:
        """Expose discovered links through a requests-compatible data URL is impossible.

        Store them for the collector and return a sentinel handled before HTTP.
        """
        self._sitemap_links = links
        return "sitemap://opereta"

    def _is_property_link(self, url: str, anchor: Tag) -> bool:
        if urlparse(url).netloc != urlparse(self.base_url).netloc:
            return False
        haystack = f"{url} {' '.join(anchor.get('class', []))}".lower()
        return any(token in haystack for token in ("nekretnina", "/nekretnine/", "property", "oglas")) and not any(
            token in haystack for token in ("page=", "/kategorija/", "vrsta=")
        )

    @classmethod
    def parse_detail(cls, html: str, url: str) -> PropertyDTO:
        """Parse one detail page; public to support fixture-based regression tests."""
        soup = BeautifulSoup(html, "html.parser")
        data = cls._json_ld(soup)
        text = soup.get_text(" ", strip=True)
        title = cls._first(data.get("name"), cls._meta(soup, "og:title"), cls._text(soup, "h1"))
        if not title:
            raise ValueError("Listing has no title")
        identifier = cls._first(
            data.get("sku"), data.get("productID"), cls._match(text, r"(?:šifra|id)(?:\s+oglasa)?\s*[:#]?\s*([A-Z0-9_-]+)")
        )
        if not identifier:
            identifier = url.rstrip("/").rsplit("/", 1)[-1]
        offers = data.get("offers", {}) if isinstance(data.get("offers"), dict) else {}
        address = data.get("address", {}) if isinstance(data.get("address"), dict) else {}
        location = " ".join(filter(None, [str(address.get("addressLocality", "")), cls._text(soup, ".location, .lokacija")]))
        images = data.get("image", [])
        if isinstance(images, str):
            images = [images]
        images = list(images) if isinstance(images, list) else []
        images.extend(str(img.get("src") or img.get("data-src")) for img in soup.select(".gallery img, .slider img") if img.get("src") or img.get("data-src"))
        latitude, longitude = cls._coordinates(data, soup)
        description = cls._first(data.get("description"), cls._meta(soup, "og:description"), cls._text(soup, ".description, .opis"))
        price = cls._number(cls._first(offers.get("price"), cls._meta(soup, "product:price:amount"), cls._match(text, r"(?:cijena)?\s*([\d.\s]+(?:,\d+)?)\s*€")))
        living = cls._number(cls._label_value(text, ("stambena površina", "površina kuće", "living area")))
        land = cls._number(cls._label_value(text, ("površina zemljišta", "okućnica", "land area")))
        county = cls._label_value(text, ("županija", "county"), numeric=False)
        municipality = cls._label_value(text, ("općina", "gradska četvrt", "municipality"), numeric=False)
        city = cls._first(address.get("addressLocality"), cls._label_value(text, ("grad", "mjesto"), numeric=False))
        return PropertyDTO(
            portal="opereta", portal_id=str(identifier), url=url, title=str(title), property_type="house",
            price=price, living_area=living, land_area=land, city=city, municipality=municipality,
            county=county, description=str(description) if description else None,
            images=list(dict.fromkeys(urljoin(url, image) for image in images if image and image != "None")),
            latitude=latitude, longitude=longitude,
        )

    @staticmethod
    def _json_ld(soup: BeautifulSoup) -> dict[str, Any]:
        for script in soup.select("script[type='application/ld+json']"):
            try:
                value = json.loads(script.string or "{}")
            except json.JSONDecodeError:
                continue
            nodes: Iterable[Any] = value if isinstance(value, list) else value.get("@graph", [value]) if isinstance(value, dict) else []
            for node in nodes:
                if isinstance(node, dict) and any(key in node for key in ("offers", "productID", "sku")):
                    return node
        return {}

    @staticmethod
    def _number(value: Any) -> Decimal | None:
        if value is None:
            return None
        cleaned = re.sub(r"[^\d,.-]", "", str(value)).replace(".", "").replace(",", ".")
        try:
            return Decimal(cleaned) if cleaned else None
        except InvalidOperation:
            return None

    @staticmethod
    def _label_value(text: str, labels: tuple[str, ...], numeric: bool = True) -> Any:
        label_pattern = "|".join(re.escape(label) for label in labels)
        value = OperetaScraper._match(text, rf"(?:{label_pattern})\s*:?\s*([^|•]+?)(?=\s+(?:[A-ZČĆŽŠĐ][\wčćžšđ ]+)\s*:|$)")
        if numeric and value:
            value = OperetaScraper._match(str(value), r"([\d.,]+)")
        return value.strip() if isinstance(value, str) else value

    @staticmethod
    def _coordinates(data: dict[str, Any], soup: BeautifulSoup) -> tuple[float | None, float | None]:
        geo = data.get("geo", {}) if isinstance(data.get("geo"), dict) else {}
        lat_element = soup.select_one("[data-lat], [data-latitude]")
        lng_element = soup.select_one("[data-lng], [data-lon], [data-longitude]")
        lat = geo.get("latitude") or lat_element
        lng = geo.get("longitude") or lng_element
        try:
            latitude = (
                lat.get("data-lat") or lat.get("data-latitude")
                if isinstance(lat, Tag)
                else lat
            )
            longitude = (
                lng.get("data-lng") or lng.get("data-lon") or lng.get("data-longitude")
                if isinstance(lng, Tag)
                else lng
            )
            return OperetaScraper._valid_coordinates(latitude, longitude)
        except (TypeError, ValueError):
            pass

        # Some detail pages keep map coordinates in an inline script or iframe
        # instead of schema.org markup. Support the common representations.
        html = str(soup)
        coordinate_patterns = (
            r'["\'](?:latitude|lat)["\']\s*[:=]\s*["\']?(-?\d{1,2}\.\d+)["\']?.{0,160}?["\'](?:longitude|lng|lon)["\']\s*[:=]\s*["\']?(-?\d{1,3}\.\d+)',
            r'(?:@|[?&](?:q|query)=)(-?\d{1,2}\.\d+)[,%2C\s]+(-?\d{1,3}\.\d+)',
        )
        for pattern in coordinate_patterns:
            match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
            if match:
                try:
                    return OperetaScraper._valid_coordinates(match.group(1), match.group(2))
                except ValueError:
                    continue
        return None, None

    @staticmethod
    def _valid_coordinates(latitude: Any, longitude: Any) -> tuple[float, float]:
        lat, lng = float(latitude), float(longitude)
        if not (42.0 <= lat <= 47.0 and 13.0 <= lng <= 20.0):
            raise ValueError("Coordinates are outside Croatia")
        return lat, lng

    @staticmethod
    def _match(text: str, pattern: str) -> str | None:
        result = re.search(pattern, text, re.IGNORECASE)
        return result.group(1).strip() if result else None

    @staticmethod
    def _meta(soup: BeautifulSoup, prop: str) -> str | None:
        element = soup.select_one(f"meta[property='{prop}'], meta[name='{prop}']")
        return str(element.get("content")) if element and element.get("content") else None

    @staticmethod
    def _text(soup: BeautifulSoup, selector: str) -> str | None:
        element = soup.select_one(selector)
        return element.get_text(" ", strip=True) if element else None

    @staticmethod
    def _first(*values: Any) -> Any:
        return next((value for value in values if value not in (None, "", [])), None)
