import sys
from pathlib import Path

# Cuando corre como .exe (PyInstaller frozen), los archivos de datos
# van junto al ejecutable, no dentro del bundle comprimido.
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

CUIT_NAIMAN = '33708955499'
PUNTO_VENTA_FIJO = '4'   # todas las facturas se cargan con este punto de venta
LABEL_PROCESADO = 'Procesado'

EXCEL_FACTURAS   = BASE_DIR / 'facturas.xlsx'
EXCEL_PROVEEDORES = BASE_DIR / 'proveedores.xlsx'
JSON_ESTADO      = BASE_DIR / 'estado.json'
CREDENTIALS_FILE = BASE_DIR / 'credentials.json'
TOKEN_FILE       = BASE_DIR / 'token.json'

GMAIL_SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

# Columnas del Excel (1-indexed), coinciden con Registro_de_facturas.xlsx
COLS = {
    'DA':                    1,   # A  - fecha/hora de procesamiento
    'TIPO_COMPROBANTE':      2,   # B  - Tipo
    'NUMERO':                3,   # C  - Número Desde
    'PUNTO_VENTA':           4,   # D  - Punto de Venta
    'FECHA':                 5,   # E  - Fecha
    'DENOMINACION':          6,   # F  - Denominación
    'CUIT':                  7,   # G  - CUIT
    'NETO':                  8,   # H  - Neto gravado
    'IVA':                   9,   # I  - Iva
    'NO_GRAVADO':           10,   # J  - No gravado
    'IMP_INTERNOS':         11,   # K  - Imp. Internos
    'EXENTOS':              12,   # L  - Exentos
    'PERCEPCION_IVA':       13,   # M  - Percepción IVA
    'PERCEPCION_IIBB':      14,   # N  - Percepción IIBB
    'KILOS':                15,   # O  - Kilos
    'PRECIO_UNITARIO':      16,   # P  - Precio unitario
    'MONOTRIBUTISTA':       17,   # Q  - Monotributista
    'PERCEPCION_GANANCIAS': 18,   # R  - Percepción Ganancias
    'TOTAL':                19,   # S  - Total
    'TASA':                 20,   # T  - Tasa
    'GASTO':                21,   # U  - Gasto
    'RUBRO':                22,   # V  - Rubro
    'MES_IMPUTACION':       23,   # W  - Mes de imputación
    'ANIO_IMPUTACION':      24,   # X  - Año imputación
    'CODIGO_OPERACION':     25,   # Y  - Código de operación
    'POSICION':             26,   # Z  - Posición
    #                       27    # AA (vacío)
    'DESCRIPCION_GASTO':    28,   # AB - Descripción gasto
    'DESCRIPCION_RUBRO':    29,   # AC - Descripción rubro
    #                       30    # AD (vacío)
    'ESTADO':               31,   # AE - Estado
    'HORA_ESTADO':          32,   # AF - Estado (hora)
    'ERROR_GENERAL':        33,   # AG - Error general
    # Columnas ocultas — no tienen encabezado, solo para control de duplicados
    'NOMBRE_ADJUNTO':       34,   # AH
    'CLAVE_COMPROBANTE':    35,   # AI
}

NUM_COLS = 35

# Encabezados visibles de la hoja FACTURAS (cols 1-33, None = columna vacía)
HEADERS_FACTURAS = [
    'Da', 'Tipo', 'Número Desde', 'Punto de Venta', 'Fecha',
    'Denominación', 'CUIT', 'Neto gravado', 'Iva', 'No gravado',
    'Imp. Internos', 'Exentos', 'Percepción IVA', 'Percepción IIBB',
    'Kilos', 'Precio unitario', 'Monotributista', 'Percepción Ganancias',
    'Total', 'Tasa', 'Gasto', 'Rubro', 'Mes de imputación', 'Año imputación',
    'Código de operación', 'Posición', None, 'Descripción gasto',
    'Descripción rubro', None, 'Estado', 'Estado', 'Error general. Revisar hoja ERRORES.',
]
