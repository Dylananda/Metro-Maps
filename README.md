# Metro Maps BCN

Guía por dentro del Metro, FGC y Rodalies de Barcelona: por qué boca entrar, qué andén y dirección tomar, en qué parte del tren ir, cómo hacer el transbordo y por qué salida salir.

La app está en `docs/` y se publica con GitHub Pages. Se puede instalar en el móvil, usa el GPS para guiarte hasta la boca y la salida, y funciona sin conexión.

## Cómo está hecha

| Archivo | Qué hace |
| --- | --- |
| `data/q_*.txt` | Consultas a OpenStreetMap (Overpass) para descargar líneas, estaciones, bocas, lugares y el mapa base |
| `tools_overpass.py` | Lanza una consulta: `python tools_overpass.py data/q_full.txt data/osm_full.json` |
| `build_data.py` | Convierte las descargas en `data/network.json` |
| `engine.js` | Motor de rutas (bocas, líneas, transbordos, posición en el tren) |
| `app_template.html` | Interfaz, mapa y guía GPS |
| `build_page.py` | Genera `docs/` (la app) y `metro-maps-bcn.html` (versión sin GPS) |
| `make_icons.py` | Dibuja los iconos de la app |
| `test_engine.js` | Trayectos de prueba: `node test_engine.js` |

## Actualizar los datos

```bash
python tools_overpass.py data/q_full.txt data/osm_full.json
python tools_overpass.py data/q_poi.txt data/osm_poi.json
python tools_overpass.py data/q_bg.txt data/osm_bg.json
python build_data.py
python build_page.py
```

`build_page.py` necesita `data/leaflet.js` (Leaflet 1.9.4, de cdnjs) junto a `data/leaflet.css`.

## Datos y límites

Datos © colaboradores de [OpenStreetMap](https://www.openstreetmap.org/copyright), con licencia ODbL. La posición en el tren y los tiempos son estimaciones; las estaciones sin bocas registradas en OpenStreetMap muestran "busca la entrada principal". Comprueba siempre la señalización de la estación.
