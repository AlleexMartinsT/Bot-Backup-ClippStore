# main.py
# Inicia tray, interface e agendador.

import threading
import os
import sys
from pathlib import Path
from interface import InterfaceApp
from tray import TrayController  # alterado aqui
from agendador import loopAgendador
from utils import log

_stop_event = threading.Event()
tray = None  # variável global opcional para acessar de outros módulos

def abrir_relatorios():
    from os import startfile
    appdata = Path(os.getenv("APPDATA", Path.home() / "AppData/Roaming")) / "BackupBot" / "relatorios"
    appdata.mkdir(parents=True, exist_ok=True)
    startfile(str(appdata))

def on_tray_sair():
    log("Usuário solicitou sair pelo tray.")
    _stop_event.set()
    try:
        sys.exit(0)
    except SystemExit:
        pass

def main():
    global tray
    log("Backup Bot iniciando.")

    # inicia o tray
    tray = TrayController(abrir_relatorios, on_tray_sair)
    tray.run()
    tray.set_status("inicio")  # ícone inicial

    # inicia o agendador em thread separada
    th_ag = threading.Thread(target=loopAgendador, args=(_stop_event,), daemon=True)
    th_ag.start()

    # inicia interface principal
    app = InterfaceApp()
    app.start()

if __name__ == "__main__":
    main()
