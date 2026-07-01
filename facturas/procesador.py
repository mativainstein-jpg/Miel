import json
from PyQt5.QtCore import QThread, pyqtSignal
from gmail_client import autenticar, buscar_pdfs_gmail, descargar_adjunto, aplicar_label
from pdf_parser import extraer_texto, es_texto_valido, parsear_factura
from excel_manager import ExcelManager, cargar_indice_proveedores
from config import JSON_ESTADO, LABEL_PROCESADO


class ProcesadorGmailWorker(QThread):
    log       = pyqtSignal(str)
    progreso  = pyqtSignal(int, int)
    terminado = pyqtSignal(dict)
    error_critico = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._cancelado = False

    def cancelar(self):
        self._cancelado = True

    def run(self):
        try:
            self._ejecutar()
        except Exception as e:
            self.error_critico.emit(str(e))

    def _ejecutar(self):
        self.log.emit('Autenticando con Gmail...')
        try:
            service = autenticar()
        except FileNotFoundError as e:
            self.error_critico.emit(str(e))
            return

        self.log.emit('Buscando PDFs en Gmail...')
        todos = buscar_pdfs_gmail(service)

        estado = _cargar_estado()
        pendientes = [p for p in todos if p['clave'] not in estado]

        self.log.emit(f'Total en Gmail: {len(todos)} | Nuevos a procesar: {len(pendientes)}')

        if not pendientes:
            self.terminado.emit({'ok': 0, 'duplicados': 0, 'errores': 0, 'verificar': 0})
            return

        indice_proveedores = cargar_indice_proveedores()
        if not indice_proveedores:
            self.log.emit(
                '  ⚠ No se encontró "proveedores.xlsx" (o está vacío): '
                'Gasto y Rubro quedarán en VERIFICAR para todas las facturas.'
            )
        excel = ExcelManager()
        indice_duplicados = excel.cargar_indice_duplicados()

        ok = duplicados = errores = verificar = 0
        threads_completos = {}  # thread_id → set of claves del thread procesadas hoy

        try:
            for i, item in enumerate(pendientes):
                if self._cancelado:
                    self.log.emit('↩ Cancelado por el usuario.')
                    break

                self.progreso.emit(i + 1, len(pendientes))
                self.log.emit(f'[{i+1}/{len(pendientes)}] {item["filename"]}')

                try:
                    pdf_bytes = descargar_adjunto(service, item['message_id'], item['attachment_id'])
                    texto = extraer_texto(pdf_bytes)

                    if not es_texto_valido(texto):
                        self.log.emit(f'  ⚠ Tipo no reconocido o texto insuficiente')
                        excel.registrar_error(item['filename'], 'Texto PDF insuficiente o tipo no reconocido')
                        estado.add(item['clave'])
                        errores += 1
                        continue

                    datos = parsear_factura(texto, item['filename'], indice_proveedores, pdf_bytes=pdf_bytes)

                    if datos['clave'] in indice_duplicados['claves']:
                        excel.registrar_duplicado(item['filename'], datos['clave'],
                                                  'Duplicado por clave comprobante', item['thread_id'])
                        estado.add(item['clave'])
                        duplicados += 1
                        self.log.emit(f'  ↩ Duplicada: {datos["clave"]}')
                        continue

                    if item['filename'] in indice_duplicados['nombres']:
                        excel.registrar_duplicado(item['filename'], datos['clave'],
                                                  'Duplicado por nombre adjunto', item['thread_id'])
                        estado.add(item['clave'])
                        duplicados += 1
                        self.log.emit(f'  ↩ Duplicada (nombre): {item["filename"]}')
                        continue

                    cols_verificar = excel.escribir_factura(datos)
                    indice_duplicados['nombres'].add(item['filename'])
                    indice_duplicados['claves'].add(datos['clave'])
                    estado.add(item['clave'])
                    ok += 1
                    if cols_verificar:
                        verificar += 1

                    if cols_verificar:
                        self.log.emit(f'  ✓ OK (revisar col. {cols_verificar}): '
                                      f'{datos["tipo"]} PV {datos["punto_venta"]} N° {datos["numero"]}')
                    else:
                        self.log.emit(f'  ✓ OK: {datos["tipo"]} PV {datos["punto_venta"]} N° {datos["numero"]}')

                    tid = item['thread_id']
                    threads_completos.setdefault(tid, set()).add(item['clave'])

                except Exception as e:
                    errores += 1
                    self.log.emit(f'  ✗ Error: {e}')
                    excel.registrar_error(item['filename'], str(e))
                    estado.add(item['clave'])

        finally:
            excel.guardar()
            excel.cerrar()
            _guardar_estado(estado)

        # Aplicar label de Gmail a los threads completamente procesados
        for tid, claves_hoy in threads_completos.items():
            try:
                aplicar_label(service, tid, LABEL_PROCESADO)
            except Exception as e:
                self.log.emit(f'  ⚠ No se pudo aplicar label al thread: {e}')

        self.terminado.emit({'ok': ok, 'duplicados': duplicados,
                             'errores': errores, 'verificar': verificar})


# ---------------------------------------------------------------------------
# Worker para PDFs locales (sin Gmail)
# ---------------------------------------------------------------------------

class ProcesadorLocalWorker(QThread):
    """
    Parses PDFs and emits a `preview` signal with the results.
    Does NOT write to Excel — writing happens on the main thread after
    the user confirms the preview dialog.
    """
    log          = pyqtSignal(str)
    progreso     = pyqtSignal(int, int)
    preview      = pyqtSignal(list)   # list of result dicts
    error_critico = pyqtSignal(str)

    def __init__(self, rutas):
        super().__init__()
        self.rutas = rutas  # list of Path objects
        self._cancelado = False

    def cancelar(self):
        self._cancelado = True

    def run(self):
        try:
            self._ejecutar()
        except Exception as e:
            self.error_critico.emit(str(e))

    def _ejecutar(self):
        indice_proveedores = cargar_indice_proveedores()
        if not indice_proveedores:
            self.log.emit(
                '  ⚠ No se encontró "proveedores.xlsx" (o está vacío): '
                'Gasto y Rubro quedarán en VERIFICAR para todas las facturas.'
            )

        # Read duplicate indices without keeping workbook open
        excel = ExcelManager()
        indice_duplicados = excel.cargar_indice_duplicados()
        excel.cerrar()

        total = len(self.rutas)
        resultados = []

        for i, ruta in enumerate(self.rutas):
            if self._cancelado:
                self.log.emit('↩ Cancelado por el usuario.')
                break

            self.progreso.emit(i + 1, total)
            self.log.emit(f'[{i+1}/{total}] Leyendo {ruta.name}...')

            entry = {
                'ruta':       ruta,
                'filename':   ruta.name,
                'datos':      None,
                'error':      None,
                'dup_clave':  False,
                'dup_nombre': False,
            }
            try:
                pdf_bytes = ruta.read_bytes()
                texto = extraer_texto(pdf_bytes)

                if not es_texto_valido(texto):
                    entry['error'] = 'Texto PDF insuficiente o tipo no reconocido'
                else:
                    dados = parsear_factura(texto, ruta.name, indice_proveedores, pdf_bytes=pdf_bytes)
                    entry['datos']      = dados
                    entry['dup_clave']  = dados['clave'] in indice_duplicados['claves']
                    entry['dup_nombre'] = ruta.name in indice_duplicados['nombres']
            except Exception as e:
                entry['error'] = str(e)

            resultados.append(entry)

        self.preview.emit(resultados)


def escribir_resultados_en_excel(resultados):
    """
    Write pre-parsed results to Excel. Called from the main thread after
    the user confirms the preview dialog.
    Returns {'ok', 'duplicados', 'errores', 'verificar'}.
    'verificar' = cuántas facturas quedaron con algún campo en rojo (VERIFICAR).
    """
    excel = ExcelManager()
    indice_duplicados = excel.cargar_indice_duplicados()

    ok = duplicados = errores = verificar = 0

    try:
        for r in resultados:
            datos = r['datos']

            if r['error']:
                excel.registrar_error(r['filename'], r['error'])
                errores += 1
                continue

            # Re-check duplicates in case the index changed since parsing
            dup_clave  = r['dup_clave']  or datos['clave']    in indice_duplicados['claves']
            dup_nombre = r['dup_nombre'] or r['filename'] in indice_duplicados['nombres']

            if dup_clave or dup_nombre:
                razon = ('Duplicado por clave comprobante' if dup_clave
                         else 'Duplicado por nombre adjunto')
                excel.registrar_duplicado(r['filename'], datos['clave'], razon, '')
                duplicados += 1
                continue

            cols_verificar = excel.escribir_factura(datos)
            if cols_verificar:
                verificar += 1
            indice_duplicados['nombres'].add(r['filename'])
            indice_duplicados['claves'].add(datos['clave'])
            ok += 1

    finally:
        excel.guardar()
        excel.cerrar()

    return {'ok': ok, 'duplicados': duplicados, 'errores': errores, 'verificar': verificar}


# ---------------------------------------------------------------------------
# Estado persistente (JSON)
# ---------------------------------------------------------------------------

def _cargar_estado():
    if JSON_ESTADO.exists():
        with open(str(JSON_ESTADO)) as f:
            return set(json.load(f).get('procesados', []))
    return set()


def _guardar_estado(estado):
    with open(str(JSON_ESTADO), 'w') as f:
        json.dump({'procesados': sorted(estado)}, f, indent=2)
