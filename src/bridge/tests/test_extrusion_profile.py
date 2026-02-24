"""
Unit tests for W26 extrusion profile module.

Tests LinearProfile, PolynomialProfile, LookupProfile, JSON loading,
fallback behaviour, and edge cases.
"""

import json
import os

import pytest

from bridge.extrusion_profile import (
    LinearProfile,
    PolynomialProfile,
    LookupProfile,
    _build_profile,
    load_profiles,
    get_profile,
    load_active_profile,
)


# ---------------------------------------------------------------------------
# LinearProfile
# ---------------------------------------------------------------------------

class TestLinearProfile:
    def test_identity(self):
        p = LinearProfile(multiplier=1.0, offset=0.0)
        assert p.apply(10.0) == 10.0

    def test_multiplier(self):
        p = LinearProfile(multiplier=2.5, offset=0.0)
        assert p.apply(4.0) == 10.0

    def test_offset(self):
        p = LinearProfile(multiplier=1.0, offset=3.0)
        assert p.apply(7.0) == 10.0

    def test_zero_speed(self):
        p = LinearProfile(multiplier=2.0, offset=1.0)
        assert p.apply(0.0) == 1.0

    def test_negative_result_clamped_to_zero(self):
        p = LinearProfile(multiplier=1.0, offset=-20.0)
        assert p.apply(5.0) == 0.0

    def test_validate_positive_multiplier(self):
        p = LinearProfile(multiplier=1.0)
        p.validate()  # should not raise

    def test_validate_negative_multiplier_raises(self):
        p = LinearProfile(multiplier=-1.0)
        with pytest.raises(ValueError, match="multiplier"):
            p.validate()

    def test_repr(self):
        p = LinearProfile(multiplier=1.5, offset=0.5)
        assert "1.5" in repr(p)


# ---------------------------------------------------------------------------
# PolynomialProfile
# ---------------------------------------------------------------------------

class TestPolynomialProfile:
    def test_constant(self):
        p = PolynomialProfile(coefficients=[5.0])
        assert p.apply(100.0) == 5.0

    def test_linear_via_polynomial(self):
        # rate = 0 + 2*speed
        p = PolynomialProfile(coefficients=[0.0, 2.0])
        assert p.apply(5.0) == 10.0

    def test_quadratic(self):
        # rate = 1 + 0*speed + 0.5*speed^2 => at speed=4: 1 + 0 + 8 = 9
        p = PolynomialProfile(coefficients=[1.0, 0.0, 0.5])
        assert p.apply(4.0) == pytest.approx(9.0)

    def test_zero_speed(self):
        p = PolynomialProfile(coefficients=[3.0, 2.0, 1.0])
        assert p.apply(0.0) == 3.0

    def test_negative_result_clamped(self):
        p = PolynomialProfile(coefficients=[-10.0, 1.0])
        assert p.apply(5.0) == 0.0  # -10 + 5 = -5, clamped to 0

    def test_validate_empty_raises(self):
        p = PolynomialProfile(coefficients=[])
        with pytest.raises(ValueError, match="at least one"):
            p.validate()

    def test_validate_nonempty_passes(self):
        p = PolynomialProfile(coefficients=[1.0])
        p.validate()


# ---------------------------------------------------------------------------
# LookupProfile
# ---------------------------------------------------------------------------

class TestLookupProfile:
    @pytest.fixture
    def basic_lookup(self):
        return LookupProfile(points=[(0, 0), (10, 8), (20, 18), (50, 40)])

    def test_exact_point(self, basic_lookup):
        assert basic_lookup.apply(10.0) == pytest.approx(8.0)

    def test_interpolation_midpoint(self, basic_lookup):
        # Between (10, 8) and (20, 18): at 15 => 8 + 0.5*(18-8) = 13
        assert basic_lookup.apply(15.0) == pytest.approx(13.0)

    def test_below_range_clamps(self, basic_lookup):
        assert basic_lookup.apply(-5.0) == 0.0

    def test_above_range_clamps(self, basic_lookup):
        assert basic_lookup.apply(100.0) == pytest.approx(40.0)

    def test_first_point(self, basic_lookup):
        assert basic_lookup.apply(0.0) == 0.0

    def test_last_point(self, basic_lookup):
        assert basic_lookup.apply(50.0) == pytest.approx(40.0)

    def test_empty_points(self):
        p = LookupProfile(points=[])
        assert p.apply(10.0) == 0.0

    def test_nearest_interpolation(self):
        p = LookupProfile(points=[(0, 0), (10, 10), (20, 20)],
                          interpolation="nearest")
        assert p.apply(4.0) == 0.0   # closer to 0
        assert p.apply(6.0) == 10.0  # closer to 10
        assert p.apply(5.0) == 0.0   # tie goes to lower

    def test_validate_one_point_raises(self):
        p = LookupProfile(points=[(5.0, 5.0)])
        with pytest.raises(ValueError, match="at least 2"):
            p.validate()

    def test_validate_unsorted_raises(self):
        p = LookupProfile(points=[(10.0, 10.0), (5.0, 5.0)])
        with pytest.raises(ValueError, match="sorted"):
            p.validate()

    def test_validate_duplicates_raises(self):
        p = LookupProfile(points=[(5.0, 5.0), (5.0, 10.0)])
        with pytest.raises(ValueError, match="sorted"):
            p.validate()

    def test_validate_good_passes(self, basic_lookup):
        basic_lookup.validate()


# ---------------------------------------------------------------------------
# Profile building from spec dict
# ---------------------------------------------------------------------------

class TestBuildProfile:
    def test_build_linear(self):
        spec = {"type": "linear", "multiplier": 2.0, "offset": 1.0}
        p = _build_profile("test", spec)
        assert isinstance(p, LinearProfile)
        assert p.apply(5.0) == 11.0

    def test_build_polynomial(self):
        spec = {"type": "polynomial", "coefficients": [0.0, 1.0]}
        p = _build_profile("test", spec)
        assert isinstance(p, PolynomialProfile)

    def test_build_lookup(self):
        spec = {"type": "lookup", "points": [[0, 0], [10, 10]]}
        p = _build_profile("test", spec)
        assert isinstance(p, LookupProfile)

    def test_build_piecewise(self):
        spec = {
            "type": "piecewise",
            "breakpoints": [
                {"speed": 0, "rate": 0},
                {"speed": 10, "rate": 10},
            ],
        }
        p = _build_profile("test", spec)
        assert isinstance(p, LookupProfile)

    def test_build_unknown_type_raises(self):
        spec = {"type": "magic"}
        with pytest.raises(ValueError, match="Unknown profile type"):
            _build_profile("test", spec)


# ---------------------------------------------------------------------------
# JSON loading
# ---------------------------------------------------------------------------

class TestLoadProfiles:
    def test_load_from_file(self, tmp_path):
        data = {
            "profiles": {
                "my_linear": {
                    "type": "linear",
                    "multiplier": 1.5,
                }
            },
            "active_profile": "my_linear",
        }
        path = tmp_path / "profiles.json"
        path.write_text(json.dumps(data))

        profiles, active = load_profiles(str(path))
        assert "my_linear" in profiles
        assert active == "my_linear"
        assert profiles["my_linear"].apply(10.0) == 15.0

    def test_load_real_profiles_json(self):
        """Load the actual profiles.json shipped with the bridge."""
        path = os.path.join(os.path.dirname(__file__), "..", "profiles.json")
        if not os.path.exists(path):
            pytest.skip("profiles.json not found")
        profiles, active = load_profiles(path)
        assert len(profiles) >= 1
        assert active == "linear"


class TestGetProfile:
    def test_found(self):
        profiles = {"linear": LinearProfile()}
        assert isinstance(get_profile(profiles, "linear"), LinearProfile)

    def test_not_found_falls_back(self):
        profiles = {}
        p = get_profile(profiles, "nonexistent")
        assert isinstance(p, LinearProfile)
        assert "fallback" in p.description


class TestLoadActiveProfile:
    def test_missing_file_returns_default(self, tmp_path):
        p = load_active_profile(profile_file=str(tmp_path / "nope.json"))
        assert isinstance(p, LinearProfile)

    def test_bad_json_returns_default(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("not json {{{")
        p = load_active_profile(profile_file=str(path))
        assert isinstance(p, LinearProfile)

    def test_override_profile_name(self, tmp_path):
        data = {
            "profiles": {
                "a": {"type": "linear", "multiplier": 1.0},
                "b": {"type": "linear", "multiplier": 3.0},
            },
            "active_profile": "a",
        }
        path = tmp_path / "profiles.json"
        path.write_text(json.dumps(data))
        p = load_active_profile(profile_file=str(path), profile_name="b")
        assert p.apply(10.0) == 30.0
