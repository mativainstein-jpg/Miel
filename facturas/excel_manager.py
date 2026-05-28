import re
from datetime import datetime
import openpyxl
from openpyxl.styles import PatternFill, Font
from config import COLS, NUM_COLS, EXCEL_FACTURAS, EXCEL_PROVEEDORES

_FILL_ROJO  = PatternFill(start_color='FF0000', end_color='FF0000', fill_type='solid')
_FONT_BLANCO = Font(color='FFFFFF', bold=True)


class ExcelManager:
    """Keeps the workbook open for the duration of a processing run."""

    def __init__(self):
        if EXCEL_FACTURAS.exists():
            self.wb = openpyxl.load_workbook(str(EXCEL_FACTURAS))
        else:
            self.wb = openpyxl.Workbook()
            self.wb.active.title = 'FACTURAS'

        self._ensure('FACTURAS')
        self._ensure('DUPLICADAS', ['Fecha', 'Nombre adjunto', 'Clave comprobante', 'Motivo', 'Thread ID'])
        self._ensure('ERRORES',    ['Fecha hora', 'Nombre adjunto', 'Nivel', 'Mensaje'])

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _ensure(self, nombre, headers=None):
        if nombre not in self.wb.sheetnames:
            ws = self.wb.create_sheet(nombre)
            if headers:
                ws.append(headers)

    # ------------------------------------------------------------------
    # Lectura de índices
    # ------------------------------------------------------------------

    def cargar_indice_duplicados(self):
        nombres, claves = set(), set()
        ws = self.wb['FACTURAS']
        for row in ws.iter_rows(min_row=2, values_only=True):
            if len(row) >= COLS['NOMBRE_ADJUNTO']:
                v = row[COLS['NOMBRE_ADJUNTO'] - 1]
                if v:
                    nombres.add(str(v))
            if len(row) >= COLS['CLAVE_COMPROBANTE']:
                v = row[COLS['CLAVE_COMPROBANTE'] - 1]
                if v:
                    claves.add(str(v))
        return {'nombres': nombres, 'claves': claves}

    # ------------------------------------------------------------------
    # Escritura
    # ------------------------------------------------------------------

    def escribir_factura(self, datos):
        fila, cols_verificar = _armar_fila_verificada(datos)
        ws = self.wb['FACTURAS']
        ws.append(fila)

        fila_num = ws.max_row
        for col in cols_verificar:
            cell = ws.cell(row=fila_num, column=col)
            cell.fill = _FILL_ROJO
            cell.font = _FONT_BLANCO

        return cols_verificar

    def registrar_duplicado(self, nombre, clave, motivo, thread_id):
        self.wb['DUPLICADAS'].append([datetime.now(), nombre, clave, motivo, thread_id])

    def registrar_error(self, nombre, mensaje):
        self.wb['ERRORES'].append([datetime.now(), nombre, 'ERROR', mensaje])

    # ------------------------------------------------------------------
    # Persistencia
    # ------------------------------------------------------------------

    def guardar(self):
        self.wb.save(str(EXCEL_FACTURAS))

    def cerrar(self):
        self.wb.close()


# ------------------------------------------------------------------
# Lectura de proveedores (independiente del workbook principal)
# ------------------------------------------------------------------

def cargar_indice_proveedores():
    indice = {}
    if not EXCEL_PROVEEDORES.exists():
        return indice

    wb = openpyxl.load_workbook(str(EXCEL_PROVEEDORES), read_only=True)
    ws = wb.active
    for row in ws.iter_rows(min_row=2, values_only=True):
        if len(row) >= 2 and row[0] and row[1]:
            cuit = re.sub(r'\D', '', str(row[0]))
            den  = str(row[1]).strip()
            if cuit and den:
                indice[cuit] = den
    wb.close()
    return indice


# ------------------------------------------------------------------
# Construcción de fila
# ------------------------------------------------------------------

def _armar_fila_verificada(d):
    fila = [None] * NUM_COLS
    cols_verificar = []

    def set_col(key, valor):
        fila[COLS[key] - 1] = valor

    set_col('TIPO_COMPROBANTE',  d['tipo'])
    set_col('TIPO_NUMERO',       d['tipo_numero'])
    set_col('NUMERO',            d['numero'])
    set_col('PUNTO_VENTA',       d['punto_venta'])
    set_col('FECHA',             d['fecha'])
    set_col('DENOMINACION',      d['denominacion'])
    set_col('CUIT',              d['cuit'])
    set_col('NETO',              d['neto_num'])
    set_col('IVA',               d['iva_num'])
    set_col('KILOS',             d['kilos_num'])
    set_col('PRECIO_UNITARIO',   d['precio_unitario_num'])
    set_col('MONOTRIBUTISTA',    d['monotributista'])
    set_col('TOTAL',             d['total_num'])
    set_col('TASA',              d['tasa'])
    set_col('GASTO',             d['gasto'])
    set_col('RUBRO',             d['rubro'])
    set_col('MES_IMPUTACION',    d['mes'])
    set_col('ANIO_IMPUTACION',   d['anio'])
    set_col('CODIGO_OPERACION',  d['codigo_operacion'])
    set_col('POSICION',          d['posicion'])
    set_col('DESCRIPCION_GASTO', d['descripcion_gasto'])
    set_col('DESCRIPCION_RUBRO', d['descripcion_rubro'])
    set_col('NOMBRE_ADJUNTO',    d['nombre_adjunto'])
    set_col('CLAVE_COMPROBANTE', d['clave'])

    def verificar(key, valor):
        if not valor and valor != 0:
            fila[COLS[key] - 1] = 'VERIFICAR'
            cols_verificar.append(COLS[key])

    verificar('TIPO_COMPROBANTE', d['tipo'])
    verificar('NUMERO',           d['numero'])
    verificar('PUNTO_VENTA',      d['punto_venta'])
    verificar('FECHA',            d['fecha'])
    verificar('DENOMINACION',     d['denominacion'])
    verificar('CUIT',             d['cuit'])

    if not d['kilos_num'] or d['kilos_num'] <= 0:
        fila[COLS['KILOS'] - 1] = 'VERIFICAR'
        cols_verificar.append(COLS['KILOS'])

    if not d['precio_unitario_num'] or d['precio_unitario_num'] <= 0:
        fila[COLS['PRECIO_UNITARIO'] - 1] = 'VERIFICAR'
        cols_verificar.append(COLS['PRECIO_UNITARIO'])

    if not d['total_num'] or d['total_num'] <= 0:
        fila[COLS['TOTAL'] - 1] = 'VERIFICAR'
        cols_verificar.append(COLS['TOTAL'])
    elif d['tipo'] == 'FCA':
        suma = d['neto_num'] + d['iva_num'] + d['otros_tributos_num']
        if abs(d['total_num'] - suma) > 1.0:
            for key in ('NETO', 'IVA', 'TOTAL'):
                fila[COLS[key] - 1] = 'VERIFICAR (Suma)'
                if COLS[key] not in cols_verificar:
                    cols_verificar.append(COLS[key])

    if not d['mes']:
        fila[COLS['MES_IMPUTACION'] - 1] = 'VERIFICAR'
        cols_verificar.append(COLS['MES_IMPUTACION'])

    if not d['anio']:
        fila[COLS['ANIO_IMPUTACION'] - 1] = 'VERIFICAR'
        cols_verificar.append(COLS['ANIO_IMPUTACION'])

    return fila, cols_verificar
