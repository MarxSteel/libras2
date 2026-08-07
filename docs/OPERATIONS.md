# Runbook — vlibras em produção

## TL;DR

```bash
# checar se tudo está vivo
./scripts/health.sh

# ver logs em tempo real
journalctl -u vlibras -f

# reiniciar
sudo systemctl restart vlibras
```

## Onde fica cada coisa no `vareni-8`

| Componente | Path |
|---|---|
| Repo | `/opt/vlibras` |
| API (FastAPI) | `127.0.0.1:8088` |
| Dataset V-LIBRASIL | `/opt/vlibras/data/vlibrasil/videos/` |
| Cache de vídeos gerados | `/opt/vlibras/data/cache/` |
| Logs | `journalctl -u vlibras` |
| Swagger UI | `http://vareni-8:8088/docs` |

## Procedimentos

### Reiniciar a API

```bash
sudo systemctl restart vlibras
sleep 2
./scripts/health.sh
```

### Adicionar uma palavra ao vocabulário

O V-LIBRASIL não cobre todas as palavras. Para adicionar:

1. Grave 1-3 vídeos curtos (~2s) do sinal, fundo neutro, boa iluminação.
2. Coloque em `/opt/vlibras/data/vlibrasil/videos/<palavra>/01.mp4` (e `02.mp4`, etc).
3. Sem acento no nome da pasta (ex: `agua`, não `água`).
4. `sudo systemctl restart vlibras` (recarrega índice).
5. Teste: `curl -X POST http://127.0.0.1:8088/translate -d '{"text":"..."}'`

### Disco cheio

O cache de vídeos gerados cresce. Rotação automática via cron:

```cron
0 3 * * * /opt/vlibras/scripts/rotate-cache.sh 7
```

Manual:

```bash
du -sh /opt/vlibras/data/cache
/opt/vlibras/scripts/rotate-cache.sh 7
```

### Memória alta

O `vlibras` tem `MemoryMax=2G` no systemd. Se matar o processo, cheque:

```bash
journalctl -u vlibras -n 50 | grep -i "killed\|memory"
free -h
```

Possíveis culpados:
- Worker do uvicorn segurando o modelo de tradução.
- ffmpeg travado em uma frase muito longa.
- Cache sem rotação.

### Substituir o dataset V-LIBRASIL

```bash
sudo systemctl stop vlibras
rm -rf /opt/vlibras/data/vlibrasil
python /opt/vlibras/scripts/download_vlibrasil.py
sudo systemctl start vlibras
./scripts/health.sh
```

### Validar uma frase sem subir o servidor

```bash
source /opt/vlibras/venv/bin/activate
python -c "
import sys; sys.path.insert(0, '/opt/vlibras/service/src')
from service.translator import Translator
from service.gloss import normalize_pt
t = Translator(data_dir=__import__('pathlib').Path('/opt/vlibras/data/vlibrasil'))
text = 'bom dia'
tokens = normalize_pt(text)
gloss, missing = t.to_gloss(tokens)
print(f'tokens={tokens}')
print(f'gloss={gloss}')
print(f'missing={missing}')
"
```

## Métricas pra olhar

- Latência `/translate`: `journalctl -u vlibras | grep translate | tail`
- Falhas: `journalctl -u vlibras | grep -c ERROR`
- Tamanho do cache: `du -sh /opt/vlibras/data/cache`
- Tamanho do vocabulário: `curl -s http://127.0.0.1:8088/health | jq .vocab_size`
- Memória: `systemctl status vlibras` (linha `Memory:`)

## Backups

O que vale a pena fazer backup (o resto é regenerável):

- `data/vlibrasil/` — dataset, ~3GB. Se perdeu, rebaixe via `scripts/download_vlibrasil.py`.

Sugestão: `borg backup` ou `restic` pro `/opt/vlibras/data/vlibrasil`. Diário, retenção 7d.
