# Setup — Procesador de Facturas

## 1. Instalar dependencias

```bash
pip install -r requirements.txt
```

## 2. Obtener credenciales de Gmail (una sola vez)

1. Ir a https://console.cloud.google.com/
2. Crear un proyecto nuevo (o usar uno existente)
3. Habilitar la **Gmail API**: APIs y servicios → Biblioteca → buscar "Gmail API" → Habilitar
4. Crear credenciales: APIs y servicios → Credenciales → Crear credenciales → **ID de cliente OAuth 2.0**
   - Tipo de aplicación: **Aplicación de escritorio**
   - Nombre: cualquiera (ej. "Procesador Facturas")
5. Descargar el JSON → renombrarlo a `credentials.json` → copiarlo en esta carpeta (`facturas/`)

## 3. Primera ejecución

Al ejecutar por primera vez, se abre el navegador para autorizar el acceso a Gmail.
Una vez autorizado, se guarda `token.json` y las siguientes ejecuciones son automáticas.

## 4. Archivos generados

| Archivo | Descripción |
|---------|-------------|
| `facturas.xlsx` | Excel con las facturas procesadas (hojas: FACTURAS, DUPLICADAS, ERRORES) |
| `estado.json` | Registro interno de PDFs ya procesados (no borrar) |
| `token.json` | Token de autenticación Gmail (no compartir) |

## 5. Proveedores (opcional)

Para resolver denominaciones desde el CUIT, crear `proveedores.xlsx` en esta carpeta con:
- Columna A: CUIT
- Columna B: Denominación sistema

## 6. Ejecutar

- **Windows**: doble clic en `procesar.bat`
- **Mac/Linux**: `python main.py`
