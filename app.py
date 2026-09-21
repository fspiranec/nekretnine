"""Nekretnine.hr Flask application entry point."""

from __future__ import annotations

import logging
from threading import Lock, Thread

from flask import Flask, jsonify, render_template, request
from sqlalchemy import distinct, select

from config import Config
from database import Database
from models import Property
from scrapers.opereta import OperetaScraper
from services.filters import PropertyFilters, filtered_properties, serialize_property
from services.sync import SyncService


class ApplicationState:
    """Keep mutable process state scoped to one Flask application."""

    def __init__(self, database: Database, config: Config) -> None:
        self.database = database
        self.config = config
        self.sync_lock = Lock()
        self.sync_status: dict[str, object] = {"running": False, "message": "Spremno"}

    def refresh_opereta(self) -> None:
        if not self.sync_lock.acquire(blocking=False):
            return
        self.sync_status = {"running": True, "message": "Opereta sinkronizacija je u tijeku…"}
        try:
            scraper = OperetaScraper(
                self.config.opereta_houses_url, self.config.opereta_base_url,
                self.config.request_timeout, self.config.scraper_max_pages,
            )
            with self.database.session() as session:
                result = SyncService(session).run(scraper)
            self.sync_status = {
                "running": False,
                "message": f"Gotovo: {result.inserted} novih, {result.updated} osvježenih, {result.price_changes} promjena cijene.",
            }
        except Exception as exc:  # Background boundary: retain useful status and log the traceback.
            logging.exception("Opereta refresh failed")
            self.sync_status = {"running": False, "message": f"Sinkronizacija nije uspjela: {exc}"}
        finally:
            self.sync_lock.release()


def create_app(config: Config | None = None) -> Flask:
    settings = config or Config()
    app = Flask(__name__)
    app.config.update(SECRET_KEY=settings.secret_key, JSON_AS_ASCII=False)
    state = ApplicationState(Database(settings.database_url), settings)
    state.database.create_all()
    app.extensions["state"] = state

    @app.get("/")
    def index() -> str:
        with state.database.session() as session:
            counties = list(session.scalars(select(distinct(Property.county)).where(Property.county.is_not(None)).order_by(Property.county)))
            municipalities = list(session.scalars(select(distinct(Property.municipality)).where(Property.municipality.is_not(None)).order_by(Property.municipality)))
        return render_template("index.html", counties=counties, municipalities=municipalities)

    @app.get("/api/properties")
    def properties_api():
        filters = PropertyFilters.from_query(request.args, request.args.getlist)
        with state.database.session() as session:
            items = [serialize_property(item) for item in filtered_properties(session, filters)]
        return jsonify({"properties": items, "count": len(items)})

    @app.post("/api/refresh/opereta")
    def refresh_opereta():
        if state.sync_status.get("running"):
            return jsonify(state.sync_status), 409
        Thread(target=state.refresh_opereta, name="opereta-sync", daemon=True).start()
        return jsonify({"running": True, "message": "Sinkronizacija je pokrenuta."}), 202

    @app.get("/api/refresh/status")
    def refresh_status():
        return jsonify(state.sync_status)

    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    create_app().run(host="127.0.0.1", port=5000, debug=False)
