# agendador.py
import json
import schedule
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from automacao_refatorado import executar_backup_completo
from utils import log, carregar_config

_conf_path = Path(__file__).parent / "config.json"

conf = None
PROXIMO_BACKUP = None  # datetime do próximo backup manual
_lock = threading.Lock()

DIAS_MAP = {
    0: "Segunda",
    1: "Terca",
    2: "Quarta",
    3: "Quinta",
    4: "Sexta",
    5: "Sabado",
    6: "Domingo"
}

tray = None  # variável que será configurada pelo main.py

# ----------------- Backup -----------------
def job_fazer_backup():
    global tray
    log("Agendador: iniciando job de backup agendado.")

    if tray:
        tray.set_status("rodando")

    try:
        sucesso = executar_backup_completo()
        if sucesso == "reset":
            executar_backup_completo()
            if sucesso == "reset":
                log("Agendador: Falha no login após duas tentativas")
                if tray:
                    tray.set_status("erro")
            elif sucesso:
                log("Agendador: backup concluído com sucesso.")
                if tray:
                    tray.set_status("inicio")
            else:
                log("Agendador: backup finalizado com falha/timeout.")
                if tray:
                    tray.set_status("erro")
        else:
            if sucesso == "done":
                log("Agendador: backup concluído com sucesso.")
                if tray:
                    tray.set_status("inicio")
            else:
                log("Agendador: backup finalizado com falha/timeout.")
                if tray:
                    tray.set_status("erro")

    except Exception as e:
        log(f"Agendador: erro ao executar backup: {e}")
        if tray:
            tray.set_status("erro")

# ----------------- Agenda -----------------
def agenda():
    schedule.clear()
    conf = carregar_config()

    for i in range(7):
        dia_nome = DIAS_MAP[i]
        if i < 5:  # segunda a sexta
            chave = f"horario{dia_nome}"
            hora = conf.get(chave, conf.get("horarioSemana", "18:30"))
        elif i == 5:  # sábado
            chave = "horarioSabado"
            hora = conf.get(chave, "13:00")
        else:
            continue  # domingo sem backup

        # agenda a função no schedule
        if i == 0:
            schedule.every().monday.at(hora).do(job_fazer_backup)
        elif i == 1:
            schedule.every().tuesday.at(hora).do(job_fazer_backup)
        elif i == 2:
            schedule.every().wednesday.at(hora).do(job_fazer_backup)
        elif i == 3:
            schedule.every().thursday.at(hora).do(job_fazer_backup)
        elif i == 4:
            schedule.every().friday.at(hora).do(job_fazer_backup)
        elif i == 5:
            schedule.every().saturday.at(hora).do(job_fazer_backup)

    log("Agendador: agenda atualizada.")

# ----------------- Loop principal -----------------
def loopAgendador(stop_event: threading.Event, tray_ref=None):
    global tray
    tray = tray_ref  # salva referência do tray

    agenda()
    while not stop_event.is_set():
        try:
            schedule.run_pending()
            # executa backup manual se PROXIMO_BACKUP chegou
            with _lock:
                global PROXIMO_BACKUP
                if PROXIMO_BACKUP and datetime.now() >= PROXIMO_BACKUP:
                    log("⏰ Chegou o horário manual do próximo backup.")
                    threading.Thread(target=job_fazer_backup, daemon=True).start()
                    PROXIMO_BACKUP = None
        except Exception as e:
            log(f"Agendador erro no run_pending: {e}")
            if tray:
                tray.set_status("erro")
        time.sleep(1)

# ----------------- Próximo backup -----------------
def get_proximo_backup() -> datetime | None:
    now = datetime.now()
    horarios = []

    with _lock:
        if PROXIMO_BACKUP:
            return PROXIMO_BACKUP

        conf = carregar_config()
        for i in range(7):
            dia = (now + timedelta(days=i)).weekday()
            data_dia = now + timedelta(days=i)

            if dia < 5:  # segunda a sexta
                dia_nome = DIAS_MAP[dia]
                chave = f"horario{dia_nome}"
                hora = conf.get(chave, conf.get("horarioSemana","18:30"))
            elif dia == 5:  # sábado
                hora = conf.get("horarioSabado","13:00")
            else:
                continue

            hh, mm = map(int, hora.split(":"))
            dt = data_dia.replace(hour=hh, minute=mm, second=0, microsecond=0)
            if dt > now:
                horarios.append(dt)

    return min(horarios) if horarios else None

# ----------------- Atualizar horário -----------------
def atualizar_horario_config(tipo, hora, dia_especifico=None, dia_semana=None):
    global PROXIMO_BACKUP
    conf = carregar_config()
    
    if tipo == "proximo":
        now = datetime.now()
        hh, mm = map(int, hora.split(":"))
        proximo = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if proximo <= now:
            proximo += timedelta(days=1)  # se passou, adiciona 1 dia
        PROXIMO_BACKUP = proximo
        log(f"Alterando próximo backup para: {PROXIMO_BACKUP.strftime('%d/%m/%Y %H:%M')}")
        return

    elif tipo == "uteis":
        for d in ["Segunda","Terca","Quarta","Quinta","Sexta"]:
            conf[f"horario{d}"] = hora
    elif tipo == "sabado":
        conf["horarioSabado"] = hora
    elif tipo == "dia_semana" and dia_semana:
        chave = f"horario{dia_semana.split('-')[0]}"  # "Segunda-feira" -> "horarioSegunda"
        conf[chave] = hora
    elif tipo == "especifico" and dia_especifico:
        conf[f"horario{dia_especifico}"] = hora
    else:
        return

    with open(_conf_path, "w", encoding="utf-8") as f:
        json.dump(conf, f, indent=2)
    log(f"Configuração atualizada: {tipo} -> {hora}")
