import os, json
import re
import uuid
from datetime import datetime
from pathlib import Path
import pyautogui, threading
import ctypes
import time
from pywinauto import Application, Desktop

APPDATA = Path(os.getenv("APPDATA", Path.home() / "AppData/Roaming"))
LOG_DIR = APPDATA / "BackupBot" / "relatorios"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "backup_log.txt"
LOG_JSON = LOG_DIR / "backup_log.jsonl"

_SESSION_ID = uuid.uuid4().hex
_CURRENT_RUN_ID = None

_START_RE = re.compile(r"Iniciando backup completo", re.IGNORECASE)
_SUCCESS_RE = re.compile(r"backup conclu[ií]do com sucesso", re.IGNORECASE)
_FAIL_RE = re.compile(r"falha|erro|timeout|n[aã]o detectei|n[aã]o foi poss[ií]vel", re.IGNORECASE)
    
def get_config_path() -> Path:
    try:
        appdata = Path(os.getenv("APPDATA")) / "BackupBot"
        appdata.mkdir(parents=True, exist_ok=True)
        ctypes.windll.kernel32.SetFileAttributesW(str(appdata), 2)  # deixa oculto
        config_path = appdata / "config.json"

        # se não existir, cria base
        if not config_path.exists():
            default_path = Path(__file__).parent / "config.json"
            if default_path.exists():
                config_path.write_text(default_path.read_text(encoding="utf-8"), encoding="utf-8")
            else:
                config_path.write_text("{}", encoding="utf-8")

        return config_path
    except Exception:
        return Path(__file__).parent / "config.json"

_conf_path = get_config_path()

BM_CLICK = 0x00F5

def carregar_config():
    global conf
    with open(_conf_path, encoding="utf-8") as f:
        conf = json.load(f)
    return conf

def _click_control_no_mouse(ctrl) -> bool:
    """
    Tenta clicar num controle sem mover o mouse:
      1) invoke() (se exposto)
      2) wrapper_object().click()
      3) PostMessageW(BM_CLICK) no handle do controle
      4) fallback: click_input() (move o mouse)
    Retorna True se algum método funcionou.
    """
    try:
        # 1) invoke()
        if hasattr(ctrl, "invoke"):
            try:
                ctrl.invoke()
                return True
            except Exception:
                pass

        # 2) wrapper.click()
        try:
            wrapper = getattr(ctrl, "wrapper_object", lambda: ctrl)()
            if hasattr(wrapper, "click"):
                wrapper.click()
                return True
        except Exception:
            pass

        # 3) PostMessageW BM_CLICK
        try:
            h = None
            if hasattr(ctrl, "handle"):
                h = int(getattr(ctrl, "handle"))
            else:
                h = int(getattr(getattr(ctrl, "element_info", ctrl), "handle", 0))
            if h:
                ctypes.windll.user32.PostMessageW(h, BM_CLICK, 0, 0)
                return True
        except Exception:
            pass

        # 4) fallback
        try:
            ctrl.click_input()
            return True
        except Exception:
            pass

    except Exception:
        pass

    return False

def find_and_click_information_ok(logger=None, timeout: int = 8) -> bool:
    """
    Procura por uma janela cujo título contenha 'informação' ou 'information' e tenta clicar no botão OK.
    Retorna True se clicou no OK.
    """
    desktop = Desktop(backend="win32")
    t0 = time.time()

    if logger is None:
        def logger(msg): print(msg)

    while time.time() - t0 < timeout:
        for w in desktop.windows():
            try:
                titulo = (w.window_text() or "").strip().lower()
            except Exception:
                continue
            if "informação" in titulo or "informacao" in titulo or "information" in titulo:
                logger(f"🪟 Janela detectada: {w.window_text()} | Handle: {w.handle}")
                try:
                    app = Application(backend="win32").connect(handle=w.handle)
                    dlg = app.window(handle=w.handle)

                    # 1) tenta children() diretos
                    for c in dlg.children():
                        try:
                            txt = (c.window_text() or "").strip().lower()
                            cls = getattr(c.element_info, "class_name", "")
                            if cls == "Button" and "ok" in txt:
                                logger(f"🎯 Botão OK encontrado (handle {getattr(c,'handle', None)}). Tentando clicar sem mover o mouse...")
                                ok = _click_control_no_mouse(c)
                                if ok:
                                    logger("✅ OK clicado com sucesso.")
                                    return True
                        except Exception:
                            pass

                    # 2) tenta descendants() (mais profundo)
                    for c in dlg.descendants():
                        try:
                            txt = (c.window_text() or "").strip().lower()
                            cls = getattr(c.element_info, "class_name", "")
                            if cls == "Button" and "ok" in txt:
                                logger(f"🎯 (descendant) Botão OK encontrado (handle {getattr(c,'handle', None)}). Tentando clicar...")
                                ok = _click_control_no_mouse(c)
                                if ok:
                                    logger("✅ OK clicado com sucesso (descendant).")
                                    return True
                        except Exception:
                            pass

                    # 3) fallback: postar BM_CLICK no primeiro Button que encontrar (sem checar texto)
                    for c in dlg.children():
                        try:
                            cls = getattr(c.element_info, "class_name", "")
                            if cls == "Button":
                                h = int(getattr(c, "handle", getattr(c.element_info, "handle", 0)))
                                if h:
                                    ctypes.windll.user32.PostMessageW(h, BM_CLICK, 0, 0)
                                    logger("⚠️ Fallback PostMessageW(BM_CLICK) enviado para um Button.")
                                    return True
                        except Exception:
                            pass

                    # 4) por fim, envia ENTER para a janela (fallback final)
                    try:
                        dlg.set_focus()
                        dlg.type_keys("{ENTER}")
                        logger("⚠️ Fallback: ENTER enviado para a janela de informação.")
                        return True
                    except Exception:
                        pass

                except Exception as e:
                    logger(f"⚠️ Erro ao tentar fechar janela de informação: {e}")
                    # tentar next window
                # se chegou até aqui, esperar um pouco e tentar de novo
        time.sleep(0.6)
    return False

def _update_run_context(mensagem: str):
    global _CURRENT_RUN_ID
    event = None

    if _START_RE.search(mensagem):
        _CURRENT_RUN_ID = uuid.uuid4().hex
        event = "BACKUP_START"
    elif _SUCCESS_RE.search(mensagem):
        event = "BACKUP_DONE"
        _CURRENT_RUN_ID = None
    elif _FAIL_RE.search(mensagem):
        event = "BACKUP_FAIL"
        _CURRENT_RUN_ID = None

    return _CURRENT_RUN_ID, event

def _write_json_log(ts: str, mensagem: str, run_id: str | None, event: str | None):
    payload = {
        "ts": ts,
        "session_id": _SESSION_ID,
        "run_id": run_id,
        "event": event,
        "message": mensagem,
    }
    try:
        with open(LOG_JSON, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass

def log(mensagem: str):
    ts = datetime.now().isoformat(sep=' ', timespec='seconds')
    run_id, event = _update_run_context(mensagem)
    linha = f"{ts} - {mensagem}\n"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(linha)
    except Exception:
        pass
    _write_json_log(ts, mensagem, run_id, event)
    print(linha.strip())

def salvar_screenshot(prefixo="erro"):
    try:
        pasta_relatorios = LOG_DIR
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_arquivo = f"{prefixo}_{timestamp}.png"
        caminho_completo = pasta_relatorios / nome_arquivo
        screenshot = pyautogui.screenshot()
        screenshot.save(caminho_completo)
        log(f"📸 Screenshot salvo em: {caminho_completo}")
        return caminho_completo
    except Exception as e:
        print(f"❌ Falha ao salvar screenshot: {e}")
        return None
