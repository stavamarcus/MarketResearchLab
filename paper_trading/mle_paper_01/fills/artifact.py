"""Normalized fill artifact: canonical form, hashing, conflict policy.

Canonical content (decision 8) is the artifact WITHOUT ``generated_at_utc``
and ``canonical_sha256``. Two runs over the same inputs must produce the same
``canonical_sha256``; the wall-clock stamp is excluded by construction.

Canonical content is a pure function of raw dump + Trade Plan + explicit
operator assertions (decision 6). Nothing derived from the journal enters it.
"""
import hashlib
import json
import os
from pathlib import Path

from .states import ImportError_, NORMALIZED_ARTIFACT_CONFLICT

SCHEMA = "normalized_fills/1.0"

# Excluded from canonical content: wall clock and the hash itself.
NON_CANONICAL_KEYS = ("generated_at_utc", "canonical_sha256",
                      "non_canonical_metadata")


def canonical_bytes(artifact: dict) -> bytes:
    """Deterministic serialisation of the canonical content."""
    payload = {k: v for k, v in artifact.items() if k not in NON_CANONICAL_KEYS}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def canonical_sha256(artifact: dict) -> str:
    return hashlib.sha256(canonical_bytes(artifact)).hexdigest()


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def relative_path(path, root) -> str:
    """POSIX-style path relative to the project root.

    Decision 5: no machine-specific absolute paths in canonical content.
    """
    rel = os.path.relpath(str(Path(path).resolve()), str(Path(root).resolve()))
    return rel.replace(os.sep, "/")


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def serialise(artifact: dict) -> str:
    return json.dumps(artifact, indent=2, ensure_ascii=False, sort_keys=True)


def write_artifact(artifact: dict, path, conflict_artifact: bool = False):
    """Conflict policy (decision 8).

    missing        -> create
    same hash      -> no-op, file untouched (mtime preserved)
    different hash -> NORMALIZED_ARTIFACT_CONFLICT, previous file untouched

    Returns "created" | "unchanged"; raises ImportError_ on conflict.
    """
    path = Path(path)
    digest = canonical_sha256(artifact)
    artifact = dict(artifact)
    artifact["canonical_sha256"] = digest

    if not path.exists():
        _atomic_write(path, serialise(artifact))
        return "created"

    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
        existing_digest = existing.get("canonical_sha256")
    except Exception:
        existing_digest = None

    if existing_digest == digest:
        return "unchanged"          # deliberately not rewritten

    if conflict_artifact:
        stamp = artifact.get("generated_at_utc", "").replace(":", "").replace("-", "")
        alt = path.with_name(f"{path.stem}.conflict_{stamp or 'unknown'}.json")
        _atomic_write(alt, serialise(artifact))
        raise ImportError_(
            NORMALIZED_ARTIFACT_CONFLICT,
            f"existing artifact has a different canonical hash; diagnostic "
            f"copy written to {alt.name}; previous artifact untouched",
            existing_sha256=existing_digest, new_sha256=digest,
            conflict_copy=alt.name)

    raise ImportError_(
        NORMALIZED_ARTIFACT_CONFLICT,
        "existing artifact has a different canonical hash; re-run with "
        "--conflict-artifact to keep a diagnostic copy; previous artifact "
        "untouched",
        existing_sha256=existing_digest, new_sha256=digest)
