"""Convierte los datos de OpenStreetMap descargados en data/*.json en un único
fichero compacto (data/network.json) que usa la app.

Uso:  python build_data.py
"""
import json, math, re, collections

BBOX = (41.25, 1.85, 41.65, 2.35)  # zona metropolitana que recortamos
CORE = (41.30, 2.03, 41.50, 2.27)  # mapa base

def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)["elements"]

E = load("data/osm_full.json")
nodes = {e["id"]: e for e in E if e["type"] == "node"}
ways = {e["id"]: e for e in E if e["type"] == "way"}
rels = {e["id"]: e for e in E if e["type"] == "relation"}

def inside(lat, lon, b=BBOX):
    return b[0] <= lat <= b[2] and b[1] <= lon <= b[3]

def dist(a, b):
    """Distancia en metros entre (lat, lon)."""
    la = math.radians((a[0] + b[0]) / 2)
    dx = (b[1] - a[1]) * 111320 * math.cos(la)
    dy = (b[0] - a[0]) * 110540
    return math.hypot(dx, dy)

def ll(e):
    if "lat" in e:
        return (e["lat"], e["lon"])
    if "center" in e:
        return (e["center"]["lat"], e["center"]["lon"])
    return None

def r5(x):
    return round(x, 5)

# ---------------------------------------------------------------- modos
def mode_of(t):
    net = t.get("network", "")
    if t.get("route") == "funicular":
        return "funicular"
    if net == "Metro de Barcelona":
        return "metro"
    if net.startswith("Metro del"):
        return "fgc"
    return "rodalies"

OPERATOR = {"Transports Metropolitans de Barcelona": "TMB",
            "Ferrocarrils de la Generalitat de Catalunya": "FGC",
            "Renfe": "Renfe"}
DEFAULT_COLOR = {"metro": "#888888", "fgc": "#F47216", "rodalies": "#E2001A", "funicular": "#5E8C31"}
# minutos medios entre trenes si OSM no trae "interval"
DEFAULT_HEADWAY = {"metro": 4, "fgc": 8, "rodalies": 15, "funicular": 10}
# velocidad comercial (m/min) incluida la parada
SPEED = {"metro": 450, "fgc": 600, "rodalies": 800, "funicular": 120}
DWELL = 0.4
REGIONAL = re.compile(r"^(R1[1-7]|RG|RL|RT|R3$)")

def parse_interval(s):
    if not s:
        return None
    m = re.match(r"^(\d+):(\d+)(?::(\d+))?$", s.strip())
    if m:
        h, mi, se = int(m[1]), int(m[2]), int(m[3] or 0)
        # "00:03:28" → 3.5 min ; "00:15" → 15 min
        return h * 60 + mi + se / 60 if m[3] else h * 60 + mi
    if s.strip().isdigit():
        return int(s)
    return None

# ---------------------------------------------------------------- estaciones
area_of_stop = collections.defaultdict(list)
for r in rels.values():
    if r["tags"].get("public_transport") == "stop_area":
        for m in r["members"]:
            if m["type"] == "node":
                area_of_stop[m["ref"]].append(r["id"])

stations = {}  # sid -> dict

def station_for_stop(nid, mode):
    n = nodes[nid]
    areas = area_of_stop.get(nid)
    if areas:
        sid = "a%d" % areas[0]
        if sid not in stations:
            a = rels[areas[0]]
            name = a["tags"].get("name") or n.get("tags", {}).get("name") or "?"
            stations[sid] = {"id": sid, "name": name, "pts": [], "modes": set(), "area": areas[0]}
        return sid
    # parada sin stop_area: agrupamos por nombre y cercanía
    name = n.get("tags", {}).get("name") or "?"
    for s in stations.values():
        if s.get("area") is None and s["name"] == name and s["pts"] and dist(s["pts"][0], ll(n)) < 400:
            return s["id"]
    sid = "n%d" % nid
    stations[sid] = {"id": sid, "name": name, "pts": [], "modes": set(), "area": None}
    return sid

def clean_name(s):
    """'Catalunya (L3)' → 'Catalunya', '- Sants (RENFE)' → 'Sants', 'Barcelona-Sants' → 'Sants'."""
    s = re.sub(r"\s*\((L\d+[NS]?|L\d+/L\d+|RENFE|Renfe|FGC|FM|TMB|Rodalies|Metro|metro|Adif)[^)]*\)", "", s)
    s = re.sub(r"\s+metro$", "", s)
    s = re.sub(r"^Barcelona\s*[-–]?\s*", "", s) if len(s) > 12 else s
    return s.strip(" -–")

# ---------------------------------------------------------------- líneas
patterns = []
lines = {}
for r in rels.values():
    t = r["tags"]
    if t.get("type") != "route":
        continue
    mode = mode_of(t)
    ref = t.get("ref") or "?"
    lid = "%s|%s" % (mode, ref)
    op = OPERATOR.get(t.get("operator"), t.get("operator", ""))
    color = t.get("colour") or DEFAULT_COLOR[mode]
    if not color.startswith("#"):
        color = DEFAULT_COLOR[mode]
    lines.setdefault(lid, {"id": lid, "ref": ref, "mode": mode, "op": op, "color": color,
                           "net": t.get("network", ""), "hours": t.get("opening_hours", "")})
    seq = []
    for m in r["members"]:
        if m["type"] != "node" or m["ref"] not in nodes:
            continue
        role = m["role"]
        if not role.startswith("stop"):
            continue
        n = nodes[m["ref"]]
        if not inside(*ll(n)):
            continue
        sid = station_for_stop(m["ref"], mode)
        st = stations[sid]
        st["pts"].append(ll(n))
        st["modes"].add(mode)
        if seq and seq[-1]["s"] == sid:
            continue
        seq.append({"s": sid, "n": m["ref"], "role": role})
    if len(seq) < 2:
        continue
    hw = parse_interval(t.get("interval")) or DEFAULT_HEADWAY[mode]
    if mode == "rodalies" and REGIONAL.match(ref):
        hw = max(hw, 60)  # regionales: pocos trenes, no sirven para moverse por la ciudad
    to = t.get("to") or (t.get("name", "").split("=>")[-1].split("→")[-1].strip())
    patterns.append({"id": r["id"], "line": lid, "to": to.strip(), "from": t.get("from", ""),
                     "hw": round(hw, 1), "seq": seq})

# ---------------------------------------------------------------- andenes (centro)
platform_centers = collections.defaultdict(list)  # sid -> [(lat,lon)]
for sid, s in stations.items():
    if s["area"]:
        for m in rels[s["area"]]["members"]:
            if m["role"] == "platform":
                el = (ways if m["type"] == "way" else nodes).get(m["ref"])
                if el and ll(el):
                    platform_centers[sid].append(ll(el))

for s in stations.values():
    pts = s["pts"] + platform_centers.get(s["id"], [])
    s["lat"] = sum(p[0] for p in pts) / len(pts)
    s["lon"] = sum(p[1] for p in pts) / len(pts)

def platform_point(sid, stop_nid):
    """Punto medio del andén donde para el tren (aprox.)."""
    p = ll(nodes[stop_nid])
    best = None
    for c in platform_centers.get(sid, []):
        d = dist(p, c)
        if d < 120 and (best is None or d < best[0]):
            best = (d, c)
    return best[1] if best else p

# ---------------------------------------------------------------- accesos
entrances = []
station_ids_by_area = {s["area"]: sid for sid, s in stations.items() if s["area"]}
for e in E:
    t = e.get("tags", {})
    if e["type"] != "node" or t.get("railway") not in ("subway_entrance", "train_station_entrance"):
        continue
    p = ll(e)
    sids = [station_ids_by_area[a] for a in area_of_stop.get(e["id"], []) if a in station_ids_by_area]
    if not sids:
        cands = sorted((dist(p, (s["lat"], s["lon"])), sid) for sid, s in stations.items())
        cands = [c for c in cands if c[0] < 220]
        if not cands:
            continue
        sids = [cands[0][1]]
    entrances.append({
        "id": e["id"], "lat": r5(p[0]), "lon": r5(p[1]),
        "name": t.get("name") or t.get("ref") or "Acceso sin nombre",
        "ref": t.get("ref", ""),
        "lift": t.get("highway") == "elevator",
        "wc": {"yes": 1, "no": 0, "limited": 2}.get(t.get("wheelchair"), -1),
        "hours": t.get("opening_hours", ""),
        "lvl": t.get("level", ""),
        "s": sids,
    })

# ---------------------------------------------------------------- correspondencias
def tokens(name):
    w = re.findall(r"[a-zàèéíïòóúüç·]+", name.lower())
    stop = {"de", "del", "la", "el", "les", "els", "i", "barcelona", "plaça", "pl", "estació", "l", "d"}
    return {x for x in w if x not in stop and len(x) > 2}

# pares con nombre distinto pero unidos por pasillo interior
INTERIOR_LINKS = [{"Diagonal", "Provença"}]
sids = list(stations)
transfers = []
for i, a in enumerate(sids):
    A = stations[a]
    for b in sids[i + 1:]:
        B = stations[b]
        d = dist((A["lat"], A["lon"]), (B["lat"], B["lon"]))
        if d > 420:
            continue
        same = bool(tokens(A["name"]) & tokens(B["name"])) or A["name"] == B["name"]             or {clean_name(A["name"]), clean_name(B["name"])} in INTERIOR_LINKS
        if not same and d > 250:
            continue
        mins = max(2.0, d * 1.4 / 75) + 1.0  # 75 m/min a pie por pasillos
        transfers.append([a, b, round(mins, 1), round(d), 1 if same else 0])

# ---------------------------------------------------------------- lugares
POI_KIND = [("aeroway", "terminal", "Aeropuerto"), ("amenity", "hospital", "Hospital"),
            ("amenity", "university", "Universidad"), ("amenity", "theatre", "Teatro"),
            ("amenity", "concert_hall", "Auditorio"), ("amenity", "marketplace", "Mercado"),
            ("tourism", "museum", "Museo"), ("tourism", "zoo", "Zoo"), ("tourism", "aquarium", "Acuario"),
            ("tourism", "theme_park", "Parque temático"), ("leisure", "stadium", "Estadio"),
            ("leisure", "park", "Parque"), ("natural", "beach", "Playa"), ("shop", "mall", "Centro comercial"),
            ("tourism", "attraction", "Lugar de interés"), ("historic", None, "Monumento")]
pois, seen = [], set()
for e in load("data/osm_poi.json"):
    t = e.get("tags", {})
    p = ll(e)
    if not p or not t.get("name"):
        continue
    kind = next((lab for k, v, lab in POI_KIND if (v is None and k in t) or t.get(k) == v), "Lugar")
    key = (t["name"].lower(), kind)
    if key in seen:
        continue
    seen.add(key)
    pois.append([t["name"], kind, r5(p[0]), r5(p[1])])

# ---------------------------------------------------------------- mapa base
def simplify(pts, tol):
    """Douglas-Peucker en metros."""
    if len(pts) < 3:
        return pts
    a, b = pts[0], pts[-1]
    la = math.radians(a[0])
    def xy(p):
        return ((p[1] - a[1]) * 111320 * math.cos(la), (p[0] - a[0]) * 110540)
    ax, ay = xy(a); bx, by = xy(b)
    dx, dy = bx - ax, by - ay
    L = math.hypot(dx, dy) or 1e-9
    best, idx = -1, 0
    for i in range(1, len(pts) - 1):
        px, py = xy(pts[i])
        d = abs(dy * px - dx * py + bx * ay - by * ax) / L
        if d > best:
            best, idx = d, i
    if best <= tol:
        return [a, b]
    return simplify(pts[:idx + 1], tol)[:-1] + simplify(pts[idx:], tol)

bg = {"road": [], "major": [], "coast": [], "park": []}
for e in load("data/osm_bg.json"):
    t = e.get("tags", {})
    g = [(p["lat"], p["lon"]) for p in e.get("geometry", []) if p]
    if len(g) < 2:
        continue
    if t.get("natural") == "coastline":
        kind, tol = "coast", 12
    elif t.get("leisure") == "park":
        kind, tol = "park", 10
    elif t.get("highway") in ("motorway", "trunk"):
        kind, tol = "major", 8
    else:
        kind, tol = "road", 6
    if kind == "road" and t.get("oneway") == "yes" and t.get("highway") == "secondary":
        pass
    s = simplify(g, tol)
    bg[kind].append([v for p in s for v in (round(p[0], 5), round(p[1], 5))])

# ---------------------------------------------------------------- salida
st_list = []
for sid, s in stations.items():
    st_list.append({"id": sid, "name": clean_name(s["name"]), "full": s["name"],
                    "lat": r5(s["lat"]), "lon": r5(s["lon"]), "modes": sorted(s["modes"])})

pat_out = []
for p in patterns:
    seq = []
    for i, x in enumerate(p["seq"]):
        pp = platform_point(x["s"], x["n"])
        seq.append([x["s"], r5(pp[0]), r5(pp[1]),
                    {"stop": 0, "stop_entry_only": 1, "stop_exit_only": 2}.get(x["role"], 0)])
    pat_out.append({"id": p["id"], "line": p["line"], "to": p["to"], "from": p["from"],
                    "hw": p["hw"], "seq": seq})

used_lines = {p["line"] for p in pat_out}
out = {"generated": "OpenStreetMap (ODbL), descargado 2026-10-31",
       "speed": SPEED, "dwell": DWELL,
       "lines": [l for l in lines.values() if l["id"] in used_lines], "stations": st_list, "patterns": pat_out,
       "entrances": entrances, "transfers": transfers, "pois": pois, "bg": bg}
with open("data/network.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, separators=(",", ":"))

print("líneas", len(lines), "recorridos", len(pat_out), "estaciones", len(st_list),
      "accesos", len(entrances), "transbordos", len(transfers), "lugares", len(pois))
print("bg", {k: len(v) for k, v in bg.items()})
