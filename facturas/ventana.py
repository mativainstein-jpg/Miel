import os
import subprocess
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QHBoxLayout, QLabel, QMainWindow, QProgressBar,
    QPushButton, QTextEdit, QVBoxLayout, QWidget,
)

from config import EXCEL_FACTURAS
from procesador import ProcesadorWorker


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

        self.btn_procesar = QPushButton('📥  Procesar Facturas')
        self.btn_procesar.setMinimumHeight(38)
        self.btn_procesar.setFont(QFont('Arial', 10))
        self.btn_procesar.clicked.connect(self._procesar)
        botones.addWidget(self.btn_procesar)

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

    def _procesar(self):
        self.btn_procesar.setEnabled(False)
        self.barra.setValue(0)
        self.barra.setVisible(True)
        self._log('─' * 55)

        self.worker = ProcesadorWorker()
        self.worker.log.connect(self._log)
        self.worker.progreso.connect(self._progreso)
        self.worker.terminado.connect(self._finalizado)
        self.worker.error_critico.connect(self._error_critico)
        self.worker.start()

    def _log(self, mensaje):
        self.log_text.append(mensaje)
        sb = self.log_text.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _progreso(self, actual, total):
        self.barra.setMaximum(total)
        self.barra.setValue(actual)

    def _finalizado(self, resumen):
        self.btn_procesar.setEnabled(True)
        self.barra.setVisible(False)
        self._log('─' * 55)
        self._log(
            f'✅  Listo — '
            f'OK: {resumen["ok"]}  |  '
            f'Duplicadas: {resumen["duplicados"]}  |  '
            f'Errores: {resumen["errores"]}'
        )

    def _error_critico(self, mensaje):
        self.btn_procesar.setEnabled(True)
        self.barra.setVisible(False)
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
