# Runbook — libras2 em produção

## TL;DR

```bash
# checar se tudo está vivo
./scripts/health.sh

# ver logs em tempo real
journalctl -u libras2 -f

# reiniciar
sudo systemctl restart libras2
```

## Onde fica cada coisa no `vareni-8`

| Componente | Path |
|---|---|
| Repo | `/opt/libras2` |
| API (FastAPI) | `127.0.0.1:8088` |
| Dataset V-LIBRASIL | `/opt/libras2/data/vlibrasil/videos/` |
| Cache de vídeos gerados | `/opt/libras2/data/cache/` |
| Logs | `journalctl -u libras2` |
| Swagger UI | `http://vareni-8:8088/docs` |

## Procedimentos

### Reiniciar a API

```bash
sudo systemctl restart libras2
sleep 2
./scripts/health.sh
```

### Adicionar uma palavra ao vocabulário

O V-LIBRASIL não cobre todas as palavras. Para adicionar:

1. Grave 1-3 vídeos curtos (~2s) do sinal, fundo neutro, boa iluminação.
2. Coloque em `/opt/libras2/data/vlibrasil/videos/<palavra>/01.mp4` (e `02.mp4`, etc).
3. Sem acento no nome da pasta (ex: `agua`, não `água`).
4. `sudo systemctl restart libras2` (recarrega índice).
5. Teste: `curl -X POST http://127.0.0.1:8088/translate -d '{"text":"..."}'`

### Disco cheio

O cache de vídeos gerados cresce. Rotação automática via cron:

```cron
0 3 * * * /opt/libras2/scripts/rotate-cache.sh 7
```

Manual:

```bash
du -sh /opt/libras2/data/cache
/opt/libras2/scripts/rotate-cache.sh 7
```

### Memória alta

O `libras2` tem `MemoryMax=2G` no systemd. Se matar o processo, cheque:

```bash
journalctl -u libras2 -n 50 | grep -i "killed\|memory"
free -h
```

Possíveis culpados:
- Worker do uvicorn segurando o modelo de tradução.
- ffmpeg travado em uma frase muito longa.
- Cache sem rotação.

### Substituir o dataset V-LIBRASIL

```bash
sudo systemctl stop libras2
rm -rf /opt/libras2/data/vlibrasil
python /opt/libras2/scripts/download_vlibrasil.py
sudo systemctl start libras2
./scripts/health.sh
```

### Validar uma frase sem subir o servidor

```bash
source /opt/libras2/venv/bin/activate
python -c "
import sys; sys.path.insert(0, '/opt/libras2/service/src')
from service.translator import Translator
from service.gloss import normalize_pt
t = Translator(data_dir=__import__('pathlib').Path('/opt/libras2/data/vlibrasil'))
text = 'bom dia'
tokens = normalize_pt(text)
gloss, missing = t.to_gloss(tokens)
print(f'tokens={tokens}')
print(f'gloss={gloss}')
print(f'missing={missing}')
"
```

## Métricas pra olhar

- Latência `/translate`: `journalctl -u libras2 | grep translate | tail`
- Falhas: `journalctl -u libras2 | grep -c ERROR`
- Tamanho do cache: `du -sh /opt/libras2/data/cache`
- Tamanho do vocabulário: `curl -s http://127.0.0.1:8088/health | jq .vocab_size`
- Memória: `systemctl status libras2` (linha `Memory:`)

## Backups

O que vale a pena fazer backup (o resto é regenerável):

- `data/vlibrasil/` — dataset, ~3GB. Se perdeu, rebaixe via `scripts/download_vlibrasil.py`.

Sugestão: `borg backup` ou `restic` pro `/opt/libras2/data/vlibrasil`. Diário, retenção 7d.
