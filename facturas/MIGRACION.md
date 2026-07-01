# INSTRUCCIONES DE MIGRACIÓN — para Claude en el repo "Facturas"

> Este archivo es una guía para Claude Code cuando se abra una sesión en el
> repositorio nuevo **Facturas** (importado desde "Miel"). El usuario NO es
> programador: hacé vos todos los pasos de git y confirmá al final en palabras
> simples. Cuando termines, **borrá este archivo**.

## Contexto
El repo "Facturas" se creó importando el repo "Miel". Por eso trae, además de la
app de facturas (en la carpeta `facturas/`), cosas de OTRO proyecto que NO van:
un solver de optimización y planillas sueltas. Hay que dejar un repo limpio con
**solo la app de facturas, en la raíz**.

## Pasos a ejecutar

1. **Mover la app a la raíz**: mover todo el contenido de `facturas/` a la raíz
   del repo. (Todos los `.py`, `.bat`, `.md`, `requirements.txt`, `.spec` y
   `proveedores.xlsx`.)

2. **Borrar lo que NO es de la app** (del otro proyecto):
   - carpeta `Cbc-2.7.5-win64/`
   - carpeta `src/`
   - carpeta `facturas/` (ya vacía tras el paso 1)
   - `bounds.xlsx`
   - `DatosMuestras 200721.xlsx`
   - el `README.md` viejo de la raíz (se reemplaza en el paso 4)
   - este `MIGRACION.md`

3. **Reemplazar `.gitignore`** por este contenido (rutas ya en la raíz):

   ```gitignore
   # Datos propios de cada instalación (NO se versionan)
   facturas.xlsx
   credentials.json
   token.json
   estado.json
   error.log

   # proveedores.xlsx SÍ va en git (configuración compartida)
   !proveedores.xlsx

   # Python / build
   __pycache__/
   *.py[cod]
   build/
   dist/
   *.spec
   !ProcesadorFacturas.spec
   ```

4. **Escribir un `README.md` nuevo** breve: qué es la app (procesador de
   facturas AFIP → Excel), y que las instrucciones de instalación y uso están
   en `COMO_ACTUALIZAR.md`.

5. **Actualizar `COMO_ACTUALIZAR.md`**: cambiar la URL de clonado a la del repo
   nuevo — `https://github.com/mativainstein-jpg/Facturas.git` — y aclarar que
   ahora la app está en la RAÍZ del repo (ya no dentro de una subcarpeta
   `facturas/`). Es decir: tras `git clone`, entrar a la carpeta `Facturas` y
   ahí mismo está `primera_vez.bat` y `procesar.bat`.

6. **Verificar** que `python -m py_compile *.py` no dé errores.
   Nota: `actualizar.py` NO tiene una rama fija — usa la rama actual
   (`git rev-parse --abbrev-ref HEAD`), así que funciona con `master` o `main`.

7. **Commit y push a la rama por defecto del repo** (probablemente `master`).
   Usar una sola rama (el usuario no maneja ramas). Mensaje de commit:
   "Migrar app de facturas a repo propio (raíz)".

8. Confirmar al usuario, en palabras simples, que quedó listo y cómo seguir:
   instalar en la PC del administrativo siguiendo `COMO_ACTUALIZAR.md`.

## Importante
- NO toques los datos del usuario si existieran (`facturas.xlsx`, `token.json`,
  `credentials.json`) — pero en un repo recién importado seguramente no están.
- La app funciona con la app en la raíz porque `config.py` usa
  `BASE_DIR = Path(__file__).parent`. No hace falta cambiar código por la mudanza.
