# Guia do Agente — como chamar a libras2 API

Se você é um agente/LLM e precisa traduzir Português → Libras, este arquivo é pra você.

**Base URL**: `http://195.200.0.69:8088` (IP público da `vareni-8`, exposto via ufw allow 8088/tcp)

Alternativas:
- HTTPS via Tailscale Funnel: `https://srv1521298.tail00b260.ts.net`
- Tailscale IP: `http://100.72.235.55:8088` (rede privada)
- Loopback local: `http://127.0.0.1:8088` (rodando direto na vareni-8)

## 1. Verificar se a API está no ar

```bash
curl -sS http://195.200.0.69:8088/health
```

Resposta esperada:
```json
{"status":"ok","vocab_size":1364,"data_dir":"...","cache_dir":"..."}
```

Se `status != "ok"`, **não prossiga**. Reporta pro usuário que a API está fora.

## 2. Verificar cobertura do vocabulário antes de traduzir

```bash
curl -sS http://195.200.0.69:8088/vocab
```

Devolve `{words: [...], size: N}`. Útil pra saber se a palavra do usuário existe.

## 3. Traduzir

### 3a. Só a glosa (não precisa de dataset, funciona AGORA)

```bash
curl -sS -X POST http://195.200.0.69:8088/glosa \
    -H 'content-type: application/json' \
    -d '{"text":"bom dia"}'
```

Resposta (consulta a API oficial do VLibras, com reordenação SOV Libras):
```json
{"text":"bom dia","gloss":["BOM","DIA"],"backend":"vlibras"}
```

Exemplos reais (a API oficial faz supressão de pronomes e escolha de sinônimos):

| Input | Gloss oficial |
|---|---|
| `bom dia` | `BOM DIA` |
| `eu gosto de café com leite` | `GOSTAR CAFE LEITE` |
| `bom dia, meu nome é Marx` | `MELHOR DIA MEU NOME MARX` |

### 3b. Com vídeo (precisa de dataset local)

```bash
curl -sS -X POST http://195.200.0.69:8088/translate \
    -H 'content-type: application/json' \
    -d '{"text":"bom dia","format":"mp4"}'
```

Resposta (com dataset carregado):
```json
{
  "text": "bom dia",
  "gloss": ["bom", "dia"],
  "missing": [],
  "video_url": "/videos/abc123.mp4",
  "format": "mp4",
  "backend": "local",
  "note": null
}
```

Parâmetro `backend`:
- `"local"` (padrão em modo auto) — usa só dataset local
- `"vlibras"` — chama API oficial pra gloss, depois tenta mapear pros vídeos
- `"auto"` — tenta local, cai pra vlibras se gloss vazio

Sem dataset, `/translate` retorna 422 (`missing=[todas palavras]`). Use `/glosa` no lugar.

## 4. Lidar com palavras ausentes (`missing`)

Se `missing` não é vazio, o vídeo só contém os sinais que existem. Avise o usuário
em texto:

```
Traduzi "bom dia café" mas não achei o sinal de "café".
Palavras sem cobertura: café. Soletrei em datilologia.
```

Quando a Fase 3 (datilologia) estiver pronta, esse aviso sai e o vídeo já vem com
a soletração embutida.

## 5. Baixar o vídeo

O `video_url` é relativo. Pra ter o arquivo em mãos:

```bash
curl -sS -OJ http://195.200.0.69:8088/videos/abc123.mp4
# baixa pra ./abc123.mp4
```

## 6. Quando usar `format: gif` vs `mp4`

- `mp4` (~3-10s, ~200KB-2MB): padrão pra maioria dos usos. Qualidade boa.
- `gif` (~3-10s, ~500KB-5MB): pra onde MP4 não é aceito (alguns frontends antigos,
  alguns clients de chat com restrição de tipo). GIF leva mais tempo pra gerar
  (2 passadas do ffmpeg com `palettegen`).

## 7. Snippet Python pronto

```python
import httpx

def to_libras(text: str, fmt: str = "mp4") -> tuple[bytes, dict]:
    base = "http://195.200.0.69:8088"
    r = httpx.post(f"{base}/translate", json={"text": text, "format": fmt}, timeout=30)
    r.raise_for_status()
    meta = r.json()
    media = httpx.get(f"{base}{meta['video_url']}").content
    return media, meta

# uso
video_bytes, meta = to_libras("bom dia")
print(f"gloss={meta['gloss']} missing={meta['missing']}")
# salva: open("out.mp4", "wb").write(video_bytes)
```

## 8. Quando desistir

- API retorna 503/500 por mais de 2 minutos → reporta, não tenta novamente sozinho.
- `vocab_size` é 0 (dataset não carregado) → reporta, não finge que traduziu.
- `missing` cobre **toda** a frase (nenhum sinal achado) → reporta ao usuário que
  a frase não tem cobertura, oferece alternativas se existirem.
