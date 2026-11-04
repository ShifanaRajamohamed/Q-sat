"""Fetch historical meteorological data for Tiruchirappalli reference ground station.

Queries the documented Open-Meteo Historical Weather API (ERA5 Reanalysis)
for specified date ranges and converts the response into standardized Q-SAT CSV format.

Attribution: Weather data courtesy of Open-Meteo.com under CC BY 4.0 license.
Data source: ERA5 / ERA5-Land reanalysis from ECMWF.
"""

import argparse
import csv
import datetime
import json
import logging
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger("qsat.fetch_weather")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

DEFAULT_LAT = 10.7905
DEFAULT_LON = 78.7047
DEFAULT_ALT = 80.0
LOCATION_NAME = "Tiruchirappalli reference ground station"
API_URL = "https://archive-api.open-meteo.com/v1/archive"


def fetch_open_meteo_historical(
    start_date: str,
    end_date: str,
    latitude: float = DEFAULT_LAT,
    longitude: float = DEFAULT_LON,
    model: str = "era5",
    output_dir: Path | str = "simulation/historical_weather"
) -> Path:
    """Fetch hourly historical data from Open-Meteo Archive API and save CSV + Metadata.
    
    Args:
        start_date: YYYY-MM-DD
        end_date: YYYY-MM-DD
        latitude: Station latitude in degrees North
        longitude: Station longitude in degrees East
        model: 'era5' or 'best_match'
        output_dir: Directory to save generated CSV and metadata
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": [
            "temperature_2m",
            "relative_humidity_2m",
            "cloud_cover",
            "wind_speed_10m",
            "shortwave_radiation_instant",
            "surface_pressure"
        ],
        "timezone": "UTC"
    }

    if model == "era5":
        params["models"] = "era5"
        model_label = "ECMWF ERA5 Reanalysis (Explicitly requested via models=era5)"
        provenance_str = "REANALYSIS_ERA5"
        slug_suffix = "_era5"
    else:
        model_label = "Open-Meteo Best Match Reanalysis Blend (Default selection, models parameter not specified)"
        provenance_str = "REANALYSIS_BEST_MATCH"
        slug_suffix = "_best_match"

    query_str = urllib.parse.urlencode(params, doseq=True)
    full_url = f"{API_URL}?{query_str}"
    logger.info("Requesting historical weather from: %s", full_url)

    req = urllib.request.Request(
        full_url,
        headers={"User-Agent": "Q-SAT-GroundStation/0.2.0 (Academic Research; https://github.com/qsat)"}
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw_data = response.read().decode("utf-8")
            data = json.loads(raw_data)
    except urllib.error.URLError as err:
        logger.error("Network or API error while contacting Open-Meteo: %s", err)
        print(f"\n[ERROR] Could not fetch data from Open-Meteo API: {err}")
        print("NOTICE: In environments without external network access, import local CSV files directly")
        print("or use the provided validated test fixture:")
        print("  simulation/historical_weather/tiruchirappalli_2024_03_synthetic_fixture.csv\n")
        raise

    retrieval_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Save raw response
    slug = f"tiruchirappalli_{start_date.replace('-', '')}_{end_date.replace('-', '')}{slug_suffix}"
    raw_path = out_path / f"{slug}_raw.json"
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    logger.info("Saved raw API response to: %s", raw_path)

    # Parse hourly arrays
    hourly = data.get("hourly", {})
    timestamps = hourly.get("time", [])
    temps = hourly.get("temperature_2m", [])
    humidity = hourly.get("relative_humidity_2m", [])
    clouds = hourly.get("cloud_cover", [])
    wind = hourly.get("wind_speed_10m", [])
    radiation = hourly.get("shortwave_radiation_instant", [])
    pressure = hourly.get("surface_pressure", [])

    rows = []
    for i, ts in enumerate(timestamps):
        # Format ISO with Z
        iso_ts = ts if ts.endswith("Z") else f"{ts}:00Z" if len(ts) == 16 else f"{ts}Z"
        rows.append({
            "timestamp": iso_ts,
            "temperature_c": temps[i] if i < len(temps) and temps[i] is not None else "",
            "relative_humidity_pct": humidity[i] if i < len(humidity) and humidity[i] is not None else "",
            "cloud_cover_pct": clouds[i] if i < len(clouds) and clouds[i] is not None else "",
            "wind_speed_m_s": round(wind[i] / 3.6, 2) if i < len(wind) and wind[i] is not None else "",  # km/h to m/s
            "shortwave_radiation_w_m2": radiation[i] if i < len(radiation) and radiation[i] is not None else 0.0,
            "surface_pressure_hpa": pressure[i] if i < len(pressure) and pressure[i] is not None else 1010.0
        })

    # Save standardized CSV
    csv_file = out_path / f"{slug}.csv"
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        f.write(f"# DATASET PROVENANCE: Open-Meteo Historical Weather API ({provenance_str})\n")
        f.write(f"# LOCATION: {LOCATION_NAME} | Lat: {latitude} N, Lon: {longitude} E, Alt: {DEFAULT_ALT} m\n")
        f.write(f"# RETRIEVAL_TIMESTAMP: {retrieval_iso} | URL: {full_url}\n")
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    logger.info("Saved standardized CSV to: %s (%d records)", csv_file, len(rows))

    # Save companion metadata
    meta_file = out_path / f"{slug}.meta.json"
    meta = {
        "dataset_name": f"Tiruchirappalli Historical Weather ({start_date} to {end_date}, {model.upper()})",
        "location_name": LOCATION_NAME,
        "data_type": model_label,
        "requested_coordinates": {
            "latitude": latitude,
            "longitude": longitude,
            "altitude_m": DEFAULT_ALT
        },
        "returned_grid_coordinates": {
            "latitude": data.get("latitude"),
            "longitude": data.get("longitude"),
            "elevation_m": data.get("elevation")
        },
        "timezone": data.get("timezone", "UTC"),
        "utc_offset_seconds": data.get("utc_offset_seconds", 0),
        "api_hourly_units": data.get("hourly_units", {}),
        "latitude": latitude,
        "longitude": longitude,
        "altitude_m": DEFAULT_ALT,
        "start_time_iso": rows[0]["timestamp"] if rows else None,
        "end_time_iso": rows[-1]["timestamp"] if rows else None,
        "total_records": len(rows),
        "temporal_resolution": "1 hour",
        "provenance": provenance_str,
        "model_requested": model,
        "is_synthetic": False,
        "api_url": full_url,
        "retrieval_timestamp_iso": retrieval_iso,
        "license": "CC BY 4.0 / Open-Meteo Terms",
        "fields": {
            "timestamp": {"unit": "ISO 8601 UTC string", "provenance": "API_TIMESTAMPS"},
            "temperature_c": {"unit": "deg C", "provenance": provenance_str},
            "relative_humidity_pct": {"unit": "%", "provenance": provenance_str},
            "cloud_cover_pct": {"unit": "%", "provenance": provenance_str},
            "wind_speed_m_s": {"unit": "m/s (converted from km/h by / 3.6)", "provenance": provenance_str},
            "shortwave_radiation_w_m2": {"unit": "W/m^2", "provenance": provenance_str},
            "surface_pressure_hpa": {"unit": "hPa", "provenance": provenance_str}
        },
        "missing_optical_channel_inputs": {
            "turbulence": {"treatment": "CONFIGURED_ASSUMPTION", "default": 0.12},
            "vibration": {"treatment": "CONFIGURED_ASSUMPTION", "default": 0.015},
            "ambient_light": {"treatment": "SOLAR_GEOMETRY_AND_RADIATION_MODELED", "default_conversion": "shortwave_w_m2 * 115 lux/(W/m2)"}
        }
    }
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=4)
    logger.info("Saved metadata to: %s", meta_file)

    return csv_file

    return csv_file


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch historical weather from Open-Meteo for Tiruchirappalli")
    parser.add_argument("--start-date", type=str, default="2024-03-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, default="2024-03-31", help="End date (YYYY-MM-DD)")
    parser.add_argument("--model", type=str, choices=["era5", "best_match"], default="era5", help="Weather model: era5 or best_match")
    parser.add_argument("--lat", type=float, default=DEFAULT_LAT, help="Station latitude")
    parser.add_argument("--lon", type=float, default=DEFAULT_LON, help="Station longitude")
    parser.add_argument("--out", type=str, default="simulation/historical_weather", help="Output directory")
    args = parser.parse_args()

    try:
        csv_out = fetch_open_meteo_historical(
            start_date=args.start_date,
            end_date=args.end_date,
            latitude=args.lat,
            longitude=args.lon,
            model=args.model,
            output_dir=args.out
        )
        print(f"Successfully created: {csv_out}")
    except Exception as exc:
        sys.exit(1)

