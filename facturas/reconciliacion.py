"""
Diálogo de conciliación: revisa y edita cada factura una por una antes de
escribir en Excel. Vista PDF al costado del formulario editable.
"""
import re

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QFont, QPixmap
from PyQt5.QtWidgets import (
    QDialog, QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QScrollArea, QSizePolicy, QSplitter,
    QVBoxLayout, QWidget,
)

try:
    import fitz as _fitz
    _PDF_OK = True
except ImportError:
    _PDF_OK = False

from pdf_parser import _num as _parsear_numero_flexible


# ---------------------------------------------------------------------------
# Definición de campos del formulario
# (key, label, crítico)
# ---------------------------------------------------------------------------
_CAMPOS = [
    ('tipo',                    'Tipo',               True),
    ('punto_venta',             'Punto de Venta',     False),
    ('numero',                  'Número',             True),
    ('fecha',                   'Fecha',              True),
    ('denominacion',            'Denominación',       True),
    ('cuit',                    'CUIT',               True),
    ('neto_num',                'Neto gravado',       True),
    ('iva_num',                 'IVA',                True),
    ('no_gravado_num',          'No gravado',         False),
    ('imp_internos_num',        'Imp. Internos',      False),
    ('exentos_num',             'Exentos',            False),
    ('percepcion_iva_num',      'Percepción IVA',     False),
    ('percepcion_iibb_num',     'Percepción IIBB',    False),
    ('percepcion_ganancias_num','Perc. Ganancias',    False),
    ('kilos_num',               'Kilos',              True),
    ('precio_unitario_num',     'Precio unitario',    True),
    ('total_num',               'Total',              True),
    ('monotributista',          'Monotributista',     False),
    ('posicion',                'Posición',           False),
    ('mes',                     'Mes',                False),
    ('anio',                    'Año',                False),
    ('tasa',                    'Tasa',               False),
    ('gasto',                   'Gasto',              True),
    ('rubro',                   'Rubro',              True),
    ('codigo_operacion',        'Cód. Operación',     False),
    ('descripcion_gasto',       'Descripción gasto',  False),
    ('descripcion_rubro',       'Descripción rubro',  False),
]

_NUM_KEYS = {k for k, *_ in _CAMPOS if k.endswith('_num')}
_INT_KEYS = {'mes', 'anio', 'tasa', 'gasto', 'rubro'}

# Campos que siempre son VERIFICAR si están vacíos
_CRITICOS = {k for k, _, crit in _CAMPOS if crit}

_SECCIONES = {
    'neto_num':    '── Importes ────────────────────────────',
    'kilos_num':   '── Cantidades ──────────────────────────',
    'monotributista': '── Contabilidad ────────────────────',
}


# ---------------------------------------------------------------------------
# Conversión valor ↔ texto
# ---------------------------------------------------------------------------

def _a_texto(key, val):
    """Convierte un valor del dict a texto para mostrar en el input."""
    if val is None:
        return ''
    if key in _NUM_KEYS:
        f = float(val)
        return f'{f:,.2f}' if f != 0.0 else '0'
    if key in _INT_KEYS:
        return str(int(val)) if val else ''
    return str(val)


def _de_texto(key, text):
    """Convierte el texto del input al tipo correcto para el dict."""
    text = text.strip()
    if not text:
        return None
    if key in _NUM_KEYS:
        # Acepta formato US (1234.56) y AR (1.234,56); rechaza texto no numérico
        # en lugar de adivinar (evita guardar un valor falso silenciosamente).
        if not re.match(r'^-?[\d.,]+$', text):
            return None
        return _parsear_numero_flexible(text)
    if key in _INT_KEYS:
        try:
            return int(text)
        except ValueError:
            return None
    return text


def _es_verificar(key, text):
    """¿Este campo debería mostrar cartel VERIFICAR?"""
    return key in _CRITICOS and not text.strip()


# ---------------------------------------------------------------------------
# Widget de un campo con cartel VERIFICAR
# ---------------------------------------------------------------------------

class _CampoInput(QWidget):

    def __init__(self, key, is_critical):
        super().__init__()
        self.key = key
        self.is_critical = is_critical

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 1, 0, 1)
        row.setSpacing(6)

        self.edit = QLineEdit()
        self.edit.setMinimumWidth(210)
        row.addWidget(self.edit, 1)

        # Cartel VERIFICAR — grande y rojo
        self.badge = QLabel('⚠  VERIFICAR')
        self.badge.setFont(QFont('Arial', 9, QFont.Bold))
        self.badge.setStyleSheet(
            'color: white;'
            'background: #cc0000;'
            'padding: 2px 8px;'
            'border-radius: 4px;'
            'letter-spacing: 1px;'
        )
        self.badge.setVisible(False)
        row.addWidget(self.badge)

        self.edit.textChanged.connect(self._actualizar)

    def _actualizar(self, text=''):
        if not text:
            text = self.edit.text()
        if _es_verificar(self.key, text):
            self.edit.setStyleSheet(
                'background: #fff0f0;'
                'border: 2px solid #cc0000;'
                'border-radius: 3px;'
                'padding: 1px 4px;'
            )
            self.badge.setVisible(True)
        else:
            self.edit.setStyleSheet('')
            self.badge.setVisible(False)

    def set_valor(self, val):
        text = _a_texto(self.key, val)
        self.edit.blockSignals(True)
        self.edit.setText(text)
        self.edit.blockSignals(False)
        self._actualizar(text)

    def get_valor(self):
        return _de_texto(self.key, self.edit.text())

    def set_readonly(self, readonly):
        self.edit.setReadOnly(readonly)
        self.edit.setStyleSheet(
            'background: #f5f5f5; color: #888;' if readonly else ''
        )
        if readonly:
            self.badge.setVisible(False)


# ---------------------------------------------------------------------------
# Diálogo principal de conciliación
# ---------------------------------------------------------------------------

class ReconciliacionDialog(QDialog):
    """
    Abre cada factura una por una:
      - izquierda: visor PDF
      - derecha:   formulario editable con carteles VERIFICAR
    Al confirmar todos, habilita el botón "Escribir en Excel".
    """

    def __init__(self, resultados, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Conciliación de Facturas')
        self.setMinimumSize(1100, 600)
        self.showMaximized()   # arranca en pantalla completa
        self._zoom = 2.5       # zoom inicial del PDF

        self._todos   = resultados
        # Solo las facturas con datos parseados pasan por conciliación manual
        self._items   = [r for r in resultados if r['datos'] and not r['error']]
        self._idx     = 0
        self._decisiones = {}  # idx → {'omitida': bool, 'datos': dict}
        self._inputs  = {}     # key → _CampoInput

        self._construir_ui()
        if self._items:
            self._cargar(0)
        else:
            self._lbl_titulo.setText('No hay facturas para conciliar.')

    # ------------------------------------------------------------------
    # Construcción de UI
    # ------------------------------------------------------------------

    def _construir_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # ── Barra superior ──────────────────────────────────────────────
        top = QHBoxLayout()
        self._lbl_titulo = QLabel()
        self._lbl_titulo.setFont(QFont('Arial', 11, QFont.Bold))
        top.addWidget(self._lbl_titulo, 1)
        self._lbl_global = QLabel()
        self._lbl_global.setFont(QFont('Courier New', 9))
        self._lbl_global.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        top.addWidget(self._lbl_global)
        root.addLayout(top)

        # ── Splitter PDF | Formulario ───────────────────────────────────
        splitter = QSplitter(Qt.Horizontal)

        # Panel PDF
        pdf_panel = QWidget()
        pdf_lo    = QVBoxLayout(pdf_panel)
        pdf_lo.setContentsMargins(0, 0, 6, 0)

        # Barra superior del panel PDF: título + botones zoom
        pdf_top = QHBoxLayout()
        lbl_pdf = QLabel('Vista previa PDF')
        lbl_pdf.setStyleSheet('color: #555;')
        pdf_top.addWidget(lbl_pdf, 1)

        btn_zoom_out = QPushButton('−')
        btn_zoom_out.setFixedWidth(28)
        btn_zoom_out.setToolTip('Reducir')
        btn_zoom_out.clicked.connect(self._zoom_out)
        pdf_top.addWidget(btn_zoom_out)

        self._lbl_zoom = QLabel('100%')
        self._lbl_zoom.setFixedWidth(40)
        self._lbl_zoom.setAlignment(Qt.AlignCenter)
        pdf_top.addWidget(self._lbl_zoom)

        btn_zoom_in = QPushButton('+')
        btn_zoom_in.setFixedWidth(28)
        btn_zoom_in.setToolTip('Ampliar')
        btn_zoom_in.clicked.connect(self._zoom_in)
        pdf_top.addWidget(btn_zoom_in)

        pdf_lo.addLayout(pdf_top)

        self._pdf_scroll = QScrollArea()
        self._pdf_scroll.setWidgetResizable(False)
        self._pdf_lbl = QLabel('Cargando...')
        self._pdf_lbl.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self._pdf_scroll.setWidget(self._pdf_lbl)
        pdf_lo.addWidget(self._pdf_scroll, 1)
        splitter.addWidget(pdf_panel)

        # Panel formulario
        form_panel = QWidget()
        form_lo    = QVBoxLayout(form_panel)
        form_lo.setContentsMargins(6, 0, 0, 0)

        lbl_form = QLabel('Datos extraídos — editables antes de confirmar')
        lbl_form.setAlignment(Qt.AlignCenter)
        lbl_form.setStyleSheet(
            'background: #e8e8e8; color: #555; padding: 3px; border-radius: 3px;'
        )
        form_lo.addWidget(lbl_form)

        form_scroll  = QScrollArea()
        form_scroll.setWidgetResizable(True)
        form_widget  = QWidget()
        self._form   = QFormLayout(form_widget)
        self._form.setRowWrapPolicy(QFormLayout.DontWrapRows)
        self._form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._form.setSpacing(4)
        self._form.setContentsMargins(8, 8, 8, 8)

        for key, label, is_crit in _CAMPOS:
            if key in _SECCIONES:
                sep = QLabel(_SECCIONES[key])
                sep.setStyleSheet('color: #aaa; font-size: 8px; padding: 6px 0 2px 0;')
                self._form.addRow(sep)

            inp = _CampoInput(key, is_crit)
            self._inputs[key] = inp

            lbl_w = QLabel(label + ':')
            if is_crit:
                lbl_w.setFont(QFont('Arial', 9, QFont.Bold))
            self._form.addRow(lbl_w, inp)

        form_scroll.setWidget(form_widget)
        form_lo.addWidget(form_scroll, 1)

        # Aviso duplicado / error
        self._lbl_aviso = QLabel()
        self._lbl_aviso.setWordWrap(True)
        self._lbl_aviso.setVisible(False)
        form_lo.addWidget(self._lbl_aviso)

        splitter.addWidget(form_panel)
        splitter.setStretchFactor(0, 6)
        splitter.setStretchFactor(1, 4)
        root.addWidget(splitter, 1)

        # ── Barra de navegación ─────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        root.addWidget(sep)

        nav = QHBoxLayout()

        self._btn_ant = QPushButton('← Anterior')
        self._btn_ant.setEnabled(False)
        self._btn_ant.clicked.connect(self._ir_anterior)
        nav.addWidget(self._btn_ant)

        self._btn_omitir = QPushButton('Omitir')
        self._btn_omitir.setToolTip('No cargar esta factura en Excel')
        self._btn_omitir.clicked.connect(self._omitir)
        nav.addWidget(self._btn_omitir)

        nav.addStretch()
        self._lbl_conteo = QLabel()
        self._lbl_conteo.setFont(QFont('Courier New', 10, QFont.Bold))
        nav.addWidget(self._lbl_conteo)
        nav.addStretch()

        self._btn_confirmar = QPushButton('Confirmar y continuar →')
        self._btn_confirmar.setDefault(True)
        self._btn_confirmar.setFont(QFont('Arial', 10, QFont.Bold))
        self._btn_confirmar.setMinimumHeight(34)
        self._btn_confirmar.clicked.connect(self._confirmar)
        nav.addWidget(self._btn_confirmar)

        root.addLayout(nav)

        # ── Barra inferior (resumen + escritura) ────────────────────────
        bot = QHBoxLayout()
        self._lbl_resumen = QLabel()
        bot.addWidget(self._lbl_resumen, 1)

        self._btn_escribir = QPushButton('✓  Escribir en Excel')
        self._btn_escribir.setFont(QFont('Arial', 11, QFont.Bold))
        self._btn_escribir.setMinimumHeight(38)
        self._btn_escribir.setEnabled(False)
        self._btn_escribir.setStyleSheet(
            'QPushButton:enabled { background: #2d7a2d; color: white; border-radius: 4px; }'
            'QPushButton:disabled { background: #ccc; color: #888; border-radius: 4px; }'
        )
        self._btn_escribir.clicked.connect(self.accept)
        bot.addWidget(self._btn_escribir)

        btn_cancelar = QPushButton('Cancelar todo')
        btn_cancelar.clicked.connect(self._cancelar_todo)
        bot.addWidget(btn_cancelar)

        root.addLayout(bot)

    def _cancelar_todo(self):
        if self._confirmar_cancelar():
            self.reject()

    def _confirmar_cancelar(self):
        resp = QMessageBox.question(
            self, 'Cancelar todo',
            'Si cancelás, se pierde toda la revisión y no se guarda ninguna '
            'factura.\n\n¿Seguro?',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        return resp == QMessageBox.Yes

    def closeEvent(self, event):
        # La X de la ventana también pide confirmación (evita perder trabajo)
        if self._confirmar_cancelar():
            event.accept()
        else:
            event.ignore()

    # ------------------------------------------------------------------
    # Carga de una factura en el formulario
    # ------------------------------------------------------------------

    def _cargar(self, idx):
        if idx < 0 or idx >= len(self._items):
            return
        self._idx = idx
        r = self._items[idx]
        total = len(self._items)

        self._lbl_titulo.setText(
            f'Factura {idx + 1} de {total}  —  {r["filename"]}'
        )

        # Usar decisión guardada si existe (al retroceder)
        if idx in self._decisiones:
            datos = self._decisiones[idx]['datos'] or r['datos']
        else:
            datos = r['datos']

        for key, *_ in _CAMPOS:
            self._inputs[key].set_valor(datos.get(key))

        # Avisos de duplicado / error
        es_dup = r['dup_clave'] or r['dup_nombre']
        if es_dup:
            self._lbl_aviso.setText(
                '⚠  Esta factura ya existe en el Excel (duplicada). '
                'Solo podés omitirla.'
            )
            self._lbl_aviso.setStyleSheet(
                'background:#fff3cd; color:#856404; padding:8px; border-radius:4px;'
            )
            self._lbl_aviso.setVisible(True)
        elif r['error']:
            self._lbl_aviso.setText(f'✗  Error al parsear: {r["error"]}')
            self._lbl_aviso.setStyleSheet(
                'background:#f8d7da; color:#842029; padding:8px; border-radius:4px;'
            )
            self._lbl_aviso.setVisible(True)
        else:
            self._lbl_aviso.setVisible(False)

        readonly = es_dup or bool(r['error'])
        for inp in self._inputs.values():
            inp.set_readonly(readonly)

        self._btn_confirmar.setEnabled(not readonly)
        self._btn_ant.setEnabled(idx > 0)

        # Renderizar PDF con breve delay para que la UI no se congele
        QTimer.singleShot(60, lambda r=r: self._renderizar(r))
        self._refrescar_contadores()

    # ------------------------------------------------------------------
    # Renderizado PDF
    # ------------------------------------------------------------------

    def _zoom_in(self):
        self._zoom = min(self._zoom + 0.5, 7.5)  # máximo 300%
        if self._items:
            self._renderizar(self._items[self._idx])

    def _zoom_out(self):
        self._zoom = max(self._zoom - 0.5, 1.25)  # mínimo 50%
        if self._items:
            self._renderizar(self._items[self._idx])

    def _renderizar(self, r):
        if not _PDF_OK:
            self._pdf_lbl.setText(
                '⚠  Vista previa no disponible.\n\n'
                'Para activarla:\n'
                '   pip install pymupdf'
            )
            self._pdf_lbl.setAlignment(Qt.AlignCenter)
            return
        try:
            pdf_bytes = r['ruta'].read_bytes()
            doc  = _fitz.open(stream=pdf_bytes, filetype='pdf')
            page = doc[0]
            mat  = _fitz.Matrix(3.0, 3.0)  # alta resolución base
            pix  = page.get_pixmap(matrix=mat, alpha=False)
            png  = pix.tobytes('png')
            doc.close()

            pixmap = QPixmap()
            pixmap.loadFromData(png)

            # zoom=2.5 → 100% (ajusta al ancho disponible)
            # zoom>2.5 → más grande, aparece scroll horizontal
            ancho_disponible = self._pdf_scroll.viewport().width() - 10
            if ancho_disponible > 50:
                ancho_objetivo = int(ancho_disponible * self._zoom / 2.5)
                pixmap = pixmap.scaledToWidth(ancho_objetivo, Qt.SmoothTransformation)

            self._pdf_lbl.setPixmap(pixmap)
            self._pdf_lbl.resize(pixmap.size())
            self._lbl_zoom.setText(f'{int(self._zoom / 2.5 * 100)}%')
        except Exception as e:
            self._pdf_lbl.setText(f'Error al renderizar:\n{e}')
            self._pdf_lbl.setAlignment(Qt.AlignCenter)

    # ------------------------------------------------------------------
    # Acciones de navegación
    # ------------------------------------------------------------------

    def _leer_form(self):
        r = self._items[self._idx]
        datos = dict(r['datos'])
        for key, *_ in _CAMPOS:
            datos[key] = self._inputs[key].get_valor()
        return datos

    def _confirmar(self):
        datos = self._leer_form()
        self._decisiones[self._idx] = {'omitida': False, 'datos': datos}
        self._avanzar()

    def _omitir(self):
        self._decisiones[self._idx] = {'omitida': True, 'datos': None}
        self._avanzar()

    def _avanzar(self):
        if self._idx + 1 < len(self._items):
            self._cargar(self._idx + 1)
        else:
            self._mostrar_fin()

    def _ir_anterior(self):
        self._cargar(self._idx - 1)

    def _mostrar_fin(self):
        confirmadas = sum(
            1 for v in self._decisiones.values() if not v['omitida']
        )
        omitidas = len(self._decisiones) - confirmadas
        self._lbl_titulo.setText(
            f'Terminaste de revisar. Ahora apretá el botón VERDE de abajo '
            f'para guardar ({confirmadas} factura/s).'
        )
        self._lbl_titulo.setStyleSheet('color: #2d7a2d;')
        self._btn_confirmar.setEnabled(False)
        self._btn_omitir.setEnabled(False)
        self._btn_escribir.setEnabled(confirmadas > 0)
        # Resaltar el botón para que sea imposible no verlo
        if confirmadas > 0:
            self._btn_escribir.setText('✓  GUARDAR EN EXCEL  ✓')
        self._refrescar_contadores()

    def _refrescar_contadores(self):
        total       = len(self._items)
        revisadas   = len(self._decisiones)
        confirmadas = sum(1 for v in self._decisiones.values() if not v['omitida'])
        omitidas    = revisadas - confirmadas
        pendientes  = total - revisadas

        self._lbl_conteo.setText(
            f'{self._idx + 1} / {total}'
        )
        self._lbl_global.setText(
            f'✓ {confirmadas}   ✗ {omitidas}   ○ {pendientes}'
        )
        self._lbl_resumen.setText(
            f'Confirmadas: {confirmadas}  |  '
            f'Omitidas: {omitidas}  |  '
            f'Pendientes: {pendientes}'
        )
        all_done = revisadas >= total
        self._btn_escribir.setEnabled(
            all_done and confirmadas > 0
        )

    # ------------------------------------------------------------------
    # Resultado final
    # ------------------------------------------------------------------

    def resultados_para_escribir(self):
        """
        Devuelve la lista de resultados a escribir en Excel.
        - Facturas confirmadas: con los datos editados del formulario.
        - Facturas con error:   incluidas tal cual para registrar_error().
        - Facturas omitidas:    excluidas.
        """
        out = []
        proc_idx = 0
        for r in self._todos:
            if r['datos'] and not r['error']:
                dec = self._decisiones.get(proc_idx)
                if dec and not dec['omitida']:
                    out.append({**r, 'datos': dec['datos']})
                # omitidas: no se incluyen
                proc_idx += 1
            else:
                out.append(r)  # errores → van a hoja ERRORES
        return out
