# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['desktop.py'],
    pathex=[],
    binaries=[],
    datas=[('frontend', 'frontend'), ('backend', 'backend'), ('backend/auth/haarcascade_frontalface_default.xml', 'backend/auth')],
    hiddenimports=[
        'spotipy', 'spotipy.oauth2',
        'google.oauth2.credentials', 'google_auth_oauthlib.flow',
        'google.auth.transport.requests', 'googleapiclient.discovery',
        'googleapiclient._helpers',
        'imaplib', 'smtplib', 'email', 'email.header',
        'email.mime.text', 'email.mime.multipart',
        'shutil',
        'backend.web_rag',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='desktop',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
