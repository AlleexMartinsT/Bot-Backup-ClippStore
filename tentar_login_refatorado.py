import time
import pyautogui
from pywinauto import Desktop, Application
from utils import log
from pywinauto.findwindows import ElementNotFoundError

def localizar_janela_login() -> object | None:
    """Procura pela janela de login do ClippPro."""
    desktop = Desktop(backend="win32")
    for w in desktop.windows():
        title = (w.window_text() or "").lower()
        if "clipppro" in title and w.is_visible():
            try:
                children = w.children()
                classes = [c.element_info.class_name for c in children]
                if any("TDBLookupComboBox" in c for c in classes) and any("TEdit" in c for c in classes):
                    return w
            except Exception:
                continue
    return None

def localizar_janela_aviso() -> object | None:
    """Procura a janela de erro de login ('Aviso')."""
    desktop = Desktop(backend="win32")
    for w in desktop.windows():
        if w.window_text().strip().lower() == "aviso" and w.is_visible():
            return w
    return None

def tentar_login_refatorado(usuario: str, senha: str, timeout: int = 30) -> bool:
    """Realiza login no ClippPro e trata erro de login automático."""
    log("🔎 Aguardando janela de login do ClippPro...")

    janela_login = None
    tempo_inicial = time.time()

    # 1️⃣ Aguarda a janela de login
    while time.time() - tempo_inicial < timeout:
        janela_login = localizar_janela_login()
        if janela_login:
            break
        time.sleep(1)

    if not janela_login:
        log("⚠️ Janela de login não encontrada dentro do timeout.")
        return False

    log(f"🪟 Janela de login detectada: {janela_login.window_text()}")
    log("🔍 Procurando campos de usuário e senha...")

    try:
        app = Application(backend="win32").connect(handle=janela_login.handle)
        dlg = app.window(handle=janela_login.handle)
        dlg.set_focus()

        user_combo = dlg.child_window(class_name="TDBLookupComboBox")
        senha_edit = dlg.child_window(class_name="TEdit")

        # --- função auxiliar pra digitar ---
        def preencher_campos(u, s):
            user_combo.set_focus()
            pyautogui.hotkey("ctrl", "a")
            pyautogui.press("backspace")
            pyautogui.typewrite(u, interval=0.05)
            pyautogui.press("tab")

            senha_edit.set_focus()
            pyautogui.hotkey("ctrl", "a")
            pyautogui.press("backspace")
            pyautogui.typewrite(s, interval=0.05)
            pyautogui.press("enter")

                # ✅ Primeira tentativa
        preencher_campos(usuario, senha)
        log("✅ Login enviado. Aguardando resposta...")

        desktop = Desktop(backend="win32")
        t0 = time.time()

        # 1️⃣ Espera alguns segundos pra ver se entrou de primeira
        while time.time() - t0 < 6:
            for win in desktop.windows():
                titulo = (win.window_text() or "").lower()
                if f"usuário: {usuario}".lower() in titulo:
                    log("🎉 Login bem-sucedido (janela principal detectada).")
                    return True

            time.sleep(0.5)

        # 2️⃣ Caso não detecte sucesso, checa se apareceu aviso
        aviso = localizar_janela_aviso()
        if aviso:
            log("⚠️ Aviso detectado — login incorreto possivelmente.")
            try:
                log(f"🪟 Janela detectada: {aviso.window_text()} | Handle: {aviso.handle}")

                ok_button = None
                for child in aviso.descendants():
                    if child.element_info.name.strip().lower() == "ok":
                        ok_button = child
                        break

                if ok_button:
                    ok_button.click_input()
                    log("✅ Botão OK clicado com sucesso.")
                else:
                    log("⚠️ Botão OK não encontrado entre os controles.")
            except Exception as e:
                log(f"⚠️ Não foi possível interagir com a janela de aviso: {e}")

            # Espera o aviso fechar antes de prosseguir
            time.sleep(1)
            try:
                aviso.wait_not('visible', timeout=5)
                log("✅ Janela de aviso fechada com sucesso.")
            except Exception:
                log("⚠️ Janela de aviso ainda visível, tentando prosseguir mesmo assim.")

            janela_login.set_focus()

            # Lê o conteúdo atual dos campos (debug)
            try:
                current_user = user_combo.window_text()
                current_pass = senha_edit.window_text()
            except Exception:
                current_user = "<erro leitura>"
                current_pass = "<erro leitura>"

            log(f"🧩 Valores atuais lidos -> Usuário: '{current_user}' | Senha: '{current_pass}'")

            # Corrige e tenta novamente
            if current_user.strip() != usuario.strip() or current_pass.strip() != senha.strip():
                log("🔁 Corrigindo campos e tentando novamente...")
                preencher_campos(usuario, senha)

                # Espera nova tentativa de login
                t0 = time.time()
                while time.time() - t0 < 6:
                    for win in desktop.windows():
                        titulo = (win.window_text() or "").lower()
                        if f"usuário: {usuario.lower()}" in titulo:
                            log("🎉 Segunda tentativa bem-sucedida (janela principal detectada).")
                            return True
                    time.sleep(0.5)

                log("🚫 Segunda tentativa também falhou. Abortando.")
                return False
            else:
                log("⚠️ Campos já estavam corretos. Login possivelmente travado.")
                return False

        log("🎉 Nenhum aviso detectado. Login provavelmente bem-sucedido.")
        return True

    except ElementNotFoundError:
        log("❌ Não foi possível encontrar elementos da tela de login.")
    except Exception as e:
        log(f"⚠️ Erro durante tentativa de login: {e}")

    return False