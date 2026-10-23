"""Actualizador de Linea de valor NFL (se ejecuta en GitHub Actions).
Descarga datos publicos y crea datos/paquete.json y datos/estado.json,
que la app carga sola al abrirse."""
import csv, io, json, os, re, sys, urllib.request
from datetime import datetime, timezone

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
now = datetime.now(timezone.utc)
season = now.year if now.month >= 3 else now.year - 1
estado = {}

def bajar(url, nombre, timeout=90):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            txt = r.read().decode("utf-8", "replace")
        print(f"OK   {nombre}")
        estado[nombre] = "ok"
        return txt
    except Exception as e:
        print(f"FALLO {nombre}: {e}")
        estado[nombre] = f"fallo: {e}"
        return None

# Estadios: codigo, lat, lon, techo, texto a buscar en el nombre (sedes internacionales)
EST = [("ARI",33.5276,-112.2626,"retractil",""),("ATL",33.7554,-84.4008,"retractil",""),("BAL",39.2780,-76.6227,"abierto",""),("BUF",42.7738,-78.7870,"abierto",""),
("CAR",35.2258,-80.8528,"abierto",""),("CHI",41.8623,-87.6167,"abierto",""),("CIN",39.0955,-84.5161,"abierto",""),("CLE",41.5061,-81.6995,"abierto",""),
("DAL",32.7473,-97.0945,"retractil",""),("DEN",39.7439,-105.0201,"abierto",""),("DET",42.3400,-83.0456,"cubierto",""),("GB",44.5013,-88.0622,"abierto",""),
("HOU",29.6847,-95.4107,"retractil",""),("IND",39.7601,-86.1639,"retractil",""),("JAX",30.3239,-81.6373,"abierto",""),("KC",39.0489,-94.4839,"abierto",""),
("LV",36.0909,-115.1833,"cubierto",""),("LAC",33.9535,-118.3392,"cubierto",""),("LAR",33.9535,-118.3392,"cubierto",""),("MIA",25.9580,-80.2389,"abierto",""),
("MIN",44.9737,-93.2575,"cubierto",""),("NE",42.0909,-71.2643,"abierto",""),("NO",29.9511,-90.0812,"cubierto",""),("NYG",40.8135,-74.0745,"abierto",""),
("NYJ",40.8135,-74.0745,"abierto",""),("PHI",39.9008,-75.1675,"abierto",""),("PIT",40.4468,-80.0158,"abierto",""),("SF",37.4030,-121.9700,"abierto",""),
("SEA",47.5952,-122.3316,"abierto",""),("TB",27.9759,-82.5033,"abierto",""),("TEN",36.1665,-86.7713,"abierto",""),("WAS",38.9077,-76.8645,"abierto",""),
("LONDRES1",51.5560,-0.2796,"abierto","wembley"),("LONDRES2",51.6043,-0.0664,"abierto","tottenham"),("MUNICH",48.2188,11.6247,"abierto","allianz"),
("BERLIN",52.5147,13.2395,"abierto","olympiastadion"),("MEXICO",19.3029,-99.1505,"abierto","azteca"),("MEXICO2",19.3029,-99.1505,"abierto","banorte"),
("MADRID",40.4531,-3.6883,"retractil","bernab"),("SAOPAULO",-23.5453,-46.4742,"abierto","corinthians"),("SAOPAULO2",-23.5453,-46.4742,"abierto","neo qu"),
("DUBLIN",53.3607,-6.2512,"abierto","croke"),("MELBOURNE",-37.8200,144.9834,"abierto","melbourne"),("RIO",-22.9122,-43.2302,"abierto","maracan")]
estadios = [{"codigo": c, "lat": la, "lon": lo, "techo": t, "buscar": b} for c, la, lo, t, b in EST]

# 1. Calendario, resultados y lineas (solo esta temporada y la anterior)
juegos = bajar("https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv", "Calendario y resultados (nflverse)")
if juegos:
    lines = juegos.splitlines()
    juegos = "\n".join([lines[0]] + [l for l in lines[1:] if l.startswith(f"{season}_") or l.startswith(f"{season-1}_")])

# 2. Lesiones (solo las dos ultimas semanas publicadas)
lesiones = bajar(f"https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_{season}.csv", "Lesiones (nflverse)")
if lesiones:
    try:
        rows = list(csv.reader(io.StringIO(lesiones)))
        h = rows[0]; wi = h.index("week") if "week" in h else None
        if wi is not None:
            ws = [int(r[wi]) for r in rows[1:] if len(r) > wi and r[wi].isdigit()]
            if ws:
                mx = max(ws); keep = [h] + [r for r in rows[1:] if len(r) > wi and r[wi].isdigit() and int(r[wi]) >= mx - 1]
                out = io.StringIO(); csv.writer(out, lineterminator="\n").writerows(keep); lesiones = out.getvalue()
    except Exception as e:
        print("Aviso al recortar lesiones:", e)

# 3. Estadisticas por equipo y partido
stats = bajar(f"https://github.com/nflverse/nflverse-data/releases/download/stats_team/stats_team_week_{season}.csv", "Estadisticas de equipos (nflverse)")

# 4. Cuotas (necesita el secreto ODDS_API_KEY)
cuotas = None
key = os.environ.get("ODDS_API_KEY", "").strip()
if key:
    reg = os.environ.get("REGIONES", "").strip() or "eu"
    t = bajar(f"https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds/?apiKey={key}&regions={reg}&markets=h2h,spreads,totals&oddsFormat=decimal", "Cuotas (The Odds API)")
    try:
        cuotas = json.loads(t) if t else None
        if not isinstance(cuotas, list):
            print("The Odds API respondio con un error:", str(cuotas)[:200]); cuotas = None
    except Exception:
        cuotas = None
else:
    print("AVISO: no hay secreto ODDS_API_KEY; se usaran las lineas de nflverse")
    estado["Cuotas (The Odds API)"] = "sin clave"

# 5. Clima de todos los estadios
lats = ",".join(str(e["lat"]) for e in estadios); lons = ",".join(str(e["lon"]) for e in estadios)
w = bajar(f"https://api.open-meteo.com/v1/forecast?latitude={lats}&longitude={lons}&hourly=temperature_2m,precipitation_probability,wind_speed_10m&wind_speed_unit=mph&timezone=GMT&forecast_days=16", "Clima (Open-Meteo)")
try:
    clima = json.loads(w) if w else None
    if isinstance(clima, dict) and "hourly" not in clima: clima = None
except Exception:
    clima = None

# 6. Tickets y dinero (pagina publica de VSiN; puede fallar si cambia la web)
html = bajar("https://data.vsin.com/nfl/betting-splits/", "Tickets y dinero (VSiN)")
splits = None
if html:
    tablas = re.findall(r"<table.*?</table>", html, flags=re.S | re.I)
    splits = "\n".join(tablas) if tablas else None

if not juegos:
    print("ERROR: sin calendario no se puede crear el paquete"); sys.exit(1)

creado = now.isoformat()
paquete = {"tipo": "crudo", "app": "linea-de-valor-nfl", "version": 2, "creado": creado, "temporada": season,
           "casa": os.environ.get("CASA", "").strip(), "estadios": estadios, "juegos": juegos, "lesiones": lesiones,
           "estadisticas": stats, "cuotas": cuotas, "clima": clima, "splits": splits}
os.makedirs("datos", exist_ok=True)
with open("datos/paquete.json", "w", encoding="utf-8") as f:
    json.dump(paquete, f, ensure_ascii=False, separators=(",", ":"))
with open("datos/estado.json", "w", encoding="utf-8") as f:
    json.dump({"creado": creado, "temporada": season, "fuentes": estado}, f, ensure_ascii=False, indent=1)
print("Paquete creado:", os.path.getsize("datos/paquete.json") // 1024, "KB")
