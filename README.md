# SPY Tracker

Dashboard estático de la composición del SPY y un pipeline Python para sus precios.

## Desarrollo

Usar Python 3.11:

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m http.server 8000 --bind 127.0.0.1
```

No hay un paso de compilación del frontend. El dashboard carga `SPY_data.json`
y muestra la fecha de mercado incluida en ese archivo. Tailwind, html2canvas y
las fuentes se descargan desde sus respectivos CDN.

## Actualización de datos

```sh
# Usar los pesos del CSV incluido y escribir fuera del repositorio.
python script.py todo --output-dir /tmp/spy-tracker-data

# Descargar la composición diaria oficial de State Street y luego los precios.
python script.py todo --fuente-pesos oficial --output-dir /tmp/spy-tracker-data

# Actualizar solo precios, usando la base de salida o la incluida si no existe.
python script.py precios --output-dir /tmp/spy-tracker-data
```

Sin `--output-dir`, los comandos escriben los JSON junto al script, como en CI.
La fuente local sigue siendo la predeterminada. La fuente oficial requiere
acceso HTTPS a `www.ssga.com`; los precios requieren Yahoo Finance.
Las pruebas usan datos controlados y no requieren red. Una falla de red no
debe interpretarse como una validación exitosa del actualizador.
