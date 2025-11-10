# winutils.py
import threading
import ctypes
import time
import pyautogui
from pywinauto import Desktop
from ctypes import wintypes

_thread_local = threading.local()

def get_desktop(backend="win32"):
    """
    Retorna uma instância Desktop por thread (cacheada).
    Isso evita recriar/destruir frequentemente e reduz risco de thread-safety.
    """
    d = getattr(_thread_local, "desktop", None)
    if d is None:
        d = Desktop(backend=backend)
        _thread_local.desktop = d
    return d

# Win32 constants
BM_CLICK = 0x00F5
WM_COMMAND = 0x0111

def _post_bm_click(handle: int) -> bool:
    try:
        ctypes.windll.user32.PostMessageW(wintypes.HWND(handle), BM_CLICK, 0, 0)
        return True
    except Exception:
        return False

def _send_bm_click(handle: int) -> bool:
    try:
        ctypes.windll.user32.SendMessageW(wintypes.HWND(handle), BM_CLICK, 0, 0)
        return True
    except Exception:
        return False

def safe_click(ctrl) -> bool:
    """
    Tenta clicar sem mover o mouse:
    1) invoke() (UIA)
    2) wrapper_object().click()
    3) PostMessageW(BM_CLICK) usando handle
    4) SendMessageW(BM_CLICK) (mais 'sincrono')
    5) fallback: click_input() mas restaura posição do mouse imediatamente depois
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

        # 3) PostMessageW/SendMessageW
        handle = None
        try:
            handle = int(getattr(ctrl, "handle", 0) or getattr(getattr(ctrl, "element_info", ctrl), "handle", 0))
        except Exception:
            handle = 0

        if handle:
            try:
                if _post_bm_click(handle):
                    return True
            except Exception:
                pass
            try:
                if _send_bm_click(handle):
                    return True
            except Exception:
                pass

        # 4) fallback click_input (move mouse) — restaura pos depois
        try:
            orig = pyautogui.position()
            ctrl.click_input()
            # pequena garantia: aguarda um pouco e restaura
            time.sleep(0.15)
            pyautogui.moveTo(orig)
            return True
        except Exception:
            pass

    except Exception:
        pass

    return False
