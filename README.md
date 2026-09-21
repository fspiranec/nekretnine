# Nekretnine.hr

Lokalna, responzivna tražilica hrvatskih nekretnina. Prva integracija prikuplja sve vrste oglasa s Operete, normalizira ih u zajednički DTO te ih sprema u SQLite. Pretraživanje i filtriranje nakon sinkronizacije ne šalju zahtjeve portalima.

## Zahtjevi

- Python 3.11 ili noviji
- Internet veza za ručno osvježavanje Operete i prikaz OpenStreetMap podloge
- Windows, macOS ili Linux; Docker i Node.js nisu potrebni

## Lokalna instalacija i pokretanje

Najprije u terminalu otvorite mapu projekta. Na Windowsu to, primjerice, izgleda ovako:

```powershell
cd C:\Users\VASE_IME\Downloads\nekretnine
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Ako PowerShell blokira aktivaciju, jednom u tom prozoru pokrenite
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, a zatim ponovno
`.venv\Scripts\Activate.ps1`. U klasičnom Command Promptu koristite
`.venv\Scripts\activate.bat` umjesto PowerShell naredbe.

Na macOS-u ili Linuxu:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Kada terminal ispiše `Running on http://127.0.0.1:5000`, ostavite ga otvorenim i u
pregledniku otvorite <http://127.0.0.1:5000>. Za zaustavljanje aplikacije pritisnite
`Ctrl+C`. Baza se automatski stvara u `data/nekretnine.db`. Klik **Osvježi Operetu**
pokreće sinkronizaciju u pozadini; status je prikazan u zaglavlju. Postavke se mogu
promijeniti varijablama `DATABASE_URL`, `SECRET_KEY`, `OPERETA_BASE_URL`,
`OPERETA_LISTINGS_URL`, `SCRAPER_TIMEOUT` i `SCRAPER_MAX_PAGES`. Stari naziv
`OPERETA_HOUSES_URL` i dalje se prihvaća radi kompatibilnosti.

Zadani Opereta URL koristi rutu `https://www.opereta.hr/nekretnine`. Scraper šalje hrvatsku jezičnu
postavku, automatski pokušava alternativne aktualne rute i, ako se navigacija portala
promijeni, pokušava pronaći oglase kroz javni sitemap. Varijablu
`OPERETA_LISTINGS_URL` postavite samo ako želite ručno zadati drugu početnu stranicu.
Scraper dodatno provjerava da je pronađena stranica stvarni oglas i odbacuje uslužne
stranice poput `property-management`. Prolazi kroz kategorije i paginaciju te sprema
stanove, kuće, zemljišta, poslovne prostore, nekretnine za odmor i ostale oglase.

Pri sljedećem osvježavanju servis automatski uklanja stare retke koji nemaju ni cijenu,
ni stambenu površinu, ni površinu zemljišta, pa ranije spremljena stranica
`property-management` više neće ostati među rezultatima. Ako ipak želite potpuno čistu
bazu, zaustavite aplikaciju, izbrišite `data/nekretnine.db`, ponovno pokrenite
`python app.py` i kliknite **Osvježi Operetu**.

## Vercel

`app.py` izvozi modulsku Flask instancu `app`, koju Vercel automatski pronalazi.
Nije potreban Build Command; Framework Preset može ostati **Other**, a Root Directory
mora biti korijen ovog repozitorija. `vercel.json` povećava dopušteno trajanje Python
funkcije kako bi ručno osvježavanje imalo više vremena.

Vercelov filesystem nije trajna baza podataka. Aplikacija zato na Vercelu koristi
zapisivi `/tmp/nekretnine.db`, ali njegov sadržaj može nestati između serverless
invokacija ili deploymenta. Vercel deployment je prikladan za demonstraciju sučelja,
ne za trajno Opereta spremište. Za stvarnu trajnu SQLite bazu pokrenite aplikaciju
lokalno ili na klasičnom Python hostingu s trajnim diskom. Vanjski trajni SQL servis
za Vercel zahtijevao bi zasebnu produkcijsku konfiguraciju i nije dio ove SQLite faze.

> Portal može promijeniti URL ili HTML. URL je zato konfigurabilan, parser preferira stabilnije schema.org JSON-LD podatke, a pojedinačni neispravan oglas ne prekida cijelo osvježavanje. Prije produkcijske uporabe provjerite uvjete korištenja i robots.txt izvornog portala.

## Funkcionalnosti

- lokalni rasponi cijene, stambene i zemljišne površine
- višestruki odabir županija i općina/gradova
- Leaflet/OpenStreetMap karta, lokalni GeoJSON sloj i označavanje oglasa
- crtanje poligona te filtriranje markera i kartica unutar nacrtanog područja
- gumb **Prikaži oglase** na karti vodi do kartica rezultata; marker i svaka kartica vode na izvorni oglas
- oglasi bez koordinata ostaju dostupni ispod karte uz jasno upozorenje da njihov položaj nije moguće potvrditi poligonom
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
