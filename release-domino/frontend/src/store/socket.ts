import { WSEventEnvelope } from '../../../shared/types';
import { useReleaseStore } from './releaseStore';

export class ReleaseEventsSocketClient {
  private ws: WebSocket | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectDelay = 1200;
  private isManuallyClosed = false;

  private getWsUrl(): string {
    if (typeof window === 'undefined') return 'ws://127.0.0.1:8000/ws/events';
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const host = window.location.host || '127.0.0.1:8000';
    return `${proto}://${host}/ws/events`;
  }

  public connect(): void {
    this.isManuallyClosed = false;
    if (
      this.ws &&
      (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    try {
      this.ws = new WebSocket(this.getWsUrl());

      this.ws.onopen = () => {
        useReleaseStore.getState().setConnected(true);
        this.reconnectDelay = 1200;
      };

      this.ws.onmessage = (event: MessageEvent) => {
        try {
          useReleaseStore.getState().appendWireLog(event.data);
          const envelope: WSEventEnvelope = JSON.parse(event.data);
          if (envelope && envelope.type) {
            useReleaseStore.getState().applyWsEvent(envelope);
          }
        } catch {
          // ignore malformed wire packet
        }
      };

      this.ws.onclose = () => {
        useReleaseStore.getState().setConnected(false);
        this.ws = null;
        if (!this.isManuallyClosed) {
          this.scheduleReconnect();
        }
      };

      this.ws.onerror = () => {
        useReleaseStore.getState().setConnected(false);
      };
    } catch {
      if (!this.isManuallyClosed) {
        this.scheduleReconnect();
      }
    }
  }

  public disconnect(): void {
    this.isManuallyClosed = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    useReleaseStore.getState().setConnected(false);
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, this.reconnectDelay);
    this.reconnectDelay = Math.min(this.reconnectDelay * 1.5, 10000);
  }
}

export const releaseSocket = new ReleaseEventsSocketClient();
