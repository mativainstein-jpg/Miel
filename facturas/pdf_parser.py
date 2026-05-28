import io
import re
import pdfplumber
from config import CUIT_NAIMAN, COLS


# ---------------------------------------------------------------------------
# Extracción de texto
# ---------------------------------------------------------------------------

def extraer_texto(pdf_bytes):
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        paginas = [p.extract_text() or '' for p in pdf.pages]
    return '\n'.join(paginas)


def es_texto_valido(texto):
    return bool(texto) and len(texto) > 100 and bool(re.search(r'COD\.\s*0*1', texto, re.I))


# ---------------------------------------------------------------------------
# Parser principal
# ---------------------------------------------------------------------------

def parsear_factura(texto, nombre_adjunto, indice_proveedores=None):
    tipo = _detectar_tipo(texto)
    linea = _extraer_linea_producto(texto)

    numero     = _campo(texto, r'Comp\.\s*Nro:\s*0*(\d+)')
    punto_venta = _campo(texto, r'Punto\s*de\s*Venta:\s*0*(\d+)')
    fecha      = _campo(texto, r'Fecha\s*de\s*Emisi[oó]n:\s*(\d{2}/\d{2}/\d{4})')

    denominacion_pdf = _extraer_denominacion(texto)
    cuit             = _extraer_cuit_emisor(texto)
    denominacion     = _resolver_denominacion(cuit, denominacion_pdf, indice_proveedores)

    neto     = _campo(texto, r'Importe\s*Neto\s*Gravado:\s*\$?\s*([\d.,]+)')
    subtotal = _campo(texto, r'Subtotal:\s*\$?\s*([\d.,]+)') or _subtotal_linea(linea)

    iva105 = _campo(texto, r'IVA\s*10[.,]5%\s*(?::)?\s*\$?\s*([\d.,]+)')
    iva21  = _campo(texto, r'IVA\s*21%\s*(?::)?\s*\$?\s*([\d.,]+)')
    iva27  = _campo(texto, r'IVA\s*27%\s*(?::)?\s*\$?\s*([\d.,]+)')
    otros  = _campo(texto, r'Importe\s*de\s*Otros\s*Tributos:\s*\$?\s*([\d.,]+)')

    total = _campo(texto, r'Importe\s*Total(?:\s*del\s*Comprobante)?:\s*\$?\s*([\d.,]+)')
    if not total and tipo == 'FCC':
        total = _subtotal_linea(linea)

    kilos          = _kilos_linea(linea)
    precio_raw     = _precio_unitario_linea(linea) or _campo(texto, r'Precio\s*Unit\.?\s*([\d.,]+)')

    kilos_num   = _num(kilos)
    neto_num    = _num(neto)
    subtotal_num = _num(subtotal)
    iva_num     = _num(iva105) + _num(iva21) + _num(iva27)
    total_num   = _num(total)
    precio_num  = _num(precio_raw)

    if precio_num > 0:
        precio_unitario_num = precio_num
    elif tipo == 'FCC' and kilos_num > 0 and subtotal_num > 0:
        precio_unitario_num = subtotal_num / kilos_num
    elif tipo == 'FCA' and kilos_num > 0 and neto_num > 0:
        precio_unitario_num = neto_num / kilos_num
    else:
        precio_unitario_num = 0

    partes_fecha = fecha.split('/') if fecha else []
    mes  = int(partes_fecha[1]) if len(partes_fecha) > 1 else None
    anio = int(partes_fecha[2]) if len(partes_fecha) > 2 else None

    posicion      = 'RM' if tipo == 'FCC' else ('RI' if tipo == 'FCA' else '')
    monotributista = 'SI' if tipo == 'FCC' else ''

    clave = '|'.join([
        tipo or 'SIN_TIPO',
        cuit or 'SIN_CUIT',
        punto_venta or 'SIN_PV',
        numero or 'SIN_NUMERO',
    ])

    return {
        'tipo':              tipo,
        'tipo_numero':       4,
        'numero':            numero,
        'punto_venta':       punto_venta,
        'fecha':             fecha,
        'denominacion':      denominacion,
        'cuit':              cuit,
        'neto_num':          0 if tipo == 'FCC' else neto_num,
        'iva_num':           0 if tipo == 'FCC' else iva_num,
        'otros_tributos_num': _num(otros),
        'kilos_num':         kilos_num,
        'precio_unitario_num': precio_unitario_num,
        'monotributista':    monotributista,
        'total_num':         total_num,
        'tasa':              0,
        'gasto':             4,
        'rubro':             6,
        'mes':               mes,
        'anio':              anio,
        'codigo_operacion':  '',
        'posicion':          posicion,
        'descripcion_gasto': 'miel',
        'descripcion_rubro': 'mercaderia',
        'nombre_adjunto':    nombre_adjunto,
        'clave':             clave,
    }


# ---------------------------------------------------------------------------
# Helpers de extracción
# ---------------------------------------------------------------------------

def _detectar_tipo(texto):
    if re.search(r'COD\.\s*0*11', texto, re.I):   return 'FCC'
    if re.search(r'COD\.\s*0*1(?!1)', texto, re.I): return 'FCA'
    return ''


def _extraer_linea_producto(texto):
    for linea in texto.splitlines():
        linea = linea.strip()

        m = re.match(
            r'(.+?)\s+([\d.,]+)\s+(kg|kilos|unidad|unidades)'
            r'\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)%\s+([\d.,]+)',
            linea, re.I
        )
        if m:
            return {
                'descripcion':   m.group(1).strip(),
                'cantidad':      m.group(2),
                'unidad':        m.group(3).lower(),
                'precio_unitario': m.group(4),
                'subtotal':      m.group(6),
            }

        m = re.match(
            r'(.+?)\s+([\d.,]+)\s+(kg|kilos|unidad|unidades)'
            r'\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)',
            linea, re.I
        )
        if m:
            return {
                'descripcion':   m.group(1).strip(),
                'cantidad':      m.group(2),
                'unidad':        m.group(3).lower(),
                'precio_unitario': m.group(4),
                'subtotal':      m.group(7),
            }

    return None


def _kilos_linea(linea):
    if not linea:
        return ''
    return linea['cantidad'] if linea['unidad'] in ('kg', 'kilos', 'unidad', 'unidades') else ''


def _precio_unitario_linea(linea):
    return linea['precio_unitario'] if linea else ''


def _subtotal_linea(linea):
    return linea['subtotal'] if linea else ''


def _extraer_denominacion(texto):
    m = re.search(r'Raz[oó]n\s*Social:\s*([A-ZÁÉÍÓÚÑ0-9 .,\-]+)', texto, re.I)
    if m:
        return _limpiar_texto(m.group(1))

    lineas = [l.strip() for l in texto.splitlines() if l.strip()]
    for i, linea in enumerate(lineas):
        if re.match(r'^(ORIGINAL|DUPLICADO|TRIPLICADO)$', linea, re.I):
            nombre = lineas[i + 1] if i + 1 < len(lineas) else ''
            siguiente = lineas[i + 2] if i + 2 < len(lineas) else ''
            if siguiente and not re.match(
                r'^\d|CUIT|Condici[oó]n|Domicilio|Contado|Cuenta|Entre R[ií]os|Santa Fe|Buenos Aires',
                siguiente, re.I
            ):
                nombre += ' ' + siguiente
            return _limpiar_texto(nombre)

    return ''


def _extraer_cuit_emisor(texto):
    for m in re.finditer(r'\b\d{2}-\d{8}-\d\b', texto):
        limpio = re.sub(r'\D', '', m.group())
        if limpio != CUIT_NAIMAN:
            return _normalizar_cuit(limpio)

    for m in re.finditer(r'\b\d{11}\b', texto):
        if m.group() != CUIT_NAIMAN:
            return _normalizar_cuit(m.group())

    return ''


def _resolver_denominacion(cuit, denominacion_pdf, indice):
    if indice and cuit:
        cuit_limpio = re.sub(r'\D', '', cuit)
        den = indice.get(cuit_limpio)
        if den:
            return den
    return denominacion_pdf or ''


def _campo(texto, patron):
    m = re.search(patron, texto, re.I)
    return m.group(1).strip() if m else ''


def _num(s):
    if not s:
        return 0.0
    s = str(s).replace(' ', '').replace('$', '').strip()
    if not s:
        return 0.0

    if '.' in s and ',' in s:
        s = s.replace('.', '').replace(',', '.')
    elif ',' in s:
        s = s.replace(',', '.')
    elif '.' in s:
        partes = s.split('.')
        if len(partes) > 2 or len(partes[-1]) >= 3:
            s = s.replace('.', '')

    try:
        return float(s)
    except ValueError:
        return 0.0


def _normalizar_cuit(cuit):
    c = re.sub(r'\D', '', str(cuit))
    return f'{c[:2]}-{c[2:10]}-{c[10]}' if len(c) == 11 else cuit


def _limpiar_texto(texto):
    if not texto:
        return ''
    texto = re.sub(r'\s+', ' ', str(texto))
    texto = re.sub(r'CUIT.*',        '', texto, flags=re.I)
    texto = re.sub(r'Condici[oó]n.*','', texto, flags=re.I)
    texto = re.sub(r'Domicilio.*',   '', texto, flags=re.I)
    return texto.strip()
