import { ReplayControlMsg, ServerToClientMsg } from '../../../shared/types';
import { useGraphStore } from './graphStore';

class SocketManager {
  private ws: WebSocket | null = null;
  private url: string = 'ws://localhost:8000/ws';
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  connect(url = 'ws://localhost:8000/ws') {
    this.url = url;
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this.ws = new WebSocket(this.url);

    this.ws.onopen = () => {
      useGraphStore.getState().setConnected(true);
    };

    this.ws.onmessage = (event) => {
      try {
        const msg: ServerToClientMsg = JSON.parse(event.data);
        if (msg.kind === 'snapshot') {
          useGraphStore.getState().applySnapshot(msg.graph);
        } else if (msg.kind === 'event') {
          useGraphStore.getState().applyEvent(msg.event);
        }
      } catch (err) {
        console.error('Invalid WS message', err);
      }
    };

    this.ws.onclose = () => {
      useGraphStore.getState().setConnected(false);
      this.ws = null;
      if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
      this.reconnectTimer = setTimeout(() => this.connect(this.url), 2000);
    };

    this.ws.onerror = () => {
      this.ws?.close();
    };
  }

  sendReplayControl(action: ReplayControlMsg['action'], speed?: number) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      const payload: ReplayControlMsg = { kind: 'replay_control', action, speed };
      this.ws.send(JSON.stringify(payload));
    }
  }
}

export const socketClient = new SocketManager();