from pathlib import Path

BASE_DIR = Path(__file__).parent

CUIT_NAIMAN = '33708955499'
LABEL_PROCESADO = 'Procesado'

EXCEL_FACTURAS   = BASE_DIR / 'facturas.xlsx'
EXCEL_PROVEEDORES = BASE_DIR / 'proveedores.xlsx'
JSON_ESTADO      = BASE_DIR / 'estado.json'
CREDENTIALS_FILE = BASE_DIR / 'credentials.json'
TOKEN_FILE       = BASE_DIR / 'token.json'

GMAIL_SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

# Columnas del Excel (1-indexed, mismo orden que el Apps Script original)
COLS = {
    'TIPO_COMPROBANTE': 1,    # A
    'TIPO_NUMERO':      2,    # B
    'NUMERO':           3,    # C
    'PUNTO_VENTA':      4,    # D
    'FECHA':            5,    # E
    'DENOMINACION':     6,    # F
    'CUIT':             7,    # G
    'NETO':             8,    # H
    'IVA':              9,    # I
    'KILOS':           15,    # O
    'PRECIO_UNITARIO': 16,    # P
    'MONOTRIBUTISTA':  17,    # Q
    'TOTAL':           19,    # S
    'TASA':            20,    # T
    'GASTO':           21,    # U
    'RUBRO':           22,    # V
    'MES_IMPUTACION':  23,    # W
    'ANIO_IMPUTACION': 24,    # X
    'CODIGO_OPERACION':25,    # Y
    'POSICION':        26,    # Z
    'DESCRIPCION_GASTO':28,   # AB
    'DESCRIPCION_RUBRO':29,   # AC
    'NOMBRE_ADJUNTO':  30,    # AD
    'CLAVE_COMPROBANTE':31,   # AE
}

NUM_COLS = 31
