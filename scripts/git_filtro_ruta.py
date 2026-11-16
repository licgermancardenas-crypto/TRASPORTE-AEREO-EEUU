"""
Filtro git para el parámetro RutaDatos del modelo (expressions.tmdl).

  clean  (al hacer commit):  ruta absoluta local  ->  {{RUTA_REPO}}\\data\\
  smudge (al hacer checkout): {{RUTA_REPO}}        ->  carpeta de este clon

Así el repo no guarda rutas de ningún disco y cada clon apunta a su propia carpeta data/.
Se activa una vez por clon con:  python -I scripts/configurar_repo.py
"""
import os
import re
import sys

MARCA = "{{RUTA_REPO}}"
PATRON = re.compile(r'^(expression RutaDatos = ")([^"]*)(")', re.M)


def clean(txt: str) -> str:
    return PATRON.sub(lambda m: m.group(1) + MARCA + "\\data\\" + m.group(3), txt)


def smudge(txt: str) -> str:
    raiz = os.getcwd().replace("/", "\\")  # git ejecuta los filtros desde la raíz del repo
    return txt.replace(MARCA, raiz)


if __name__ == "__main__":
    data = sys.stdin.buffer.read().decode("utf-8")
    out = clean(data) if sys.argv[1] == "clean" else smudge(data)
    sys.stdout.buffer.write(out.encode("utf-8"))
