# interface.py
import customtkinter as ctk
import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from utils import log
from agendador import get_proximo_backup, atualizar_horario_config

_this_dir = Path(__file__).parent
_conf_path = _this_dir / "config.json"
with open(_conf_path, encoding="utf-8") as f:
    conf = json.load(f)

BASED_THEME_PATH = _this_dir / "basedTheme.json"
if BASED_THEME_PATH.exists():
    try:
        ctk.set_default_color_theme(str(BASED_THEME_PATH))
    except Exception:
        pass
ctk.set_appearance_mode("dark")

class InterfaceApp:
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("Backup Bot")
        self.root.geometry("340x100")
        self.root.resizable(False, False)
        self._posicionar_canto()

        # Variáveis
        self.backup_em_andamento = False
        self._stop_event = threading.Event()
        self._popup_aberto = None

        # Conteúdo
        self.labelTempo = ctk.CTkLabel(self.root, text="Próximo backup: --:--")
        self.labelTempo.pack(pady=(12, 6))
        self.btnFrame = ctk.CTkFrame(self.root)
        self.btnFrame.pack(fill="x", padx=12, pady=(0, 12))
        self.btnAlterar = ctk.CTkButton(self.btnFrame, text="Alterar agenda", command=self._alterar_agenda)
        self.btnAlterar.grid(row=0, column=0, padx=6)
        self.btnAgora = ctk.CTkButton(self.btnFrame, text="Fazer agora", command=self._executar_backup_agora)
        self.btnAgora.grid(row=0, column=1, padx=6)

        # Thread de atualização do label
        threading.Thread(target=self._loop_atualizar, daemon=True).start()

    # ----------------- Label/contador -----------------
    def _atualizar_label(self):
        if self.backup_em_andamento:
            self.labelTempo.configure(text="Executando backup agora...")
            return

        proximo = get_proximo_backup()
        if not proximo:
            self.labelTempo.configure(text="Próximo backup: --:--")
            return

        delta = proximo - datetime.now()
        if delta.total_seconds() <= 0:
            self.labelTempo.configure(text="Executando backup agora...")
        else:
            horas, resto = divmod(int(delta.total_seconds()), 3600)
            minutos, segundos = divmod(resto, 60)
            self.labelTempo.configure(text=f"Próximo backup: {horas:02d}:{minutos:02d}:{segundos:02d}")

    def _loop_atualizar(self):
        while not self._stop_event.is_set():
            self._atualizar_label()
            threading.Event().wait(1)

    # ----------------- Backup -----------------
    def _executar_backup_agora(self):
        if self.backup_em_andamento:
            log("Backup já em andamento, ignorando nova execução.")
            return

        def confirmar():
            self._fechar_popup()
            self.backup_em_andamento = True
            threading.Thread(target=self._backup_thread, daemon=True).start()

        self._abrir_popup_unico(lambda: self._popup_confirmar("Deseja executar o backup agora?", confirmar))

    def _backup_thread(self):
        from automacao_refatorado import executar_backup_completo
        sucesso = executar_backup_completo()
        if sucesso:
            log("🎉 Backup concluído com sucesso!")
        else:
            log("❌ Falha ao executar o backup completo.")
        self.backup_em_andamento = False


    # ----------------- Popups -----------------
    def _popup_confirmar(self, texto, callback):
        popup_confirmar = ctk.CTkToplevel(self.root)
        popup_confirmar.title("Confirmar")
        popup_confirmar.geometry("300x100")
        popup_confirmar.resizable(False, False)
        popup_confirmar.transient(self.root)
        self._centralizar(popup_confirmar)

        ctk.CTkLabel(popup_confirmar, text=texto).pack(pady=(12, 8))
        frame = ctk.CTkFrame(popup_confirmar)
        frame.pack(pady=(0, 8))
        ctk.CTkButton(frame, text="Cancelar", command=self._fechar_popup).grid(row=0, column=0, padx=6)
        ctk.CTkButton(frame, text="Confirmar", command=callback).grid(row=0, column=1, padx=6)
        popup_confirmar.bind("<Return>", lambda e: callback())
        popup_confirmar.bind("<Escape>", lambda e: self._fechar_popup())
        return popup_confirmar

    def _abrir_popup_unico(self, criar_func):
        if self._popup_aberto and self._popup_aberto.winfo_exists():
            self._popup_aberto.lift()
            return
        self._popup_aberto = criar_func()
        self._popup_aberto.protocol("WM_DELETE_WINDOW", self._fechar_popup)
        self._popup_aberto.bind("<Escape>", lambda e: self._fechar_popup())
        return self._popup_aberto

    def _fechar_popup(self):
        if self._popup_aberto and self._popup_aberto.winfo_exists():
            self._popup_aberto.destroy()
        self._popup_aberto = None

    # ----------------- Alterar agenda -----------------
    def _alterar_agenda(self):
        def criar():
            popup_tipo = ctk.CTkToplevel(self.root)
            popup_tipo.geometry("280x150")
            popup_tipo.resizable(False, False)
            popup_tipo.transient(self.root)
            self._centralizar(popup_tipo)

            ctk.CTkLabel(popup_tipo, text="Escolha o tipo de alteração:").pack(pady=(12, 8))
            frame = ctk.CTkFrame(popup_tipo)
            frame.pack(pady=(0, 12))

            def alterar_permanente():
                popup_tipo.destroy()
                self._popup_permanente()

            def alterar_proximo():
                popup_tipo.destroy()
                self._popup_hora("proximo")

            ctk.CTkButton(frame, text="Alterar permanentemente", command=alterar_permanente).pack(pady=6)
            ctk.CTkButton(frame, text="Alterar o próximo backup", command=alterar_proximo).pack(pady=6)

            popup_tipo.bind("<Return>", lambda e: alterar_proximo())
            popup_tipo.bind("<Escape>", lambda e: popup_tipo.destroy())
            return popup_tipo

        self._abrir_popup_unico(criar)

    def _popup_permanente(self):
        def criar():
            popup_permanente = ctk.CTkToplevel(self.root)
            popup_permanente.geometry("320x220")
            popup_permanente.resizable(False, False)
            popup_permanente.transient(self.root)
            self._centralizar(popup_permanente)

            ctk.CTkLabel(popup_permanente, text="Escolha qual horário alterar:").pack(pady=(12, 8))
            frame = ctk.CTkFrame(popup_permanente)
            frame.pack(pady=(0, 12))

            def escolher_tipo(tipo):
                popup_permanente.destroy()
                if tipo == "especifico":
                    self._popup_escolher_data()
                elif tipo == "dia_semana":
                    self._popup_escolher_dia_semana()
                else:
                    self._popup_hora(tipo)

            ctk.CTkButton(frame, text="Dias úteis", command=lambda: escolher_tipo("uteis")).pack(pady=6)
            ctk.CTkButton(frame, text="Sábado", command=lambda: escolher_tipo("sabado")).pack(pady=6)
            ctk.CTkButton(frame, text="Dia específico", command=lambda: escolher_tipo("especifico")).pack(pady=6)
            ctk.CTkButton(frame, text="Dia da semana", command=lambda: escolher_tipo("dia_semana")).pack(pady=6)

            popup_permanente.bind("<Escape>", lambda e: popup_permanente.destroy())
            return popup_permanente

        self._abrir_popup_unico(criar)

    def _popup_escolher_dia_semana(self):
        dias = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira",
                "Sexta-feira", "Sábado", "Domingo"]

        def criar():
            popup_dias_semana = ctk.CTkToplevel(self.root)
            popup_dias_semana.geometry("270x320")
            popup_dias_semana.resizable(False, False)
            popup_dias_semana.transient(self.root)
            self._centralizar(popup_dias_semana)

            ctk.CTkLabel(popup_dias_semana, text="Escolha o dia da semana:").pack(pady=(12, 8))
            frame = ctk.CTkFrame(popup_dias_semana)
            frame.pack(pady=(0, 12))

            for dia in dias:
                ctk.CTkButton(frame, text=dia,
                              command=lambda d=dia, p=popup_dias_semana: (p.destroy(), self._popup_hora("dia_semana", dia_semana=d))
                              ).pack(pady=4)

            popup_dias_semana.bind("<Escape>", lambda e: popup_dias_semana.destroy())
            return popup_dias_semana

        self._abrir_popup_unico(criar)

    def _popup_escolher_data(self):
        def confirmar_data():
            data = entry.get()
            try:
                datetime.strptime(data, "%d/%m/%Y")
                popup_data.destroy()
                self._popup_hora("especifico", dia_especifico=data)
            except Exception:
                entry.configure(border_color="red")

        popup_data = ctk.CTkToplevel(self.root)
        popup_data.geometry("300x120")
        popup_data.resizable(False, False)
        popup_data.transient(self.root)
        self._centralizar(popup_data)

        ctk.CTkLabel(popup_data, text="Digite a data (DD/MM/YYYY):").pack(pady=(12, 6))
        entry = ctk.CTkEntry(popup_data, text_color="white", justify="center")
        entry.pack(pady=(0, 8))
        ctk.CTkButton(popup_data, text="Confirmar", command=confirmar_data).pack()

        popup_data.bind("<Return>", lambda e: confirmar_data())
        popup_data.bind("<Escape>", lambda e: popup_data.destroy())

    def _popup_hora(self, tipo: str, dia_especifico: str | None = None, dia_semana: str | None = None):
        def confirmar_hora():
            hora = entry.get()
            try:
                hh, mm = map(int, hora.split(":"))
                print("Alterando próximo backup:", tipo, hora, dia_especifico, dia_semana)
                if not (0 <= hh < 24 and 0 <= mm < 60):
                    raise ValueError
                
                agora = datetime.now()
                proximo = agora.replace(hour=hh, minute=mm, second=0, microsecond=0)
                if proximo <= agora:
                    proximo += timedelta(days=1)
                    
                if dia_semana:
                    atualizar_horario_config("dia_semana", hora, dia_semana=dia_semana)
                elif tipo == "proximo":
                    atualizar_horario_config("proximo", hora)
                else:
                    atualizar_horario_config(tipo, hora, dia_especifico)
                    
                self._atualizar_label()
                popup_hora.destroy()
            except Exception:
                entry.configure(border_color="red")

        popup_hora = ctk.CTkToplevel(self.root)
        popup_hora.geometry("300x120")
        popup_hora.resizable(False, False)
        popup_hora.transient(self.root)
        self._centralizar(popup_hora)

        ctk.CTkLabel(popup_hora, text="Digite o horário (HH:MM):").pack(pady=(12, 6))
        entry = ctk.CTkEntry(popup_hora, text_color="white", justify="center")
        entry.pack(pady=(0, 8))
        ctk.CTkButton(popup_hora, text="Confirmar", command=confirmar_hora).pack()

        popup_hora.bind("<Return>", lambda e: confirmar_hora())
        popup_hora.bind("<Escape>", lambda e: popup_hora.destroy())

    # ----------------- Utils -----------------
    def _validar_hhmm(self, texto):
        if len(texto) != 5 or texto[2] != ":":
            return False
        h, m = texto.split(":")
        if not (h.isdigit() and m.isdigit()):
            return False
        hh, mm = int(h), int(m)
        return 0 <= hh <= 23 and 0 <= mm <= 59

    def _centralizar(self, janela):
        janela.update_idletasks()
        w, h = janela.winfo_width(), janela.winfo_height()
        sw, sh = janela.winfo_screenwidth(), janela.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        janela.geometry(f"{w}x{h}+{x}+{y}")

    def _posicionar_canto(self):
        self.root.update_idletasks()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        w, h = 320, 120
        x = sw - w - 12
        y = sh - h - 48
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def start(self):
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<Escape>", lambda e: self._on_close())
        self.root.mainloop()

    def _on_close(self):
        def criar():
            popup_sair = ctk.CTkToplevel(self.root)
            popup_sair.geometry("320x100")
            popup_sair.resizable(False, False)
            popup_sair.transient(self.root)
            self._centralizar(popup_sair)

            ctk.CTkLabel(popup_sair, text="Tem certeza que deseja fechar o Backup Bot?").pack(pady=(12, 8))
            frame = ctk.CTkFrame(popup_sair)
            frame.pack(pady=(0, 8))

            def confirmar():
                self._fechar_popup()
                self._stop_event.set()
                self.root.destroy()

            ctk.CTkButton(frame, text="Cancelar", command=self._fechar_popup).grid(row=0, column=0, padx=6)
            ctk.CTkButton(frame, text="Fechar", command=confirmar).grid(row=0, column=1, padx=6)
            popup_sair.bind("<Return>", lambda e: confirmar())
            popup_sair.bind("<Escape>", lambda e: self._fechar_popup())
            return popup_sair

        self._abrir_popup_unico(criar)
