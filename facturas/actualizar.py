"""
Busca la última versión de la app en el repositorio y la aplica.

Diseñado para ser a prueba de fallos:
  - Si no hay git, o no es un repo, o no hay internet → no hace nada y deja
    que la app abra con la versión que ya está en disco.
  - Nunca corta el arranque de la app: cualquier problema se informa y se sigue.

Se ejecuta desde procesar.bat ANTES de abrir la aplicación. Está en Python
(y no en el .bat) para que actualizarse a sí mismo sea seguro: Python carga
todo el archivo en memoria antes de ejecutarlo.
"""
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _git(*args, timeout=30):
    """Corre un comando git en la carpeta de la app. Devuelve (ok, salida)."""
    try:
        r = subprocess.run(
            ['git', *args],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return r.returncode == 0, (r.stdout + r.stderr).strip()
    except FileNotFoundError:
        return False, 'git-no-instalado'
    except subprocess.TimeoutExpired:
        return False, 'timeout'
    except Exception as e:
        return False, str(e)


def main():
    # ¿git disponible?
    ok, _ = _git('--version', timeout=10)
    if not ok:
        print('  [i] Git no esta instalado: se usa la version actual.')
        return

    # ¿esta carpeta es un repositorio git?
    ok, _ = _git('rev-parse', '--is-inside-work-tree', timeout=10)
    if not ok:
        print('  [i] La app no se instalo con Git: se usa la version actual.')
        return

    # Rama actual
    ok, rama = _git('rev-parse', '--abbrev-ref', 'HEAD', timeout=10)
    if not ok or not rama:
        print('  [i] No pude determinar la version: se usa la actual.')
        return

    # Buscar cambios en el servidor (acá se necesita internet)
    print('  Buscando actualizaciones...')
    ok, _ = _git('fetch', '--quiet', timeout=30)
    if not ok:
        print('  [i] Sin internet o sin acceso: se usa la version que ya tenes.')
        return

    # Aplicar la última versión sin riesgo de conflictos.
    # Los datos del usuario (facturas.xlsx, token.json, credentials.json) están
    # en .gitignore, así que esto NO los toca.
    ok, _ = _git('reset', '--hard', '--quiet', f'origin/{rama}', timeout=30)
    if ok:
        print('  Version actualizada a la ultima.')
    else:
        print('  [i] No pude actualizar: se usa la version que ya tenes.')


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        # Pase lo que pase, nunca frenar el arranque de la app.
        print(f'  [i] No se pudo verificar actualizaciones ({e}). Se abre igual.')
    sys.exit(0)
