# Guia do Agente — como chamar a libras2 API

Se você é um agente/LLM e precisa traduzir Português → Libras, este arquivo é pra você.

## 1. Verificar se a API está no ar

```bash
curl -sS http://vareni-8:8088/health
# ou se rodando local:
curl -sS http://127.0.0.1:8088/health
```

Resposta esperada:
```json
{"status":"ok","vocab_size":1364,"data_dir":"...","cache_dir":"..."}
```

Se `status != "ok"`, **não prossiga**. Reporta pro usuário que a API está fora.

## 2. Verificar cobertura do vocabulário antes de traduzir

```bash
curl -sS http://vareni-8:8088/vocab
```

Devolve `{words: [...], size: N}`. Útil pra saber se a palavra do usuário existe.

## 3. Traduzir

```bash
curl -sS -X POST http://vareni-8:8088/translate \
    -H 'content-type: application/json' \
    -d '{"text":"bom dia","format":"mp4"}'
```

Resposta:
```json
{
  "text": "bom dia",
  "gloss": ["bom", "dia"],
  "missing": [],
  "video_url": "/videos/abc123.mp4",
  "format": "mp4"
}
```

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
curl -sS -OJ http://vareni-8:8088/videos/abc123.mp4
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
    base = "http://vareni-8:8088"
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
