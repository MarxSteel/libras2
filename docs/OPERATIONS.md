# Runbook — vlibras em produção

## TL;DR

```bash
# checar se tudo está vivo
./scripts/health.sh

# ver logs em tempo real
journalctl -u vlibras -f
journalctl --user -u hermes-gateway -f

# reiniciar
sudo systemctl restart vlibras
hermes gateway restart
```

## Onde fica cada coisa no `vareni-8`

| Componente | Path |
|---|---|
| Repo | `/opt/vlibras` |
| API (FastAPI) | `127.0.0.1:8088` |
| Hermes gateway | `~/.hermes/` (user service) |
| Dataset V-LIBRASIL | `/opt/vlibras/data/vlibrasil/videos/` |
| Cache de vídeos gerados | `/opt/vlibras/data/cache/` |
| Logs Libras | `journalctl -u vlibras` |
| Logs WhatsApp | `journalctl --user -u hermes-gateway` |
| Mídia baixada pela skill | `/tmp/vlibras-media/` |

## Procedimentos

### Reiniciar tudo depois de uma mudança

```bash
sudo systemctl restart vlibras
sleep 2
hermes gateway restart
./scripts/health.sh
```

### Adicionar uma palavra ao vocabulário

O V-LIBRASIL não cobre todas as palavras. Para adicionar:

1. Grave 1-3 vídeos curtos (~2s) do sinal, fundo neutro, boa iluminação.
2. Coloque em `/opt/vlibras/data/vlibrasil/videos/<palavra>/01.mp4` (e `02.mp4`, etc).
3. Sem acento no nome da pasta (ex: `agua`, não `água`).
4. `sudo systemctl restart vlibras` (recarrega índice).
5. Teste: `curl -X POST http://127.0.0.1:8088/translate -d '{"text":"..."}'`

### Quando o WhatsApp desconecta

Sintoma: o bot para de responder.

```bash
hermes whatsapp status
# se mostrar "disconnected":
hermes whatsapp relink   # novo QR code aparece no terminal
# escaneie com WhatsApp > Aparelhos conectados > Conectar um aparelho
```

Causa comum: bateria do celular acabou, ou o WhatsApp Web expirou (90 dias de inatividade).

### Banimento do número

O Baileys emula o WhatsApp Web. Se você mandar muito spam ou o Meta sinalizar uso indevido, o número pode ser banido. Mitigações:

- Use um **número dedicado** (chip separado) só pro bot.
- Responda só para números na whitelist (`WHATSAPP_ALLOWED_USERS`).
- Evite mensagens em massa.
- Se banido, recorra em https://www.whatsapp.com/contact/?subject=banido ou troque de número.

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

## Métricas pra olhar

- Latência `/translate`: `journalctl -u vlibras | grep translate | tail`
- Falhas de API: `journalctl -u vlibras | grep -c ERROR`
- Fila do cache: `ls /opt/vlibras/data/cache | wc -l`
- Memória: `systemctl status vlibras` (linha `Memory:`)

## Backups

O que vale a pena fazer backup (o resto é regenerável):

- `data/vlibrasil/` — dataset, ~3GB. Se perdeu, rebaixe via `scripts/download_vlibrasil.py`.
- `~/.hermes/whatsapp/` — credencial do Baileys. Se perdeu, vai ter que re-escanear QR.
- `~/.hermes/memory/` — histórico. Se perdeu, o bot esquece contatos.

Sugestão: `borg backup` ou `restic` pro `/opt/vlibras/data/vlibrasil` + `~/.hermes/whatsapp`. Diário, retenção 7d.
