import os
import time
import shutil, json
from datetime import datetime
from pathlib import Path

_this_dir = Path(__file__).parent
_conf_path = _this_dir / "config.json"
with open(_conf_path, encoding="utf-8") as f:
    conf = json.load(f)

MESES = [
    "JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO",
    "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO"
]

def criar_pasta_backup(base_dir: str) -> Path:
    hoje = datetime.now()
    ano = hoje.strftime("%Y")
    mes_nome = MESES[hoje.month - 1]
    nome_pasta = hoje.strftime("%d_%m_%Y")
    destino = Path(base_dir) / f"BACKUP {ano}" / mes_nome / nome_pasta
    destino.mkdir(parents=True, exist_ok=True)
    return destino

def _eh_nome_backup(nome: str, padrao: str) -> bool:
    """Retorna True se o nome do arquivo corresponde ao padrão CLIPPddmmyyyy (aceita sufixos após .zip)."""
    # comparação case-insensitive
    n = nome.lower()
    p = padrao.lower()
    if not n.startswith(p):
        return False
    # aceitar se contiver .zip em algum ponto após o prefixo (ex: .zip, .zip_done, .zip.part)
    return ".zip" in n

def _arquivo_estavel(caminho: Path, intervalo: int = 5) -> bool:
    """
    Verifica se arquivo estável: tamanho igual após `intervalo` segundos.
    Retorna True se o arquivo existir e tamanho não mudou na janela de verificação.
    """
    try:
        if not caminho.exists():
            return False
        t1 = caminho.stat().st_size
        time.sleep(intervalo)
        t2 = caminho.stat().st_size
        return t1 == t2
    except Exception:
        return False

def aguardar_arquivos_backup(origem_dir: str, log=print, timeout_seg=900, intervalo=5, esperado=3):
    """
    Aguarda até detectar 'esperado' arquivos CLIPPddmmyyyy*.zip (aceitando sufixos).
    Verifica estabilidade do arquivo antes de considerá-lo.
    """
    inicio = time.time()
    hoje = datetime.now().strftime("%d%m%Y")
    padrao = f"CLIPP{hoje}"

    log(f"Aguardando geração dos arquivos de backup (padrão: {padrao}*, aguardando {esperado})...")
    encontrados = {}

    while time.time() - inicio < timeout_seg:
        try:
            nomes = os.listdir(origem_dir)
        except Exception as e:
            log(f"Erro lendo diretório '{origem_dir}': {e}")
            time.sleep(intervalo)
            continue

        # verifica candidatos que batem no nome
        candidatos = [f for f in nomes if _eh_nome_backup(f, padrao)]
        # checa estabilidade e adiciona aos encontrados se estáveis
        for nome in candidatos:
            if nome in encontrados:
                continue  # já verificado como estável
            caminho = Path(origem_dir) / nome
            if _arquivo_estavel(caminho, intervalo=5):
                encontrados[nome] = caminho
                log(f"Arquivo estável detectado: {nome}")
            else:
                log(f"Arquivo ainda em escrita ou instável: {nome}")

        if len(encontrados) >= esperado:
            lista = sorted(encontrados.keys())
            log(f"Detectados {len(lista)} arquivos de backup estáveis: {lista}")
            return lista  # retorna lista de nomes (strings)
        time.sleep(intervalo)

    log("Timeout esperando arquivos de backup.")
    return []

def mover_arquivos(origem_dir: str, destino_dir: Path, arquivos: list, log=print):
    """Move apenas os arquivos .zip válidos, ignorando *_done ou temporários."""
    for nome in arquivos:
        # ignora arquivos temporários
        if nome.lower().endswith("_done.zip") or nome.lower().endswith(".zip_done") or nome.lower().endswith(".zip.part"):
            # Exclui o arquivo temporario:
            os.remove(Path(origem_dir) / nome)
            log(f"Arquivo temporário excluído: {nome}")
            continue

        origem = Path(origem_dir) / nome
        destino = destino_dir / nome

        # se já existe no destino, gera sufixo para evitar sobrescrever
        if destino.exists():
            stem = destino.stem
            ext = destino.suffix
            i = 1
            while True:
                candidato = destino_dir / f"{stem}_{i}{ext}"
                if not candidato.exists():
                    destino = candidato
                    break
                i += 1

        try:
            shutil.move(str(origem), str(destino))
            log(f"Arquivo movido: {origem.name} → {destino.name}")
        except Exception as e:
            log(f"Erro ao mover {origem.name}: {e}")

def gerenciar_backup(backup_dir: str, log=print):
    """
    Cria a pasta do dia, aguarda a geração dos arquivos de backup e os move.
    Retorna True se tudo ocorreu bem.
    """
    destino = criar_pasta_backup(backup_dir)
    arquivos = aguardar_arquivos_backup(backup_dir, log=log)
    if not arquivos:
        return False
    mover_arquivos(backup_dir, destino, arquivos, log=log)
    log(f"✅ Backup concluído e armazenado em: {destino}")
    return True
