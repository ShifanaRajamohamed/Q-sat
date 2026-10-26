import { Component, OnInit, OnDestroy, AfterViewInit, ViewChild, ElementRef, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Subscription } from 'rxjs';
import * as echarts from 'echarts';

import { TelemetryService, ConnectionStatus, HistoryPoint } from './services/telemetry.service';
import { TelemetryPacket } from './models/telemetry.model';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './app.html',
  styleUrl: './app.css'
})
export class App implements OnInit, OnDestroy, AfterViewInit {
  public telemetryService = inject(TelemetryService);

  @ViewChild('worldMapCanvas', { static: false }) worldMapCanvasRef!: ElementRef<HTMLCanvasElement>;
  @ViewChild('skyCanvas', { static: false }) skyCanvasRef!: ElementRef<HTMLCanvasElement>;
  @ViewChild('chartContainer', { static: false }) chartContainerRef!: ElementRef<HTMLDivElement>;

  public isDarkMode: boolean = true;
  private currentHistory: HistoryPoint[] = [];

  public telemetry: TelemetryPacket | null = null;
  public connectionStatus: ConnectionStatus = 'DISCONNECTED';
  public activeTab: 'dual' | 'qber' | 'skr' | 'loss' | 'actuators' = 'dual';

  public selectedScenario: string = 'CLEAR_SKY';
  public anomalyActive: boolean = false;
  public showMissionBriefing: boolean = false;

  public showResultsModal: boolean = false;
  public activeResultsTab: 'leaderboard' | 'statistics' | 'datasets' | 'figures' | 'report' = 'leaderboard';
  public isRunningDemo: boolean = false;
  public demoSummary: any[] | null = null;
  public masterSummary: any = null;

  public datasetsCatalog: any[] = [];
  public selectedDatasetScenario: string = 'CLEAR_SKY';
  public selectedDatasetData: any = null;
  public isLoadingDataset: boolean = false;

  // Live Mission Activity Log & Telemetry Message Stream
  public missionLogs: Array<{
    id: number;
    time: string;
    source: 'SYS' | 'SAT' | 'QKD' | 'AI' | 'SEC' | 'ENV';
    level: 'INFO' | 'SUCCESS' | 'WARN' | 'DANGER';
    message: string;
    provenance: string;
  }> = [
    {
      id: 1,
      time: '22:00:01',
      source: 'SYS',
      level: 'INFO',
      message: 'Q-SAT Mission Control Online. Optical Ground Station Bob (Trichy, 10.79°N, 78.70°E) active.',
      provenance: '[SIMULATION]'
    },
    {
      id: 2,
      time: '22:00:03',
      source: 'SAT',
      level: 'INFO',
      message: 'Alice (LEO 500 km) orbit propagated via Keplerian topocentric model.',
      provenance: '[SIMULATION]'
    },
    {
      id: 3,
      time: '22:00:05',
      source: 'QKD',
      level: 'SUCCESS',
      message: 'BB84 Quantum Key Distribution channel online. SPAD detector efficiency = 10%.',
      provenance: '[SIMULATION]'
    },
    {
      id: 4,
      time: '22:00:08',
      source: 'AI',
      level: 'INFO',
      message: 'Hierarchical Multi-Agent AI controller active. Real-time actuator tuning engaged.',
      provenance: '[AI OUTPUT]'
    }
  ];
  public logFilter: 'ALL' | 'SEC' | 'AI' | 'QKD' | 'SAT' = 'ALL';
  private lastLogTimestamp = 0;
  private lastVisibleState: boolean | null = null;
  private lastControllerMode: string = '';
  private lastAnomalyState: boolean = false;

  private subs = new Subscription();
  private echartInstance: echarts.ECharts | null = null;
  private canvasCtx: CanvasRenderingContext2D | null = null;
  private trajectoryPoints: Array<{ x: number; y: number }> = [];

  ngOnInit(): void {
    if (typeof window !== 'undefined') {
      const savedTheme = localStorage.getItem('qsat_theme');
      if (savedTheme) {
        this.isDarkMode = savedTheme === 'dark';
      } else {
        this.isDarkMode = !window.matchMedia || !window.matchMedia('(prefers-color-scheme: light)').matches;
      }
      this.applyTheme(this.isDarkMode, false);
    }

    this.subs.add(
      this.telemetryService.connectionStatus$.subscribe(status => {
        this.connectionStatus = status;
        if (status === 'CONNECTED') {
          this.addLog('SYS', 'SUCCESS', 'Telemetry stream connected to backend WebSocket gateway (/ws/live).', '[LIVE STREAM]');
        } else if (status === 'DISCONNECTED') {
          this.addLog('SYS', 'WARN', 'Telemetry stream disconnected. Reconnection watchdog active.', '[WATCHDOG]');
        }
      })
    );

    this.subs.add(
      this.telemetryService.telemetry$.subscribe(packet => {
        if (packet) {
          this.telemetry = packet;
          this.anomalyActive = (packet.qkd?.qber_decomposition?.security_anomaly_component || 0) > 0.001;
          this.processTelemetryLogs(packet);
          this.drawSkyDome();
          this.drawWorldMap();
        }
      })
    );

    this.subs.add(
      this.telemetryService.history$.subscribe(history => {
        this.currentHistory = history;
        this.updateChart(history);
      })
    );
  }

  ngAfterViewInit(): void {
    if (this.skyCanvasRef) {
      this.canvasCtx = this.skyCanvasRef.nativeElement.getContext('2d');
      this.drawSkyDome();
    }

    if (this.worldMapCanvasRef) {
      this.drawWorldMap();
    }

    if (this.chartContainerRef) {
      this.echartInstance = echarts.init(this.chartContainerRef.nativeElement, this.isDarkMode ? 'dark' : undefined);
      window.addEventListener('resize', this.onResize);
    }
  }

  ngOnDestroy(): void {
    this.subs.unsubscribe();
    window.removeEventListener('resize', this.onResize);
    if (this.echartInstance) {
      this.echartInstance.dispose();
      this.echartInstance = null;
    }
  }

  private onResize = () => {
    if (this.echartInstance) {
      this.echartInstance.resize();
    }
    this.drawSkyDome();
    this.drawWorldMap();
  };

  public toggleTheme(): void {
    this.isDarkMode = !this.isDarkMode;
    if (typeof window !== 'undefined') {
      localStorage.setItem('qsat_theme', this.isDarkMode ? 'dark' : 'light');
    }
    this.applyTheme(this.isDarkMode, true);
  }

  private applyTheme(dark: boolean, log: boolean = true): void {
    if (typeof document !== 'undefined') {
      document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
      document.body.classList.toggle('dark-theme', dark);
      document.body.classList.toggle('light-theme', !dark);
    }

    if (this.echartInstance && this.chartContainerRef) {
      this.echartInstance.dispose();
      this.echartInstance = echarts.init(this.chartContainerRef.nativeElement, dark ? 'dark' : undefined);
      if (this.currentHistory && this.currentHistory.length > 0) {
        this.updateChart(this.currentHistory);
      }
    }

    this.drawSkyDome();
    this.drawWorldMap();

    if (log) {
      this.addLog('SYS', 'INFO', `Mission Control interface theme changed to ${dark ? 'High-Tech Dark' : 'Daylight Laboratory'} Mode.`, '[THEME]');
    }
  }

  public toggleMissionBriefing(): void {
    this.showMissionBriefing = !this.showMissionBriefing;
  }

  public get aesKeysEquivalent(): number {
    const skr = this.telemetry?.qkd?.secret_key_rate || 0;
    return Math.max(0, Math.floor((skr * 120) / 256));
  }

  public get passTimerLabel(): string {
    if (!this.telemetry || !this.telemetry.satellite) return 'SEARCHING';
    const sat = this.telemetry.satellite;
    if (sat.is_visible) {
      const s = Math.round(sat.time_to_los_s || 0);
      const m = Math.floor(s / 60);
      const rem = s % 60;
      return `LOS IN ${m.toString().padStart(2, '0')}:${rem.toString().padStart(2, '0')}`;
    } else {
      const s = Math.round(sat.time_to_aos_s || 0);
      const m = Math.floor(s / 60);
      const rem = s % 60;
      return `AOS IN ${m.toString().padStart(2, '0')}:${rem.toString().padStart(2, '0')}`;
    }
  }

  public get qkdStatusClass(): string {
    if (!this.telemetry || !this.telemetry.qkd) return 'badge-cyan';
    const status = this.telemetry.qkd.status_label;
    const isVis = this.telemetry.satellite?.is_visible;
    const qber = this.telemetry.qkd.qber || 0;
    if (qber >= 0.11 || status === 'CRITICAL_QBER' || (status as string) === 'ABORT') return 'badge-red';
    if (!isVis || status === 'LINK_DOWN') return 'badge-cyan';
    if (status === 'DEGRADED') return 'badge-amber';
    return 'badge-green';
  }

  public get qkdStatusText(): string {
    if (!this.telemetry || !this.telemetry.qkd) return 'SYNCHRONIZING';
    const status = this.telemetry.qkd.status_label;
    const isVis = this.telemetry.satellite?.is_visible;
    const qber = this.telemetry.qkd.qber || 0;
    if (qber >= 0.11 || status === 'CRITICAL_QBER' || (status as string) === 'ABORT') return 'SECURITY CUTOFF (QBER ≥ 11%)';
    if (!isVis || status === 'LINK_DOWN') return 'STANDBY (SUB-HORIZON)';
    if (status === 'DEGRADED') return 'DEGRADED CHANNEL';
    return 'SECURE (KEY SIFTING)';
  }

  public fastForwardPass(): void {
    this.trajectoryPoints = [];
    this.telemetryService.resetSimulation().subscribe({
      next: () => {
        this.addLog('SAT', 'SUCCESS', 'Acquired pass window (El 30.0°, Slant Range 909 km). Optical link active.', '[SIMULATION]');
      },
      error: (err) => console.error('Error acquiring pass:', err)
    });
  }

  public get filteredLogs() {
    if (this.logFilter === 'ALL') return this.missionLogs;
    return this.missionLogs.filter(l => l.source === this.logFilter);
  }

  public setLogFilter(filter: 'ALL' | 'SEC' | 'AI' | 'QKD' | 'SAT'): void {
    this.logFilter = filter;
  }

  public clearLogs(): void {
    this.missionLogs = [];
  }

  private processTelemetryLogs(packet: TelemetryPacket): void {
    // Log satellite AOS / LOS
    if (this.lastVisibleState !== null && this.lastVisibleState !== packet.satellite.is_visible) {
      if (packet.satellite.is_visible) {
        this.addLog('SAT', 'SUCCESS', `AOS: Alice acquired at El ${(packet.satellite.elevation_deg || 0).toFixed(1)}°, Az ${(packet.satellite.azimuth_deg || 0).toFixed(1)}°. Link active.`, '[SIMULATION]');
      } else {
        this.addLog('SAT', 'WARN', `LOS: Alice sub-horizon (El < 10°). Transmitter in standby.`, '[SIMULATION]');
      }
    }
    this.lastVisibleState = packet.satellite.is_visible;

    // Log controller mode switch
    if (packet.control?.mode && this.lastControllerMode !== packet.control.mode) {
      this.addLog('AI', 'INFO', `Controller policy changed to ${packet.control.mode}`, '[AI OUTPUT]');
      this.lastControllerMode = packet.control.mode;
    }

    // Log anomaly / cyber attack detection
    const isAnomaly = (packet.qkd?.qber_decomposition?.security_anomaly_component || 0) > 0.001;
    if (isAnomaly !== this.lastAnomalyState) {
      if (isAnomaly) {
        this.addLog('SEC', 'DANGER', `CYBER ALERT: Security Agent detected anomalous QBER (+${((packet.qkd?.qber_decomposition?.security_anomaly_component || 0) * 100).toFixed(1)}%). Potential eavesdropping!`, '[AI OUTPUT]');
      } else {
        this.addLog('SEC', 'SUCCESS', `Channel cleared: Security Agent reports channel nominal.`, '[AI OUTPUT]');
      }
      this.lastAnomalyState = isAnomaly;
    }

    // Periodic heartbeat log (every 6 seconds)
    const currentEpoch = Date.now();
    if (currentEpoch - this.lastLogTimestamp > 6000) {
      this.lastLogTimestamp = currentEpoch;
      if (packet.satellite.is_visible) {
        const skrKbps = ((packet.qkd?.secret_key_rate || 0) / 1000).toFixed(2);
        const qberPct = ((packet.qkd?.qber || 0) * 100).toFixed(2);
        const pwr = packet.control?.current?.transmission_power_pct?.toFixed(0) || '0';
        this.addLog('QKD', 'INFO', `Live frame: SKR=${skrKbps} kbps | QBER=${qberPct}% | Laser Power=${pwr}% | Loss=${packet.channel?.total_loss_db?.toFixed(1) || '0'} dB`, '[SIMULATION]');
      } else {
        const range = packet.satellite.slant_range_km?.toFixed(0) || '0';
        this.addLog('SAT', 'INFO', `Orbit tracking: Range=${range} km | Alt=${packet.satellite.altitude_km} km | Awaiting optical pass window`, '[SIMULATION]');
      }
    }
  }

  private addLog(source: 'SYS' | 'SAT' | 'QKD' | 'AI' | 'SEC' | 'ENV', level: 'INFO' | 'SUCCESS' | 'WARN' | 'DANGER', message: string, provenance: string): void {
    const timeStr = new Date().toTimeString().split(' ')[0];
    this.missionLogs.unshift({
      id: Date.now() + Math.random(),
      time: timeStr,
      source,
      level,
      message,
      provenance
    });
    if (this.missionLogs.length > 50) {
      this.missionLogs.pop();
    }
  }

  public setTab(tab: 'dual' | 'qber' | 'skr' | 'loss' | 'actuators'): void {
    this.activeTab = tab;
    this.telemetryService.history$.subscribe(history => {
      this.updateChart(history);
    }).unsubscribe();
  }

  public onControllerChange(mode: 'STATIC' | 'RULE_BASED' | 'PPO' | 'MULTI_AGENT'): void {
    this.telemetryService.switchController(mode).subscribe({
      next: () => console.log(`Controller switched to ${mode}`),
      error: (err) => console.error('Error switching controller:', err)
    });
  }

  public onScenarioChange(scenario: string): void {
    this.selectedScenario = scenario;
    this.telemetryService.switchScenario(scenario).subscribe({
      next: () => console.log(`Scenario switched to ${scenario}`),
      error: (err) => console.error('Error switching scenario:', err)
    });
  }

  public toggleAnomaly(): void {
    if (this.anomalyActive) {
      this.telemetryService.clearAnomaly().subscribe({
        next: () => {
          this.anomalyActive = false;
        },
        error: (err) => console.error('Error clearing anomaly:', err)
      });
    } else {
      this.telemetryService.injectAnomaly(0.06, 'EAVESDROPPING').subscribe({
        next: () => {
          this.anomalyActive = true;
        },
        error: (err) => console.error('Error injecting anomaly:', err)
      });
    }
  }

  public resetSimulation(): void {
    this.trajectoryPoints = [];
    this.telemetryService.resetSimulation().subscribe({
      next: () => console.log('Simulation reset'),
      error: (err) => console.error('Error resetting simulation:', err)
    });
  }

  public toggleResultsModal(): void {
    this.showResultsModal = !this.showResultsModal;
    if (this.showResultsModal) {
      if (!this.masterSummary) {
        this.loadMasterSummary();
      }
      if (this.datasetsCatalog.length === 0) {
        this.loadSimulationDatasets();
      }
    }
  }

  public setResultsTab(tab: 'leaderboard' | 'statistics' | 'datasets' | 'figures' | 'report'): void {
    this.activeResultsTab = tab;
    if (tab === 'datasets') {
      if (this.datasetsCatalog.length === 0) {
        this.loadSimulationDatasets();
      }
      if (!this.selectedDatasetData) {
        this.onSelectDataset(this.selectedDatasetScenario);
      }
    }
  }

  public loadMasterSummary(): void {
    this.telemetryService.getExperimentsSummary().subscribe({
      next: (data) => {
        this.masterSummary = data;
      },
      error: (err) => console.error('Error loading experiments summary:', err)
    });
  }

  public loadSimulationDatasets(): void {
    this.telemetryService.getSimulationDatasets().subscribe({
      next: (res) => {
        this.datasetsCatalog = res.datasets || [];
      },
      error: (err) => console.error('Error loading datasets catalog:', err)
    });
  }

  public onSelectDataset(scenario: string): void {
    this.selectedDatasetScenario = scenario;
    this.isLoadingDataset = true;
    this.telemetryService.getSimulationDataset(scenario).subscribe({
      next: (res) => {
        this.isLoadingDataset = false;
        this.selectedDatasetData = res;
      },
      error: (err) => {
        this.isLoadingDataset = false;
        console.error('Error loading dataset:', err);
      }
    });
  }

  public onRunFullDemonstration(): void {
    if (this.isRunningDemo) return;
    this.isRunningDemo = true;
    this.demoSummary = null;
    this.showResultsModal = true;
    this.activeResultsTab = 'leaderboard';

    this.telemetryService.runDemonstration().subscribe({
      next: (res) => {
        this.isRunningDemo = false;
        this.demoSummary = res.summary || [];
        this.loadMasterSummary();
      },
      error: (err) => {
        this.isRunningDemo = false;
        console.error('Error running demonstration:', err);
      }
    });
  }

  /**
   * Draw 2D Equirectangular World Orbit Map with Satellite Ground Track & Ground Station Footprint.
   */
  private drawWorldMap(): void {
    if (!this.worldMapCanvasRef) return;
    const canvas = this.worldMapCanvasRef.nativeElement;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const w = canvas.width;
    const h = canvas.height;

    // 1. Ocean Background (Dynamic for Dark vs Light mode)
    const bgGrad = ctx.createLinearGradient(0, 0, 0, h);
    if (this.isDarkMode) {
      bgGrad.addColorStop(0, '#060b17');
      bgGrad.addColorStop(0.5, '#081122');
      bgGrad.addColorStop(1, '#050a14');
    } else {
      bgGrad.addColorStop(0, '#e0f2fe');
      bgGrad.addColorStop(0.5, '#f0f9ff');
      bgGrad.addColorStop(1, '#e2e8f0');
    }
    ctx.fillStyle = bgGrad;
    ctx.fillRect(0, 0, w, h);

    // 2. Latitude & Longitude Coordinate Grids
    ctx.strokeStyle = this.isDarkMode ? 'rgba(56, 189, 248, 0.08)' : 'rgba(2, 132, 199, 0.12)';
    ctx.lineWidth = 1;

    // Latitudes (every 30 degrees)
    for (let lat = -60; lat <= 60; lat += 30) {
      const y = ((90 - lat) / 180) * h;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();

      // Label
      ctx.fillStyle = this.isDarkMode ? 'rgba(148, 163, 184, 0.35)' : 'rgba(71, 85, 105, 0.6)';
      ctx.font = '8px JetBrains Mono, monospace';
      ctx.fillText(`${lat >= 0 ? lat + '°N' : Math.abs(lat) + '°S'}`, 4, y - 2);
    }

    // Longitudes (every 60 degrees)
    for (let lon = -120; lon <= 120; lon += 60) {
      const x = ((lon + 180) / 360) * w;
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h);
      ctx.stroke();

      // Label
      ctx.fillStyle = this.isDarkMode ? 'rgba(148, 163, 184, 0.35)' : 'rgba(71, 85, 105, 0.6)';
      ctx.font = '8px JetBrains Mono, monospace';
      ctx.fillText(`${lon >= 0 ? lon + '°E' : Math.abs(lon) + '°W'}`, x + 3, h - 4);
    }

    // Equator highlight
    const eqY = h / 2;
    ctx.strokeStyle = this.isDarkMode ? 'rgba(56, 189, 248, 0.2)' : 'rgba(2, 132, 199, 0.25)';
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(0, eqY);
    ctx.lineTo(w, eqY);
    ctx.stroke();
    ctx.setLineDash([]);

    // 3. Simplified Vector Continents
    const toX = (lon: number) => ((lon + 180) / 360) * w;
    const toY = (lat: number) => ((90 - lat) / 180) * h;

    const continents: Array<Array<[number, number]>> = [
      // North America
      [[-165, 68], [-140, 70], [-100, 75], [-60, 60], [-55, 45], [-75, 25], [-85, 20], [-95, 18], [-105, 22], [-125, 38], [-130, 50], [-165, 60]],
      // South America
      [[-80, 10], [-60, 10], [-35, -5], [-40, -22], [-55, -38], [-70, -55], [-75, -45], [-80, -15], [-80, 10]],
      // Eurasia & India
      [[-10, 36], [10, 38], [25, 40], [35, 30], [50, 25], [60, 25], [70, 22], [78, 8], [88, 22], [95, 15], [105, 10], [120, 22], [130, 35], [140, 50], [160, 65], [170, 70], [100, 75], [50, 70], [25, 70], [5, 60], [-5, 45]],
      // Africa
      [[-15, 35], [30, 32], [42, 12], [50, 10], [40, -15], [30, -32], [20, -35], [15, -30], [10, -5], [-15, 15], [-15, 35]],
      // Australia
      [[115, -22], [130, -15], [145, -15], [150, -25], [148, -38], [135, -35], [115, -32], [115, -22]]
    ];

    ctx.fillStyle = this.isDarkMode ? 'rgba(26, 41, 66, 0.55)' : '#ffffff';
    ctx.strokeStyle = this.isDarkMode ? 'rgba(56, 189, 248, 0.3)' : 'rgba(2, 132, 199, 0.35)';
    ctx.lineWidth = 1;

    continents.forEach(poly => {
      ctx.beginPath();
      ctx.moveTo(toX(poly[0][0]), toY(poly[0][1]));
      for (let i = 1; i < poly.length; i++) {
        ctx.lineTo(toX(poly[i][0]), toY(poly[i][1]));
      }
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
    });

    // 4. Ground Station Bob (Trichy, India: 10.7905° N, 78.7047° E)
    const gsLon = 78.7047;
    const gsLat = 10.7905;
    const gsX = toX(gsLon);
    const gsY = toY(gsLat);

    // Ground station visibility coverage circle (~1500 km radius cone)
    const coneRadius = (1500 / 40075) * w; // Slant range projected
    ctx.fillStyle = this.isDarkMode ? 'rgba(0, 255, 157, 0.07)' : 'rgba(5, 150, 105, 0.09)';
    ctx.strokeStyle = this.isDarkMode ? 'rgba(0, 255, 157, 0.4)' : 'rgba(5, 150, 105, 0.45)';
    ctx.lineWidth = 1.2;
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    ctx.arc(gsX, gsY, coneRadius, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    ctx.setLineDash([]);

    // Ground Station Center Beacon
    ctx.fillStyle = this.isDarkMode ? '#00ff9d' : '#059669';
    ctx.beginPath();
    ctx.arc(gsX, gsY, 4, 0, Math.PI * 2);
    ctx.fill();

    // Ground Station Label
    ctx.fillStyle = this.isDarkMode ? '#00ff9d' : '#047857';
    ctx.font = 'bold 9.5px Inter, sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText('Bob (OGS Trichy)', gsX + 7, gsY + 3);

    // 5. Orbital Ground Track Line
    ctx.strokeStyle = this.isDarkMode ? 'rgba(168, 85, 247, 0.4)' : 'rgba(124, 58, 237, 0.55)';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([5, 4]);
    ctx.beginPath();
    for (let x = 0; x <= w; x += 4) {
      const lon = (x / w) * 360 - 180;
      const lat = 65 * Math.sin(((lon - 15) * Math.PI) / 180);
      const y = toY(lat);
      if (x === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.setLineDash([]);

    if (!this.telemetry || !this.telemetry.satellite) return;
    const sat = this.telemetry.satellite;

    // 6. Active Satellite Alice Position
    const satLon = sat.longitude;
    const satLat = sat.latitude;
    const satX = toX(satLon);
    const satY = toY(satLat);

    // Satellite Footprint
    const satFootprintR = (1200 / 40075) * w;
    ctx.fillStyle = this.isDarkMode ? 'rgba(0, 240, 255, 0.08)' : 'rgba(2, 132, 199, 0.1)';
    ctx.strokeStyle = this.isDarkMode ? 'rgba(0, 240, 255, 0.4)' : 'rgba(2, 132, 199, 0.45)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.arc(satX, satY, satFootprintR, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    // 7. Live Quantum Laser Link Beam (When in line-of-sight tracking)
    if (sat.is_visible) {
      ctx.save();
      ctx.shadowBlur = this.anomalyActive ? 15 : 12;
      ctx.shadowColor = this.anomalyActive ? '#ef4444' : (this.isDarkMode ? '#00f0ff' : '#0284c7');
      ctx.strokeStyle = this.anomalyActive ? 'rgba(239, 68, 68, 0.9)' : (this.isDarkMode ? 'rgba(0, 240, 255, 0.85)' : 'rgba(2, 132, 199, 0.9)');
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.moveTo(satX, satY);
      ctx.lineTo(gsX, gsY);
      ctx.stroke();

      // Pulsing Photon Packets along beam
      const pulseFrac = (Date.now() % 1200) / 1200;
      const pulseX = satX + (gsX - satX) * pulseFrac;
      const pulseY = satY + (gsY - satY) * pulseFrac;
      ctx.fillStyle = this.isDarkMode ? '#ffffff' : '#0284c7';
      ctx.beginPath();
      ctx.arc(pulseX, pulseY, 3, 0, Math.PI * 2);
      ctx.fill();

      ctx.restore();
    }

    // Satellite Beacon Icon
    ctx.save();
    ctx.shadowBlur = 12;
    ctx.shadowColor = this.isDarkMode ? '#00f0ff' : 'rgba(2, 132, 199, 0.5)';
    ctx.fillStyle = this.isDarkMode ? '#00f0ff' : '#0284c7';
    ctx.beginPath();
    ctx.arc(satX, satY, 5, 0, Math.PI * 2);
    ctx.fill();

    // Satellite Solar Panels Icon
    ctx.fillStyle = this.isDarkMode ? '#38bdf8' : '#2563eb';
    ctx.fillRect(satX - 10, satY - 2, 5, 4);
    ctx.fillRect(satX + 5, satY - 2, 5, 4);

    // Label
    ctx.fillStyle = this.isDarkMode ? '#ffffff' : '#0f172a';
    ctx.font = 'bold 10px JetBrains Mono, monospace';
    ctx.textAlign = 'left';
    ctx.fillText('Alice (Q-SAT-1)', satX + 8, satY - 6);
    ctx.restore();
  }

  /**
   * Draw 2D Polar Sky Dome Radar Canvas.
   */
  private drawSkyDome(): void {
    if (!this.canvasCtx || !this.skyCanvasRef) return;
    const ctx = this.canvasCtx;
    const canvas = this.skyCanvasRef.nativeElement;
    const w = canvas.width;
    const h = canvas.height;
    const cx = w / 2;
    const cy = h / 2;
    const maxR = (w / 2) - 16;

    ctx.clearRect(0, 0, w, h);

    // Background gradient (Dynamic for Dark vs Light mode)
    const grad = ctx.createRadialGradient(cx, cy, 5, cx, cy, maxR);
    if (this.isDarkMode) {
      grad.addColorStop(0, '#0a1424');
      grad.addColorStop(1, '#050a12');
    } else {
      grad.addColorStop(0, '#f8fafc');
      grad.addColorStop(1, '#e2e8f0');
    }
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(cx, cy, maxR, 0, Math.PI * 2);
    ctx.fill();

    // Concentric elevation rings (10 deg horizon, 30 deg, 60 deg, 90 deg center)
    const elevations = [10, 30, 60];
    elevations.forEach(el => {
      const r = maxR * (1 - (el - 10) / 80);
      ctx.strokeStyle = this.isDarkMode ? 'rgba(56, 189, 248, 0.15)' : 'rgba(2, 132, 199, 0.22)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.stroke();

      // Elevation label
      ctx.fillStyle = this.isDarkMode ? 'rgba(148, 163, 184, 0.6)' : 'rgba(71, 85, 105, 0.8)';
      ctx.font = '9px JetBrains Mono, monospace';
      ctx.fillText(`${el}°`, cx + 3, cy - r + 9);
    });

    // Crosshairs & Compass Spokes
    ctx.strokeStyle = this.isDarkMode ? 'rgba(56, 189, 248, 0.15)' : 'rgba(2, 132, 199, 0.22)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(cx, cy - maxR);
    ctx.lineTo(cx, cy + maxR);
    ctx.moveTo(cx - maxR, cy);
    ctx.lineTo(cx + maxR, cy);
    ctx.stroke();

    // Cardinal Labels
    ctx.fillStyle = this.isDarkMode ? '#38bdf8' : '#0284c7';
    ctx.font = 'bold 10px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('N', cx, cy - maxR + 8);
    ctx.fillText('S', cx, cy + maxR - 8);
    ctx.fillText('E', cx + maxR - 8, cy);
    ctx.fillText('W', cx - maxR + 8, cy);

    // Ground Station Center Anchor
    ctx.fillStyle = this.isDarkMode ? '#00f0ff' : '#0284c7';
    ctx.beginPath();
    ctx.arc(cx, cy, 3, 0, Math.PI * 2);
    ctx.fill();

    if (!this.telemetry || !this.telemetry.satellite) return;

    const sat = this.telemetry.satellite;
    const el = Math.max(10, Math.min(90, sat.elevation_deg));
    const azRad = (sat.azimuth_deg - 90) * (Math.PI / 180);
    const rSat = maxR * (1 - (el - 10) / 80);

    const satX = cx + rSat * Math.cos(azRad);
    const satY = cy + rSat * Math.sin(azRad);

    this.trajectoryPoints.push({ x: satX, y: satY });
    if (this.trajectoryPoints.length > 40) {
      this.trajectoryPoints.shift();
    }

    // Draw Trajectory Trail
    if (this.trajectoryPoints.length > 1) {
      ctx.strokeStyle = this.isDarkMode ? 'rgba(0, 240, 255, 0.35)' : 'rgba(2, 132, 199, 0.4)';
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(this.trajectoryPoints[0].x, this.trajectoryPoints[0].y);
      for (let i = 1; i < this.trajectoryPoints.length; i++) {
        ctx.lineTo(this.trajectoryPoints[i].x, this.trajectoryPoints[i].y);
      }
      ctx.stroke();
    }

    // Draw Line-of-Sight Laser Link Beam
    if (sat.is_visible) {
      ctx.strokeStyle = this.anomalyActive ? 'rgba(239, 68, 68, 0.6)' : (this.isDarkMode ? 'rgba(0, 255, 157, 0.5)' : 'rgba(5, 150, 105, 0.55)');
      ctx.lineWidth = 1.5;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.lineTo(satX, satY);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // Draw Satellite Blip
    ctx.fillStyle = sat.is_visible ? (this.anomalyActive ? '#ef4444' : (this.isDarkMode ? '#00ff9d' : '#059669')) : (this.isDarkMode ? '#94a3b8' : '#64748b');
    ctx.shadowColor = sat.is_visible ? (this.anomalyActive ? '#ef4444' : (this.isDarkMode ? '#00ff9d' : '#059669')) : 'transparent';
    ctx.shadowBlur = 10;
    ctx.beginPath();
    ctx.arc(satX, satY, 5, 0, Math.PI * 2);
    ctx.fill();
    ctx.shadowBlur = 0;

    // Satellite label
    ctx.fillStyle = this.isDarkMode ? '#ffffff' : '#0f172a';
    ctx.font = 'bold 9px JetBrains Mono, monospace';
    ctx.fillText('Alice', satX + 8, satY - 6);
  }

  /**
   * Update ECharts multi-series chart.
   */
  private updateChart(history: HistoryPoint[]): void {
    if (!this.echartInstance || history.length === 0) return;

    const times = history.map(h => h.timeLabel);
    const textColor = this.isDarkMode ? '#94a3b8' : '#334155';
    const axisLabelColor = this.isDarkMode ? '#64748b' : '#64748b';
    const splitLineColor = this.isDarkMode ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)';

    let option: echarts.EChartsOption = {};

    if (this.activeTab === 'dual') {
      const skrValues = history.map(h => h.skrKbps);
      const qberValues = history.map(h => h.qberPct);
      option = {
        backgroundColor: 'transparent',
        tooltip: { trigger: 'axis' },
        legend: { data: ['Secret Key Rate (kbps)', 'QBER (%)'], textStyle: { color: textColor, fontSize: 10 } },
        grid: { top: 35, right: 45, bottom: 25, left: 45 },
        xAxis: { type: 'category', data: times, axisLabel: { color: axisLabelColor, fontSize: 10 } },
        yAxis: [
          {
            type: 'value',
            name: 'SKR (kbps)',
            nameTextStyle: { color: this.isDarkMode ? '#00ff9d' : '#059669', fontSize: 10 },
            axisLabel: { color: this.isDarkMode ? '#00ff9d' : '#059669', fontSize: 10 },
            splitLine: { lineStyle: { color: splitLineColor } }
          },
          {
            type: 'value',
            name: 'QBER (%)',
            nameTextStyle: { color: '#f59e0b', fontSize: 10 },
            axisLabel: { color: '#f59e0b', fontSize: 10 },
            splitLine: { show: false },
            max: 20
          }
        ],
        series: [
          {
            name: 'Secret Key Rate (kbps)',
            type: 'line',
            yAxisIndex: 0,
            smooth: true,
            data: skrValues,
            itemStyle: { color: this.isDarkMode ? '#00ff9d' : '#059669' },
            areaStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: this.isDarkMode ? 'rgba(0, 255, 157, 0.25)' : 'rgba(5, 150, 105, 0.2)' },
                { offset: 1, color: 'rgba(0, 255, 157, 0.0)' }
              ])
            }
          },
          {
            name: 'QBER (%)',
            type: 'line',
            yAxisIndex: 1,
            smooth: true,
            data: qberValues,
            itemStyle: { color: '#f59e0b' },
            markLine: {
              silent: true,
              data: [
                {
                  yAxis: 11.0,
                  name: 'BB84 Cutoff (11%)',
                  lineStyle: { color: '#ef4444', width: 2, type: 'dashed' },
                  label: { formatter: '11% Cutoff Limit', color: '#ef4444', position: 'insideEndTop' }
                }
              ]
            }
          }
        ]
      };
    } else if (this.activeTab === 'qber') {
      const qberValues = history.map(h => h.qberPct);
      option = {
        backgroundColor: 'transparent',
        tooltip: { trigger: 'axis' },
        grid: { top: 30, right: 20, bottom: 25, left: 45 },
        xAxis: { type: 'category', data: times, axisLabel: { color: axisLabelColor, fontSize: 10 } },
        yAxis: {
          type: 'value',
          name: 'QBER (%)',
          nameTextStyle: { color: textColor, fontSize: 10 },
          axisLabel: { color: axisLabelColor, fontSize: 10 },
          splitLine: { lineStyle: { color: splitLineColor } },
          max: 20
        },
        series: [
          {
            name: 'Total QBER (%)',
            type: 'line',
            smooth: true,
            data: qberValues,
            itemStyle: { color: '#f59e0b' },
            areaStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: 'rgba(245, 158, 11, 0.3)' },
                { offset: 1, color: 'rgba(245, 158, 11, 0.0)' }
              ])
            },
            markLine: {
              silent: true,
              data: [
                {
                  yAxis: 11.0,
                  name: 'BB84 Cutoff (11%)',
                  lineStyle: { color: '#ef4444', width: 2, type: 'dashed' },
                  label: { formatter: '11% Cutoff', color: '#ef4444', position: 'insideEndTop' }
                }
              ]
            }
          }
        ]
      };
    } else if (this.activeTab === 'skr') {
      const skrValues = history.map(h => h.skrKbps);
      option = {
        backgroundColor: 'transparent',
        tooltip: { trigger: 'axis' },
        grid: { top: 30, right: 20, bottom: 25, left: 45 },
        xAxis: { type: 'category', data: times, axisLabel: { color: axisLabelColor, fontSize: 10 } },
        yAxis: {
          type: 'value',
          name: 'SKR (kbps)',
          nameTextStyle: { color: textColor, fontSize: 10 },
          axisLabel: { color: axisLabelColor, fontSize: 10 },
          splitLine: { lineStyle: { color: splitLineColor } }
        },
        series: [
          {
            name: 'Secret Key Rate (kbps)',
            type: 'line',
            smooth: true,
            data: skrValues,
            itemStyle: { color: this.isDarkMode ? '#00ff9d' : '#059669' },
            areaStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: this.isDarkMode ? 'rgba(0, 255, 157, 0.35)' : 'rgba(5, 150, 105, 0.25)' },
                { offset: 1, color: 'rgba(0, 255, 157, 0.0)' }
              ])
            }
          }
        ]
      };
    } else if (this.activeTab === 'loss') {
      const lossValues = history.map(h => h.totalLossDb);
      option = {
        backgroundColor: 'transparent',
        tooltip: { trigger: 'axis' },
        grid: { top: 30, right: 20, bottom: 25, left: 45 },
        xAxis: { type: 'category', data: times, axisLabel: { color: axisLabelColor, fontSize: 10 } },
        yAxis: {
          type: 'value',
          name: 'Loss (dB)',
          nameTextStyle: { color: textColor, fontSize: 10 },
          axisLabel: { color: axisLabelColor, fontSize: 10 },
          splitLine: { lineStyle: { color: splitLineColor } }
        },
        series: [
          {
            name: 'Total Optical Loss (dB)',
            type: 'line',
            smooth: true,
            data: lossValues,
            itemStyle: { color: this.isDarkMode ? '#38bdf8' : '#0284c7' }
          }
        ]
      };
    } else if (this.activeTab === 'actuators') {
      const pValues = history.map(h => h.laserPowerMw);
      const rValues = history.map(h => h.repetitionRateMhz);
      const dValues = history.map(h => h.beamDivergenceUrad);
      option = {
        backgroundColor: 'transparent',
        tooltip: { trigger: 'axis' },
        grid: { top: 30, right: 20, bottom: 25, left: 45 },
        legend: { data: ['Power (mW)', 'Rate (MHz)', 'Divergence (µrad)'], textStyle: { color: textColor, fontSize: 10 } },
        xAxis: { type: 'category', data: times, axisLabel: { color: axisLabelColor, fontSize: 10 } },
        yAxis: {
          type: 'value',
          axisLabel: { color: axisLabelColor, fontSize: 10 },
          splitLine: { lineStyle: { color: splitLineColor } }
        },
        series: [
          { name: 'Power (mW)', type: 'line', smooth: true, data: pValues, itemStyle: { color: '#ef4444' } },
          { name: 'Rate (MHz)', type: 'line', smooth: true, data: rValues, itemStyle: { color: '#a855f7' } },
          { name: 'Divergence (µrad)', type: 'line', smooth: true, data: dValues, itemStyle: { color: this.isDarkMode ? '#00f0ff' : '#0284c7' } }
        ]
      };
    }

    this.echartInstance.setOption(option, true);
  }
}
