"""Planos interiores de estaciones a partir de OpenStreetMap.

Para cada estación de la lista descarga (si hace falta) sus pasillos, escaleras, ascensores, andenes
y bocas, los convierte en un grafo por el que se puede calcular el camino y lo guarda en
data/indoor.json, que la app usa para dibujar el plano y el recorrido dentro de la estación.

Uso:  python build_indoor.py
"""
import json, math, os, re, collections
from tools_overpass import q as overpass

# Estaciones con plano (de momento, el prototipo). centro y radio cubren todo el conjunto de líneas.
STATIONS = [
    {"name": "Passeig de Gràcia", "slug": "pg", "lat": 41.3912, "lon": 2.1665, "r": 400},
]
GAP_BRIDGE = 8    # m: une pasillos que en el mapa casi se tocan
SNAP_MAX = 25     # m: distancia máxima para enganchar una boca o un andén suelto al pasillo más cercano
KIND = {"corridor": 0, "steps": 1, "elevator": 2, "platform": 3, "gap": 4}

def dist(a, b):
    la = math.radians((a[0] + b[0]) / 2)
    return math.hypot((b[1] - a[1]) * 111320 * math.cos(la), (b[0] - a[0]) * 110540)

def level_of(t):
    m = re.match(r"^\s*(-?\d+(?:\.\d+)?)", str(t.get("level", "")))
    return float(m[1]) if m else None

def underground(t):
    return bool(t.get("tunnel") or t.get("indoor") or str(t.get("level", "0")).startswith("-")
                or str(t.get("layer", "0")).startswith("-") or t.get("highway") in ("steps", "elevator", "corridor"))

def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)["elements"]

# andén (way) → recorridos (relaciones de ruta) que paran en él
routes_by_platform = collections.defaultdict(set)
for r in load("data/osm_full.json"):
    if r["type"] == "relation" and r["tags"].get("type") == "route":
        for m in r["members"]:
            if m["type"] == "way" and m["role"].startswith("platform"):
                routes_by_platform[m["ref"]].add(r["id"])

network = json.load(open("data/network.json", encoding="utf-8"))
pattern_ids = {p["id"] for p in network["patterns"]}

out = {}
for S in STATIONS:
    path = "data/osm_indoor_%s.json" % S["slug"]
    if not os.path.exists(path):
        query = open("data/q_indoor.txt", encoding="utf-8").read()
        query = query.replace("{{LAT}}", str(S["lat"])).replace("{{LON}}", str(S["lon"])).replace("{{R}}", str(S["r"]))
        overpass(query, path)
    E = load(path)
    ways = [e for e in E if e["type"] == "way" and "geometry" in e]

    coords, levels = {}, {}
    edges = {}  # (a, b) -> kind
    draw, platforms, rooms = [], [], []

    def add_way(w, kind):
        lvl = level_of(w["tags"])
        ids = w["nodes"]
        for n, g in zip(ids, w["geometry"]):
            coords[n] = (g["lat"], g["lon"])
            if lvl is not None and n not in levels:
                levels[n] = lvl
        for a, b in zip(ids, ids[1:]):
            if a != b:
                edges[tuple(sorted((a, b)))] = kind
        return ids, lvl

    for w in ways:
        t = w["tags"]
        if t.get("railway") == "platform" or t.get("public_transport") == "platform" and t.get("railway") != "bus_stop" and "bus" not in t:
            if t.get("highway") == "bus_stop" or t.get("bus") == "yes":
                continue
            ids, lvl = add_way(w, "platform")
            pats = sorted(p for p in routes_by_platform.get(w["id"], ()) if p in pattern_ids)
            platforms.append({"id": w["id"], "name": t.get("name", ""), "lvl": lvl, "nodes": ids, "pats": pats})
        elif t.get("highway") in ("footway", "corridor", "steps", "elevator", "path") and underground(t):
            kind = "steps" if t["highway"] == "steps" else "elevator" if t["highway"] == "elevator" else "corridor"
            ids, lvl = add_way(w, kind)
            draw.append({"k": kind, "lvl": lvl, "nodes": ids})
        elif t.get("indoor") in ("corridor",) :
            ids, lvl = add_way(w, "corridor")
            draw.append({"k": "corridor", "lvl": lvl, "nodes": ids})
        elif t.get("indoor") in ("room", "area"):
            rooms.append([(g["lat"], g["lon"]) for g in w["geometry"]])

    # --- componentes conexas y puentes en los huecos del mapa
    adj = collections.defaultdict(set)
    for a, b in edges:
        adj[a].add(b); adj[b].add(a)

    def components():
        comp, cid = {}, 0
        for n in adj:
            if n in comp:
                continue
            cid += 1
            stack = [n]; comp[n] = cid
            while stack:
                x = stack.pop()
                for y in adj[x]:
                    if y not in comp:
                        comp[y] = cid; stack.append(y)
        return comp

    def bridge(a, b):
        edges[tuple(sorted((a, b)))] = "gap"
        adj[a].add(b); adj[b].add(a)

    # Nunca se tiende un puente entre dos andenes distintos: sería cruzar las vías.
    platform_of = {n: p["id"] for p in platforms for n in p["nodes"]}

    def allowed(a, b):
        pa, pb = platform_of.get(a), platform_of.get(b)
        return not (pa and pb and pa != pb)

    def closest_between(ca, cb, comp):
        best = None
        A = [n for n in comp if comp[n] == ca]
        B = [n for n in comp if comp[n] == cb]
        for a in A:
            for b in B:
                if not allowed(a, b):
                    continue
                d = dist(coords[a], coords[b])
                if best is None or d < best[0]:
                    best = (d, a, b)
        return best

    # Une piezas cercanas de una en una: primero los huecos pequeños, luego lo suelto que quede cerca de la pieza mayor.
    for limit, only_main in ((GAP_BRIDGE, False), (SNAP_MAX, True)):
        while True:
            comp = components()
            ids = list(collections.Counter(comp.values()))
            main = collections.Counter(comp.values()).most_common(1)[0][0]
            best = None
            for i, ca in enumerate(ids):
                for cb in ids[i + 1:]:
                    if only_main and main not in (ca, cb):
                        continue
                    c = closest_between(ca, cb, comp)
                    if c and c[0] <= limit and (best is None or c[0] < best[0]):
                        best = c
            if not best:
                break
            bridge(best[1], best[2])

    # --- bocas: enganchadas a su nodo o al pasillo más cercano
    ents = []
    for e in E:
        if e["type"] != "node" or e.get("tags", {}).get("railway") not in ("subway_entrance", "train_station_entrance"):
            continue
        p = (e["lat"], e["lon"])
        coords.setdefault(e["id"], p)
        if e["id"] not in adj:
            cands = [(dist(p, coords[n]), n) for n in list(adj)]
            if cands:
                d, n = min(cands)
                if d <= SNAP_MAX:
                    bridge(e["id"], n)
        ents.append({"id": e["id"], "name": e["tags"].get("name", ""), "lift": e["tags"].get("highway") == "elevator"})

    comp = components()
    sizes = collections.Counter(comp.values())
    main = sizes.most_common(1)[0][0]

    # --- salida compacta: nodos por índice
    used = sorted(set(n for ab in edges for n in ab) | {e["id"] for e in ents})
    idx = {n: i for i, n in enumerate(used)}
    out[S["name"]] = {
        "name": S["name"],
        "center": [S["lat"], S["lon"]],
        "sids": [s["id"] for s in network["stations"] if s["name"] == S["name"] or s["full"].endswith(S["name"])
                 and dist((s["lat"], s["lon"]), (S["lat"], S["lon"])) < S["r"]],
        "nodes": [[round(coords[n][0], 6), round(coords[n][1], 6), levels.get(n)] for n in used],
        "edges": [[idx[a], idx[b], KIND[k]] for (a, b), k in edges.items()],
        "draw": [{"k": d["k"], "lvl": d["lvl"], "n": [idx[n] for n in d["nodes"]]} for d in draw],
        "platforms": [{"id": p["id"], "name": p["name"], "lvl": p["lvl"], "n": [idx[n] for n in p["nodes"]], "pats": p["pats"]}
                      for p in platforms],
        "rooms": [[[round(a, 6), round(b, 6)] for a, b in r] for r in rooms],
        "ents": [{"id": e["id"], "name": e["name"], "i": idx[e["id"]], "ok": comp.get(e["id"]) == main} for e in ents],
        "source": "OpenStreetMap (ODbL)",
    }
    st = out[S["name"]]
    print(S["name"], "| nodos", len(st["nodes"]), "| tramos", len(st["edges"]),
          "| puentes", sum(1 for e in st["edges"] if e[2] == KIND["gap"]),
          "| andenes", len(platforms), "conectados", sum(1 for p in platforms if comp.get(p["nodes"][0]) == main),
          "| bocas", len(ents), "conectadas", sum(1 for e in st["ents"] if e["ok"]),
          "| piezas sueltas", len(sizes) - 1)

with open("data/indoor.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
print("data/indoor.json", os.path.getsize("data/indoor.json") // 1024, "KB")
