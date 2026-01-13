"""
Refatoração inicial de automacao.py — foco em:
- Transformar "Abrir o Clipp" em função que só retorna quando o Clipp realmente abriu.
- Extrair o monitor de "Aviso de Segurança" para um watcher rodando em background (thread daemon)
  que tenta interagir automaticamente com as janelas de SmartScreen/Aviso.

Objetivo: manter comportamento atual, mas facilitar testes e correções locais
(mais funções menores, sinalização entre fluxo principal e watcher).
"""

import os, time, threading, traceback, json, pyautogui, psutil, sys
from fecharClipp import fechar_clipp_e_confirmar_backup_refatorado
from pathlib import Path
from pywinauto import Desktop, Application
from utils import get_config_path
from tentar_login_refatorado import tentar_login_refatorado
from winutils import get_desktop, safe_click
from backup_watcher import BackupWatcher
from utils import log, salvar_screenshot, APPDATA, LOG_DIR, LOG_FILE, find_and_click_information_ok

backup_watcher = BackupWatcher()
sys.path.append(str(Path(__file__).parent))

# --- SecurityWatcher: roda em background e interage com avisos de segurança automaticamente ---
class SecurityWatcher:
    """Classe que monitora janelas de aviso de segurança (SmartScreen / Aviso do Windows)
    e tenta clicar nos botões necessários (ex: Esconder "Mais informações" + "Executar assim mesmo").

    Comunicação com o fluxo principal:
    - self.handled_event é acionado sempre que o watcher interagiu com um aviso.
    - self.running_event indica que o watcher está em execução.
    """

    def __init__(self, backend="win32", poll_interval=1.0):
        self.backend = backend
        self.poll_interval = poll_interval
        self._stop_event = threading.Event()
        self._thread = None
        self.handled_event = threading.Event()
        self.running_event = threading.Event()

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="SecurityWatcher")
        self._thread.start()
        # Espera um breve momento até a thread marcar como em execução
        start_time = time.time()
        while time.time() - start_time < 3 and not self.running_event.is_set():
            time.sleep(0.05)

    def stop(self, timeout=3):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=timeout)

    def is_running(self):
        return self._thread is not None and self._thread.is_alive()

    def _run(self):

        desktop = get_desktop(self.backend)
        self.running_event.set()
        log("🔒 SecurityWatcher iniciado (thread daemon).")

        try:
            while not self._stop_event.is_set():
                try:
                    for w in desktop.windows():
                        try:
                            title = (w.window_text() or "").lower()
                        except Exception:
                            continue

                        # Palavras-chave do aviso de segurança
                        if any(k in title for k in ("aviso de segurança", "segurança do windows", "smartscreen", "abrir arquivo")):
                            log(f"⚠️ SecurityWatcher: janela detectada: '{w.window_text()}'.")

                            try:
                                w.set_focus()

                                # 🔹 Tenta localizar o botão “Executar”
                                btn_executar = None
                                for c in w.children():
                                    texto = (c.window_text() or "").strip().lower()
                                    classe = c.element_info.class_name
                                    if classe == "Button" and ("executar" in texto or "&executar" in texto):
                                        btn_executar = c
                                        break

                                if btn_executar:
                                    log("🟢 SecurityWatcher: botão 'Executar' encontrado, tentando clicar sem mover o mouse...")
                                    if safe_click(btn_executar):
                                        self.handled_event.set()
                                        threading.Timer(0.2, lambda: self.handled_event.clear()).start()
                                        log("✅ SecurityWatcher: aviso tratado com sucesso (clicou em Executar).")
                                        time.sleep(2)
                                        continue
                                    else:
                                        log("⚠️ SecurityWatcher: não conseguiu clicar sem mover; fallback pyautogui (teclas).")
                                        pyautogui.press("left"); time.sleep(0.1); pyautogui.press("enter")
                                        self.handled_event.set()
                                        threading.Timer(0.2, lambda: self.handled_event.clear()).start()


                            except Exception as e:
                                log(f"❌ SecurityWatcher erro ao interagir: {e}")
                                salvar_screenshot("securitywatcher_error")

                    time.sleep(self.poll_interval)

                except Exception:
                    log("⚠️ SecurityWatcher encontrou exceção interna, continuando")
                    time.sleep(1)
        finally:
            self.running_event.clear()
            log("🟢 SecurityWatcher encerrado.")


# --- Função refatorada para abrir o Clipp e garantir que ele abriu antes de retornar ---
def abrir_clipp_com_tratativa_refatorado(exe_path: Path, watcher: SecurityWatcher = None, timeout_open: int = 30) -> bool:
    """
    Abre o executável do Clipp e retorna apenas quando detectar que o Clipp realmente abriu.

    Args:
        exe_path: Path para o executável do Clipp.
        watcher: instância de SecurityWatcher (opcional). Se fornecida, o watcher
                 deverá já estar executando. Se None, a função inicializará um watcher
                 temporário que será interrompido ao final.
        timeout_open: segundos de timeout para considerar que o Clipp não abriu.

    Retorna:
        True se o Clipp abriu; False caso contrário.
    """

    nome_exe = exe_path.name

    # Mata processos antigos com o mesmo nome
    for p in psutil.process_iter(['pid', 'name']):
        try:
            if p.info['name'] and p.info['name'].lower() == nome_exe.lower():
                log(f"Encerrando processo antigo PID{p.info['pid']}")
                try:
                    p.kill()
                except Exception:
                    pass
        except Exception:
            continue

    watcher_interno = False
    if watcher is None:
        watcher = SecurityWatcher()
        watcher.start()
        watcher_interno = True
    else:
        # se watcher fornecido mas não estiver rodando, iniciá-lo
        if not watcher.is_running():
            watcher.start()

    desktop = Desktop(backend="win32")

    def clipp_esta_aberto():
        # Verifica por processo ou por janela cujo título contenha 'clipp'
        for p in psutil.process_iter(['name']):
            try:
                if p.info['name'] and 'clipp' in p.info['name'].lower():
                    return True
            except Exception:
                continue
        for w in desktop.windows():
            try:
                if 'clipp' in (w.window_text() or "").lower():
                    return True
            except Exception:
                continue
        return False

    try:
        # Inicia o executável
        os.chdir(exe_path.parent)
        log(f"Iniciando {exe_path.name} no diretório {exe_path.parent}")
        try:
            app = Application(backend="win32").start(f'"{exe_path}"', work_dir=str(exe_path.parent), timeout=30)
        except Exception as e_start:
            log(f"❌ Falha ao iniciar aplicativo: {e_start}")
            salvar_screenshot("erro_iniciar_clipp")
            if watcher_interno:
                watcher.stop()
            return False

        # Aguarda até que o Clipp apareça (processo + janela) ou até o timeout
        t0 = time.time()
        while time.time() - t0 < timeout_open:
            # Se detectado que o Clipp está aberto, podemos sair
            if clipp_esta_aberto():
                log("✅ Clipp detectado como aberto.")
                if watcher_interno:
                    # opcional: manter watcher rodando ou parar aqui se preferir
                    # watcher.stop()
                    pass
                return True

            # Se houver um aviso de segurança, o fluxo principal identifica e dá um tempo
            # para o watcher atuar, sem bloquear indefinidamente.
            aviso_presente = False
            for w in desktop.windows():
                try:
                    title = (w.window_text() or "").lower()
                except Exception:
                    continue
                if any(k in title for k in ("aviso de segurança", "segurança do windows", "smartscreen")):
                    aviso_presente = True
                    log("⚠️ Aviso de segurança detectado pelo fluxo principal — aguardando SecurityWatcher agir...")
                    # Espera até que o watcher sinalize que tratou (ou timeout curto)
                    handled = watcher.handled_event.wait(timeout=12)
                    if handled:
                        log("✅ Fluxo principal: watcher sinalizou que tratou o aviso.")
                    else:
                        log("⚠️ Fluxo principal: watcher não sinalizou dentro do timeout; prosseguindo checagens.")
                    break

            if not aviso_presente:
                # pequeno sleep para não consumir CPU
                time.sleep(0.5)
            # volta a checar

        log(f"❌ Timeout ({timeout_open}s) aguardando Clipp abrir.")
        if watcher_interno:
            watcher.stop()
        return False

    except Exception as e:
        salvar_screenshot("erro_abertura_clipp")
        log(f"Erro ao abrir Clipp com tratativa: {e}")
        log(traceback.format_exc())
        if watcher_interno:
            watcher.stop()
        return False
    
def executar_backup_completo(config_path: Path | None = None) -> str:
    """
    Executa o fluxo completo do backup:
      1. Lê config.json
      2. Abre o Clipp (com tratativa de aviso de segurança)
      3. Faz login
      4. Fecha o Clipp e confirma o backup
      5. Aguarda a conclusão do backup detectada pelo watcher
      6. Move os arquivos do backup para a pasta designada

    Retorna:
        "done"   -> backup concluído com sucesso
        "reset"  -> erro de login, tentar novamente
        "erro"   -> falha geral / timeout / qualquer outro erro
    """

    try:
        # --- 1. Carregar config.json ---
        if config_path is None:
            config_path = get_config_path()

        if not config_path.exists():
            log(f"❌ Arquivo de configuração não encontrado em {config_path}")
            return "erro"

        with open(config_path, "r", encoding="utf-8") as f:
            conf = json.load(f)

        exe_path = Path(conf.get("aplicativo", ""))
        usuario = conf.get("usuario", "SUPERVISOR")
        senha = conf.get("senha", "")

        if not exe_path.exists():
            log(f"❌ Caminho inválido do Clipp: {exe_path}")
            return "erro"

        log(f"🚀 Iniciando backup completo para o usuário '{usuario}'")

        # --- 2. Iniciar watchers ---
        watcher = SecurityWatcher()
        watcher.start()
        backup_watcher = BackupWatcher()

        # --- 3. Abrir Clipp ---
        if not abrir_clipp_com_tratativa_refatorado(exe_path=exe_path, watcher=watcher):
            log("❌ Falha ao abrir o Clipp. Abortando backup.")
            watcher.stop()
            return "erro"

        # --- 4. Fazer login ---
        login_ok = tentar_login_refatorado(usuario=usuario, senha=senha, timeout=45)
        if login_ok == "reset":
            log("⚠️ Falha no login. Solicitando reinício.")
            watcher.stop()
            return "reset"
        elif not login_ok:
            log("❌ Falha ao fazer login no Clipp.")
            watcher.stop()
            return "erro"

        log("✅ Login efetuado com sucesso.")

        # --- 5. Fechar Clipp e confirmar backup ---
        log("📦 Fechando Clipp e aguardando confirmação de backup...")
        if not fechar_clipp_e_confirmar_backup_refatorado(usuario=usuario, backup_watcher=backup_watcher):
            log("⚠️ Falha ao confirmar backup automaticamente.")
            watcher.stop()
            backup_watcher.stop()
            return "erro"

        # --- 6. Esperar conclusão do backup ---
        log("⏳ Aguardando conclusão do backup...")
        backup_watcher.completed_event.wait(timeout=backup_watcher.timeout_total)

        from backup_manager import gerenciar_backup
        if backup_watcher.completed_event.is_set():
            log("Backup finalizado — nenhum arquivo adicional será criado.")
            gerenciar_backup(backup_dir=conf.get("backupDir", "D:\\BACKUP"), log=log, esperado_minimo=1)
            watcher.stop()
            backup_watcher.stop()
            return "done"
        else:
            log("⚠️ Timeout aguardando conclusão do backup.")
            watcher.stop()
            backup_watcher.stop()
            return "erro"

    except Exception as e:
        import traceback
        log(f"❌ Erro inesperado em executar_backup_completo: {e}")
        log(traceback.format_exc())
        return "erro"
