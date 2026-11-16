"""
Configura este clon: activa el filtro de ruta del modelo Power BI y
reescribe expressions.tmdl con la ruta local de data/.

Uso (desde la raíz del repo):  python -I scripts/configurar_repo.py
"""
import os
import subprocess

TMDL = "pbip/BSI_Transporte_EEUU.SemanticModel/definition/expressions.tmdl"


def git(*args):
    subprocess.run(["git", *args], check=True)


git("config", "filter.rutadatos.clean", "python -I scripts/git_filtro_ruta.py clean")
git("config", "filter.rutadatos.smudge", "python -I scripts/git_filtro_ruta.py smudge")
git("config", "filter.rutadatos.required", "true")
os.remove(TMDL)  # forzar que git lo reescriba aplicando smudge
git("checkout", "HEAD", "--", TMDL)
print("Listo: filtro 'rutadatos' activo y RutaDatos apunta a la carpeta data/ de este clon.")
