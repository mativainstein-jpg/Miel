import io
import re
import pdfplumber
from config import CUIT_NAIMAN, COLS, PUNTO_VENTA_FIJO


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

def parsear_factura(texto, nombre_adjunto, indice_proveedores=None, pdf_bytes=None):
    tipo = _detectar_tipo(texto)
    linea = _extraer_linea_producto(texto, pdf_bytes)

    numero      = _campo(texto, r'Comp\.\s*Nro:\s*0*(\d+)')
    punto_venta = PUNTO_VENTA_FIJO
    fecha       = _campo(texto, r'Fecha\s*de\s*Emisi[oó]n:\s*(\d{2}/\d{2}/\d{4})')

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

    # Campos de percepción e impuestos adicionales
    no_gravado     = _campo(texto, r'Importe\s*No\s*Gravado:\s*\$?\s*([\d.,]+)')
    imp_internos   = _campo(texto, r'Impuestos?\s*Internos?:\s*\$?\s*([\d.,]+)')
    exentos        = _campo(texto, r'Importe\s*Exento[s]?:\s*\$?\s*([\d.,]+)')
    perc_iva       = _campo(texto, r'Percepci[oó]n\s*(?:de\s*)?IVA\s*(?:[\d.,]+\s*%)?\s*:?\s*\$?\s*([\d.,]+)')
    perc_iibb      = _campo(texto, r'Percepci[oó]n\s*(?:de\s*)?(?:Ingresos?\s*Brutos?|IIBB)\s*(?:[\d.,]+\s*%)?\s*:?\s*\$?\s*([\d.,]+)')
    perc_ganancias = _campo(texto, r'Percepci[oó]n\s*(?:de\s*)?Ganancias?\s*(?:[\d.,]+\s*%)?\s*:?\s*\$?\s*([\d.,]+)')

    kilos      = _kilos_linea(linea)
    precio_raw = _precio_unitario_linea(linea) or _campo(texto, r'Precio\s*Unit\.?\s+([\d.,]+)')

    # None = no encontrado en el PDF (mostrar VERIFICAR en la UI)
    # 0.0  = encontrado pero es cero (dato real)
    kilos_num    = _num_o_none(kilos)
    neto_num     = _num_o_none(neto) if tipo == 'FCA' else 0.0
    subtotal_num = _num(subtotal)
    iva_num      = (_num(iva105) + _num(iva21) + _num(iva27)) or (None if tipo == 'FCA' else 0.0)
    total_num    = _num_o_none(total)
    precio_num   = _num(precio_raw)

    if precio_num and precio_num > 0:
        precio_unitario_num = precio_num
    elif tipo == 'FCC' and kilos_num and kilos_num > 0 and subtotal_num > 0:
        precio_unitario_num = subtotal_num / kilos_num
    elif tipo == 'FCA' and kilos_num and kilos_num > 0 and neto_num and neto_num > 0:
        precio_unitario_num = neto_num / kilos_num
    else:
        precio_unitario_num = None

    partes_fecha = fecha.split('/') if fecha else []
    mes  = int(partes_fecha[1]) if len(partes_fecha) > 1 else None
    anio = int(partes_fecha[2]) if len(partes_fecha) > 2 else None

    # Cruce con proveedores para gasto / rubro
    prov = None
    if indice_proveedores and cuit:
        cuit_num = re.sub(r'\D', '', cuit)
        prov = indice_proveedores.get(cuit_num)

    gasto      = prov['gasto']      if prov else None
    rubro      = prov['rubro']      if prov else None
    desc_gasto = prov['desc_gasto'] if prov else None
    desc_rubro = prov['desc_rubro'] if prov else None

    posicion       = 'RM' if tipo == 'FCC' else ('RI' if tipo == 'FCA' else '')
    monotributista = 'SI' if tipo == 'FCC' else ''

    clave = '|'.join([
        tipo or 'SIN_TIPO',
        cuit or 'SIN_CUIT',
        punto_venta or 'SIN_PV',
        numero or 'SIN_NUMERO',
    ])

    return {
        'tipo':                    tipo   or None,
        'numero':                  numero or None,
        'punto_venta':             punto_venta,   # default '4' si no se extrae
        'fecha':                   fecha  or None,
        'denominacion':            denominacion or None,
        'cuit':                    cuit   or None,
        'neto_num':                neto_num,
        'iva_num':                 iva_num,
        'otros_tributos_num':      _num_o_none(otros),
        'no_gravado_num':          _num_o_none(no_gravado),
        'imp_internos_num':        _num_o_none(imp_internos),
        'exentos_num':             _num_o_none(exentos),
        'percepcion_iva_num':      _num_o_none(perc_iva),
        'percepcion_iibb_num':     _num_o_none(perc_iibb),
        'percepcion_ganancias_num': _num_o_none(perc_ganancias),
        'kilos_num':               kilos_num,
        'precio_unitario_num':     precio_unitario_num,
        'monotributista':          monotributista,
        'total_num':               total_num,
        'tasa':                    0,
        'gasto':                   gasto,
        'rubro':                   rubro,
        'mes':                     mes,
        'anio':                    anio,
        'codigo_operacion':        '',
        'posicion':                posicion,
        'descripcion_gasto':       desc_gasto,
        'descripcion_rubro':       desc_rubro,
        'nombre_adjunto':          nombre_adjunto,
        'clave':                   clave,
    }


# ---------------------------------------------------------------------------
# Extracción de línea de producto — cascada de 3 estrategias
# ---------------------------------------------------------------------------

def _extraer_linea_producto(texto, pdf_bytes=None):
    # 1. pdfplumber table extraction (best for structured AFIP tables)
    if pdf_bytes:
        result = _extraer_de_tablas(pdf_bytes)
        if result:
            return result

    # 2. Single-line regex (works when pdfplumber reconstructs row layout)
    result = _extraer_linea_single(texto)
    if result:
        return result

    # 3. Multi-line anchor-based search (fallback for column-per-line layouts)
    return _extraer_multilinea(texto)


def _extraer_de_tablas(pdf_bytes):
    """Use pdfplumber table detection to find the product row."""
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                for table in (page.extract_tables() or []):
                    for row in table:
                        if not row:
                            continue
                        cells = [str(c).strip() if c else '' for c in row]
                        row_str = ' '.join(cells)
                        m = re.search(r'([\d.,]+)\s*(kg|kilos|unidad(?:es)?)', row_str, re.I)
                        if not m:
                            continue
                        cantidad = m.group(1)
                        raw_unit = m.group(2).lower()
                        unidad   = 'kg' if 'kg' in raw_unit or 'kilo' in raw_unit else 'unidades'
                        nums     = re.findall(r'[\d.,]+', row_str)
                        # Last two numbers are typically unit price and line total
                        precio   = nums[-2] if len(nums) >= 3 else (nums[-1] if len(nums) >= 2 else '')
                        subtotal = nums[-1] if len(nums) >= 2 else ''
                        return {
                            'descripcion':     '',
                            'cantidad':        cantidad,
                            'unidad':          unidad,
                            'precio_unitario': precio,
                            'subtotal':        subtotal,
                        }
    except Exception:
        pass
    return None


def _extraer_linea_single(texto):
    """Single-line regex — works when pdfplumber merges table columns into one line."""
    for linea in texto.splitlines():
        linea = linea.strip()

        m = re.match(
            r'(.+?)\s+([\d.,]+)\s+(kg|kilos|unidad(?:es)?)'
            r'\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)%\s+([\d.,]+)',
            linea, re.I
        )
        if m:
            return {
                'descripcion':     m.group(1).strip(),
                'cantidad':        m.group(2),
                'unidad':          m.group(3).lower(),
                'precio_unitario': m.group(4),
                'subtotal':        m.group(6),
            }

        m = re.match(
            r'(.+?)\s+([\d.,]+)\s+(kg|kilos|unidad(?:es)?)'
            r'\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)',
            linea, re.I
        )
        if m:
            return {
                'descripcion':     m.group(1).strip(),
                'cantidad':        m.group(2),
                'unidad':          m.group(3).lower(),
                'precio_unitario': m.group(4),
                'subtotal':        m.group(7),
            }

    return None


def _extraer_multilinea(texto):
    """
    Anchor-based fallback for PDFs where each table column appears on its own line.

    Uses "Precio Unit." as anchor:
      - scan BACKWARD → first standalone number = quantity
      - scan FORWARD  → first standalone number = unit price

    This handles both orderings found in the wild:
      Layout A: quantity … "Precio Unit." … price  (BUZZATTO / ALASINO)
      Layout B: quantity   "Precio Unit."   price   (LEFFLER)
    """
    lineas = [l.strip() for l in texto.splitlines()]

    precio_unitario   = ''
    cantidad          = ''
    unidad_encontrada = 'kg'

    # Find "Precio Unit." line
    precio_idx = -1
    for i, linea in enumerate(lineas):
        m = re.match(r'^Precio\s*Unit\.?\s*([\d.,]+)?$', linea, re.I)
        if m:
            precio_idx = i
            if m.group(1):
                precio_unitario = m.group(1)
            break

    if precio_idx < 0:
        return None

    # Scan backward for quantity (skip labels, take first standalone number)
    for j in range(precio_idx - 1, max(precio_idx - 15, -1), -1):
        cand = lineas[j]
        if re.match(r'^[\d.,]+$', cand) and _num(cand) > 0:
            cantidad = cand
            break

    # Scan forward for price if not already on the same line
    if not precio_unitario:
        for j in range(precio_idx + 1, min(precio_idx + 8, len(lineas))):
            if re.match(r'^[\d.,]+$', lineas[j]) and _num(lineas[j]) > 0:
                precio_unitario = lineas[j]
                break

    # Detect unit (scan nearby lines for kg / unidades)
    search_start = max(0, precio_idx - 15)
    search_end   = min(len(lineas), precio_idx + 10)
    for linea in lineas[search_start:search_end]:
        if re.match(r'^(kg|kilos)$', linea, re.I):
            unidad_encontrada = 'kg'
            break
        if re.match(r'^unidad(?:es)?$', linea, re.I):
            unidad_encontrada = 'unidades'
            break
        m = re.search(r'([\d.,]+)\s+(kg|kilos|unidad(?:es)?)', linea, re.I)
        if m:
            raw = m.group(2).lower()
            unidad_encontrada = 'kg' if 'kg' in raw or 'kilo' in raw else 'unidades'
            if not cantidad:
                cantidad = m.group(1)
            break

    if not cantidad and not precio_unitario:
        return None

    return {
        'descripcion':     '',
        'cantidad':        cantidad,
        'unidad':          unidad_encontrada,
        'precio_unitario': precio_unitario,
        'subtotal':        '',
    }


# ---------------------------------------------------------------------------
# Helpers secundarios
# ---------------------------------------------------------------------------

def _kilos_linea(linea):
    if not linea:
        return ''
    return linea['cantidad'] if linea['unidad'] in ('kg', 'kilos', 'unidad', 'unidades') else ''


def _precio_unitario_linea(linea):
    return linea['precio_unitario'] if linea else ''


def _subtotal_linea(linea):
    return linea['subtotal'] if linea else ''


def _detectar_tipo(texto):
    if re.search(r'COD\.\s*0*11', texto, re.I):      return 'FCC'
    if re.search(r'COD\.\s*0*1(?!1)', texto, re.I):  return 'FCA'
    return ''


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
    # El índice de proveedores ya no contiene denominación → usar siempre el PDF
    return denominacion_pdf or ''


def _campo(texto, patron):
    m = re.search(patron, texto, re.I)
    return m.group(1).strip() if m else ''


def _num_o_none(s):
    """Like _num() but returns None when the string is absent/empty."""
    if not s or str(s).strip() == '':
        return None
    return _num(s)


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
    # Cortar en cualquier campo AFIP que aparezca pegado al nombre
    texto = re.sub(r'\s*Fecha\s*de\s*Emisi[oó]n.*', '', texto, flags=re.I)
    texto = re.sub(r'\s*CUIT.*',                     '', texto, flags=re.I)
    texto = re.sub(r'\s*Condici[oó]n.*',             '', texto, flags=re.I)
    texto = re.sub(r'\s*Domicilio.*',                '', texto, flags=re.I)
    texto = re.sub(r'\s*Punto\s*de\s*Venta.*',       '', texto, flags=re.I)
    return texto.strip()
