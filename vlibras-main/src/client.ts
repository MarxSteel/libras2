import axios, { AxiosInstance } from 'axios';

export class VLibrasClient {
  private client: AxiosInstance;

  constructor(baseUrl: string) {
    this.client = axios.create({
      baseURL: baseUrl,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });
  }

  async healthcheck(): Promise<boolean> {
    try {
      const response = await this.client.get('/healthcheck');
      return response.status === 200;
    } catch {
      return false;
    }
  }

  async translate(text: string): Promise<{ translation: string }> {
    const response = await this.client.post('/translate', { text });
    return response.data;
  }

  async generateVideo(gloss: string, avatar: string = 'icaro', caption: string = 'off'): Promise<{ requestUID: string }> {
    const response = await this.client.post('/video', { gloss, avatar, caption });
    return response.data;
  }

  async getVideoStatus(requestUID: string): Promise<{ status: string; size?: number }> {
    const response = await this.client.get(`/video/status/${requestUID}`);
    return response.data;
  }

  async downloadVideo(requestUID: string): Promise<Buffer> {
    const response = await this.client.get(`/video/download/${requestUID}`, {
      responseType: 'arraybuffer',
    });
    return Buffer.from(response.data);
  }
}
