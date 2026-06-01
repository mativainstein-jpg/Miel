import os
import subprocess
import sys
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout, QHeaderView,
    QLabel, QMainWindow, QProgressBar, QPushButton, QTableWidget,
    QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

from config import EXCEL_FACTURAS
from procesador import (
    ProcesadorGmailWorker, ProcesadorLocalWorker, escribir_resultados_en_excel,
)


# ---------------------------------------------------------------------------
# Diálogo de previsualización
# ---------------------------------------------------------------------------

class DialogoPreview(QDialog):
    """Shows parsed invoice data before committing to Excel."""

    _COLS = ['Archivo', 'Estado', 'Tipo', 'Proveedor', 'CUIT',
             'Fecha', 'Kilos', 'Precio Unit.', 'Total']

    def __init__(self, resultados, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Vista previa — Facturas a procesar')
        self.setMinimumWidth(860)
        self.setMinimumHeight(480)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(14, 14, 14, 14)

        n_ok  = sum(1 for r in resultados
                    if r['datos'] and not r['dup_clave'] and not r['dup_nombre'])
        n_dup = sum(1 for r in resultados
                    if r['datos'] and (r['dup_clave'] or r['dup_nombre']))
        n_err = sum(1 for r in resultados if r['error'])

        lbl = QLabel(
            f'<b>{n_ok}</b> para escribir &nbsp;|&nbsp; '
            f'<b>{n_dup}</b> duplicada(s) &nbsp;|&nbsp; '
            f'<b>{n_err}</b> con error'
        )
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setFont(QFont('Arial', 10))
        layout.addWidget(lbl)

        table = QTableWidget(len(resultados), len(self._COLS))
        table.setHorizontalHeaderLabels(self._COLS)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setFont(QFont('Courier New', 9))
        table.verticalHeader().setVisible(False)

        for row, r in enumerate(resultados):
            d = r['datos']
            if r['error']:
                vals  = [r['filename'], 'ERROR', '', '', '', '', '', '', '']
                color = QColor(200, 0, 0)
            elif r['dup_clave'] or r['dup_nombre']:
                vals  = self._fila_valores(r['filename'], 'DUPLICADA', d)
                color = QColor(130, 130, 130)
            else:
                vals  = self._fila_valores(r['filename'], 'OK', d)
                color = None

            for col, val in enumerate(vals):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                if color:
                    item.setForeground(color)
                elif val == 'VERIFICAR':
                    item.setForeground(QColor(190, 90, 0))
                table.setItem(row, col, item)

        layout.addWidget(table)

        btns   = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_ok = btns.button(QDialogButtonBox.Ok)
        btn_ok.setText(f'✓  Escribir {n_ok} factura(s) en Excel')
        btn_ok.setEnabled(n_ok > 0)
        btns.button(QDialogButtonBox.Cancel).setText('Cancelar')
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    @staticmethod
    def _fila_valores(filename, estado, d):
        return [
            filename,
            estado,
            d['tipo']         or 'VERIFICAR',
            d['denominacion'] or 'VERIFICAR',
            d['cuit']         or 'VERIFICAR',
            d['fecha']        or 'VERIFICAR',
            f"{d['kilos_num']:,.0f}"          if d['kilos_num']           else 'VERIFICAR',
            f"{d['precio_unitario_num']:,.2f}" if d['precio_unitario_num'] else 'VERIFICAR',
            f"{d['total_num']:,.2f}"           if d['total_num']           else 'VERIFICAR',
        ]


# ---------------------------------------------------------------------------
# Ventana principal
# ---------------------------------------------------------------------------

class VentanaFacturas(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Procesador de Facturas')
        self.setGeometry(100, 100, 660, 520)
        self.worker = None
        self._init_ui()

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

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont('Courier New', 9))
        layout.addWidget(self.log_text)

        self.barra = QProgressBar()
        self.barra.setVisible(False)
        layout.addWidget(self.barra)

        botones = QHBoxLayout()

        self.btn_gmail = QPushButton('📧  Buscar en Gmail')
        self.btn_gmail.setMinimumHeight(38)
        self.btn_gmail.setFont(QFont('Arial', 10))
        self.btn_gmail.setToolTip('Busca PDFs nuevos en Gmail, los procesa y etiqueta los ya procesados')
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
        self.btn_gmail.setEnabled(False)
        self.btn_local.setEnabled(False)
        self.barra.setValue(0)
        self.barra.setVisible(True)
        self._log('─' * 55)

    def _desbloquear(self):
        self.btn_gmail.setEnabled(True)
        self.btn_local.setEnabled(True)
        self.barra.setVisible(False)

    # ------------------------------------------------------------------
    # Gmail flow — procesa y escribe directamente (batch sin preview)
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
    # Local flow — parsea → muestra preview → confirma → escribe
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
        self.worker.preview.connect(self._mostrar_preview)
        self.worker.error_critico.connect(self._error_critico)
        self.worker.start()

    def _mostrar_preview(self, resultados):
        self._desbloquear()
        dlg = DialogoPreview(resultados, self)
        if dlg.exec_() == QDialog.Accepted:
            self._escribir_resultados(resultados)
        else:
            self._log('↩ Cancelado por el usuario.')

    def _escribir_resultados(self, resultados):
        self._log('Escribiendo en Excel...')
        try:
            resumen = escribir_resultados_en_excel(resultados)
            self._finalizado(resumen)
        except Exception as e:
            self._error_critico(str(e))

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
        self._log('─' * 55)
        self._log(
            f'✅  Listo — '
            f'OK: {resumen["ok"]}  |  '
            f'Duplicadas: {resumen["duplicados"]}  |  '
            f'Errores: {resumen["errores"]}'
        )

    def _error_critico(self, mensaje):
        self._desbloquear()
        self._log(f'❌  ERROR CRÍTICO:\n{mensaje}')

    def _abrir_excel(self):
        if not EXCEL_FACTURAS.exists():
            self._log(f'Todavía no existe {EXCEL_FACTURAS.name}. Procesá facturas primero.')
            return

        path = str(EXCEL_FACTURAS)
        if sys.platform == 'win32':
            os.startfile(path)
        elif sys.platform == 'darwin':
            subprocess.run(['open', path])
        else:
            subprocess.run(['xdg-open', path])
