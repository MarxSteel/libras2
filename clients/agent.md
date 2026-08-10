# Guia do Agente — como chamar a libras2 API

Se você é um agente/LLM e precisa traduzir Português → Libras, este arquivo é pra você.

**Base URL produção**: `http://195.200.0.69:8088` (vareni-8, IP público, ufw 8088)
**Base URL dev**: `http://127.0.0.1:8088` (rodando direto na máquina)
**HTTPS alternativo**: `https://srv1521298.tail00b260.ts.net` (Tailscale Funnel)

> Atualizado em 2026-08-10. Avatar 3D Ícaro do VLibras é o output padrão de vídeo.
> Não precisa de dataset local — o widget oficial sabe renderizar qualquer um dos
> 22.498 sinais do dicionário.

---

## Fluxo recomendado

```
1. /health     → confirma que API tá no ar
2. /glosa      → valida input e vê cobertura (opcional)
3. /translate?output=video   → recebe MP4 com avatar 3D
4. Entrega o MP4 pro usuário
```

---

## 1. Verificar se a API está no ar

```bash
curl -sS http://195.200.0.69:8088/health
```

Resposta esperada:
```json
{
  "status": "ok",
  "vocab_size": 0,
  "dictionary": {"version": "2018.3.1", "platform": "WEBGL"}
}
```

Se `status != "ok"`, **não prossiga**. Reporta pro usuário que a API está fora.

---

## 2. Validar input com `/glosa` (rápido, < 1s)

```bash
curl -sS -X POST http://195.200.0.69:8088/glosa \
    -H 'content-type: application/json' \
    -d '{"text":"bom dia meu nome é Marx"}'
```

Resposta:
```json
{
  "text": "bom dia meu nome é Marx",
  "gloss": ["bom&bom-dia", "meu&meu-nome", "Marx"],
  "backend": "vlibras"
}
```

**Notas sobre o gloss:**
- É uma lista de **gloss tokens**, cada um pode ser uma palavra ou expressão multi-palavra
  (separadas por `&`, ex: `"bom&bom-dia"` = "bom" ou "bom-dia").
- A API oficial VLibras já faz: tokenização, lematização, supressão de pronomes,
  escolha de sinônimos, reordenação SOV (Libras).
- O gloss retornado **é o que vai ser renderizado** em vídeo. Use isso pra confirmar
  antes de gastar 60-200s renderizando.

Exemplos reais:

| Input | Gloss oficial |
|---|---|
| `bom dia` | `bom&bom-dia` |
| `eu gosto de café com leite` | `gostar&gosto cafe leite` |
| `bom dia, meu nome é Marx` | `melhor&bom dia meu&meu-nome Marx` |
| `obrigado meu amigo` | `obrigado&agradecimento meu amigo` |

---

## 3. Gerar vídeo com avatar 3D (60-200s cold, < 1s warm)

```bash
# cold: primeira vez dessa frase
curl -sS -X POST "http://195.200.0.69:8088/translate?output=video" \
    -H 'content-type: application/json' \
    -d '{"text":"obrigado meu amigo"}' \
    -OJ --output saida.mp4

# warm: mesma frase, cache hit
# tempo: < 1s, sai o mesmo arquivo
```

**O que é o vídeo:**
- Avatar 3D **Ícaro** (oficial VLibras) em fullscreen 1920×1080
- Cada sinal do gloss executado pelo avatar
- Legenda com a palavra atual destacada em azul (sincronizada com timing)
- 1.5s de intro + 2.5s por palavra
- Formato: MP4 (libx264) ou GIF (palettegen)

**Quando o cache é hit:**
- Mesmo texto exato (case-sensitive, espaços normalizados) → cache hit
- Texto diferente → cache miss, renderiza do zero

**Para forçar re-render:**
```bash
ssh vareni-8 'rm /opt/libras2/data/cache/widget_$(echo -n "obrigado meu amigo" | sha256sum | cut -c1-16).mp4'
```

---

## 4. Player HTML interativo (preview)

```bash
# gera URL que o usuário pode abrir no browser
open "http://195.200.0.69:8088/signs/play?text=obrigado"
```

- Player HTML standalone
- Embedda widget oficial VLibras
- Avatar 3D interativo, com controles do gov.br
- Útil pra preview antes de gastar tempo renderizando vídeo

---

## 5. Validar vocabulário antes de renderizar

```bash
curl -sS http://195.200.0.69:8088/signs/obrigado/info
```

Resposta:
```json
{
  "word": "obrigado",
  "exists": true,
  "size_bytes": 184320,
  "dictionary": {"version": "2018.3.1", "platform": "WEBGL"}
}
```

**Quando usar:** validar input antes de gastar 60-200s num sinal que talvez
não exista. Pra frases curtas (< 3 palavras) e vocabulário comum, não precisa.

---

## 6. Modelos 3D standalone (`.glb`)

```bash
# baixa o .glb do sinal "obrigado"
curl -o obrigado.glb http://195.200.0.69:8088/signs/obrigado/glb

# abre em https://gltf-viewer.donmccurdy.com/
```

Útil pra integrar o sinal em outro player Three.js ou em Unity próprio.

---

## 7. Snippets prontos

### Python (com httpx)

```python
import httpx

BASE = "http://195.200.0.69:8088"

def to_libras(text: str, fmt: str = "mp4") -> bytes:
    """Traduz PT → Libras e retorna bytes do MP4/GIF."""
    r = httpx.post(
        f"{BASE}/translate?output={fmt}",
        json={"text": text, "format": fmt},
        timeout=300.0,  # cold render pode levar 200s
    )
    r.raise_for_status()
    return r.content

def to_gloss(text: str) -> list[str]:
    """Traduz PT → gloss (uppercase Libras)."""
    r = httpx.post(f"{BASE}/glosa", json={"text": text}, timeout=30.0)
    r.raise_for_status()
    return r.json()["gloss"]

# uso
gloss = to_gloss("bom dia")
print(gloss)  # ['bom&bom-dia']

video = to_libras("bom dia")
with open("bom_dia.mp4", "wb") as f:
    f.write(video)
```

### Node (fetch nativo)

```js
const BASE = "http://195.200.0.69:8088";

async function toLibras(text) {
  const res = await fetch(`${BASE}/translate?output=video`, {
    method: "POST",
    headers: {"content-type": "application/json"},
    body: JSON.stringify({text, format: "mp4"}),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const buf = Buffer.from(await res.arrayBuffer());
  return buf;
}

// uso
const mp4 = await toLibras("obrigado meu amigo");
require("fs").writeFileSync("saida.mp4", mp4);
```

### Shell (com curl + jq)

```bash
#!/bin/bash
# uso: ./traduz.sh "bom dia meu nome é Marx"
set -e
TEXT="$1"
BASE="${LIBRAS2_BASE:-http://195.200.0.69:8088}"

# 1. valida gloss
GLOSS=$(curl -sS -X POST "$BASE/glosa" \
    -H 'content-type: application/json' \
    -d "{\"text\":\"$TEXT\"}" | jq -r '.gloss | join(" ")')
echo "gloss: $GLOSS"

# 2. renderiza MP4
curl -sS -X POST "$BASE/translate?output=video" \
    -H 'content-type: application/json' \
    -d "{\"text\":\"$TEXT\"}" \
    -o saida.mp4
echo "salvo: saida.mp4 ($(stat -c%s saida.mp4) bytes)"
```

---

## 8. Quando NÃO chamar a API

- **Input vazio ou só com pontuação** — `400 empty text after normalization`. Pega isso
  antes de gastar request.
- **Input > 500 chars** — vai dar erro. Trunca no client ou quebra em frases.
- **Mesmo texto em loop** — cache hit é < 1s, mas se você tem N agentes mandando o
  mesmo texto, considere um cache local de MP4.

---

## 9. Quando desistir (não tentar de novo sozinho)

- API retorna 503 (VLibras backend fora) por > 2 min → reporta, espera
- API retorna 500 (renderer quebrou) por > 2 min → reporta, espera
- Render time > 300s (timeout) → reporta, oferece alternativa (URL do player HTML
  pra usuário abrir manualmente)

---

## 10. Próxima fase (Fase 6 do PLAN)

A API vai ser exposta como **MCP tools** via `fastapi-mcp`. Se você é um agente
MCP-aware, em vez de chamar HTTP direto, vai ver as tools:

- `glosa(text: str) → gloss_tokens: list[str]`
- `translate(text: str, format: str = "mp4") → video_url: str, gloss: list[str]`
- `get_sign_info(word: str) → exists: bool, size_bytes: int`
- `get_sign_glb(word: str) → glb_url: str` (modelo 3D standalone)
- `play(text: str) → player_url: str` (player HTML interativo)

Endpoint MCP: `http://195.200.0.69:8088/mcp` (Fase 6, em breve).
