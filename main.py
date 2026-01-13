# main.py
import threading
import os
import sys
from pathlib import Path
from interface import InterfaceApp
from tray import TrayController
from agendador import loopAgendador
from utils import log

_stop_event = threading.Event()
tray = None

def abrir_relatorios():
    from os import startfile
    appdata = Path(os.getenv("APPDATA", Path.home() / "AppData/Roaming")) / "BackupBot" / "relatorios"
    appdata.mkdir(parents=True, exist_ok=True)
    startfile(str(appdata))

def main():
    global tray
    log("Backup Bot iniciando.")

    # 1️Cria a interface primeiro
    app = InterfaceApp()

    # 2️Cria o tray e passa a interface para ele
    tray = TrayController(abrir_relatorios)
    tray.interface_ref = app       # <-- ESSENCIAL
    tray.run()
    tray.set_status("inicio")

    # 3️Inicia o agendador
    th_ag = threading.Thread(target=loopAgendador, args=(_stop_event,), daemon=True)
    th_ag.start()

    # 4️Inicia a interface
    app.start()

if __name__ == "__main__":
    main()
