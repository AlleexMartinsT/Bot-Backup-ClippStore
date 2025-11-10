import threading
import os
import sys
from pathlib import Path
import pystray
from PIL import Image
from utils import log, fechar_tudo

def resource_path(relative_path: str) -> str:
    """Retorna o caminho absoluto do recurso, compatível com PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

ICON_PATH = resource_path("icons/backup_icon.ico")

class TrayController:
    def __init__(self, on_abrir_relatorio, on_sair):
        self.on_abrir_relatorio = on_abrir_relatorio
        self.on_sair = on_sair

        # Carrega o ícone único
        self.icon_image = Image.open(ICON_PATH)

        # Cria o ícone da bandeja
        self.icon = pystray.Icon("BackupBot", self.icon_image, "Backup Bot", menu=pystray.Menu(
            pystray.MenuItem("Abrir relatórios", self._abrir_relatorios)
        ))

    def _abrir_relatorios(self, icon, item):
        self.on_abrir_relatorio()

    def _sair(self, icon, item):
        fechar_tudo()

    def run(self):
        threading.Thread(target=self.icon.run, daemon=True).start()

    def set_status(self, status=None):
        """Mantém sempre o mesmo ícone — função mantida por compatibilidade."""
        self.icon.icon = self.icon_image