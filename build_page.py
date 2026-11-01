"""Genera, a partir de la misma plantilla, el motor y los datos:
  - metro-maps-bcn.html  la página que se publica como Artifact (sin GPS)
  - docs/                la app instalable con GPS y modo sin conexión
Necesita data/network.json (build_data.py) y data/indoor.json (build_indoor.py).
"""
import hashlib, json, os, shutil

t = open("app_template.html", encoding="utf-8").read()
css = open("data/leaflet.css", encoding="utf-8").read()
eng = open("engine.js", encoding="utf-8").read()
eng += "\n" + open("indoor.js", encoding="utf-8").read()
indoor = open("data/indoor.json", encoding="utf-8").read().replace("</", r"<\/")
data = open("data/network.json", encoding="utf-8").read().replace("</", r"<\/")
json.loads(data.replace(r"<\/", "</"))
body = t.replace("/*__LEAFLET_CSS__*/", css).replace("/*__ENGINE__*/", eng).replace("/*__DATA__*/", data).replace("/*__INDOOR_DATA__*/", indoor).replace("/*__INDOOR__*/", "")

# ---------------------------------------------------------------- Artifact
page = body.replace("/*__LEAFLET_SRC__*/", "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js")
open("metro-maps-bcn.html", "w", encoding="utf-8").write(page)
print("metro-maps-bcn.html", len(page.encode()) // 1024, "KB")

# ---------------------------------------------------------------- app instalable
os.makedirs("docs/icons", exist_ok=True)
app = body.replace("/*__LEAFLET_SRC__*/", "leaflet.js").replace("const PWA = /*__PWA__*/false;", "const PWA = true;")
head = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#18222C">
<meta name="description" content="Por qué boca entrar, qué andén tomar, en qué parte del tren ir y por qué salida salir en el Metro, FGC y Rodalies de Barcelona.">
<link rel="manifest" href="manifest.webmanifest">
<link rel="icon" href="icons/icon-192.png">
<link rel="apple-touch-icon" href="icons/apple-180.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Metro Maps">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<style>:root{color-scheme:light;padding-top:env(safe-area-inset-top);padding-bottom:env(safe-area-inset-bottom)}body{margin:0;font:14px system-ui}img{max-width:100%}[hidden]{display:none!important}</style>
</head>
<body>
"""
tail = """
<script>
if ("serviceWorker" in navigator) addEventListener("load", () => navigator.serviceWorker.register("sw.js").catch(() => {}));
</script>
</body>
</html>
"""
html = head + app + tail
open("docs/index.html", "w", encoding="utf-8").write(html)
shutil.copy("data/leaflet.js", "docs/leaflet.js")

version = hashlib.sha1(html.encode()).hexdigest()[:10]
sw = open("sw_template.js", encoding="utf-8").read().replace("/*__VERSION__*/", version)
open("docs/sw.js", "w", encoding="utf-8").write(sw)

manifest = {
    "name": "Metro Maps BCN",
    "short_name": "Metro Maps",
    "description": "Guía por dentro del Metro, FGC y Rodalies de Barcelona: bocas, andenes, transbordos y salidas.",
    "lang": "es",
    "start_url": "./",
    "scope": "./",
    "display": "standalone",
    "background_color": "#18222C",
    "theme_color": "#18222C",
    "icons": [
        {"src": "icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
        {"src": "icons/icon-512.png", "sizes": "512x512", "type": "image/png"},
        {"src": "icons/maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
    ],
}
json.dump(manifest, open("docs/manifest.webmanifest", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("docs/ lista, versión", version)

# copia local de la página del Artifact con su esqueleto, para probarla en el navegador
skel = ('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
        '<style>:root{color-scheme:light;padding-top:env(safe-area-inset-top);padding-bottom:env(safe-area-inset-bottom)}body{margin:0;font:14px system-ui}[hidden]{display:none!important}</style></head><body>')
open("data/preview.html", "w", encoding="utf-8").write(skel + page + "</body></html>")
