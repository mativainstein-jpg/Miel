from PyQt5.QtWidgets import QApplication, QWidget, QInputDialog, QLineEdit, QFileDialog, QMainWindow, QVBoxLayout, QLabel
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QStatusBar
from PyQt5.QtWidgets import QPushButton
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QCoreApplication
from PyQt5.QtWidgets import QTableWidget,QTableWidgetItem
import MielPulp
import json
import os

class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.title = 'Buscador de combinación óptima.'
        self.left = 20
        self.top =  20 
        self.width = 630
        self.height = 480
        self.miel = MielPulp.MielPulp() 
        self.initUI()
    
    def initUI(self):
        self.setWindowTitle(self.title)
        self.setGeometry(self.left, self.top, self.width, self.height)
        self.showGUI()
    
    def loadDataDir(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        dataDir, _ = QFileDialog.getOpenFileName(self,"Selección del archivo Excel", "","Excel Files (*.xlsx)", options=options)
        if dataDir:
            self.miel.setDataFromDir(dataDir, "excel")
            self.setDataTable()

            #self.cntOptimal = model.algoritmoPuLP(dataFrameDir) 

    def setDataTable(self): 
        data =  json.loads(self.miel.getDataJson())
        horHeaders = []
        self.dataTable.clear()
        horHeaders = list(data.keys())
        self.dataTable.setColumnCount(len(horHeaders))
        fKey = horHeaders[0]
        self.dataTable.setRowCount(len(data[fKey]))

        for n, key in enumerate(data.keys()):
            for m in list(data[key].keys()):
                item = str(data[key][m])
                newitem = QTableWidgetItem(item)
                self.dataTable.setItem(int(m), n, newitem)
        self.dataTable.setHorizontalHeaderLabels(horHeaders)   

    def showGUI(self):
        self.vBox = QVBoxLayout()
        self.widget = QWidget()
        self.widget.setLayout(self.vBox)
        self.setCentralWidget(self.widget)

        l0 = QLabel()
        l0.setText("Datos Cargados")
        self.vBox.addWidget(l0)
        
        self.dataTable = QTableWidget()
        self.vBox.addWidget(self.dataTable)

        hBox = QHBoxLayout()
        hBox.addStretch()
        hBox.addStretch()

        ldf = QPushButton('Cargar Datos')
        ldf.clicked.connect(self.loadDataDir)

        hBox.addWidget(ldf)

        self.vBox.addLayout(hBox)
        
        hBox2 = QHBoxLayout()

        pbtn = QPushButton('Procesar')
        pbtn.clicked.connect(self.processMiel)
        hBox2.addWidget(pbtn)

        #hBox2.addStretch()

        qbtn = QPushButton('Salir')
        qbtn.clicked.connect(QCoreApplication.instance().quit)
        hBox2.addWidget(qbtn)

        self.vBox.addLayout(hBox2)
        self.show()

    def processMiel(self):
        sep = os.sep
        self.miel.setBoundsFromDir(".." + sep + "bounds.xlsx", "excel")
        import platform
        if platform.system() == "Windows":
            cwd = os.getcwd()
            solveDirTemp = ".." + sep + "Cbc-2.7.5-win64" + sep + "bin" + sep + "cbc.exe"
            solveDir = os.path.join(cwd, solveDirTemp)
        else:
            solveDir = ""

        self.optimals = self.miel.processModel(solveDir)
        #self.statusBar().showMessage('Procesando...')

        self.saveResults()
    
    def saveResults(self):
        msg = 'Soluciones óptimas: ' + str(self.optimals)
        if hasattr(self.miel, 'rowScores') and self.miel.rowScores:
            best = self.miel.rowScores[0]
            if best > 0:
                msg += '  |  Mejor puntaje de posición (solución 1): ' + str(best) + ' tambores en misma columna'
        self.statusBar().showMessage(msg)
        self.miel.saveResultsToExcelDir(".." + os.sep + "results.xlsx")

