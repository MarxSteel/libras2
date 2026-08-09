# VLibras MCP Server

![VLibras](https://img.shields.io/badge/Libras-Tradutor-blue)
![MCP](https://img.shields.io/badge/Protocol-MCP-green)
![Node](https://img.shields.io/badge/Node.js-20+-green)
![TypeScript](https://img.shields.io/badge/TypeScript-5.3-blue)

**Servidor MCP para tradução PT-BR → Libras e geração de vídeos em Libras.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## Índice

- [Visão Geral](#visão-geral)
- [Arquitetura](#arquitetura)
- [Pré-requisitos](#pré-requisitos)
- [Instalação](#instalação)
- [Configuração](#configuração)
- [Tools (MCP)](#tools-mcp)
- [API REST](#api-rest)
- [Exemplos de Uso](#exemplos-de-uso)
- [Infraestrutura](#infraestrutura)
- [Troubleshooting](#troubleshooting)
- [Contribuindo](#contribuindo)
- [Licença](#licença)

---

## Visão Geral

O **VLibras MCP Server** é um servidor que implementa o [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) para integrar funcionalidades de tradução para Libras (Língua Brasileira de Sinais) em assistentes de IA como Claude Desktop, Cursor, VS Code Copilot e outros.

### Funcionalidades

- **Tradução de Texto**: Converte texto em Português Brasileiro para gloss Libras
- **Geração de Vídeos**: Cria vídeos com avatar interpretando Libras
- **Download de Vídeos**: Obtém o vídeo gerado em formato MP4
- **Cache Inteligente**: Traduções são cacheadas no Redis para performance

---

## Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│                        MCP Client                                │
│              (Claude Desktop / Cursor / VS Code)                 │
└───────────────────────────┬─────────────────────────────────────┘
                            │ MCP Protocol (stdio)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    VLibras MCP Server                            │
│                    (Node.js + TypeScript)                        │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │ translate   │  │ video       │  │ status/download         │ │
│  │ _to_libras  │  │ _generate   │  │ _video                  │ │
│  └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘ │
└─────────┼────────────────┼─────────────────────┼───────────────┘
          │                │                     │
          ▼                ▼                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                      VLibras API                                │
│                   (Node.js / Express)                           │
│                      Porta 3000                                  │
│                                                                 │
│  POST /translate    POST /video    GET /video/status/:uid       │
│  GET /video/download/:uid          GET /healthcheck             │
└─────────┬───────────────────────────────────────┬───────────────┘
          │                                       │
          ▼                                       ▼
┌─────────────────────┐             ┌─────────────────────────────┐
│     RabbitMQ        │             │         MongoDB             │
│   (translate.to_*)  │             │    Armazena traduções       │
└─────────┬───────────┘             └─────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Workers (Python)                              │
│                                                                 │
│  ┌─────────────────────┐    ┌─────────────────────────────┐    │
│  │  vlibras-text-core  │    │   vlibras-video-core        │    │
│  │  (Tradução)         │    │   (Geração de Vídeo)        │    │
│  └─────────────────────┘    └─────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Pré-requisitos

- **Node.js** 20+ (recomendado: LTS)
- **npm** ou **yarn**
- **API VLibras** rodando (porta 3000)
- **MongoDB** (porta 27017)
- **Redis** (porta 6379)
- **RabbitMQ** (porta 5672)

---

## Instalação

### 1. Clone o repositório

```bash
git clone https://github.com/seu-usuario/vlibras-mcp-server.git
cd vlibras-mcp-server
```

### 2. Instale as dependências

```bash
npm install
```

### 3. Compile o TypeScript

```bash
npm run build
```

### 4. Teste a inicialização

```bash
VLIBRAS_API_URL=http://localhost:3000 node dist/index.js
```

Se tudo estiver correto, você verá:
```
VLibras MCP Server running on stdio
API URL: http://localhost:3000
```

---

## Configuração

### Variáveis de Ambiente

| Variável | Default | Descrição |
|----------|---------|-----------|
| `VLIBRAS_API_URL` | `http://localhost:3000` | URL da API VLibras backend |

### Claude Desktop

Edite o arquivo `~/.claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "vlibras": {
      "command": "node",
      "args": ["/caminho/para/vlibras-mcp-server/dist/index.js"],
      "env": {
        "VLIBRAS_API_URL": "http://localhost:3000"
      }
    }
  }
}
```

**Mac/Linux:**
```bash
~/.claude/claude_desktop_config.json
```

**Windows:**
```
%APPDATA%\Claude\claude_desktop_config.json
```

### Cursor

Crie o arquivo `.cursor/mcp.json` na raiz do seu projeto:

```json
{
  "mcpServers": {
    "vlibras": {
      "command": "node",
      "args": ["/caminho/para/vlibras-mcp-server/dist/index.js"],
      "env": {
        "VLIBRAS_API_URL": "http://localhost:3000"
      }
    }
  }
}
```

### VS Code (Copilot)

Adicione ao `settings.json`:

```json
{
  "mcp": {
    "servers": {
      "vlibras": {
        "command": "node",
        "args": ["/caminho/para/vlibras-mcp-server/dist/index.js"],
        "env": {
          "VLIBRAS_API_URL": "http://localhost:3000"
        }
      }
    }
  }
}
```

### Docker

```bash
docker build -t vlibras-mcp-server .
docker run -e VLIBRAS_API_URL=http://host.docker.internal:3000 vlibras-mcp-server
```

---

## Tools (MCP)

### translate_to_libras

Traduz texto em Português Brasileiro para gloss Libras.

**Parâmetros:**

| Parâmetro | Tipo | Obrigatório | Descrição |
|-----------|------|-------------|-----------|
| `text` | string | ✅ | Texto em PT-BR para traduzir (máx. 5000 caracteres) |

**Exemplo de uso:**
```
Usuário: "Traduza 'Bom dia, como você está?' para Libras"
```

**Resposta:**
```
Tradução para Libras (gloss): BOM DIA COMO VOCÊ ESTAR
```

---

### generate_libras_video

Gera vídeo em Libras a partir de um gloss.

**Parâmetros:**

| Parâmetro | Tipo | Obrigatório | Default | Descrição |
|-----------|------|-------------|---------|-----------|
| `gloss` | string | ✅ | - | Gloss Libras para gerar vídeo |
| `avatar` | string | ❌ | `icaro` | Avatar do intérprete (`icaro` ou `hozana`) |
| `caption` | string | ❌ | `off` | Legendas (`on` ou `off`) |

**Exemplo de uso:**
```
Usuário: "Gere um vídeo em Libras com a tradução de 'Olá mundo'"
```

**Resposta:**
```
Vídeo em processamento. Use get_libras_video_status com requestUID: abc-123-def-456
```

---

### get_libras_video_status

Consulta o status de geração de vídeo.

**Parâmetros:**

| Parâmetro | Tipo | Obrigatório | Descrição |
|-----------|------|-------------|-----------|
| `requestUID` | string (UUID) | ✅ | UID retornado por `generate_libras_video` |

**Status possíveis:**

| Status | Descrição |
|--------|-----------|
| `queued` | Na fila de processamento |
| `processing` | Processando |
| `generated` | Vídeo pronto para download |
| `failed` | Falha na geração |
| `expired` | Vídeo expirado |

**Exemplo de resposta:**
```json
{
  "status": "generated",
  "size": 2048576
}
```

---

### download_libras_video

Faz o download do vídeo gerado.

**Parâmetros:**

| Parâmetro | Tipo | Obrigatório | Descrição |
|-----------|------|-------------|-----------|
| `requestUID` | string (UUID) | ✅ | UID do vídeo gerado |

**Retorno:** Vídeo em formato base64 (MP4)

---

## API REST

O MCP Server é um wrapper sobre a API REST VLibras. Você também pode usar a API diretamente:

### Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| `POST` | `/translate` | Traduz texto para gloss Libras |
| `POST` | `/video` | Gera vídeo em Libras |
| `GET` | `/video/status/:uid` | Status do vídeo |
| `GET` | `/video/download/:uid` | Download do vídeo MP4 |
| `GET` | `/healthcheck` | Health check da API |
| `GET` | `/docs` | Swagger UI |

### Exemplos com curl

**Traduzir texto:**
```bash
curl -X POST http://localhost:3000/translate \
  -H "Content-Type: application/json" \
  -d '{"text": "Bom dia, como você está?"}'
```

**Gerar vídeo:**
```bash
curl -X POST http://localhost:3000/video \
  -H "Content-Type: application/json" \
  -d '{
    "gloss": "BOM DIA COMO VOCÊ ESTAR",
    "avatar": "icaro",
    "caption": "off"
  }'
```

**Consultar status:**
```bash
curl http://localhost:3000/video/status/{requestUID}
```

**Baixar vídeo:**
```bash
curl -O http://localhost:3000/video/download/{requestUID}
```

---

## Exemplos de Uso

### Fluxo Completo com Claude Desktop

```
Você: Traduza "Bom dia, como você está?" para Libras e gere um vídeo

Claude (executa):
1. translate_to_libras({ text: "Bom dia, como você está?" })
   → "BOM DIA COMO VOCÊ ESTAR"

2. generate_libras_video({ gloss: "BOM DIA COMO VOCÊ ESTAR", avatar: "icaro" })
   → { requestUID: "abc-123-def-456" }

3. Aguarda 10 segundos...

4. get_libras_video_status({ requestUID: "abc-123-def-456" })
   → { status: "generated", size: 2048576 }

5. download_libras_video({ requestUID: "abc-123-def-456" })
   → [base64 do vídeo]

Claude: "Tradução: BOM DIA COMO VOCÊ ESTAR
Vídeo gerado com sucesso! [arquivo vlibrasvideo.mp4]"
```

### Uso no Cursor

```
Cursor AI: Gere um vídeo em Libras dizendo "Obrigado por assistir"

Result: 
1. translate_to_libras({ text: "Obrigado por assistir" })
   → "OBRIGADO ASSISTIR"

2. generate_libras_video({ gloss: "OBRIGADO ASSISTIR" })
   → Vídeo gerado com sucesso!
```

---

## Infraestrutura

### docker-compose.yml

```yaml
services:
  vlibras-text-core:
    build:
      context: ./vlibras-translator-text-core
    container_name: vlibras-text-core
    environment:
      AMQP_HOST: 10.0.0.1
      AMQP_PORT: 5672
      AMQP_USER: vlibras
      AMQP_PASS: vlibras
      AMQP_PREFETCH_COUNT: 1
      TRANSLATOR_QUEUE: "translate.to_text"
      ENABLE_DL_TRANSLATION: "false"
      HEALTHCHECK_PORT: 8080
    restart: unless-stopped
    mem_limit: 2g
    network_mode: host

  vlibras-video-core:
    build:
      context: ./vlibras-complete
      dockerfile: vlibras-video/Dockerfile
    container_name: vlibras-video-core
    ports:
      - "9001:9001"
    environment:
      AMQP_HOST: 10.0.0.1
      AMQP_PORT: 5672
      AMQP_USER: vlibras
      AMQP_PASS: vlibras
      VIDEOMAKER_QUEUE: "translate.to_video"
      VLIBRAS_VIDEO_IP: "0.0.0.0"
      VLIBRAS_VIDEO_PORT: "9001"
    restart: unless-stopped
    mem_limit: 4g
    network_mode: host
    volumes:
      - vlibras-storage:/home/vlibras/storage
      - vlibras-logs:/home/vlibras/log
    command: >
      sh -c "python3 /home/vlibras/processManager.py & cd /home/vlibras/vlibras-api && nodejs server.js"

  vlibras-api:
    build:
      context: ./vlibras-translator-api
    container_name: vlibras-api
    environment:
      PORT: 3000
      NODE_ENV: production
      DB_HOST: 10.0.0.1
      DB_PORT: 27017
      DB_NAME: "vlibras-db"
      CACHE_HOST: 10.0.0.1
      CACHE_PORT: 6379
      CACHE_NAME: "vlibras-cache"
      CACHE_SIZE: 104857600
      CACHE_EXP: 604800
      AMQP_PROTOCOL: amqp
      AMQP_HOST: 10.0.0.1
      AMQP_PORT: 5672
      AMQP_USER: vlibras
      AMQP_PASS: vlibras
      TRANSLATOR_QUEUE: "translate.to_text"
      VIDEOMAKER_QUEUE: "translate.to_video"
      API_CONSUMER_QUEUE: "amq.rabbitmq.reply-to"
      VLIBRAS_VIDEO_URL: "http://10.0.0.1:9001"
    restart: unless-stopped
    mem_limit: 1g
    network_mode: host

  vlibras-mongodb:
    image: mongo:6
    container_name: vlibras-mongodb
    ports:
      - "27017:27017"
    volumes:
      - vlibras-mongodb-data:/data/db
    restart: unless-stopped
    mem_limit: 1g
    network_mode: host

volumes:
  vlibras-storage:
  vlibras-logs:
  vlibras-mongodb-data:
```

### Portas

| Serviço | Porta | Descrição |
|---------|-------|-----------|
| VLibras API | 3000 | API REST principal |
| MongoDB | 27017 | Banco de dados |
| Redis | 6379 | Cache |
| RabbitMQ | 5672 | Message broker |
| VLibras Video | 9001 | Serviço de vídeo |

---

## Troubleshooting

### API não conecta ao MongoDB

```bash
# Verifique se o MongoDB está rodando
docker ps | grep mongodb

# Reinicie a API
docker restart vlibras-api
```

### MCP Server não inicia

```bash
# Verifique se o build foi feito
npm run build

# Teste manualmente
VLIBRAS_API_URL=http://localhost:3000 node dist/index.js
```

### Erro de tradução

```bash
# Verifique se o vlibras-text-core está rodando
docker ps | grep text-core

# Verifique os logs
docker logs vlibras-text-core --tail 50
```

### Vídeo não gera

```bash
# Verifique se o vlibras-video-core está rodando
docker ps | grep video-core

# Verifique os logs
docker logs vlibras-video-core --tail 50
```

### Claude Desktop não conecta ao MCP

1. Verifique se o caminho no `claude_desktop_config.json` está correto
2. Reinicie o Claude Desktop
3. Verifique os logs do Claude Desktop

---

## Estrutura do Projeto

```
vlibras-mcp-server/
├── src/
│   ├── index.ts              # Entry point do servidor MCP
│   ├── client.ts             # HTTP client para a API VLibras
│   └── tools/
│       ├── translate.ts      # Tool: translate_to_libras
│       └── video.ts          # Tools: generate_video, status, download
├── dist/                     # JavaScript compilado
├── package.json
├── tsconfig.json
├── Dockerfile
└── README.md
```

---

## Contribuindo

1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/nova-feature`)
3. Commit suas mudanças (`git commit -m 'Adiciona nova feature'`)
4. Push para a branch (`git push origin feature/nova-feature`)
5. Abra um Pull Request

---

## Licença

Este projeto está licenciado sob a Licença MIT - veja o arquivo [LICENSE](LICENSE) para detalhes.

---

## Links Úteis

- [Model Context Protocol](https://modelcontextprotocol.io/)
- [VLibras](https://www.vlibras.gov.br/)
- [MCP SDK](https://github.com/modelcontextprotocol/typescript-sdk)

---

## Créditos

Inserir créditos
