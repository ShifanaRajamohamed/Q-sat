export interface SatelliteTelemetry {
  timestamp: number;
  satellite_name?: string;
  elevation_deg: number;
  azimuth_deg: number;
  slant_range_km: number;
  altitude_km: number;
  latitude: number;
  longitude: number;
  is_visible: boolean;
  pass_progress: number;
  link_status?: string;
  time_to_los_s?: number;
  time_to_aos_s?: number | null;
}

export interface EnvironmentTelemetry {
  temperature: number;
  humidity: number;
  ambient_light: number;
  vibration: number;
  cloud_factor: number;
  turbulence: number;
  data_source: 'SIMULATION' | 'HARDWARE';
  scenario_name: string;
  timestamp: number;
}

export interface OpticalChannelTelemetry {
  total_loss_db: number;
  transmittance: number;
  fspl_loss_db: number;
  atmospheric_loss_db: number;
  pointing_loss_db: number;
  scintillation_loss_db: number;
  received_photon_rate: number;
  background_noise_rate: number;
  snr_db: number;
  beam_spot_radius_m: number;
}

export interface QBERDecomposition {
  base_error: number;
  atmospheric_noise: number;
  background_light_noise: number;
  pointing_error: number;
  detector_noise: number;
  security_anomaly_component: number;
  total_qber: number;
}

export interface QKDTelemetry {
  timestamp: number;
  transmitted_photon_rate: number;
  received_photon_rate: number;
  raw_key_rate: number;
  sifted_key_rate: number;
  qber: number;
  secret_key_rate: number;
  qber_decomposition: QBERDecomposition;
  channel_loss_db: number;
  channel_transmittance: number;
  is_key_distillation_possible: boolean;
  status_label: 'SECURE' | 'DEGRADED' | 'ANOMALY' | 'ABORT';
}

export interface ControlTelemetry {
  current: {
    transmission_power_pct: number;
    photon_rate_norm: number;
    beam_divergence_norm: number;
    controller_type: string;
    reason?: string;
  };
  delta?: {
    delta_power_pct: number;
    delta_photon_rate: number;
    delta_beam_divergence: number;
    controller_type?: string;
  };
  mode: 'STATIC' | 'RULE_BASED' | 'PPO' | 'MULTI_AGENT';
}

export interface MultiAgentTelemetry {
  weather_agent?: {
    condition: string;
    power_boost_factor: number;
    divergence_factor: number;
    notes?: string;
  };
  communication_agent?: {
    recommended_repetition_rate_mhz: number;
    recommended_divergence_urad: number;
    link_margin_db: number;
    notes?: string;
  };
  security_agent?: {
    security_status: string;
    detected_anomaly: boolean;
    anomaly_score: number;
    anomaly_type?: string;
    action_override: boolean;
    notes?: string;
  };
  coordinator?: {
    final_action: {
      laser_power_mw: number;
      repetition_rate_mhz: number;
      beam_divergence_urad: number;
    };
    arbitration_reason: string;
    active_overrides: string[];
  };
}

export interface AlertItem {
  id: string;
  severity: 'INFO' | 'WARNING' | 'CRITICAL';
  category: string;
  title: string;
  message: string;
  timestamp: string;
  is_active: boolean;
}

export interface TelemetryPacket {
  timestamp: number;
  satellite: SatelliteTelemetry;
  environment: EnvironmentTelemetry;
  channel?: OpticalChannelTelemetry;
  qkd: QKDTelemetry;
  control: ControlTelemetry;
  ai_agents?: MultiAgentTelemetry | null;
  alerts: AlertItem[];
}
