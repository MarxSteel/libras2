import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { z } from 'zod';
import { VLibrasClient } from '../client.js';

export function registerTranslateTool(server: McpServer, client: VLibrasClient) {
  server.tool(
    'translate_to_libras',
    'Traduz texto em Português Brasileiro para Libras (gloss). Use para converter frases PT-BR em representação em sinais de Libras.',
    {
      text: z.string().max(5000).describe('Texto em PT-BR para traduzir (máx 5000 caracteres)'),
    },
    async ({ text }) => {
      try {
        const result = await client.translate(text);
        return {
          content: [
            {
              type: 'text',
              text: `Tradução para Libras (gloss): ${result.translation}`,
            },
          ],
        };
      } catch (error: any) {
        return {
          content: [
            {
              type: 'text',
              text: `Erro na tradução: ${error.message}`,
            },
          ],
          isError: true,
        };
      }
    }
  );
}
