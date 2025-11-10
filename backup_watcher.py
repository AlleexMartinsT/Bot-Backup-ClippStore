import time, threading, pyautogui, traceback, json, os
from datetime import datetime
from pathlib import Path
from utils import log, salvar_screenshot, find_and_click_information_ok, APPDATA, LOG_DIR

class BackupWatcher:
    """
    Monitora o progresso do backup do Clipp:
    - Aguarda a criação e estabilização dos arquivos de backup
    - Detecta e fecha automaticamente a janela 'Informação'
    - Ajusta dinamicamente o timeout com base no tempo gasto
    """

    def __init__(self, poll_interval: float = 2.0, timeout_total: int = 7200):
        self.poll_interval = poll_interval
        self.timeout_total = timeout_total
        self._stop_event = threading.Event()
        self._thread = None
        self.completed_event = threading.Event()
        self.running_event = threading.Event()

        appdata = Path(os.getenv("APPDATA", Path.home() / "AppData/Roaming"))
        stats_dir = appdata / "BackupBot" / "relatorios"
        stats_dir.mkdir(parents=True, exist_ok=True)
        self.stats_path = LOG_DIR / "backup_stats.json"

        self.timeout_total = self._carregar_timeout(default_timeout=self.timeout_total)

    # --- Configuração adaptativa ---
    def _carregar_timeout(self, default_timeout):
        if self.stats_path.exists():
            try:
                data = json.loads(self.stats_path.read_text(encoding="utf-8"))
                return data.get("ultimo_timeout", default_timeout)
            except Exception:
                pass
        return default_timeout

    def _salvar_stats(self, novo_timeout=None, duracao=None):
        self.stats_path.parent.mkdir(parents=True, exist_ok=True)
        data = {}

        if self.stats_path.exists():
            try:
                data = json.loads(self.stats_path.read_text(encoding="utf-8"))
            except Exception:
                data = {}

        historico = data.get("historico", [])
        if duracao is not None:
            historico.append({
                "data": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "duracao_seg": round(duracao, 1)
            })
            historico = historico[-5:]

        if novo_timeout:
            data["ultimo_timeout"] = novo_timeout
        elif "ultimo_timeout" not in data:
            data["ultimo_timeout"] = self.timeout_total

        data["historico"] = historico
        self.stats_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    # --- Controle de thread ---
    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="BackupWatcher")
        self._thread.start()
        start = time.time()
        while time.time() - start < 3 and not self.running_event.is_set():
            time.sleep(0.05)

    def stop(self, timeout=5):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=timeout)

    def is_running(self):
        return self._thread and self._thread.is_alive()

    # --- Função principal ---
    def _run(self):
        self.running_event.set()
        log(f"🧩 BackupWatcher iniciado (timeout atual: {self.timeout_total}s).")
        self.inicio_backup = time.time()
        ultimo_check_info = 0  # ← controle para espaçar a verificação da janela "Informação"

        try:
            while not self._stop_event.is_set():
                tempo_decorrido = time.time() - self.inicio_backup
                if tempo_decorrido > self.timeout_total:
                    log(f"⚠️ Tempo limite de {self.timeout_total}s atingido sem concluir o backup.")
                    break

                # 🔹 1) Verificar a janela 'Informação' apenas a cada 30 segundos
                if time.time() - ultimo_check_info > 30:
                    ultimo_check_info = time.time()
                    try:
                        if find_and_click_information_ok(logger=log, timeout=3):
                            duracao = time.time() - self.inicio_backup
                            log(f"✅ Backup concluído (janela 'Informação' detectada e fechada em {duracao:.1f}s).")
                            self._ajustar_timeout(duracao)
                            self.completed_event.set()
                            break
                    except Exception as e:
                        log(f"⚠️ Erro ao tentar fechar janela 'Informação': {e}")

                # 🔹 2) Verificar arquivos de backup estáveis
                try:
                    backup_dir = Path(os.getenv("BACKUP_DIR", "D:\\BACKUP"))

                    # 🔹 Verifica se o diretório existe antes de tentar listar
                    if not backup_dir.exists():
                        log(f"❌ Diretório de backup não encontrado: {backup_dir}")
                        import ctypes
                        ctypes.windll.user32.MessageBoxW(
                            0,
                            "⚠️ O backup não pode ser concluído pois a pasta de backup não foi encontrada.\n\n"
                            "Verifique se a pasta de backup do Clipp e do Aplicativo de Backup estão sincronizados.",
                            "Erro de Backup",
                            0x10  # Ícone de erro (MB_ICONERROR)
                        )
                        salvar_screenshot("erro_pasta_backup_inexistente")
                        # encerra o watcher com segurança
                        self._stop_event.set()
                        break

                    hoje = datetime.now().strftime("%d%m%Y")
                    padrao = f"CLIPP{hoje}"
                    arquivos = [f for f in os.listdir(backup_dir)
                                if f.startswith(padrao) and f.endswith(".zip")]

                    if arquivos:
                        estaveis = True
                        for nome in arquivos:
                            caminho = backup_dir / nome
                            tamanho_inicial = caminho.stat().st_size
                            time.sleep(3)
                            if not caminho.exists() or caminho.stat().st_size != tamanho_inicial:
                                estaveis = False
                                break

                        if estaveis:
                            duracao = time.time() - self.inicio_backup
                            log(f"✅ Arquivos de backup detectados e estáveis ({len(arquivos)}): {arquivos}")
                            self._ajustar_timeout(duracao)
                            try:
                                find_and_click_information_ok(logger=log, timeout=3)
                            except Exception:
                                pass
                            self.completed_event.set()
                            break

                except Exception as e:
                    log(f"⚠️ Erro ao verificar arquivos de backup: {e}")

                time.sleep(self.poll_interval)

        except Exception as e:
            salvar_screenshot("erro_backupwatcher")
            log(f"❌ Erro no BackupWatcher: {e}")
            log(traceback.format_exc())

        finally:
            self.running_event.clear()
            log("🟢 BackupWatcher encerrado.")

    # --- Ajuste automático do timeout ---
    def _ajustar_timeout(self, duracao):
        limite_atual = self.timeout_total
        razao = duracao / limite_atual
        novo_timeout = limite_atual

        if razao >= 0.8:
            novo_timeout = int(limite_atual * 1.1)
            log(f"⚙️ Backup demorou {razao*100:.1f}% do limite — aumentando timeout para {novo_timeout}s na próxima execução.")
        elif razao <= 0.3 and limite_atual > 3600:
            novo_timeout = int(limite_atual * 0.9)
            log(f"⚙️ Backup terminou rápido ({razao*100:.1f}% do limite) — reduzindo timeout para {novo_timeout}s.")
        else:
            log(f"✅ Backup dentro do tempo esperado ({duracao:.1f}s de {limite_atual}s).")

        self._salvar_stats(novo_timeout, duracao)
