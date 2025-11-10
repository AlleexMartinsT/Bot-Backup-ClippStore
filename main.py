# main.py
# Inicia tray, interface e agendador.

import threading
import os
import sys
from pathlib import Path
from interface import InterfaceApp
from tray import TrayController  # alterado aqui
from agendador import loopAgendador
from utils import log, fechar_tudo

_stop_event = threading.Event()

tray = None  # variável global opcional para acessar de outros módulos

def abrir_relatorios():
    from os import startfile
    appdata = Path(os.getenv("APPDATA", Path.home() / "AppData/Roaming")) / "BackupBot" / "relatorios"
    appdata.mkdir(parents=True, exist_ok=True)
    startfile(str(appdata))

    try:
        if tray and tray.icon:
            tray.icon.visible = False
            tray.icon.stop()
    except Exception as e:
        log(f"Erro ao parar tray: {e}")

    os._exit(0)

def main():
    global tray
    log("Backup Bot iniciando.")

    # inicia o tray
    tray = TrayController(abrir_relatorios, fechar_tudo)
    tray.run()
    tray.set_status("inicio")  # ícone inicial

    # inicia o agendador em thread separada
    th_ag = threading.Thread(target=loopAgendador, args=(_stop_event,), daemon=True)
    th_ag.start()

    # inicia interface principal
    app = InterfaceApp()
    app.fechar_callback = fechar_tudo  # adiciona essa linha
    app.start()

if __name__ == "__main__":
    main()
