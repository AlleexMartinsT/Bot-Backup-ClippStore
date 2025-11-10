import time, traceback
from pywinauto import Desktop
from pywinauto.keyboard import send_keys
from datetime import datetime
from pathlib import Path
from utils import log, salvar_screenshot


def fechar_clipp_e_confirmar_backup_refatorado(usuario: str, timeout_backup_confirm: int = 60, backup_watcher=None) -> bool:
    """
    Fecha o Clipp após login e confirma o diálogo 'Cópia de segurança dos dados'.

    Args:
        usuario: nome do usuário logado (ex: "SUPERVISOR")
        timeout_backup_confirm: tempo máximo (segundos) para aguardar a janela de backup.

    Retorna:
        True se conseguiu confirmar o backup, False caso contrário.
    """
    try:
        desktop = Desktop(backend="win32")

        # 🔹 Passo 1 — Localiza a janela principal do Clipp
        log("🔍 Procurando janela principal do Clipp...")
        main_win = None
        for w in desktop.windows():
            titulo = (w.window_text() or "").lower()
            if "clipp" in titulo and f"usuário: {usuario.lower()}" in titulo:
                main_win = w
                break

        if not main_win:
            log(f"⚠️ Não encontrei a janela principal com o usuário '{usuario}'.")
            salvar_screenshot("janela_principal_nao_encontrada")
            return False

        log(f"🪟 Janela principal detectada: {main_win.window_text()} (Handle: {main_win.handle})")

        # 🔹 Passo 2 — Fecha com Alt+F4
        try:
            main_win.set_focus()
            send_keys("%{F4}")  # Alt+F4
            log("🧩 Comando Alt+F4 enviado para fechar o Clipp.")
        except Exception as e_alt:
            salvar_screenshot("erro_altf4")
            log(f"⚠️ Falha ao enviar Alt+F4: {e_alt}")

        # 🔸 Aguarda alguns segundos para permitir que eventuais avisos apareçam
        log("⏳ Aguardando possíveis avisos de segurança antes do backup...")
        time.sleep(5)  # tempo para SecurityWatcher atuar

        # 🔹 Passo 3 — Aguarda a janela de backup aparecer
        log("⏳ Aguardando janela de confirmação de backup...")
        t0 = time.time()
        janela_backup = None

        while time.time() - t0 < timeout_backup_confirm:
            for w in desktop.windows():
                titulo = (w.window_text() or "").strip().lower()
                if any(k in titulo for k in ("cópia de segurança dos dados", "copia de seguranca dos dados")):
                    janela_backup = w
                    break
            if janela_backup:
                break
            time.sleep(1)

        if not janela_backup:
            log("❌ Não detectei a janela 'Cópia de segurança dos dados' dentro do tempo limite.")
            salvar_screenshot("janela_backup_nao_detectada")
            return False

        log(f"🪟 Janela detectada: {janela_backup.window_text()} | Handle: {janela_backup.handle}")

        # 🔹 Passo 4 — Aguarda um pouco mais antes de clicar (para segurança)
        time.sleep(1.5)
        try:
            if backup_watcher:
                if not backup_watcher.is_running():
                    backup_watcher.start()
                    log("🟢 backup_watcher iniciado antes de confirmar 'Sim' (garantia).")
        except Exception as e:
            log(f"⚠️ Falha ao iniciar backup_watcher: {e}")

        # 🔹 Passo 5 — Localiza o botão '&Sim' e clica
        try:
            for ctrl in janela_backup.children():
                texto = (ctrl.window_text() or "").strip().lower()
                classe = ctrl.element_info.class_name
                if classe == "Button" and ("sim" in texto or "&sim" in texto):
                    log(f"🎯 Botão 'Sim' encontrado (Handle: {ctrl.handle}). Clicando...")
                    ctrl.click_input()
                    log("✅ Backup confirmado com sucesso (clicou em 'Sim').")
                    return True

            # fallback: se não achou o botão, tenta ENTER global
            log("⚠️ Botão 'Sim' não encontrado — enviando ENTER como fallback.")
            janela_backup.set_focus()
            send_keys("{ENTER}")
            time.sleep(0.5)
            return True

        except Exception as e_click:
            salvar_screenshot("erro_clicar_sim")
            log(f"❌ Falha ao clicar em 'Sim': {e_click}")
            log(traceback.format_exc())
            return False

    except Exception as e:
        salvar_screenshot("erro_fechar_clipp")
        log(f"❌ Erro inesperado ao fechar Clipp e confirmar backup: {e}")
        log(traceback.format_exc())
        return False