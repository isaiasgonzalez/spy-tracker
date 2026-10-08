# Nuevo lanzador: Python + Git

Este ejecutable Linux es un script Bash independiente. No usa el ejecutable
anterior, la API de GitHub ni PyInstaller.

## Requisitos

- Una copia **Git** del repositorio en tu computadora, en la rama `main`.
- Python con las dependencias de `requirements.txt`: el comando
  `python script.py pesos` debe funcionar en esa copia.
- Git con tu nombre/email y autenticación de escritura ya configurados para
  el remoto `origin`. No pide un token adicional ni cambia esas credenciales.

## Uso en CachyOS

1. Extraé `SPY-Pesos-Git-Linux.tar.gz`.
2. Ejecutá `bash install_pesos_git.sh` dentro de la carpeta extraída.
3. Abrí `Publicar-pesos-Git.desktop`. KDE puede pedir marcarlo como confiable.
4. Indicá la ruta de tu copia local del repositorio cuando la solicite.

Si extraés el lanzador en el propio repositorio, detecta la carpeta solo.
Antes de abrirlo, editá o reemplazá **spy500.csv** en esa copia del repositorio.
No selecciona otro CSV: usa exactamente el mismo archivo que `script.py pesos`.

También podés ejecutarlo directamente desde una terminal:

```sh
bash Actualizar-Pesos-Git --repo /ruta/spy-tracker
```

Si usás un entorno virtual distinto de `.venv`, indicá su intérprete:

```sh
bash Actualizar-Pesos-Git --repo /ruta/spy-tracker --python /ruta/entorno/bin/python
```

## Qué hace

Sincroniza `main` sin sobrescribir cambios, ejecuta **script.py pesos**, aplica
los nuevos pesos a `SPY_data.json` usando los precios existentes, y hace
commit/push de `spy500.csv` y los dos JSON. No consulta precios ni modifica
otros archivos. El hosting conectado al repo despliega con su mecanismo normal.

Si hay cambios preparados para otro commit, cambios de código, conflictos de
Git o commits locales pendientes, se detiene y conserva tu trabajo. No fuerza
el push. El resultado y cualquier error quedan visibles en la terminal.
