import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { VLibrasClient } from './client.js';
import { registerTranslateTool } from './tools/translate.js';
import { registerVideoTools } from './tools/video.js';

const VLIBRAS_API_URL = process.env.VLIBRAS_API_URL || 'http://localhost:3000';

async function main() {
  const client = new VLibrasClient(VLIBRAS_API_URL);

  const server = new McpServer({
    name: 'vlibras-mcp-server',
    version: '1.0.0',
  });

  registerTranslateTool(server, client);
  registerVideoTools(server, client);

  const transport = new StdioServerTransport();
  await server.connect(transport);

  console.error('VLibras MCP Server running on stdio');
  console.error(`API URL: ${VLIBRAS_API_URL}`);
}

main().catch((error) => {
  console.error('Fatal error:', error);
  process.exit(1);
});
