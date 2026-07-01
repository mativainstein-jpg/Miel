import os
import subprocess
import sys
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QProgressBar,
    QPushButton, QTextEdit, QVBoxLayout, QWidget,
)

from config import EXCEL_FACTURAS
from procesador import (
    ProcesadorGmailWorker, ProcesadorLocalWorker, escribir_resultados_en_excel,
)
from reconciliacion import ReconciliacionDialog


class VentanaFacturas(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Procesador de Facturas')
        self.setGeometry(100, 100, 660, 560)
        self.worker = None
        self._procesando = False
        self._init_ui()
        self._log('Listo para trabajar. Empezá con "Insertar Factura".')

    def _init_ui(self):
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)
        widget.setLayout(layout)
        self.setCentralWidget(widget)

        titulo = QLabel('Procesador de Facturas')
        titulo.setFont(QFont('Arial', 13, QFont.Bold))
        titulo.setAlignment(Qt.AlignCenter)
        layout.addWidget(titulo)

        # Instrucciones simples, siempre visibles arriba
        ayuda = QLabel(
            'Paso 1: apretá "Insertar Factura" y elegí uno o varios PDF.\n'
            'Paso 2: revisá los datos de cada factura y confirmá.\n'
            'Paso 3: se guardan en el Excel. Las celdas en ROJO hay que revisarlas a mano.'
        )
        ayuda.setStyleSheet(
            'background: #eef4ff; color: #244; padding: 8px; border-radius: 4px;'
        )
        ayuda.setWordWrap(True)
        layout.addWidget(ayuda)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont('Courier New', 9))
        layout.addWidget(self.log_text)

        self.barra = QProgressBar()
        self.barra.setVisible(False)
        layout.addWidget(self.barra)

        self.btn_cancelar = QPushButton('✕  Cancelar')
        self.btn_cancelar.setVisible(False)
        self.btn_cancelar.clicked.connect(self._cancelar_worker)
        layout.addWidget(self.btn_cancelar)

        botones = QHBoxLayout()

        self.btn_gmail = QPushButton('📧  Buscar en Gmail')
        self.btn_gmail.setMinimumHeight(38)
        self.btn_gmail.setFont(QFont('Arial', 10))
        self.btn_gmail.setToolTip(
            'Busca PDFs nuevos en Gmail, los procesa y etiqueta los ya procesados'
        )
        self.btn_gmail.clicked.connect(self._procesar_gmail)
        botones.addWidget(self.btn_gmail)

        self.btn_local = QPushButton('📄  Insertar Factura')
        self.btn_local.setMinimumHeight(38)
        self.btn_local.setFont(QFont('Arial', 10))
        self.btn_local.setToolTip('Seleccioná uno o más PDFs locales para procesar')
        self.btn_local.clicked.connect(self._insertar_local)
        botones.addWidget(self.btn_local)

        self.btn_excel = QPushButton('📊  Abrir Excel')
        self.btn_excel.setMinimumHeight(38)
        self.btn_excel.setFont(QFont('Arial', 10))
        self.btn_excel.clicked.connect(self._abrir_excel)
        botones.addWidget(self.btn_excel)

        btn_salir = QPushButton('Salir')
        btn_salir.setMinimumHeight(38)
        btn_salir.clicked.connect(self.close)
        botones.addWidget(btn_salir)

        layout.addLayout(botones)
        self.show()

    # ------------------------------------------------------------------

    def _bloquear(self):
        self._procesando = True
        self.btn_gmail.setEnabled(False)
        self.btn_local.setEnabled(False)
        self.barra.setValue(0)
        self.barra.setVisible(True)
        self.btn_cancelar.setEnabled(True)
        self.btn_cancelar.setVisible(True)
        self._log('─' * 55)

    def _desbloquear(self):
        self._procesando = False
        self.btn_gmail.setEnabled(True)
        self.btn_local.setEnabled(True)
        self.barra.setVisible(False)
        self.btn_cancelar.setVisible(False)

    def _cancelar_worker(self):
        if self.worker is not None:
            self.worker.cancelar()
            self.btn_cancelar.setEnabled(False)
            self._log('… cancelando (termina la factura en curso)…')

    # ------------------------------------------------------------------
    # Gmail — procesa y escribe directamente (batch sin conciliación)
    # ------------------------------------------------------------------

    def _procesar_gmail(self):
        self._bloquear()
        self.worker = ProcesadorGmailWorker()
        self.worker.log.connect(self._log)
        self.worker.progreso.connect(self._progreso)
        self.worker.terminado.connect(self._finalizado)
        self.worker.error_critico.connect(self._error_critico)
        self.worker.start()

    # ------------------------------------------------------------------
    # Local — parsea → conciliación factura por factura → escribe
    # ------------------------------------------------------------------

    def _insertar_local(self):
        rutas, _ = QFileDialog.getOpenFileNames(
            self, 'Seleccionar facturas PDF', '', 'Archivos PDF (*.pdf)'
        )
        if not rutas:
            return

        self._bloquear()
        self.worker = ProcesadorLocalWorker([Path(r) for r in rutas])
        self.worker.log.connect(self._log)
        self.worker.progreso.connect(self._progreso)
        self.worker.preview.connect(self._abrir_conciliacion)
        self.worker.error_critico.connect(self._error_critico)
        self.worker.start()

    def _abrir_conciliacion(self, resultados):
        self._desbloquear()
        n_parseable = sum(1 for r in resultados if r['datos'] and not r['error'])
        if n_parseable == 0:
            self._log('✗ No se pudo leer ninguna factura.')
            QMessageBox.warning(
                self,
                'No se pudo leer ninguna factura',
                'Ninguno de los archivos elegidos pudo procesarse.\n\n'
                'Puede pasar si:\n'
                '  • el PDF es una foto o imagen escaneada (no texto),\n'
                '  • no es una factura A o C de AFIP,\n'
                '  • el archivo está dañado.\n\n'
                'Probá con otro archivo o revisá que sea el PDF correcto.'
            )
            return

        dlg = ReconciliacionDialog(resultados, self)
        if dlg.exec_() == ReconciliacionDialog.Accepted:
            self._escribir(dlg.resultados_para_escribir())
        else:
            self._log('↩ Revisión cancelada. No se guardó nada.')

    def _escribir(self, resultados):
        # Reintenta sin perder la revisión ya hecha (caso típico: Excel abierto)
        while True:
            self._log('Guardando en Excel...')
            try:
                resumen = escribir_resultados_en_excel(resultados)
                self._finalizado(resumen)
                return
            except PermissionError as e:
                resp = QMessageBox.warning(
                    self, 'El Excel está abierto',
                    f'{e}\n\n'
                    'Cerrá el Excel y apretá "Reintentar". '
                    'No perdés lo que ya revisaste.',
                    QMessageBox.Retry | QMessageBox.Cancel, QMessageBox.Retry
                )
                if resp != QMessageBox.Retry:
                    self._log('↩ Guardado cancelado. La revisión no se guardó.')
                    return
            except Exception as e:
                self._error_critico(str(e))
                return

    # ------------------------------------------------------------------

    def _log(self, mensaje):
        self.log_text.append(mensaje)
        sb = self.log_text.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _progreso(self, actual, total):
        self.barra.setMaximum(total)
        self.barra.setValue(actual)

    def _finalizado(self, resumen):
        self._desbloquear()
        ok         = resumen.get('ok', 0)
        duplicados = resumen.get('duplicados', 0)
        errores    = resumen.get('errores', 0)
        verificar  = resumen.get('verificar', 0)

        self._log('─' * 55)
        self._log(
            f'✅  Listo — Guardadas: {ok}  |  '
            f'Repetidas: {duplicados}  |  '
            f'Con problemas: {errores}  |  '
            f'A revisar (rojo): {verificar}'
        )

        # Resumen en un cartel, en palabras simples
        partes = [f'Se guardaron {ok} factura(s) en el Excel.']
        if verificar:
            partes.append(
                f'\n⚠ {verificar} tienen celdas en ROJO que hay que revisar y '
                'completar a mano dentro del Excel.'
            )
        if duplicados:
            partes.append(f'\n{duplicados} ya estaban cargadas y se saltearon.')
        if errores:
            partes.append(
                f'\n{errores} no se pudieron leer (mirá la hoja "ERRORES" del Excel).'
            )

        if ok == 0 and duplicados == 0 and errores == 0:
            QMessageBox.information(self, 'Terminado', 'No había facturas nuevas para cargar.')
            return

        mensaje = ' '.join(partes)
        caja = QMessageBox(self)
        caja.setIcon(QMessageBox.Information)
        caja.setWindowTitle('Terminado')
        caja.setText(mensaje)
        if ok > 0:
            btn_abrir = caja.addButton('Abrir Excel', QMessageBox.AcceptRole)
            caja.addButton('Cerrar', QMessageBox.RejectRole)
            caja.exec_()
            if caja.clickedButton() == btn_abrir:
                self._abrir_excel()
        else:
            caja.exec_()

    def _error_critico(self, mensaje):
        self._desbloquear()
        self._log(f'❌  {mensaje}')
        QMessageBox.critical(
            self,
            'No se pudo completar',
            f'{mensaje}\n\nCuando lo soluciones, volvé a intentarlo.'
        )

    def _abrir_excel(self):
        if not EXCEL_FACTURAS.exists():
            QMessageBox.information(
                self, 'Todavía no hay Excel',
                'Todavía no se cargó ninguna factura, así que el Excel no existe.\n\n'
                'Cargá facturas primero con "Insertar Factura".'
            )
            return

        path = str(EXCEL_FACTURAS)
        try:
            if sys.platform == 'win32':
                os.startfile(path)
            elif sys.platform == 'darwin':
                subprocess.run(['open', path])
            else:
                subprocess.run(['xdg-open', path])
        except Exception:
            QMessageBox.information(
                self, 'Abrí el Excel a mano',
                'No pude abrir el Excel automáticamente.\n\n'
                f'Está guardado en:\n{path}'
            )

    def closeEvent(self, event):
        # Evitar que cierre a mitad de un proceso y deje el Excel a medias
        if self._procesando:
            resp = QMessageBox.question(
                self, 'Hay un proceso en curso',
                'Se están procesando facturas en este momento.\n\n'
                '¿Seguro que querés cerrar? Se puede perder lo que falta cargar.',
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if resp != QMessageBox.Yes:
                event.ignore()
                return
            if self.worker is not None:
                self.worker.cancelar()
                self.worker.wait(3000)
        event.accept()
