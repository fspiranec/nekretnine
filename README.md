# Nekretnine.hr

Lokalna, responzivna tražilica hrvatskih nekretnina. Prva integracija prikuplja kuće s Operete, normalizira podatke u zajednički DTO te ih sprema u SQLite. Pretraživanje i filtriranje nakon sinkronizacije ne šalju zahtjeve portalima.

## Zahtjevi

- Python 3.11 ili noviji
- Internet veza za ručno osvježavanje Operete i prikaz OpenStreetMap podloge
- Windows, macOS ili Linux; Docker i Node.js nisu potrebni

## Instalacija i pokretanje

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# Windows cmd.exe:   .venv\Scripts\activate.bat
# macOS/Linux:       source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Otvorite <http://127.0.0.1:5000>. Baza se automatski stvara u `data/nekretnine.db`. Klik **Osvježi Operetu** pokreće sinkronizaciju u pozadini; status je prikazan u zaglavlju. Postavke se mogu promijeniti varijablama `DATABASE_URL`, `SECRET_KEY`, `OPERETA_BASE_URL`, `OPERETA_HOUSES_URL`, `SCRAPER_TIMEOUT` i `SCRAPER_MAX_PAGES`.

> Portal može promijeniti URL ili HTML. URL je zato konfigurabilan, parser preferira stabilnije schema.org JSON-LD podatke, a pojedinačni neispravan oglas ne prekida cijelo osvježavanje. Prije produkcijske uporabe provjerite uvjete korištenja i robots.txt izvornog portala.

## Funkcionalnosti

- lokalni rasponi cijene, stambene i zemljišne površine
- višestruki odabir županija i općina/gradova
- Leaflet/OpenStreetMap karta, lokalni GeoJSON sloj i označavanje oglasa
- crtanje poligona te filtriranje markera i kartica unutar nacrtanog područja
- idempotentni upsert po `(portal, portal_id)` i odvojena povijest promjena cijene
- asinkrono ručno osvježavanje Operete

## Struktura

```text
app.py                      Flask factory, HTTP rute i pozadinsko osvježavanje
config.py                   konfiguracija iz okoline
database.py                 engine i transakcijski session lifecycle
models.py                   SQLAlchemy Property i PriceHistory modeli
scrapers/base.py            zajednički PropertyDTO i ugovor adaptera
scrapers/opereta.py         Opereta HTTP adapter i parser
services/sync.py            portal-neovisan upsert i praćenje cijene
services/filters.py         lokalni SQLite upiti i API serijalizacija
templates/index.html        responzivno Bootstrap sučelje
static/css, static/js       stilovi, Leaflet prikaz i klijentski filtri
static/data                 lokalni GeoJSON administrativnih područja
data/nekretnine.db          lokalna baza (nastaje pri prvom pokretanju)
```

## Testiranje

```bash
python -m unittest discover -s tests
```

Testovi ne pristupaju mreži i koriste privremene SQLite baze.

## Dodavanje novog portala

Napravite novu datoteku, primjerice `scrapers/njuskalo.py`, implementirajte `BaseScraper.scrape()` i vratite `list[PropertyDTO]`. Adapter jedini poznaje HTML i semantiku portala. Modeli i `SyncService` ne ovise o portalu, pa ih nije potrebno mijenjati; nova HTTP ruta ili scheduler samo instancira adapter i predaje ga postojećem servisu.

## Plan razvoja (faza 2 — nije implementirano)

- adapteri Njuškalo, Eurovilla, REMAX, Dogma i Index Oglasi
- automatizirani raspored sinkronizacije i izvještaji o greškama parsera
- geokodiranje oglasa kojima portal ne pruža koordinate
- potpune službene geometrije svih općina te administracijsko sučelje
- arhiviranje uklonjenih oglasa, analitika cijena i spremljene pretrage
