"""HistoricalWeatherProvider: Replays timestamped historical weather CSV data for Tiruchirappalli.

Implements the EnvironmentProvider interface, feeding real-world reanalysis or local meteorological
records into the Q-SAT optical channel and digital twin simulation.

Preserves scientific integrity:
- Clearly separates meteorological cloud cover (%) from optical cloud factor / optical depth.
- Marks unmeasured quantities (turbulence, vibration) as configured assumptions.
- Models ambient background light from solar geometry/irradiance without pretending it was measured.
- Distinguishes exact hourly held observations from linearly interpolated values.
"""

from dataclasses import dataclass
import datetime
import json
import logging
from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple
import numpy as np
import pandas as pd

from backend.app.config import settings
from backend.app.models.environment import EnvironmentData, HistoricalReplayStatus
from digital_twin.environment_provider import EnvironmentProvider

logger = logging.getLogger("qsat.historical_weather_provider")


@dataclass
class WeatherRecord:
    """Internal standardized weather observation record."""
    epoch_s: float
    datetime_iso: str
    temperature_c: float
    humidity_pct: float
    cloud_cover_pct: float
    wind_speed_m_s: float
    shortwave_radiation_w_m2: float
    surface_pressure_hpa: float


class HistoricalWeatherProvider(EnvironmentProvider):
    """Feeds timestamped historical meteorological data into the simulation clock."""

    def __init__(
        self,
        csv_path: str | Path = "simulation/historical_weather/tiruchirappalli_20240301_20240331_era5.csv",
        start_datetime_iso: Optional[str] = None,
        interpolation_mode: Literal["HOLD", "LINEAR"] = "LINEAR",
        assumed_turbulence: float = 0.12,
        assumed_vibration_g: float = 0.015,
        default_ambient_light_lux: float = 300.0
    ):
        self.csv_path = Path(csv_path)
        self.requested_start_iso = start_datetime_iso
        self.interpolation_mode = interpolation_mode
        self.assumed_turbulence = assumed_turbulence
        self.assumed_vibration_g = assumed_vibration_g
        self.default_ambient_light_lux = default_ambient_light_lux

        self.records: List[WeatherRecord] = []
        self.meta: Dict = {}
        self.start_epoch_s: float = 0.0
        self.end_epoch_s: float = 0.0
        self.current_sim_time_s: float = 0.0

        self._load_and_validate_csv()
        self.reset()

    def _load_and_validate_csv(self) -> None:
        """Parse CSV, validate timestamps, gaps, value ranges, and read metadata."""
        if not self.csv_path.exists():
            raise FileNotFoundError(f"Historical weather CSV not found at: {self.csv_path}")

        # Attempt reading companion metadata
        meta_candidates = [
            self.csv_path.with_suffix(".meta.json"),
            Path(str(self.csv_path) + ".meta.json")
        ]
        for candidate in meta_candidates:
            if candidate.exists():
                try:
                    with open(candidate, "r", encoding="utf-8") as f:
                        self.meta = json.load(f)
                    break
                except Exception as e:
                    logger.warning("Could not parse companion metadata %s: %s", candidate, e)

        # Parse CSV (filtering comment lines)
        try:
            df = pd.read_csv(self.csv_path, comment="#")
        except Exception as exc:
            raise ValueError(f"Failed to read CSV at {self.csv_path}: {exc}")

        # Validate required columns
        req_cols = ["timestamp", "temperature_c", "relative_humidity_pct", "cloud_cover_pct"]
        missing = [c for c in req_cols if c not in df.columns]
        if missing:
            raise ValueError(f"CSV at {self.csv_path} is missing required columns: {missing}")

        # Parse timestamps to UTC epoch seconds
        records = []
        prev_epoch = None

        for idx, row in df.iterrows():
            ts_raw = str(row["timestamp"]).strip()
            try:
                # Handle ISO timestamps with or without timezone
                if ts_raw.endswith("Z"):
                    dt = datetime.datetime.fromisoformat(ts_raw[:-1]).replace(tzinfo=datetime.timezone.utc)
                else:
                    dt = datetime.datetime.fromisoformat(ts_raw)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=datetime.timezone.utc)
            except Exception as e:
                raise ValueError(f"Invalid timestamp format at row {idx} ('{ts_raw}'): {e}")

            epoch_s = dt.timestamp()

            # Monotonicity check
            if prev_epoch is not None and epoch_s <= prev_epoch:
                raise ValueError(f"Timestamps in {self.csv_path} are not strictly monotonic at row {idx}: {ts_raw}")
            prev_epoch = epoch_s

            # Value validation & clamping
            temp = float(row["temperature_c"])
            if not (-50.0 <= temp <= 65.0):
                raise ValueError(f"Temperature {temp} C out of physical bounds at row {idx}")

            hum = float(row["relative_humidity_pct"])
            if not (0.0 <= hum <= 100.0):
                raise ValueError(f"Humidity {hum}% out of physical bounds at row {idx}")

            cloud = float(row["cloud_cover_pct"])
            if not (0.0 <= cloud <= 100.0):
                raise ValueError(f"Cloud cover {cloud}% out of physical bounds at row {idx}")

            wind = float(row.get("wind_speed_m_s", 2.5))
            wind = max(0.0, wind)

            solar = float(row.get("shortwave_radiation_w_m2", 0.0))
            solar = max(0.0, solar)

            pressure = float(row.get("surface_pressure_hpa", 1010.0))

            records.append(WeatherRecord(
                epoch_s=epoch_s,
                datetime_iso=dt.isoformat(),
                temperature_c=temp,
                humidity_pct=hum,
                cloud_cover_pct=cloud,
                wind_speed_m_s=wind,
                shortwave_radiation_w_m2=solar,
                surface_pressure_hpa=pressure
            ))

        if not records:
            raise ValueError(f"CSV {self.csv_path} contains 0 valid weather records.")

        self.records = records
        self.file_start_epoch_s = records[0].epoch_s
        self.file_end_epoch_s = records[-1].epoch_s

        # Determine target starting epoch
        if self.requested_start_iso:
            try:
                dt_req = datetime.datetime.fromisoformat(self.requested_start_iso.replace("Z", "+00:00"))
                target_epoch = dt_req.timestamp()
                if not (self.file_start_epoch_s <= target_epoch <= self.file_end_epoch_s):
                    raise ValueError(
                        f"Requested start date {self.requested_start_iso} is outside dataset range "
                        f"[{records[0].datetime_iso} to {records[-1].datetime_iso}]"
                    )
                self.start_epoch_s = target_epoch
            except Exception as e:
                raise ValueError(f"Invalid requested start date {self.requested_start_iso}: {e}")
        else:
            self.start_epoch_s = self.file_start_epoch_s

        logger.info(
            "HistoricalWeatherProvider loaded %d records from %s (Span: %s to %s)",
            len(records), self.csv_path.name, records[0].datetime_iso, records[-1].datetime_iso
        )

    def set_start_datetime(self, start_iso: str) -> None:
        """Dynamically re-anchor the historical replay to a new start date/time."""
        self.requested_start_iso = start_iso
        self._load_and_validate_csv()
        self.reset()

    def set_interpolation_mode(self, mode: Literal["HOLD", "LINEAR"]) -> None:
        """Switch between Zero-Order Hold and Linear Interpolation."""
        self.interpolation_mode = mode

    def reset(self, seed: Optional[int] = None) -> EnvironmentData:
        """Reset replay clock to configured start time."""
        self.current_sim_time_s = 0.0
        return self._evaluate_at_current_time()

    def step(self, dt: float = 1.0) -> EnvironmentData:
        """Advance replay clock by dt seconds."""
        self.current_sim_time_s += dt
        return self._evaluate_at_current_time()

    def get_current_environment(self) -> EnvironmentData:
        """Return the current environmental state vector."""
        return self._evaluate_at_current_time()

    def _evaluate_at_current_time(self) -> EnvironmentData:
        """Interpolate or hold records at (start_epoch_s + current_sim_time_s)."""
        current_epoch = self.start_epoch_s + self.current_sim_time_s

        # Clamp to available dataset boundaries
        clamped_epoch = min(max(current_epoch, self.file_start_epoch_s), self.file_end_epoch_s)

        # Find bounding records
        idx = self._find_record_index(clamped_epoch)
        rec0 = self.records[idx]

        is_interpolated = False
        method = self.interpolation_mode

        if self.interpolation_mode == "HOLD" or idx >= len(self.records) - 1:
            temp = rec0.temperature_c
            hum = rec0.humidity_pct
            cloud = rec0.cloud_cover_pct
            wind = rec0.wind_speed_m_s
            solar = rec0.shortwave_radiation_w_m2
            is_interpolated = False
            dt_curr = datetime.datetime.fromtimestamp(clamped_epoch, tz=datetime.timezone.utc)
        else:
            rec1 = self.records[idx + 1]
            t0, t1 = rec0.epoch_s, rec1.epoch_s
            alpha = (clamped_epoch - t0) / (t1 - t0) if t1 > t0 else 0.0
            alpha = max(0.0, min(1.0, alpha))

            temp = rec0.temperature_c + alpha * (rec1.temperature_c - rec0.temperature_c)
            hum = rec0.humidity_pct + alpha * (rec1.humidity_pct - rec0.humidity_pct)
            cloud = rec0.cloud_cover_pct + alpha * (rec1.cloud_cover_pct - rec0.cloud_cover_pct)
            wind = rec0.wind_speed_m_s + alpha * (rec1.wind_speed_m_s - rec0.wind_speed_m_s)
            solar = rec0.shortwave_radiation_w_m2 + alpha * (rec1.shortwave_radiation_w_m2 - rec0.shortwave_radiation_w_m2)

            is_interpolated = (0.001 < alpha < 0.999)
            dt_curr = datetime.datetime.fromtimestamp(clamped_epoch, tz=datetime.timezone.utc)

        # 1. Optical Cloud Factor derivation (separate from meteorological cloud cover)
        # Meteorological cloud cover [0, 100]% is mapped to optical cloud factor [0.0, 1.0]
        # through an explicit optical transmission transfer function:
        # e.g., cloud_factor = min(1.0, (cloud_cover / 100.0) ^ 1.25)
        cloud_factor = float(np.clip((cloud / 100.0) ** 1.25, 0.0, 1.0))

        # 2. Ambient Light modeling:
        # Solar radiation in W/m^2 converted via luminous efficacy (~115 lux per W/m^2 for terrestrial sunlight)
        if solar > 0.0:
            ambient_light = float(solar * 115.0)
        else:
            ambient_light = 0.0  # Nighttime / zero solar irradiance

        # 3. Turbulence modeling:
        # Configured assumption baseline, mildly modulated by ground wind shear
        turbulence = float(np.clip(self.assumed_turbulence + 0.012 * wind, 0.01, 1.0))

        # 4. Mount vibration:
        # Purely mechanical platform property; unmeasured by weather stations
        vibration = float(self.assumed_vibration_g)

        # Explicit provenance ledger
        source_tag = self.meta.get("provenance", "REANALYSIS_CSV")
        field_provenance = {
            "temperature": source_tag,
            "humidity": source_tag,
            "meteorological_cloud_cover_pct": source_tag,
            "wind_speed": source_tag,
            "cloud_factor": "DERIVED_OPTICAL_MODEL (f(cloud_cover^1.25))",
            "ambient_light": "SOLAR_RADIATION_MODELED (115 lux/(W/m^2))",
            "turbulence": f"CONFIGURED_ASSUMPTION (baseline={self.assumed_turbulence:.2f})",
            "vibration": f"CONFIGURED_ASSUMPTION (baseline={self.assumed_vibration_g:.3f}g)"
        }

        return EnvironmentData(
            timestamp=round(self.current_sim_time_s, 2),
            temperature=round(temp, 2),
            humidity=round(hum, 1),
            ambient_light=round(ambient_light, 1),
            vibration=round(vibration, 3),
            cloud_factor=round(cloud_factor, 4),
            turbulence=round(turbulence, 3),
            data_source="HISTORICAL_REPLAY",
            scenario_name=f"HISTORICAL_REPLAY ({self.csv_path.stem})",
            meteorological_cloud_cover_pct=round(cloud, 1),
            wind_speed_m_s=round(wind, 2),
            datetime_iso=dt_curr.isoformat(),
            is_interpolated=is_interpolated,
            interpolation_method=method,
            field_provenance=field_provenance
        )

    def _find_record_index(self, epoch_s: float) -> int:
        """Binary search for the greatest index where records[idx].epoch_s <= epoch_s."""
        epochs = [r.epoch_s for r in self.records]
        import bisect
        idx = bisect.bisect_right(epochs, epoch_s) - 1
        return max(0, min(idx, len(self.records) - 1))

    def get_mode(self) -> str:
        return "historical_replay"

    def is_healthy(self) -> bool:
        return len(self.records) > 0

    def get_status(self) -> HistoricalReplayStatus:
        """Return structured status metadata."""
        curr = self._evaluate_at_current_time()
        return HistoricalReplayStatus(
            is_active=True,
            csv_file=self.csv_path.name,
            dataset_source=self.meta.get("dataset_name", self.csv_path.stem),
            location_name=self.meta.get("location_name", "Tiruchirappalli reference ground station"),
            latitude=self.meta.get("latitude", settings.GROUND_STATION_LAT),
            longitude=self.meta.get("longitude", settings.GROUND_STATION_LON),
            file_start_iso=self.records[0].datetime_iso if self.records else None,
            file_end_iso=self.records[-1].datetime_iso if self.records else None,
            current_time_iso=curr.datetime_iso,
            total_records=len(self.records),
            interpolation_mode=self.interpolation_mode,
            is_interpolated=curr.is_interpolated,
            notes=(
                "Meteorological data (temp, humidity, cloud cover, wind) loaded from CSV. "
                "Optical cloud depth derived separately from cloud cover. "
                "Turbulence, vibration, and background light are configured models/assumptions."
            )
        )

