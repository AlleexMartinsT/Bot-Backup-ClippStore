# detecta_janelas.py
import time
import ctypes
from ctypes import wintypes

EnumWindows = ctypes.windll.user32.EnumWindows
EnumChildWindows = ctypes.windll.user32.EnumChildWindows
EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
GetWindowText = ctypes.windll.user32.GetWindowTextW
GetWindowTextLength = ctypes.windll.user32.GetWindowTextLengthW
GetClassName = ctypes.windll.user32.GetClassNameW
IsWindowVisible = ctypes.windll.user32.IsWindowVisible


def listar_controles(hwnd_pai, titulo_pai):
    """Lista os controles (child windows) dentro de uma janela específica"""
    def foreach_child(hwnd, lParam):
        if not IsWindowVisible(hwnd):
            return True

        class_name = ctypes.create_unicode_buffer(256)
        GetClassName(hwnd, class_name, 256)
        cls = class_name.value

        length = GetWindowTextLength(hwnd)
        buff = ctypes.create_unicode_buffer(length + 1)
        GetWindowText(hwnd, buff, length + 1)
        title = buff.value or "<sem texto>"

        print(f"    ↳ Controle: {title} | Classe: {cls} | Handle: {hwnd}")
        return True

    print(f"\n--- Controles da janela: {titulo_pai} ---")
    EnumChildWindows(hwnd_pai, EnumWindowsProc(foreach_child), 0)
    print("=========================================")


def listar_janelas(filtro_palavra=None, excecoes=None):
    """Lista todas as janelas visíveis, com opção de filtro e exceções"""
    def foreach_window(hwnd, lParam):
        if not IsWindowVisible(hwnd):
            return True

        length = GetWindowTextLength(hwnd)
        buff = ctypes.create_unicode_buffer(length + 1)
        GetWindowText(hwnd, buff, length + 1)
        title = buff.value or "<sem título>"
        titulo_lower = title.lower()

        # Filtro
        if filtro_palavra and filtro_palavra.lower() not in titulo_lower:
            return True

        # Exceções
        if excecoes and any(exc.lower() in titulo_lower for exc in excecoes):
            return True

        print(f"\n🪟 Janela detectada: {title} | Handle: {hwnd}")
        listar_controles(hwnd, title)
        return True

    EnumWindows(EnumWindowsProc(foreach_window), 0)


if __name__ == "__main__":
    print("=== 🔍 Monitor de Janelas ===\n")
    print("1️⃣  Procurar por uma palavra específica (ex: Clipp)")
    print("2️⃣  Listar todas as janelas\n")

    escolha = input("Escolha uma opção (1 ou 2): ").strip()

    if escolha == "1":
        filtro = input("\n🔎 Digite a palavra para procurar (ex: clipp): ").strip()
        excecoes_raw = input("🚫 Digite exceções separadas por vírgula (ou deixe vazio): ").strip()
        excecoes = [e.strip() for e in excecoes_raw.split(",") if e.strip()]
        print(f"\nBuscando janelas que contenham '{filtro}' (ignorando {excecoes or 'nenhuma'})...\n")
    else:
        filtro = None
        excecoes_raw = input("🚫 Digite exceções separadas por vírgula (ou deixe vazio): ").strip()
        excecoes = [e.strip() for e in excecoes_raw.split(",") if e.strip()]
        print(f"\n📋 Listando todas as janelas visíveis do sistema e (ignorando {excecoes or 'nenhuma'})...\n")

    try:
        while True:
            listar_janelas(filtro, excecoes)
            print("\n⏳ Aguardando 60 segundos para próxima varredura...\n")
            time.sleep(60)
    except KeyboardInterrupt:
        print("\nEncerrado pelo usuário.")
