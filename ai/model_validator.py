"""PPO Model Archive Validator and Integrity Manager.

Validates that a Stable-Baselines3 model archive contains all required files
at the expected root directory level, verifies observation and action spaces,
detects nested subdirectories (such as those created by manual re-zipping),
and provides verified archive repair while strictly preserving originals.
"""

from dataclasses import dataclass, field
import io
import json
import logging
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple
import zipfile

logger = logging.getLogger("qsat.model_validator")

# Critical files required by Stable-Baselines3 for PPO models
REQUIRED_FILES = [
    "data",
    "policy.pth",
    "pytorch_variables.pth",
    "_stable_baselines3_version",
]

# Workaround for Windows environments where lazy tensorboard imports trigger
# corrupted/inaccessible TensorFlow installations
if "tensorflow" not in sys.modules:
    try:
        import os
        os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")
    except Exception:
        pass


def sanitize_environment_for_sb3():
    """Ensure safe import of Stable-Baselines3 without TensorFlow permission errors."""
    if "tensorflow" not in sys.modules:
        try:
            # Block lazy TensorFlow import by tensorboard which can cause PermissionError on Windows
            sys.modules["tensorflow"] = None  # type: ignore
        except Exception:
            pass


@dataclass
class ValidationReport:
    """Report detailing the structural integrity of a model zip archive."""
    archive_path: Path
    is_valid_zip: bool = False
    files_present: List[str] = field(default_factory=list)
    required_at_root: bool = False
    missing_files: List[str] = field(default_factory=list)
    is_nested: bool = False
    nested_prefix: Optional[str] = None
    sb3_version: Optional[str] = None
    observation_space_info: Optional[Dict[str, Any]] = None
    action_space_info: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

    @property
    def is_loadable(self) -> bool:
        """True only if the archive is valid, un-nested, and has all root files."""
        return self.is_valid_zip and self.required_at_root and not self.missing_files and not self.is_nested


def validate_ppo_archive(archive_path: Path | str) -> ValidationReport:
    """Thoroughly audit a PPO model archive."""
    path = Path(archive_path)
    report = ValidationReport(archive_path=path)

    if not path.exists():
        report.error_message = f"Archive file does not exist: {path}"
        return report

    if not zipfile.is_zipfile(path):
        report.error_message = f"File is not a valid zip archive: {path}"
        return report

    report.is_valid_zip = True

    try:
        with zipfile.ZipFile(path, "r") as zf:
            namelist = zf.namelist()
            report.files_present = namelist

            # Check for direct presence at root level
            root_present = [f for f in REQUIRED_FILES if f in namelist]
            root_missing = [f for f in REQUIRED_FILES if f not in namelist]

            if not root_missing:
                report.required_at_root = True
                report.missing_files = []
            else:
                report.required_at_root = False
                report.missing_files = root_missing

                # Check if files are nested under a single directory
                for entry in namelist:
                    if "/" in entry:
                        candidate_prefix = entry.split("/")[0] + "/"
                        nested_checks = [candidate_prefix + req for req in REQUIRED_FILES]
                        if all(req in namelist for req in nested_checks):
                            report.is_nested = True
                            report.nested_prefix = candidate_prefix
                            break

            # Try to read SB3 version and data JSON
            sb3_ver_name = "_stable_baselines3_version" if report.required_at_root else (
                (report.nested_prefix or "") + "_stable_baselines3_version"
            )
            if sb3_ver_name in namelist:
                try:
                    report.sb3_version = zf.read(sb3_ver_name).decode("utf-8").strip()
                except Exception as e:
                    logger.debug("Failed reading SB3 version: %s", e)

            data_name = "data" if report.required_at_root else ((report.nested_prefix or "") + "data")
            if data_name in namelist:
                try:
                    raw_data = zf.read(data_name).decode("utf-8")
                    data_json = json.loads(raw_data)
                    obs_space = data_json.get("observation_space", {})
                    act_space = data_json.get("action_space", {})
                    report.observation_space_info = {
                        "shape": obs_space.get("_shape"),
                        "dtype": obs_space.get("dtype"),
                        "low": obs_space.get("low"),
                        "high": obs_space.get("high"),
                    }
                    report.action_space_info = {
                        "shape": act_space.get("_shape"),
                        "dtype": act_space.get("dtype"),
                        "low": act_space.get("low"),
                        "high": act_space.get("high"),
                    }
                except Exception as e:
                    logger.debug("Could not parse data json: %s", e)

    except Exception as exc:
        report.error_message = f"Error inspecting zipfile: {exc}"

    return report


def repair_nested_archive(
    source_path: Path | str,
    target_path: Path | str,
    backup_original: bool = True
) -> ValidationReport:
    """Repair an archive with nested directory structure by extracting files to root level.
    
    If backup_original is True and source_path == target_path, creates a backup first.
    """
    src = Path(source_path)
    dst = Path(target_path)

    initial_report = validate_ppo_archive(src)
    if not initial_report.is_valid_zip:
        raise ValueError(f"Cannot repair: Invalid archive at {src}: {initial_report.error_message}")

    if initial_report.is_loadable:
        logger.info("Archive at %s is already at root level, no repair needed.", src)
        return initial_report

    if not initial_report.is_nested or not initial_report.nested_prefix:
        raise ValueError(
            f"Cannot automatically repair {src}: Archive missing required files without recognized nested prefix: "
            f"{initial_report.missing_files}"
        )

    # If overwriting source, ensure backup exists
    if src.resolve() == dst.resolve() and backup_original:
        backup_path = src.parent / f"{src.stem}_original_nested{src.suffix}"
        if not backup_path.exists():
            import shutil
            shutil.copy2(src, backup_path)
            logger.info("Created original archive backup at: %s", backup_path)

    prefix = initial_report.nested_prefix
    temp_dst = dst.parent / f"{dst.stem}_repaired_temp{dst.suffix}"

    with zipfile.ZipFile(src, "r") as zf_in:
        with zipfile.ZipFile(temp_dst, "w", compression=zipfile.ZIP_DEFLATED) as zf_out:
            for item in zf_in.infolist():
                if item.filename.startswith(prefix) and len(item.filename) > len(prefix):
                    new_name = item.filename[len(prefix):]
                    file_data = zf_in.read(item.filename)
                    zf_out.writestr(new_name, file_data)
                elif not item.filename.startswith(prefix) and not item.filename.endswith("/"):
                    # Preserve any non-nested files
                    file_data = zf_in.read(item.filename)
                    zf_out.writestr(item.filename, file_data)

    # Atomic replace
    if dst.exists():
        dst.unlink()
    temp_dst.rename(dst)

    # Final validation of repaired archive
    final_report = validate_ppo_archive(dst)
    if not final_report.is_loadable:
        raise RuntimeError(f"Repaired archive failed validation: {final_report.error_message or final_report.missing_files}")

    logger.info("Successfully repaired archive saved to: %s", dst)
    return final_report

