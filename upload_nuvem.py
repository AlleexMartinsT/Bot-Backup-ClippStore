# upload_nuvem.py
import os
import subprocess
from pathlib import Path
from datetime import datetime
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
from utils import log

# Ajuste conforme seu ambiente
BASE_DIR = r"C:\BackupBot\backups"
PASTA_NUVEM_ID = "1mTFQP0RMzk8rogI5TU1XdNt4v6DFv0xs" 

def autenticar():
    """Autentica no Google Drive usando pydrive2 e settings.yaml + client_secrets.json."""
    gauth = GoogleAuth()
    # O pydrive2 vai ler settings.yaml por padrão se existir.
    # Se for a primeira vez, abrirá o navegador para autenticar.
    try:
        gauth.LocalWebserverAuth()  # abre navegador e salva credentials.json
    except Exception as e:
        log(f"⚠️ LocalWebserverAuth falhou: {e} — tentando CommandLineAuth (útil em servidores).")
        gauth.CommandLineAuth()
    # SaveCredentialsFile só para garantir
    try:
        gauth.SaveCredentialsFile("credentials.json")
    except Exception:
        pass
    return GoogleDrive(gauth)

def obter_ultima_pasta(base_dir: str) -> Path:
    base = Path(base_dir)
    anos = sorted(base.glob("BACKUP *"))
    if not anos:
        raise FileNotFoundError("Nenhum backup encontrado.")
    ultimo_ano = anos[-1]
    meses = sorted(
        ((ultimo_ano / m) for m in os.listdir(ultimo_ano) if (ultimo_ano / m).is_dir()),
        key=lambda p: p.name
    )
    if not meses:
        raise FileNotFoundError(f"Nenhum mês encontrado dentro de {ultimo_ano}.")
    ultima_pasta_mes = meses[-1]
    pastas_dia = sorted((p for p in ultima_pasta_mes.iterdir() if p.is_dir()), key=os.path.getmtime)
    if not pastas_dia:
        raise FileNotFoundError(f"Nenhum dia encontrado em {ultima_pasta_mes}.")
    return pastas_dia[-1]

def enviar_para_drive(drive, pasta_local: Path, id_pasta_drive: str):
    arquivos = sorted(pasta_local.glob("*.zip"))
    if not arquivos:
        log("Nenhum arquivo ZIP encontrado para upload.")
        return
    for arquivo in arquivos:
        try:
            log(f"☁️ Enviando: {arquivo.name} ...")
            f = drive.CreateFile({'title': arquivo.name, 'parents': [{'id': id_pasta_drive}]})
            f.SetContentFile(str(arquivo))
            f.Upload(param={'supportsAllDrives': True})
            log(f"✅ Upload concluído: {arquivo.name}")
        except Exception as e:
            log(f"❌ Erro ao enviar {arquivo.name}: {e}")

def main():
    try:
        drive = autenticar()
        pasta = obter_ultima_pasta(BASE_DIR)
        log(f"📦 Último backup detectado: {pasta}")
        enviar_para_drive(drive, pasta, PASTA_NUVEM_ID)
        log("☁️ Upload para Google Drive finalizado com sucesso.")
    except Exception as e:
        log(f"⚠️ Erro ao enviar para nuvem: {e}")