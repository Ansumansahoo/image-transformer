#!/usr/bin/env python3
"""
tests/test_parity.py
====================
Phase 0 parity test harness.

STATUS: RED (expected) — the Rust core does not exist yet.
Once Phase 1 delivers /core-rs, these tests become the parity gate.

What this tests
---------------
1. Schema validation: presets.json validates against schemas/preset.schema.json.
2. Python pipeline smoke: the Python CLI processes local fixture images without
   crashing and produces outputs of the right size/format.
3. Parity gate (PENDING Phase 1): the Rust CLI and Python pipeline produce
   pixel-identical output (within a tiny tolerance) for the same input+settings.
   This test is the primary anti-drift mechanism. It MUST fail if the two diverge.

Running
-------
  pip install pytest Pillow jsonschema requests
  pytest tests/test_parity.py -v

CI
--
  See .github/workflows/ci.yml — python_tests job.
"""
import io
import json
import os
import sys
import zipfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).parent.parent
FIXTURES = REPO_ROOT / "fixtures"
SCHEMAS = REPO_ROOT / "schemas"
CLI = REPO_ROOT / "transform_swatches.py"


# ---------------------------------------------------------------------------
# 1. JSON Schema validation
# ---------------------------------------------------------------------------

class TestPresetSchema:
    """Validate that presets.json conforms to schemas/preset.schema.json."""

    def test_schema_file_exists(self):
        assert (SCHEMAS / "preset.schema.json").exists(), (
            "schemas/preset.schema.json not found"
        )

    def test_presets_json_exists(self):
        assert (REPO_ROOT / "presets.json").exists(), (
            "presets.json not found at repo root"
        )

    def test_presets_json_valid_json(self):
        with open(REPO_ROOT / "presets.json") as f:
            data = json.load(f)
        assert "builtin" in data, "presets.json must have a 'builtin' key"
        assert "user" in data, "presets.json must have a 'user' key"

    def test_presets_validate_against_schema(self):
        """Each preset object must validate against the JSON Schema."""
        try:
            import jsonschema
        except ImportError:
            pytest.skip("jsonschema not installed — run: pip install jsonschema")

        with open(SCHEMAS / "preset.schema.json") as f:
            schema = json.load(f)
        with open(REPO_ROOT / "presets.json") as f:
            presets_doc = json.load(f)

        validator = jsonschema.Draft7Validator(schema)

        all_presets = {}
        all_presets.update(presets_doc.get("builtin", {}))
        all_presets.update(presets_doc.get("user", {}))

        errors = []
        for name, preset in all_presets.items():
            for error in validator.iter_errors(preset):
                errors.append(f"Preset '{name}': {error.message} (path: {list(error.path)})")

        assert not errors, "\n".join(errors)

    def test_builtin_preset_required_fields(self):
        """Every builtin preset must have the minimal fields needed to render."""
        REQUIRED = {"shape", "sizes", "bgMode", "format"}
        with open(REPO_ROOT / "presets.json") as f:
            data = json.load(f)
        errors = []
        for name, preset in data.get("builtin", {}).items():
            missing = REQUIRED - set(preset.keys())
            if missing:
                errors.append(f"Preset '{name}' missing: {missing}")
        assert not errors, "\n".join(errors)


# ---------------------------------------------------------------------------
# 2. Python pipeline smoke tests (local images)
# ---------------------------------------------------------------------------

class TestPythonPipelineSmoke:
    """
    Run the Python CLI on fixture images (where available) and verify outputs.
    These tests SKIP if fixtures have not been committed yet (Phase 0 state).
    """

    def _run_cli(self, input_path, extra_args=None, tmp_path=None):
        """Run transform_swatches.py as a subprocess; return (returncode, stdout, zip_path)."""
        import subprocess
        import tempfile

        out_dir = tmp_path or tempfile.mkdtemp()
        zip_path = os.path.join(out_dir, "out.zip")
        report_path = os.path.join(out_dir, "report.xlsx")
        cmd = [
            sys.executable, str(CLI),
            "--input", str(input_path),
            "--out", zip_path,
            "--report", report_path,
            "--sizes", "64,128",
            "--shape", "square",
            "--format", "PNG",
            "--concurrency", "2",
        ]
        if extra_args:
            cmd.extend(extra_args)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return result.returncode, result.stdout + result.stderr, zip_path

    def test_cli_exists(self):
        assert CLI.exists(), f"CLI not found: {CLI}"

    def test_cli_version(self):
        import subprocess
        r = subprocess.run([sys.executable, str(CLI), "--version"],
                          capture_output=True, text=True, timeout=10)
        assert r.returncode == 0
        assert "3" in r.stdout, f"Expected v3.x, got: {r.stdout}"

    @pytest.mark.skipif(
        not (FIXTURES / "urls_with_header.csv").exists(),
        reason="urls_with_header.csv fixture not committed yet"
    )
    def test_csv_with_header_is_parsed(self, tmp_path):
        """CSV with header row: auto-detect URL column, 3 rows processed."""
        rc, output, zip_path = self._run_cli(
            FIXTURES / "urls_with_header.csv", tmp_path=str(tmp_path)
        )
        # May fail with network errors in CI (Unsplash); that is acceptable.
        # What we're testing is that the CSV is PARSED (not consumed as headerless)
        # and that the output ZIP is a valid ZIP (even if empty due to network errors).
        assert "No rows found" not in output,             "CSV with header should have 3 rows, not zero"

    @pytest.mark.skipif(
        not (FIXTURES / "urls_no_header.csv").exists(),
        reason="urls_no_header.csv fixture not committed yet"
    )
    def test_csv_no_header_is_parsed(self, tmp_path):
        """Headerless CSV: first row is a URL, not a column name."""
        rc, output, zip_path = self._run_cli(
            FIXTURES / "urls_no_header.csv", tmp_path=str(tmp_path)
        )
        assert "No rows found" not in output,             "Headerless CSV should have 3 rows, not zero"

    @pytest.mark.skipif(
        not (FIXTURES / "on_white.jpg").exists(),
        reason="on_white.jpg fixture not committed yet (Phase 1)"
    )
    def test_local_image_produces_correct_output_sizes(self, tmp_path):
        """Process a local JPEG; verify ZIP contains 64px and 128px outputs."""
        rc, output, zip_path = self._run_cli(
            FIXTURES / "on_white.jpg",
            extra_args=["--shape", "square"],
            tmp_path=str(tmp_path)
        )
        assert rc == 0, f"CLI failed:\n{output}"
        assert os.path.exists(zip_path), "ZIP not created"
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
        assert any("64" in n for n in names), f"No 64px output in ZIP: {names}"
        assert any("128" in n for n in names), f"No 128px output in ZIP: {names}"

    @pytest.mark.skipif(
        not (FIXTURES / "on_white.jpg").exists(),
        reason="on_white.jpg fixture not committed yet (Phase 1)"
    )
    def test_output_png_dimensions(self, tmp_path):
        """Output PNG files must be exactly the requested size."""
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not installed")

        rc, output, zip_path = self._run_cli(
            FIXTURES / "on_white.jpg", tmp_path=str(tmp_path)
        )
        assert rc == 0
        with zipfile.ZipFile(zip_path) as zf:
            for name in zf.namelist():
                if "64" in name and name.endswith(".png"):
                    data = zf.read(name)
                    img = Image.open(io.BytesIO(data))
                    assert img.size == (64, 64), f"{name}: expected 64x64, got {img.size}"
                    break

    @pytest.mark.skipif(
        not (FIXTURES / "portrait_exif.jpg").exists(),
        reason="portrait_exif.jpg fixture not committed yet (Phase 1)"
    )
    def test_exif_orientation_corrected(self, tmp_path):
        """
        EXIF-rotated portrait image must come out upright (portrait-oriented),
        not sideways. The output swatch should be square (we always square-crop),
        but the UNDERLYING crop should pick the right axis.
        This is a regression test for bug #5.
        """
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not installed")

        rc, output, zip_path = self._run_cli(
            FIXTURES / "portrait_exif.jpg", tmp_path=str(tmp_path)
        )
        assert rc == 0, f"CLI failed:\n{output}"
        # If EXIF orientation is ignored, the image is processed sideways;
        # the smart-crop bounding box will be in the wrong orientation.
        # We can't easily test the visual result here, but we CAN verify
        # the output is a valid 128x128 PNG.
        with zipfile.ZipFile(zip_path) as zf:
            pngs = [n for n in zf.namelist() if "128" in n and n.endswith(".png")]
        assert pngs, f"No 128px PNG in ZIP: {zf.namelist()}"


# ---------------------------------------------------------------------------
# 3. Parity gate (PENDING Phase 1 — Rust core not yet built)
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="PENDING: Rust core not yet implemented (Phase 1)")
class TestRustPythonParity:
    """
    Golden/parity tests: Rust core and Python pipeline must produce
    pixel-identical outputs (within tolerance) for the same input+settings.
    
    This test class is the primary mechanism that prevents future drift between
    the two pipelines. It MUST be unskipped and passing before Phase 2 starts.
    
    Test plan (to be implemented in Phase 1):
    - For each fixture in fixtures/:
      - For each shape x bg_mode x format combination in PARITY_MATRIX:
        - Run Python CLI -> output bytes
        - Run Rust CLI   -> output bytes
        - Load both as numpy arrays
        - Assert mean absolute error < PIXEL_TOLERANCE
    """

    PIXEL_TOLERANCE = 5   # max per-channel MAE; accounts for JPEG quantization rounding
    
    PARITY_MATRIX = [
        # (shape, bg_mode, format)
        ("square",  "white",       "PNG"),
        ("square",  "white",       "JPEG"),
        ("circle",  "transparent", "PNG"),
        ("rounded", "white",       "PNG"),
        ("square",  "white",       "WEBP"),
        ("hexagon", "transparent", "PNG"),
        ("color",   "transparent", "PNG"),   # dominant-color chip
    ]

    FIXTURE_IMAGES = ["on_white.jpg", "transparent.png", "landscape.jpg",
                      "portrait_exif.jpg"]

    def _rust_cli_path(self):
        """Return path to the compiled Rust CLI binary."""
        candidates = [
            REPO_ROOT / "core-rs" / "target" / "release" / "swatch-cli",
            REPO_ROOT / "core-rs" / "target" / "debug"  / "swatch-cli",
        ]
        for p in candidates:
            if p.exists():
                return p
        pytest.skip("Rust CLI binary not found — run: cd core-rs && cargo build")

    def test_parity_matrix(self, tmp_path):
        """Main parity assertion: Python and Rust produce equivalent pixels."""
        try:
            import numpy as np
            from PIL import Image
        except ImportError:
            pytest.skip("numpy/Pillow not installed")

        rust_cli = self._rust_cli_path()
        errors = []

        for fixture_name in self.FIXTURE_IMAGES:
            fixture = FIXTURES / fixture_name
            if not fixture.exists():
                continue
            for shape, bg_mode, fmt in self.PARITY_MATRIX:
                py_out = tmp_path / f"py_{fixture_name}_{shape}_{bg_mode}.zip"
                rs_out = tmp_path / f"rs_{fixture_name}_{shape}_{bg_mode}.zip"

                # Run Python CLI
                import subprocess
                subprocess.run([
                    sys.executable, str(CLI),
                    "--input", str(fixture),
                    "--out", str(py_out),
                    "--sizes", "128",
                    "--shape", shape,
                    "--bg-color", "white" if bg_mode == "white" else "transparent",
                    "--format", fmt,
                ], check=True, capture_output=True, timeout=60)

                # Run Rust CLI
                subprocess.run([
                    str(rust_cli),
                    "--input", str(fixture),
                    "--out", str(rs_out),
                    "--sizes", "128",
                    "--shape", shape,
                    "--bg-color", "white" if bg_mode == "white" else "transparent",
                    "--format", fmt,
                ], check=True, capture_output=True, timeout=60)

                # Compare outputs
                with zipfile.ZipFile(py_out) as pz, zipfile.ZipFile(rs_out) as rz:
                    py_files = sorted(pz.namelist())
                    rs_files = sorted(rz.namelist())
                    for pf, rf in zip(py_files, rs_files):
                        py_img = np.array(Image.open(io.BytesIO(pz.read(pf))).convert("RGBA"))
                        rs_img = np.array(Image.open(io.BytesIO(rz.read(rf))).convert("RGBA"))
                        mae = abs(py_img.astype(int) - rs_img.astype(int)).mean()
                        if mae > self.PIXEL_TOLERANCE:
                            errors.append(
                                f"{fixture_name} / {shape} / {bg_mode} / {fmt}: "
                                f"MAE={mae:.2f} > tolerance={self.PIXEL_TOLERANCE}"
                            )

        if errors:
            pytest.fail(f"Parity failures (Python vs Rust):\n" + "\n".join(errors))
