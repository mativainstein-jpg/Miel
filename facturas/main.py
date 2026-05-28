import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from PyQt5.QtWidgets import QApplication
from ventana import VentanaFacturas

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = VentanaFacturas()
    sys.exit(app.exec_())
