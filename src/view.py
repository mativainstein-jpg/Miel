import os
import sys
import platform
import subprocess
import json

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QPushButton, QTableWidget,
                             QTableWidgetItem, QFileDialog, QMessageBox)
from PyQt5.QtCore import QCoreApplication, QThread, pyqtSignal

import MielPulp


# ---------------------------------------------------------------- auto-update

class UpdateChecker(QThread):
    resultado = pyqtSignal(bool)

    def run(self):
        try:
            repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            subprocess.run(
                ["git", "fetch", "origin"],
                cwd=repo_root, capture_output=True, timeout=8
            )
            status = subprocess.run(
                ["git", "status", "-uno"],
                cwd=repo_root, capture_output=True, text=True, timeout=5
            )
            hay_actualizacion = "behind" in status.stdout
            self.resultado.emit(hay_actualizacion)
        except Exception:
            self.resultado.emit(False)


def aplicarActualizacion(parent):
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    try:
        result = subprocess.run(
            ["git", "pull"],
            cwd=repo_root, capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            QMessageBox.information(
                parent, "Actualización aplicada",
                "El programa fue actualizado correctamente.\n"
                "Cerrá y volvé a abrir el programa para usar la nueva versión."
            )
        else:
            QMessageBox.warning(parent, "Error", f"No se pudo actualizar:\n{result.stderr}")
    except Exception as e:
        QMessageBox.warning(parent, "Error", f"No se pudo actualizar:\n{str(e)}")


# -------------------------------------------------------------------- UI

class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.miel = MielPulp.MielPulp()
        self.boundsLoaded = False
        self.setWindowTitle("Optimizador de mezclas de miel")
        self.setGeometry(20, 20, 720, 540)
        self.buildUI()
        self.show()
        self.verificarActualizaciones()

    def buildUI(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        root.addWidget(QLabel("Datos cargados:"))
        self.dataTable = QTableWidget()
        root.addWidget(self.dataTable)

        # fila de carga
        hCarga = QHBoxLayout()
        btnDatos = QPushButton("Cargar Datos")
        btnDatos.clicked.connect(self.loadDataDir)
        hCarga.addWidget(btnDatos)

        btnBounds = QPushButton("Cargar Bounds")
        btnBounds.clicked.connect(self.loadBoundsDir)
        hCarga.addWidget(btnBounds)

        self.lblBounds = QLabel("(sin bounds)")
        hCarga.addWidget(self.lblBounds)
        hCarga.addStretch()
        root.addLayout(hCarga)

        # fila de acciones
        hAcc = QHBoxLayout()
        btnProcesar = QPushButton("Procesar")
        btnProcesar.clicked.connect(self.processMiel)
        hAcc.addWidget(btnProcesar)

        btnSalir = QPushButton("Salir")
        btnSalir.clicked.connect(QCoreApplication.instance().quit)
        hAcc.addWidget(btnSalir)
        root.addLayout(hAcc)

    # --------------------------------------------------------- carga de datos

    def loadDataDir(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar datos", "", "Excel Files (*.xlsx)",
            options=QFileDialog.DontUseNativeDialog
        )
        if path:
            self.miel.setDataFromDir(path, "excel")
            self.refreshTable()

    def loadBoundsDir(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar bounds", "", "Excel Files (*.xlsx)",
            options=QFileDialog.DontUseNativeDialog
        )
        if path:
            self.miel.setBoundsFromDir(path, "excel")
            self.boundsLoaded = True
            tipos = list(self.miel.tipos.keys())
            self.lblBounds.setText(f"Tipos: {', '.join(tipos)}")

    def refreshTable(self):
        data = json.loads(self.miel.getDataJson())
        self.dataTable.clear()
        headers = list(data.keys())
        self.dataTable.setColumnCount(len(headers))
        self.dataTable.setRowCount(len(data[headers[0]]))
        for n, key in enumerate(headers):
            for m, val in enumerate(data[key].values()):
                self.dataTable.setItem(m, n, QTableWidgetItem(str(val)))
        self.dataTable.setHorizontalHeaderLabels(headers)

    # ------------------------------------------------------------ optimización

    def processMiel(self):
        # cargar bounds desde ruta por defecto si no se cargó manualmente
        if not self.boundsLoaded:
            sep = os.sep
            fallback = os.path.join(os.path.dirname(__file__), ".." + sep + "bounds.xlsx")
            if os.path.exists(fallback):
                self.miel.setBoundsFromDir(fallback, "excel")
                self.boundsLoaded = True
            else:
                self.statusBar().showMessage("Cargá el archivo de bounds primero.")
                return

        # solver según plataforma
        solveDir = ""
        if platform.system() == "Windows":
            sep = os.sep
            solveDir = os.path.join(
                os.path.dirname(__file__),
                ".." + sep + "Cbc-2.7.5-win64" + sep + "bin" + sep + "cbc.exe"
            )

        self.statusBar().showMessage("Procesando... puede tardar varios minutos.")
        QApplication.processEvents()

        n_tipos = self.miel.processModel(solveDir, timeLimit=7200)

        sep = os.sep
        outPath = os.path.join(os.path.dirname(__file__), ".." + sep + "results.xlsx")
        self.miel.saveResultsToExcelDir(outPath)

        total_lotes = sum(len(v) for v in self.miel.results.values())
        detalle = "  |  ".join(
            f"{t}: {len(l)} lote(s)" for t, l in self.miel.results.items()
        )
        msg = f"Listo — {total_lotes} lote(s) en {n_tipos} tipo(s).  {detalle}"
        if self.miel.rowScore > 0:
            msg += f"  |  Puntaje posición: {self.miel.rowScore}"
        self.statusBar().showMessage(msg)

    # --------------------------------------------------------- auto-update

    def verificarActualizaciones(self):
        self.statusBar().showMessage("Verificando actualizaciones...")
        self.checker = UpdateChecker()
        self.checker.resultado.connect(self.onUpdateResult)
        self.checker.start()

    def onUpdateResult(self, hayActualizacion):
        if hayActualizacion:
            self.statusBar().showMessage("Hay una actualización disponible.")
            resp = QMessageBox.question(
                self, "Actualización disponible",
                "Hay una nueva versión del programa.\n¿Querés actualizar ahora?",
                QMessageBox.Yes | QMessageBox.No
            )
            if resp == QMessageBox.Yes:
                aplicarActualizacion(self)
        else:
            self.statusBar().showMessage("El programa está actualizado.")
