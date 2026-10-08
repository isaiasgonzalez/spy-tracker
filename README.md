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

## Tu CSV y el ejecutable en CachyOS

Los pesos son tuyos: no se reemplazan automáticamente por una fuente externa.
Descargá `SPY-Pesos-Linux.tar.gz` desde Releases, extraelo en una carpeta y ejecutá:

```sh
bash install_launcher.sh
```

Luego abrí `Actualizar-pesos.desktop` (en KDE puede ser necesario marcarlo como
confiable). El lanzador abre una terminal y un selector de archivos mediante
`kdialog` o `zenity`; si no están instalados, pide la ruta del CSV.
El ejecutable no requiere Python ni Git instalados.

Usá un token fine-grained de GitHub, limitado a este repositorio, con permiso
**Contents: Read and write**. Lo pide con entrada oculta y no lo guarda.
También admite `SPY_GITHUB_TOKEN` si ya lo administrás en tu sistema.
No pegues tokens en el CSV ni en el repositorio.

El CSV acepta `Symbol`/`Ticker`, `Company`/`Name` y `Weight`; los pesos se expresan
como porcentajes (7.06 significa 7.06%). Verifica duplicados, valores inválidos,
composición completa y suma entre 95% y 105%. Omite futuros (`=F`) y posiciones
con peso cero. Publica CSV, base de pesos y dashboard en un solo commit sobre
`main`, sin forzar cambios concurrentes. Si otro proceso actualizó `main`,
repetí la operación. Si los pesos ya coinciden, no crea un commit.

Recalcula los impactos con los precios existentes, conserva su fecha de mercado
y registra los símbolos nuevos sin precio. Durante la rueda, el push de pesos
activa una actualización de precios; fuera de la rueda espera a la siguiente.
La publicación en GitHub activa el despliegue solo si tu hosting ya está
conectado al repositorio; la herramienta no configura el hosting.

Para validar sin publicar:

```sh
./SPY-Pesos --csv /ruta/tus-pesos.csv --dry-run
```

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
Las pruebas se ejecutan en un workflow separado cuando cambia el código.
