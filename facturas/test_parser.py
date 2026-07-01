#!/usr/bin/env python3
"""
Prueba el parser sobre PDFs locales sin escribir nada en Excel.

Uso:
    python test_parser.py factura1.pdf [factura2.pdf ...]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from pdf_parser import extraer_texto, es_texto_valido, parsear_factura
from excel_manager import cargar_indice_proveedores

_CAMPOS = [
    ('tipo',                'Tipo comprobante'),
    ('punto_venta',         'Punto de venta'),
    ('numero',              'Número'),
    ('fecha',               'Fecha'),
    ('denominacion',        'Denominación'),
    ('cuit',                'CUIT'),
    ('neto_num',            'Neto gravado'),
    ('iva_num',             'IVA'),
    ('otros_tributos_num',  'Otros tributos'),
    ('kilos_num',           'Kilos / Cantidad'),
    ('precio_unitario_num', 'Precio unitario'),
    ('total_num',           'Total'),
    ('monotributista',      'Monotributista'),
    ('posicion',            'Posición'),
    ('mes',                 'Mes'),
    ('anio',                'Año'),
    ('gasto',               'Gasto (cruce proveedores)'),
    ('descripcion_gasto',   'Descripción gasto'),
    ('rubro',               'Rubro (cruce proveedores)'),
    ('descripcion_rubro',   'Descripción rubro'),
    ('clave',               'Clave comprobante'),
]

# Campos críticos que se marcan con ⚠ si están vacíos
_CRITICOS = {
    'tipo', 'denominacion', 'cuit', 'fecha', 'neto_num', 'iva_num',
    'kilos_num', 'precio_unitario_num', 'total_num', 'gasto', 'rubro',
}


def _fmt(val):
    if val is None or val == '':
        return '—'
    if isinstance(val, float):
        return f'{val:,.2f}'
    return str(val)


def analizar(ruta: Path, indice_proveedores: dict):
    print(f'\n{"─" * 64}')
    print(f'  {ruta.name}')
    print(f'{"─" * 64}')

    try:
        pdf_bytes = ruta.read_bytes()
    except Exception as e:
        print(f'  ✗ No se pudo leer el archivo: {e}')
        return

    try:
        texto = extraer_texto(pdf_bytes)
    except Exception as e:
        print(f'  ✗ Error extrayendo texto del PDF: {e}')
        return

    if not es_texto_valido(texto):
        print('  ⚠  Texto insuficiente o tipo de comprobante no reconocido.')
        print('     (El PDF puede ser imagen escaneada o no ser una factura AFIP)')
        return

    try:
        datos = parsear_factura(texto, ruta.name, indice_proveedores, pdf_bytes=pdf_bytes)
    except Exception as e:
        print(f'  ✗ Error al parsear: {e}')
        return

    n_problemas = 0
    for key, label in _CAMPOS:
        val = datos.get(key)
        texto_val = _fmt(val)
        # None/'' = no encontrado (VERIFICAR). 0.0 es un valor real (ej. IVA de un
        # monotributista), no "vacío" — misma semántica que excel_manager/reconciliacion.
        vacio = val is None or val == ''
        critico = key in _CRITICOS and vacio
        marca = '  ⚠' if critico else ''
        if critico:
            n_problemas += 1
        print(f'  {label:<22} {texto_val}{marca}')

    print()
    if n_problemas == 0:
        print('  ✅  Todos los campos críticos OK')
    else:
        print(f'  ⚠   {n_problemas} campo(s) crítico(s) sin valor — se marcarán VERIFICAR en Excel')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    rutas = [Path(a) for a in sys.argv[1:]]
    faltantes = [r for r in rutas if not r.exists()]
    if faltantes:
        for r in faltantes:
            print(f'Archivo no encontrado: {r}')
        sys.exit(1)

    try:
        indice_proveedores = cargar_indice_proveedores()
        if indice_proveedores:
            print(f'Índice de proveedores cargado: {len(indice_proveedores)} entradas')
    except Exception:
        indice_proveedores = {}

    for ruta in rutas:
        analizar(ruta, indice_proveedores)

    print(f'\n{"─" * 64}')
    print(f'  {len(rutas)} PDF(s) analizados')
    print(f'{"─" * 64}\n')
