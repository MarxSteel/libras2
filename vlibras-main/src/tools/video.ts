import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { z } from 'zod';
import { VLibrasClient } from '../client.js';

export function registerVideoTools(server: McpServer, client: VLibrasClient) {
  server.tool(
    'generate_libras_video',
    'Gera vídeo em Libras a partir de gloss. Retorna requestUID para acompanhar status. Use após translate_to_libras.',
    {
      gloss: z.string().describe('Gloss Libras para gerar vídeo (obtido de translate_to_libras)'),
      avatar: z.enum(['icaro', 'hozana']).default('icaro').describe('Avatar do intérprete'),
      caption: z.enum(['on', 'off']).default('off').describe('Legendas no vídeo'),
    },
    async ({ gloss, avatar, caption }) => {
      try {
        const result = await client.generateVideo(gloss, avatar, caption);
        return {
          content: [
            {
              type: 'text',
              text: `Vídeo em processamento. Use get_libras_video_status com requestUID: ${result.requestUID}`,
            },
          ],
        };
      } catch (error: any) {
        return {
          content: [
            {
              type: 'text',
              text: `Erro ao gerar vídeo: ${error.message}`,
            },
          ],
          isError: true,
        };
      }
    }
  );

  server.tool(
    'get_libras_video_status',
    'Consulta status de geração de vídeo em Libras. Status possíveis: queued, processing, generated, failed.',
    {
      requestUID: z.string().uuid().describe('UID retornado por generate_libras_video'),
    },
    async ({ requestUID }) => {
      try {
        const result = await client.getVideoStatus(requestUID);
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(result, null, 2),
            },
          ],
        };
      } catch (error: any) {
        return {
          content: [
            {
              type: 'text',
              text: `Erro ao consultar status: ${error.message}`,
            },
          ],
          isError: true,
        };
      }
    }
  );

  server.tool(
    'download_libras_video',
    'Download do vídeo gerado em Libras. Retorna o vídeo em base64. Use após verificar status com get_libras_video_status.',
    {
      requestUID: z.string().uuid().describe('UID do vídeo gerado'),
    },
    async ({ requestUID }) => {
      try {
        const videoBuffer = await client.downloadVideo(requestUID);
        const base64 = videoBuffer.toString('base64');
        return {
          content: [
            {
              type: 'text',
              text: `Vídeo em Libras (base64 MP4): ${base64.substring(0, 100)}...[${base64.length} bytes total]`,
            },
          ],
        };
      } catch (error: any) {
        return {
          content: [
            {
              type: 'text',
              text: `Erro ao baixar vídeo: ${error.message}`,
            },
          ],
          isError: true,
        };
      }
    }
  );
}
