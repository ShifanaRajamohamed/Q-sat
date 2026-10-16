import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { BehaviorSubject, Observable } from 'rxjs';
import { TelemetryPacket } from '../models/telemetry.model';

export type ConnectionStatus = 'CONNECTED' | 'CONNECTING' | 'DISCONNECTED';

export interface HistoryPoint {
  timeLabel: string;
  timestamp: number;
  qberPct: number;
  skrKbps: number;
  totalLossDb: number;
  laserPowerMw: number;
  repetitionRateMhz: number;
  beamDivergenceUrad: number;
}

@Injectable({
  providedIn: 'root'
})
export class TelemetryService {
  private http = inject(HttpClient);

  // Use dynamic location host so it works whether opened from port 4200 or 8000
  private readonly apiBase = window.location.port === '4200' ? 'http://127.0.0.1:8000' : `${window.location.protocol}//${window.location.host}`;
  private readonly wsUrl = window.location.port === '4200' ? 'ws://127.0.0.1:8000/ws/live' : `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/live`;

  private ws: WebSocket | null = null;
  private reconnectTimer: any = null;

  private telemetrySubject = new BehaviorSubject<TelemetryPacket | null>(null);
  public telemetry$: Observable<TelemetryPacket | null> = this.telemetrySubject.asObservable();

  private statusSubject = new BehaviorSubject<ConnectionStatus>('DISCONNECTED');
  public connectionStatus$: Observable<ConnectionStatus> = this.statusSubject.asObservable();

  private historySubject = new BehaviorSubject<HistoryPoint[]>([]);
  public history$: Observable<HistoryPoint[]> = this.historySubject.asObservable();

  private readonly maxHistoryLength = 60;
  private historyBuffer: HistoryPoint[] = [];

  constructor() {
    this.connectWebSocket();
  }

  public connectWebSocket(): void {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this.statusSubject.next('CONNECTING');

    try {
      this.ws = new WebSocket(this.wsUrl);

      this.ws.onopen = () => {
        this.statusSubject.next('CONNECTED');
        if (this.reconnectTimer) {
          clearTimeout(this.reconnectTimer);
          this.reconnectTimer = null;
        }
      };

      this.ws.onmessage = (event) => {
        try {
          const packet: TelemetryPacket = JSON.parse(event.data);
          this.telemetrySubject.next(packet);
          this.appendHistory(packet);
        } catch (err) {
          console.error('[WS] Telemetry JSON parse error:', err);
        }
      };

      this.ws.onclose = () => {
        this.statusSubject.next('DISCONNECTED');
        this.scheduleReconnect();
      };

      this.ws.onerror = () => {
        this.statusSubject.next('DISCONNECTED');
        if (this.ws) {
          this.ws.close();
        }
      };
    } catch (e) {
      this.statusSubject.next('DISCONNECTED');
      this.scheduleReconnect();
    }
  }

  private scheduleReconnect(): void {
    if (!this.reconnectTimer) {
      this.reconnectTimer = setTimeout(() => {
        this.reconnectTimer = null;
        this.connectWebSocket();
      }, 2000);
    }
  }

  private appendHistory(packet: TelemetryPacket): void {
    const d = new Date();
    const timeLabel = `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`;

    const point: HistoryPoint = {
      timeLabel,
      timestamp: packet.timestamp,
      qberPct: Number(((packet.qkd?.qber || 0) * 100.0).toFixed(2)),
      skrKbps: Number(((packet.qkd?.secret_key_rate || 0) / 1000.0).toFixed(3)),
      totalLossDb: Number((packet.channel?.total_loss_db || 0).toFixed(1)),
      laserPowerMw: Number((packet.control?.current?.transmission_power_pct || 0).toFixed(1)),
      repetitionRateMhz: Number(((packet.control?.current?.photon_rate_norm || 0) * 100.0).toFixed(1)),
      beamDivergenceUrad: Number(((packet.control?.current?.beam_divergence_norm || 0) * 50.0).toFixed(1)),
    };

    this.historyBuffer.push(point);
    if (this.historyBuffer.length > this.maxHistoryLength) {
      this.historyBuffer.shift();
    }

    this.historySubject.next([...this.historyBuffer]);
  }

  // REST API Actions
  public switchController(mode: string): Observable<any> {
    return this.http.post(`${this.apiBase}/api/control/switch`, { mode });
  }

  public switchScenario(scenario: string): Observable<any> {
    return this.http.post(`${this.apiBase}/api/simulation/scenario`, { scenario });
  }

  public injectAnomaly(magnitude: number = 0.06, anomalyType: string = 'EAVESDROPPING'): Observable<any> {
    return this.http.post(`${this.apiBase}/api/qkd/inject-anomaly`, {
      magnitude,
      anomaly_type: anomalyType,
      duration_steps: 30
    });
  }

  public clearAnomaly(): Observable<any> {
    return this.http.post(`${this.apiBase}/api/qkd/clear-anomaly`, {});
  }

  public resetSimulation(): Observable<any> {
    return this.http.post(`${this.apiBase}/api/simulation/reset`, {});
  }

  public getExperimentsSummary(): Observable<any> {
    return this.http.get(`${this.apiBase}/api/experiments/summary`);
  }

  public runDemonstration(): Observable<any> {
    return this.http.post(`${this.apiBase}/api/experiments/run-demo`, {});
  }
}

