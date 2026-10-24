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

  public telemetry: TelemetryPacket | null = null;
  public connectionStatus: ConnectionStatus = 'DISCONNECTED';
  public activeTab: 'dual' | 'qber' | 'skr' | 'loss' | 'actuators' = 'dual';

  public selectedScenario: string = 'CLEAR_SKY';
  public anomalyActive: boolean = false;
  public showMissionBriefing: boolean = true;

  public showResultsModal: boolean = false;
  public activeResultsTab: 'leaderboard' | 'statistics' | 'datasets' | 'figures' | 'report' = 'leaderboard';
  public isRunningDemo: boolean = false;
  public demoSummary: any[] | null = null;
  public masterSummary: any = null;

  public datasetsCatalog: any[] = [];
  public selectedDatasetScenario: string = 'CLEAR_SKY';
  public selectedDatasetData: any = null;
  public isLoadingDataset: boolean = false;

  private subs = new Subscription();
  private echartInstance: echarts.ECharts | null = null;
  private canvasCtx: CanvasRenderingContext2D | null = null;
  private trajectoryPoints: Array<{ x: number; y: number }> = [];

  ngOnInit(): void {
    this.subs.add(
      this.telemetryService.connectionStatus$.subscribe(status => {
        this.connectionStatus = status;
      })
    );

    this.subs.add(
      this.telemetryService.telemetry$.subscribe(packet => {
        if (packet) {
          this.telemetry = packet;
          this.anomalyActive = (packet.qkd?.qber_decomposition?.security_anomaly_component || 0) > 0.001;
          this.drawSkyDome();
          this.drawWorldMap();
        }
      })
    );

    this.subs.add(
      this.telemetryService.history$.subscribe(history => {
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
      this.echartInstance = echarts.init(this.chartContainerRef.nativeElement, 'dark');
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

    // 1. Deep Space Ocean Background
    const bgGrad = ctx.createLinearGradient(0, 0, 0, h);
    bgGrad.addColorStop(0, '#060b17');
    bgGrad.addColorStop(0.5, '#081122');
    bgGrad.addColorStop(1, '#050a14');
    ctx.fillStyle = bgGrad;
    ctx.fillRect(0, 0, w, h);

    // 2. Latitude & Longitude Coordinate Grids
    ctx.strokeStyle = 'rgba(56, 189, 248, 0.08)';
    ctx.lineWidth = 1;

    // Latitudes (every 30 degrees)
    for (let lat = -60; lat <= 60; lat += 30) {
      const y = ((90 - lat) / 180) * h;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();

      // Label
      ctx.fillStyle = 'rgba(148, 163, 184, 0.35)';
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
      ctx.fillStyle = 'rgba(148, 163, 184, 0.35)';
      ctx.font = '8px JetBrains Mono, monospace';
      ctx.fillText(`${lon >= 0 ? lon + '°E' : Math.abs(lon) + '°W'}`, x + 3, h - 4);
    }

    // Equator highlight
    const eqY = h / 2;
    ctx.strokeStyle = 'rgba(56, 189, 248, 0.2)';
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

    ctx.fillStyle = 'rgba(26, 41, 66, 0.55)';
    ctx.strokeStyle = 'rgba(56, 189, 248, 0.3)';
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
    ctx.fillStyle = 'rgba(0, 255, 157, 0.07)';
    ctx.strokeStyle = 'rgba(0, 255, 157, 0.4)';
    ctx.lineWidth = 1.2;
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    ctx.arc(gsX, gsY, coneRadius, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    ctx.setLineDash([]);

    // Ground Station Center Beacon
    ctx.fillStyle = '#00ff9d';
    ctx.beginPath();
    ctx.arc(gsX, gsY, 4, 0, Math.PI * 2);
    ctx.fill();

    // Ground Station Label
    ctx.fillStyle = '#00ff9d';
    ctx.font = 'bold 9.5px Inter, sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText('Bob (OGS Trichy)', gsX + 7, gsY + 3);

    // 5. Orbital Ground Track Line
    ctx.strokeStyle = 'rgba(168, 85, 247, 0.4)';
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
    ctx.fillStyle = 'rgba(0, 240, 255, 0.08)';
    ctx.strokeStyle = 'rgba(0, 240, 255, 0.4)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.arc(satX, satY, satFootprintR, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    // 7. Live Quantum Laser Link Beam (When in line-of-sight tracking)
    if (sat.is_visible) {
      ctx.save();
      ctx.shadowBlur = this.anomalyActive ? 15 : 12;
      ctx.shadowColor = this.anomalyActive ? '#ef4444' : '#00f0ff';
      ctx.strokeStyle = this.anomalyActive ? 'rgba(239, 68, 68, 0.9)' : 'rgba(0, 240, 255, 0.85)';
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.moveTo(satX, satY);
      ctx.lineTo(gsX, gsY);
      ctx.stroke();

      // Pulsing Photon Packets along beam
      const pulseFrac = (Date.now() % 1200) / 1200;
      const pulseX = satX + (gsX - satX) * pulseFrac;
      const pulseY = satY + (gsY - satY) * pulseFrac;
      ctx.fillStyle = '#ffffff';
      ctx.beginPath();
      ctx.arc(pulseX, pulseY, 3, 0, Math.PI * 2);
      ctx.fill();

      ctx.restore();
    }

    // Satellite Beacon Icon
    ctx.save();
    ctx.shadowBlur = 12;
    ctx.shadowColor = '#00f0ff';
    ctx.fillStyle = '#00f0ff';
    ctx.beginPath();
    ctx.arc(satX, satY, 5, 0, Math.PI * 2);
    ctx.fill();

    // Satellite Solar Panels Icon
    ctx.fillStyle = '#38bdf8';
    ctx.fillRect(satX - 10, satY - 2, 5, 4);
    ctx.fillRect(satX + 5, satY - 2, 5, 4);

    // Label
    ctx.fillStyle = '#ffffff';
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

    // Background gradient
    const grad = ctx.createRadialGradient(cx, cy, 5, cx, cy, maxR);
    grad.addColorStop(0, '#0a1424');
    grad.addColorStop(1, '#050a12');
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(cx, cy, maxR, 0, Math.PI * 2);
    ctx.fill();

    // Concentric elevation rings (10 deg horizon, 30 deg, 60 deg, 90 deg center)
    const elevations = [10, 30, 60];
    elevations.forEach(el => {
      const r = maxR * (1 - (el - 10) / 80);
      ctx.strokeStyle = 'rgba(56, 189, 248, 0.15)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.stroke();

      // Elevation label
      ctx.fillStyle = 'rgba(148, 163, 184, 0.6)';
      ctx.font = '9px JetBrains Mono, monospace';
      ctx.fillText(`${el}°`, cx + 3, cy - r + 9);
    });

    // Crosshairs & Compass Spokes
    ctx.strokeStyle = 'rgba(56, 189, 248, 0.15)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(cx, cy - maxR);
    ctx.lineTo(cx, cy + maxR);
    ctx.moveTo(cx - maxR, cy);
    ctx.lineTo(cx + maxR, cy);
    ctx.stroke();

    // Cardinal Labels
    ctx.fillStyle = '#38bdf8';
    ctx.font = '10px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('N', cx, cy - maxR + 8);
    ctx.fillText('S', cx, cy + maxR - 8);
    ctx.fillText('E', cx + maxR - 8, cy);
    ctx.fillText('W', cx - maxR + 8, cy);

    // Ground Station Center Anchor
    ctx.fillStyle = '#00f0ff';
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
      ctx.strokeStyle = 'rgba(0, 240, 255, 0.35)';
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
      ctx.strokeStyle = this.anomalyActive ? 'rgba(239, 68, 68, 0.6)' : 'rgba(0, 255, 157, 0.5)';
      ctx.lineWidth = 1.5;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.lineTo(satX, satY);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // Draw Satellite Blip
    ctx.fillStyle = sat.is_visible ? (this.anomalyActive ? '#ef4444' : '#00ff9d') : '#94a3b8';
    ctx.shadowColor = sat.is_visible ? (this.anomalyActive ? '#ef4444' : '#00ff9d') : 'transparent';
    ctx.shadowBlur = 10;
    ctx.beginPath();
    ctx.arc(satX, satY, 5, 0, Math.PI * 2);
    ctx.fill();
    ctx.shadowBlur = 0;

    // Satellite label
    ctx.fillStyle = '#ffffff';
    ctx.font = '9px JetBrains Mono, monospace';
    ctx.fillText('Alice', satX + 8, satY - 6);
  }

  /**
   * Update ECharts multi-series chart.
   */
  private updateChart(history: HistoryPoint[]): void {
    if (!this.echartInstance || history.length === 0) return;

    const times = history.map(h => h.timeLabel);

    let option: echarts.EChartsOption = {};

    if (this.activeTab === 'dual') {
      const skrValues = history.map(h => h.skrKbps);
      const qberValues = history.map(h => h.qberPct);
      option = {
        backgroundColor: 'transparent',
        tooltip: { trigger: 'axis' },
        legend: { data: ['Secret Key Rate (kbps)', 'QBER (%)'], textStyle: { color: '#94a3b8', fontSize: 10 } },
        grid: { top: 35, right: 45, bottom: 25, left: 45 },
        xAxis: { type: 'category', data: times, axisLabel: { color: '#64748b', fontSize: 10 } },
        yAxis: [
          {
            type: 'value',
            name: 'SKR (kbps)',
            nameTextStyle: { color: '#00ff9d', fontSize: 10 },
            axisLabel: { color: '#00ff9d', fontSize: 10 },
            splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } }
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
            itemStyle: { color: '#00ff9d' },
            areaStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: 'rgba(0, 255, 157, 0.25)' },
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
        xAxis: { type: 'category', data: times, axisLabel: { color: '#64748b', fontSize: 10 } },
        yAxis: {
          type: 'value',
          name: 'QBER (%)',
          nameTextStyle: { color: '#94a3b8', fontSize: 10 },
          axisLabel: { color: '#64748b', fontSize: 10 },
          splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
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
        xAxis: { type: 'category', data: times, axisLabel: { color: '#64748b', fontSize: 10 } },
        yAxis: {
          type: 'value',
          name: 'SKR (kbps)',
          nameTextStyle: { color: '#94a3b8', fontSize: 10 },
          axisLabel: { color: '#64748b', fontSize: 10 },
          splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } }
        },
        series: [
          {
            name: 'Secret Key Rate (kbps)',
            type: 'line',
            smooth: true,
            data: skrValues,
            itemStyle: { color: '#00ff9d' },
            areaStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: 'rgba(0, 255, 157, 0.35)' },
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
        xAxis: { type: 'category', data: times, axisLabel: { color: '#64748b', fontSize: 10 } },
        yAxis: {
          type: 'value',
          name: 'Loss (dB)',
          nameTextStyle: { color: '#94a3b8', fontSize: 10 },
          axisLabel: { color: '#64748b', fontSize: 10 },
          splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } }
        },
        series: [
          {
            name: 'Total Optical Loss (dB)',
            type: 'line',
            smooth: true,
            data: lossValues,
            itemStyle: { color: '#38bdf8' }
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
        legend: { data: ['Power (mW)', 'Rate (MHz)', 'Divergence (µrad)'], textStyle: { color: '#94a3b8', fontSize: 10 } },
        xAxis: { type: 'category', data: times, axisLabel: { color: '#64748b', fontSize: 10 } },
        yAxis: {
          type: 'value',
          axisLabel: { color: '#64748b', fontSize: 10 },
          splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } }
        },
        series: [
          { name: 'Power (mW)', type: 'line', smooth: true, data: pValues, itemStyle: { color: '#ef4444' } },
          { name: 'Rate (MHz)', type: 'line', smooth: true, data: rValues, itemStyle: { color: '#a855f7' } },
          { name: 'Divergence (µrad)', type: 'line', smooth: true, data: dValues, itemStyle: { color: '#00f0ff' } }
        ]
      };
    }

    this.echartInstance.setOption(option, true);
  }
}
