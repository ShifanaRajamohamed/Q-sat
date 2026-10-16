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

  @ViewChild('skyCanvas', { static: false }) skyCanvasRef!: ElementRef<HTMLCanvasElement>;
  @ViewChild('chartContainer', { static: false }) chartContainerRef!: ElementRef<HTMLDivElement>;

  public telemetry: TelemetryPacket | null = null;
  public connectionStatus: ConnectionStatus = 'DISCONNECTED';
  public activeTab: 'qber' | 'skr' | 'loss' | 'actuators' = 'qber';

  public selectedScenario: string = 'CLEAR_SKY';
  public anomalyActive: boolean = false;

  public showResultsModal: boolean = false;
  public activeResultsTab: 'leaderboard' | 'statistics' | 'figures' | 'report' = 'leaderboard';
  public isRunningDemo: boolean = false;
  public demoSummary: any[] | null = null;
  public masterSummary: any = null;

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
  };

  public setTab(tab: 'qber' | 'skr' | 'loss' | 'actuators'): void {
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
    if (this.showResultsModal && !this.masterSummary) {
      this.loadMasterSummary();
    }
  }

  public setResultsTab(tab: 'leaderboard' | 'statistics' | 'figures' | 'report'): void {
    this.activeResultsTab = tab;
  }

  public loadMasterSummary(): void {
    this.telemetryService.getExperimentsSummary().subscribe({
      next: (data) => {
        this.masterSummary = data;
      },
      error: (err) => console.error('Error loading experiments summary:', err)
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
      ctx.strokeStyle = 'rgba(0, 255, 157, 0.5)';
      ctx.lineWidth = 1.5;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.lineTo(satX, satY);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // Draw Satellite Blip
    ctx.fillStyle = sat.is_visible ? '#00ff9d' : '#94a3b8';
    ctx.shadowColor = sat.is_visible ? '#00ff9d' : 'transparent';
    ctx.shadowBlur = 10;
    ctx.beginPath();
    ctx.arc(satX, satY, 5, 0, Math.PI * 2);
    ctx.fill();
    ctx.shadowBlur = 0;

    // Satellite label
    ctx.fillStyle = '#ffffff';
    ctx.font = '9px JetBrains Mono, monospace';
    ctx.fillText('LEO-01', satX + 8, satY - 6);
  }

  /**
   * Update ECharts multi-series chart.
   */
  private updateChart(history: HistoryPoint[]): void {
    if (!this.echartInstance || history.length === 0) return;

    const times = history.map(h => h.timeLabel);

    let option: echarts.EChartsOption = {};

    if (this.activeTab === 'qber') {
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
