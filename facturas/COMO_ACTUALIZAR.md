# Cómo se actualiza la app sola (sin volver a descargar)

La idea: **vos hacés los ajustes y los subís; la computadora del administrativo
recibe la última versión sola cada vez que abre la app.** El administrativo
nunca descarga nada a mano.

---

## Instalación por única vez (la hacés vos en la PC del administrativo)

Esto se hace **una sola vez**. Después, el administrativo solo abre `procesar.bat`.

1. **Instalar Python**
   - Descargar de https://www.python.org/downloads/
   - Durante la instalación, **tildar "Add Python to PATH"**.

2. **Instalar Git**
   - Descargar de https://git-scm.com/download/win
   - Instalar con las opciones por defecto (Siguiente → Siguiente).

3. **Descargar la app con Git** (esto es lo que permite las actualizaciones automáticas).
   Abrir la carpeta donde quieras que viva la app, hacer clic derecho →
   "Abrir en Terminal" (o abrir "CMD") y pegar:

   ```
   git clone https://github.com/mativainstein-jpg/miel.git
   ```

   Eso crea una carpeta `miel`. La app está dentro, en `miel\facturas`.

4. **Entrar a `miel\facturas` y hacer doble clic en `primera_vez.bat`.**
   Instala las librerías necesarias. (Solo esta vez.)

5. Si usan Gmail, copiar el archivo `credentials.json` dentro de `miel\facturas`.

Listo. A partir de acá, el administrativo **solo abre `procesar.bat`**.

---

## Uso diario (lo hace el administrativo)

- Doble clic en **`procesar.bat`**.
- Al abrir, si hay internet, busca la última versión sola (2 segundos) y arranca.
- Si no hay internet, abre igual con la última versión que tenía. **No se traba.**

---

## Cuando vos hacés un cambio

1. Hacés el ajuste (acá, conmigo).
2. Se sube al repositorio (push).
3. La próxima vez que el administrativo abra `procesar.bat` **con internet**,
   ya tiene tu cambio. No descarga nada a mano.

> **Nota sobre las ramas:** no te preocupes por esto. Se usa una sola rama
> (la que trae el repo por defecto) y Claude se encarga de probar los cambios
> antes de publicarlos. Vos nunca tenés que mover nada entre ramas.

---

## Preguntas frecuentes

**¿Necesita internet siempre?**
No. Solo para *recibir* tus cambios al abrir. Procesar facturas y escribir el
Excel funciona sin internet. (Gmail sí necesita internet, obviamente.)

**¿Se pierden sus datos al actualizar?**
No. El Excel de facturas, el token de Gmail y el `credentials.json` son propios
de esa PC y la actualización no los toca.

**¿Y si no quiere instalar Git?**
La app funciona igual, pero no se actualiza sola: en ese caso le tenés que pasar
los cambios a mano (o instalás Git después y ya queda automático).
