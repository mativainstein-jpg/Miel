from PyQt5.QtWidgets import (QApplication, QWidget, QFileDialog, QMainWindow,
                             QVBoxLayout, QLabel, QHBoxLayout, QPushButton,
                             QTableWidget, QTableWidgetItem)
from PyQt5.QtCore import QCoreApplication
import MielPulp
import json
import os
import platform


class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.title = 'Buscador de combinación óptima'
        self.miel = MielPulp.MielPulp()
        self.boundsLoaded = False
        self.setGeometry(20, 20, 700, 520)
        self.setWindowTitle(self.title)
        self.initUI()

    def initUI(self):
        self.vBox = QVBoxLayout()
        self.widget = QWidget()
        self.widget.setLayout(self.vBox)
        self.setCentralWidget(self.widget)

        self.vBox.addWidget(QLabel("Datos cargados"))
        self.dataTable = QTableWidget()
        self.vBox.addWidget(self.dataTable)

        hButtons = QHBoxLayout()

        btnDatos = QPushButton("Cargar Datos")
        btnDatos.clicked.connect(self.loadDataDir)
        hButtons.addWidget(btnDatos)

        btnBounds = QPushButton("Cargar Bounds")
        btnBounds.clicked.connect(self.loadBoundsDir)
        hButtons.addWidget(btnBounds)

        self.vBox.addLayout(hButtons)

        hAcc = QHBoxLayout()

        btnProcesar = QPushButton("Procesar")
        btnProcesar.clicked.connect(self.processMiel)
        hAcc.addWidget(btnProcesar)

        btnSalir = QPushButton("Salir")
        btnSalir.clicked.connect(QCoreApplication.instance().quit)
        hAcc.addWidget(btnSalir)

        self.vBox.addLayout(hAcc)
        self.show()

    def loadDataDir(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar archivo de datos", "", "Excel Files (*.xlsx)", options=options
        )
        if path:
            self.miel.setDataFromDir(path, "excel")
            self.setDataTable()

    def loadBoundsDir(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar archivo de bounds", "", "Excel Files (*.xlsx)", options=options
        )
        if path:
            self.miel.setBoundsFromDir(path, "excel")
            self.boundsLoaded = True
            tipos = list(self.miel.tipos.keys())
            self.statusBar().showMessage(f"Bounds cargados: {', '.join(tipos)}")

    def setDataTable(self):
        data = json.loads(self.miel.getDataJson())
        self.dataTable.clear()
        headers = list(data.keys())
        self.dataTable.setColumnCount(len(headers))
        self.dataTable.setRowCount(len(data[headers[0]]))
        for n, key in enumerate(headers):
            for m, val in enumerate(data[key].values()):
                self.dataTable.setItem(m, n, QTableWidgetItem(str(val)))
        self.dataTable.setHorizontalHeaderLabels(headers)

    def processMiel(self):
        if not self.boundsLoaded:
            # fallback: buscar bounds.xlsx en la carpeta padre
            sep = os.sep
            fallback = os.path.join(os.getcwd(), ".." + sep + "bounds.xlsx")
            if os.path.exists(fallback):
                self.miel.setBoundsFromDir(fallback, "excel")
                self.boundsLoaded = True
            else:
                self.statusBar().showMessage("Cargá el archivo de bounds primero.")
                return

        # solver: HiGHS en Mac/Linux, CBC en Windows como fallback
        solveDir = ""
        if platform.system() == "Windows":
            sep = os.sep
            solveDir = os.path.join(
                os.getcwd(), ".." + sep + "Cbc-2.7.5-win64" + sep + "bin" + sep + "cbc.exe"
            )

        self.statusBar().showMessage("Procesando... puede tardar varios minutos.")
        QApplication.processEvents()

        n_tipos = self.miel.processModel(solveDir, timeLimit=7200)
        self.saveResults(n_tipos)

    def saveResults(self, n_tipos):
        sep = os.sep
        outPath = os.path.join(os.getcwd(), ".." + sep + "results.xlsx")
        self.miel.saveResultsToExcelDir(outPath)

        total_lotes = sum(len(v) for v in self.miel.results.values())
        tipos_str = ", ".join(
            f"{t}: {len(l)} lote(s)" for t, l in self.miel.results.items()
        )
        msg = f"Listo. {total_lotes} lote(s) en {n_tipos} tipo(s): {tipos_str}"
        if self.miel.rowScore > 0:
            msg += f"  |  Puntaje posición: {self.miel.rowScore}"
        self.statusBar().showMessage(msg)
