import json
from PyQt5.QtCore import QThread, pyqtSignal
from gmail_client import autenticar, buscar_pdfs_gmail, descargar_adjunto, aplicar_label
from pdf_parser import extraer_texto, es_texto_valido, parsear_factura
from excel_manager import ExcelManager, cargar_indice_proveedores
from config import JSON_ESTADO, LABEL_PROCESADO


class ProcesadorWorker(QThread):
    log       = pyqtSignal(str)
    progreso  = pyqtSignal(int, int)
    terminado = pyqtSignal(dict)
    error_critico = pyqtSignal(str)

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
            self.terminado.emit({'ok': 0, 'duplicados': 0, 'errores': 0})
            return

        indice_proveedores = cargar_indice_proveedores()
        excel = ExcelManager()
        indice_duplicados = excel.cargar_indice_duplicados()

        ok = duplicados = errores = 0
        threads_completos = {}  # thread_id → set of claves del thread procesadas hoy

        try:
            for i, item in enumerate(pendientes):
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

                    datos = parsear_factura(texto, item['filename'], indice_proveedores)

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

        self.terminado.emit({'ok': ok, 'duplicados': duplicados, 'errores': errores})


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
