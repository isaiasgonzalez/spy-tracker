# SPY Tracker

Dashboard estático de la composición del SPY y un pipeline Python para sus precios.

## Desarrollo

Usar Python 3.11:

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
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

`spy500.csv` y las herramientas personales de publicación se mantienen fuera del
repositorio. Los pesos procesados se publican en `SPY_componentes_base.json` y el
dashboard consume solamente `SPY_data.json`.

## Actualización automática de precios

Actions programa ejecuciones a los minutos **02, 17, 32 y 47**, en una ventana
UTC que cubre los horarios de verano e invierno de Nueva York. Un calendario
NYSE bloquea consultas antes de abrir, desde el cierre, en feriados y fines de
semana, y respeta cierres anticipados. GitHub Actions puede retrasar u omitir
ejecuciones programadas: no ofrece garantía de intervalos exactos. El último
snapshot del día puede ser anterior al cierre; no se pide otro precio después.
Para puntualidad estricta se necesita un scheduler externo siempre disponible.

El script vuelve a comprobar la rueda antes de cada lote y reintento. Una
consulta iniciada antes del cierre puede terminar después; no se inicia otro
lote al cerrar. Descarga lotes de 40 símbolos con hasta 8 hilos y reintenta solo
los que no devolvieron suficientes cierres. Reutiliza las referencias de SPY
una vez por sesión para calcular los horizontes con el mismo precio actual.
Los rendimientos mostrados son variaciones de precio, no rendimiento total con
dividendos reinvertidos.

No publica si falta SPY o la cobertura es inferior al 95% del peso de la base.
Preserva el último archivo válido y escribe mediante reemplazo atómico.
Los datos sin cambios no producen commits por el mero paso del tiempo.
Actions conserva la caché de referencias diarias y evita ejecuciones simultáneas.
