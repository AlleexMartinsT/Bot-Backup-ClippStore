# tray.py
import threading
import os
import sys
from pathlib import Path
import pystray
from PIL import Image

# Evita logs do pywin32
os.environ["PYWIN_AUTO_DISABLE_LOGGING"] = "1"


# ======================================================
# Função compatível com PyInstaller
# ======================================================
def resource_path(relative_path: str) -> str:
    """
    Retorna o caminho absoluto do recurso, compatível com
    execução direta e com executável PyInstaller.
    """
    try:
        # Quando empacotado pelo PyInstaller
        base_path = sys._MEIPASS
    except Exception:
        # Quando executado normalmente
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


# ======================================================
# Caminhos dos ícones (usando resource_path)
# ======================================================
ICON_INICIO = resource_path("icons/icon_inicio.png")
ICON_RODANDO = resource_path("icons/icon_rodando.png")
ICON_ERROR = resource_path("icons/icon_error.png")


# ======================================================
# Função auxiliar para carregar imagens
# ======================================================
def carregar_icone(caminho):
    try:
        return Image.open(caminho)
    except Exception as e:
        print(f"⚠️ Erro ao carregar ícone {caminho}: {e}")
        return None


# ======================================================
# Classe principal do Tray
# ======================================================
class TrayController:
    def __init__(self, on_abrir_relatorio, on_sair):
        self.on_abrir_relatorio = on_abrir_relatorio
        self.on_sair = on_sair
        self.icon = pystray.Icon("BackupBot")

        # Carrega os ícones usando os caminhos corrigidos
        self.icons = {
            "inicio": carregar_icone(ICON_INICIO),
            "rodando": carregar_icone(ICON_RODANDO),
            "erro": carregar_icone(ICON_ERROR),
        }

        # Define o ícone inicial
        self.icon.icon = self.icons["inicio"]

        # Cria o menu
        menu = pystray.Menu(
            pystray.MenuItem("Abrir relatórios", self._abrir_relatorios),
            pystray.MenuItem("Sair", self._sair)
        )
        self.icon.menu = menu

    # =====================
    # Ações do menu
    # =====================
    def _abrir_relatorios(self, icon, item):
        self.on_abrir_relatorio()

    def _sair(self, icon, item):
        self.icon.visible = False
        self.icon.stop()
        self.on_sair()

    # =====================
    # Execução do tray
    # =====================
    def run(self):
        threading.Thread(target=self.icon.run, daemon=True).start()

    # =====================
    # Atualiza o ícone
    # =====================
    def set_status(self, status):
        """
        Altera o ícone conforme o estado atual:
        status pode ser: "inicio", "rodando" ou "erro".
        """
        img = self.icons.get(status)
        if img:
            self.icon.icon = img
        else:
            print(f"⚠️ Ícone para o estado '{status}' não encontrado.")


# ======================================================
# Teste independente (executado só se rodar tray.py diretamente)
# ======================================================
if __name__ == "__main__":
    import time

    def abrir_relatorios():
        print("Abrindo relatórios...")

    def sair():
        print("Saindo...")

    tray = TrayController(abrir_relatorios, sair)
    tray.run()

    # Simula mudanças de estado
    time.sleep(3)
    tray.set_status("rodando")
    time.sleep(3)
    tray.set_status("erro")
