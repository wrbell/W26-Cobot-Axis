"""
W26 Cobot Axis -- Configurable Extrusion Profiles

Supports non-linear rate mapping between input speed and extrusion rate
to compensate for pump characteristics (progressive cavity, syringe,
peristaltic) and material properties (viscosity, temperature).

Profile types:
- Linear:     rate = speed * multiplier + offset
- Polynomial: rate = c[0] + c[1]*speed + c[2]*speed^2 + ...
- Lookup:     piecewise-linear interpolation between calibrated points

Profiles are loaded from a JSON file (default: profiles.json).

Reference: docs/design/bridge_enhancements.md, Section 5.
"""

import bisect
import json
import logging
import os

from . import config

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Profile base class
# ---------------------------------------------------------------------------

class ExtrusionProfile:
    """Base class for extrusion rate mapping functions."""

    def __init__(self, description: str = ""):
        self.description = description

    def apply(self, speed: float) -> float:
        """Map input speed (mm/s) to extrusion rate (mm/s)."""
        raise NotImplementedError

    def validate(self) -> None:
        """Validate profile parameters. Raises ValueError on error."""
        pass


# ---------------------------------------------------------------------------
# Linear profile
# ---------------------------------------------------------------------------

class LinearProfile(ExtrusionProfile):
    """rate = speed * multiplier + offset"""

    def __init__(self, multiplier: float = 1.0, offset: float = 0.0,
                 description: str = ""):
        super().__init__(description)
        self.multiplier = multiplier
        self.offset = offset

    def apply(self, speed: float) -> float:
        return max(0.0, speed * self.multiplier + self.offset)

    def validate(self) -> None:
        if self.multiplier < 0:
            raise ValueError(f"Linear profile multiplier must be >= 0, got {self.multiplier}")

    def __repr__(self):
        return f"LinearProfile(multiplier={self.multiplier}, offset={self.offset})"


# ---------------------------------------------------------------------------
# Polynomial profile
# ---------------------------------------------------------------------------

class PolynomialProfile(ExtrusionProfile):
    """rate = c[0] + c[1]*speed + c[2]*speed^2 + ..."""

    def __init__(self, coefficients: list, description: str = ""):
        super().__init__(description)
        self.coefficients = list(coefficients)

    def apply(self, speed: float) -> float:
        result = 0.0
        for i, coeff in enumerate(self.coefficients):
            result += coeff * (speed ** i)
        return max(0.0, result)

    def validate(self) -> None:
        if not self.coefficients:
            raise ValueError("Polynomial profile requires at least one coefficient")

    def __repr__(self):
        return f"PolynomialProfile(coefficients={self.coefficients})"


# ---------------------------------------------------------------------------
# Lookup table profile (with linear interpolation)
# ---------------------------------------------------------------------------

class LookupProfile(ExtrusionProfile):
    """Piecewise-linear interpolation between calibrated speed/rate points."""

    def __init__(self, points: list, interpolation: str = "linear",
                 description: str = ""):
        super().__init__(description)
        # points: list of [speed, rate] pairs, sorted by speed
        self.points = [tuple(p) for p in points]
        self.interpolation = interpolation
        # Precompute sorted speed values for bisect
        self._speeds = [p[0] for p in self.points]
        self._rates = [p[1] for p in self.points]

    def apply(self, speed: float) -> float:
        if not self.points:
            return 0.0

        # Clamp to range (no extrapolation)
        if speed <= self._speeds[0]:
            return max(0.0, self._rates[0])
        if speed >= self._speeds[-1]:
            return max(0.0, self._rates[-1])

        if self.interpolation == "nearest":
            idx = bisect.bisect_left(self._speeds, speed)
            if idx == 0:
                return max(0.0, self._rates[0])
            if idx >= len(self._speeds):
                return max(0.0, self._rates[-1])
            # Pick the closer point
            if (speed - self._speeds[idx - 1]) <= (self._speeds[idx] - speed):
                return max(0.0, self._rates[idx - 1])
            return max(0.0, self._rates[idx])

        # Linear interpolation (default)
        idx = bisect.bisect_right(self._speeds, speed) - 1
        x0, y0 = self._speeds[idx], self._rates[idx]
        x1, y1 = self._speeds[idx + 1], self._rates[idx + 1]
        t = (speed - x0) / (x1 - x0)
        return max(0.0, y0 + t * (y1 - y0))

    def validate(self) -> None:
        if len(self.points) < 2:
            raise ValueError("Lookup profile requires at least 2 points")
        for i in range(len(self.points) - 1):
            if self.points[i][0] >= self.points[i + 1][0]:
                raise ValueError(
                    f"Lookup points must be sorted by speed with no duplicates: "
                    f"point[{i}]={self.points[i][0]} >= point[{i + 1}]={self.points[i + 1][0]}"
                )

    def __repr__(self):
        return f"LookupProfile(points={len(self.points)}, interp={self.interpolation})"


# ---------------------------------------------------------------------------
# Profile loading
# ---------------------------------------------------------------------------

def _build_profile(name: str, spec: dict) -> ExtrusionProfile:
    """Build an ExtrusionProfile instance from a JSON profile specification."""
    profile_type = spec.get("type", "linear")
    description = spec.get("description", "")

    if profile_type == "linear":
        profile = LinearProfile(
            multiplier=spec.get("multiplier", 1.0),
            offset=spec.get("offset", 0.0),
            description=description,
        )

    elif profile_type == "polynomial":
        coefficients = spec.get("coefficients", [0.0, 1.0])
        profile = PolynomialProfile(
            coefficients=coefficients,
            description=description,
        )

    elif profile_type in ("lookup", "piecewise"):
        # Both "lookup" and "piecewise" use the LookupProfile class.
        # "piecewise" uses breakpoints format; "lookup" uses points format.
        if profile_type == "piecewise":
            breakpoints = spec.get("breakpoints", [])
            points = [(bp["speed"], bp["rate"]) for bp in breakpoints]
        else:
            points = spec.get("points", [])
        interpolation = spec.get("interpolation", "linear")
        profile = LookupProfile(
            points=points,
            interpolation=interpolation,
            description=description,
        )

    else:
        raise ValueError(f"Unknown profile type '{profile_type}' in profile '{name}'")

    profile.validate()
    return profile


def load_profiles(path: str) -> tuple[dict, str]:
    """
    Load all profiles from a JSON file.

    Returns:
        Tuple of (profiles_dict, active_profile_name).
        profiles_dict maps name -> ExtrusionProfile.
    """
    with open(path, "r") as f:
        data = json.load(f)

    profiles = {}
    for name, spec in data.get("profiles", {}).items():
        try:
            profiles[name] = _build_profile(name, spec)
            log.debug("Loaded profile '%s': %s", name, profiles[name])
        except (ValueError, KeyError) as exc:
            log.error("Failed to load profile '%s': %s", name, exc)

    active_name = data.get("active_profile", config.DEFAULT_PROFILE)
    log.info("Loaded %d extrusion profiles from %s (active: %s)",
             len(profiles), path, active_name)
    return profiles, active_name


def get_profile(profiles: dict, name: str) -> ExtrusionProfile:
    """
    Get a specific profile by name.

    Falls back to a default LinearProfile if not found.
    """
    if name in profiles:
        return profiles[name]

    log.warning("Profile '%s' not found, falling back to default linear profile", name)
    return LinearProfile(
        multiplier=config.EXTRUSION_MULTIPLIER,
        description="fallback linear profile",
    )


def load_active_profile(profile_file: str | None = None,
                        profile_name: str | None = None) -> ExtrusionProfile:
    """
    Convenience: load profiles from file and return the active one.

    Args:
        profile_file: Path to JSON profiles file. If None, uses default.
        profile_name: Override the active profile name from the file.

    Returns:
        The active ExtrusionProfile instance.
    """
    if profile_file is None:
        # Default: profiles.json next to this module
        profile_file = os.path.join(os.path.dirname(__file__), config.PROFILE_FILE)

    if not os.path.exists(profile_file):
        log.warning("Profile file not found: %s -- using default linear profile",
                     profile_file)
        return LinearProfile(
            multiplier=config.EXTRUSION_MULTIPLIER,
            description="default linear (no profile file)",
        )

    try:
        profiles, active_name = load_profiles(profile_file)
    except (json.JSONDecodeError, OSError) as exc:
        log.error("Failed to parse profile file %s: %s -- using default linear",
                  profile_file, exc)
        return LinearProfile(
            multiplier=config.EXTRUSION_MULTIPLIER,
            description="default linear (parse error fallback)",
        )

    # CLI override takes precedence over file setting
    if profile_name is not None:
        active_name = profile_name

    return get_profile(profiles, active_name)
