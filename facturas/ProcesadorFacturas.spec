# -*- mode: python ; coding: utf-8 -*-
# ProcesadorFacturas.spec
# Ejecutar con:  pyinstaller ProcesadorFacturas.spec --clean

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Recolectar datos necesarios de las librerías
datas = []
datas += collect_data_files('pdfminer')
datas += collect_data_files('pdfplumber')

# Imports que PyInstaller no detecta automáticamente
hidden = [
    # Google APIs
    'google.auth', 'google.auth.transport', 'google.auth.transport.requests',
    'google.auth.crypt', 'google.auth.crypt._python_rsa',
    'google.oauth2', 'google.oauth2.credentials', 'google.oauth2.service_account',
    'google_auth_oauthlib', 'google_auth_oauthlib.flow',
    'googleapiclient', 'googleapiclient.discovery', 'googleapiclient.errors',
    'googleapiclient.http',
    # PDF
    'pdfplumber', 'pdfminer', 'pdfminer.high_level', 'pdfminer.layout',
    'pdfminer.converter', 'pdfminer.pdfpage', 'pdfminer.pdfinterp',
    'fitz',
    # Excel
    'openpyxl', 'openpyxl.styles', 'openpyxl.utils', 'openpyxl.workbook',
    'openpyxl.worksheet', 'et_xmlfile',
    # Crypto / requests
    'cryptography', 'cryptography.hazmat', 'cryptography.hazmat.primitives',
    'cryptography.hazmat.backends',
    'requests', 'requests.adapters', 'charset_normalizer',
    'urllib3', 'certifi',
    # PyQt5
    'PyQt5', 'PyQt5.QtCore', 'PyQt5.QtGui', 'PyQt5.QtWidgets',
    'PyQt5.sip',
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ProcesadorFacturas',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,       # Sin ventana de consola
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
