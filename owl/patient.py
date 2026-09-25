"""Keeps ``owl-patient:local`` in sync with ``patient/`` before any task derived from it runs.

Design: specs/f2-suite-v1/design.md D3 (derivation of fixtures) and D9 (``owl validate``
"asegura owl-patient:local"). Requirements covered: R1, R3.

Every task under ``tasks/1*`` (see ``task_needs_patient_image``) does ``FROM owl-patient:local``
in its own Dockerfile; a stale base image would silently run an old ``seal.sh``/patient with no
warning. ``ensure_patient_image`` compares a content hash of ``patient/`` against the running
image's ``owl.patient_hash`` label and rebuilds only when they differ.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from owl.variants import ROOT

PATIENT_DIR = ROOT / "patient"
IMAGE_TAG = "owl-patient:local"
LABEL = "owl.patient_hash"


def _is_excluded(rel_parts: tuple[str, ...]) -> bool:
    """True if a file at ``rel_parts`` (relative to ``patient/``) is something a real
    checkout/build never ships. Mirrors ``patient/.gitignore`` literally (no ``.dockerignore``
    exists): ``node_modules/`` (the Dockerfile runs its own ``npm install``), the two scratch
    dirs under ``data/`` (each kept alive only by the placeholder file the pattern also spares),
    and any sqlite file dropped there at runtime. ``.DS_Store`` is excluded too (macOS noise, not
    part of any checkout on any platform)."""
    if "node_modules" in rel_parts:
        return True
    if rel_parts[:2] == ("data", "tmp") and rel_parts[-1] != ".gitkeep":
        return True
    if rel_parts[:2] == ("data", "backups") and rel_parts[-1] != "README.md":
        return True
    if rel_parts[:1] == ("data",) and rel_parts[-1].endswith(".db"):
        return True
    return rel_parts[-1] == ".DS_Store"


def patient_hash(patient_dir: Path = PATIENT_DIR) -> str:
    """Deterministic content hash of ``patient_dir``: sorted relative paths, each path's bytes
    folded in after its name. Stable across calls; changes whenever ``seal.sh``, the Dockerfile,
    or any source/doc file under ``patient/`` changes (see ``_is_excluded`` for what doesn't
    count)."""
    digest = hashlib.sha256()
    files = sorted(
        p
        for p in patient_dir.rglob("*")
        if p.is_file() and not _is_excluded(p.relative_to(patient_dir).parts)
    )
    for path in files:
        rel = path.relative_to(patient_dir).as_posix()
        digest.update(rel.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _current_image_label() -> str | None:
    """The running ``owl-patient:local`` image's ``owl.patient_hash`` label, or None if the
    image doesn't exist or carries no such label."""
    result = subprocess.run(
        ["docker", "image", "inspect", IMAGE_TAG, "--format", f'{{{{ index .Config.Labels "{LABEL}" }}}}'],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def ensure_patient_image(patient_dir: Path = PATIENT_DIR) -> bool:
    """Build ``owl-patient:local`` if it's missing or its ``owl.patient_hash`` label doesn't
    match the current content of ``patient_dir`` (D3, D9). Returns True if a build ran, False
    if the existing image was already current. Raises SystemExit if the build fails (fail
    loud: a stale/broken base image must never silently run downstream tasks)."""
    target_hash = patient_hash(patient_dir)
    if _current_image_label() == target_hash:
        return False

    print(f"owl-patient:local: rebuilding (hash {target_hash[:12]})", flush=True)
    result = subprocess.run(
        ["docker", "build", "-t", IMAGE_TAG, "--label", f"{LABEL}={target_hash}", str(patient_dir)],
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(f"docker build -t {IMAGE_TAG} {patient_dir} failed with exit code {result.returncode}")
    return True


def task_needs_patient_image(task_dir: Path) -> bool:
    """True if ``task_dir``'s ``environment/Dockerfile`` does ``FROM owl-patient:local`` (D3).
    ``tasks/00-smoke`` and ``tasks/01-probe`` build straight off a public base image and don't,
    so a run/validate limited to those never forces a docker build."""
    dockerfile = task_dir / "environment" / "Dockerfile"
    if not dockerfile.is_file():
        return False
    for line in dockerfile.read_text(errors="replace").splitlines():
        stripped = line.strip()
        if stripped.startswith("FROM ") and stripped.split()[1] == IMAGE_TAG:
            return True
    return False


def ensure_patient_image_for_tasks(task_paths: list[Path], patient_dir: Path = PATIENT_DIR) -> None:
    """Call ``ensure_patient_image`` once, only if at least one of ``task_paths`` needs it
    (``task_needs_patient_image``). Shared by ``owl run`` and ``owl validate`` (D9)."""
    if any(task_needs_patient_image(t) for t in task_paths):
        ensure_patient_image(patient_dir)
