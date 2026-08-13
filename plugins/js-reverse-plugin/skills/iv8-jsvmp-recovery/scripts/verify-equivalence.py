#!/usr/bin/env python3
"""Verify exact output equality without normalizing either output.

This script proves one mechanical fact only: whether the supplied oracle and
recovered output files contain identical bytes. It records hashes for the raw
input and source artifacts so the result remains tied to a declared baseline.
It does not prove that the input is truly raw, that the implementation is
independent, or that one matching sample generalizes to other inputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


SCHEMA_VERSION = 1
CONTEXT_BYTES = 16


class VerificationError(Exception):
    """Raised for invalid files or unsafe report destinations."""


@dataclass(frozen=True)
class Artifact:
    requested_path: str
    path: Path
    data: bytes

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.data).hexdigest()

    def as_report(self) -> dict[str, Any]:
        return {
            "requested_path": self.requested_path,
            "path": str(self.path),
            "size": len(self.data),
            "sha256": self.sha256,
        }


def absolute_path(path_text: str) -> Path:
    return Path(os.path.abspath(Path(path_text).expanduser()))


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare oracle and recovered outputs byte-for-byte while hashing "
            "the declared raw-input and source artifacts."
        ),
        epilog=(
            "Exit status: 0 exact match; 1 output mismatch; 2 invalid input or "
            "report error. No whitespace, Unicode, Base64, JSON, or newline "
            "normalization is performed."
        ),
    )
    parser.add_argument(
        "--input",
        action="append",
        required=True,
        metavar="FILE",
        help=(
            "Raw-input artifact to hash. Repeat for split request/environment/"
            "behavior/time/config artifacts."
        ),
    )
    parser.add_argument(
        "--source",
        action="append",
        default=[],
        metavar="FILE",
        help="Original source, bytecode, or runtime manifest to hash; repeatable.",
    )
    parser.add_argument(
        "--oracle",
        required=True,
        metavar="FILE",
        help="Output captured from the controlled original program.",
    )
    parser.add_argument(
        "--recovered",
        required=True,
        metavar="FILE",
        help="Output produced by the independent recovered implementation.",
    )
    parser.add_argument(
        "--label",
        default="baseline",
        help="Human-readable experiment label stored in the report.",
    )
    parser.add_argument(
        "--text-encoding",
        default="utf-8",
        help=(
            "Encoding used only for diagnostic previews near the first "
            "difference. It never changes comparison bytes. Default: utf-8."
        ),
    )
    parser.add_argument(
        "--report",
        metavar="FILE",
        help="Write JSON to this path instead of stdout.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow replacing an explicitly named existing report file.",
    )
    return parser.parse_args(argv)


def read_artifact(requested_path: str, role: str) -> Artifact:
    path = absolute_path(requested_path)
    try:
        metadata = path.lstat()
    except FileNotFoundError as error:
        raise VerificationError(f"{role} does not exist: {path}") from error

    if path.is_symlink():
        raise VerificationError(f"{role} must not be a symbolic link: {path}")
    if not path.is_file():
        raise VerificationError(f"{role} is not a regular file: {path}")
    if not metadata.st_size == path.stat().st_size:
        raise VerificationError(f"{role} changed while being inspected: {path}")

    try:
        data = path.read_bytes()
    except OSError as error:
        raise VerificationError(f"cannot read {role}: {path}: {error}") from error

    return Artifact(requested_path=requested_path, path=path, data=data)


def decode_preview(data: bytes, encoding: str) -> str:
    try:
        return data.decode(encoding, errors="replace")
    except LookupError as error:
        raise VerificationError(f"unknown text encoding: {encoding}") from error


def first_difference(
    oracle: bytes,
    recovered: bytes,
    encoding: str,
) -> dict[str, Any] | None:
    common_length = min(len(oracle), len(recovered))
    offset = next(
        (index for index in range(common_length) if oracle[index] != recovered[index]),
        None,
    )

    if offset is None:
        if len(oracle) == len(recovered):
            return None
        offset = common_length

    start = max(0, offset - CONTEXT_BYTES)
    stop = min(max(len(oracle), len(recovered)), offset + CONTEXT_BYTES + 1)
    oracle_context = oracle[start:min(stop, len(oracle))]
    recovered_context = recovered[start:min(stop, len(recovered))]

    return {
        "offset": offset,
        "oracle_byte": oracle[offset] if offset < len(oracle) else None,
        "recovered_byte": recovered[offset] if offset < len(recovered) else None,
        "context_start": start,
        "context_stop": stop,
        "oracle_context_hex": oracle_context.hex(),
        "recovered_context_hex": recovered_context.hex(),
        "oracle_context_text": decode_preview(oracle_context, encoding),
        "recovered_context_text": decode_preview(recovered_context, encoding),
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    inputs = [
        read_artifact(path, f"raw input #{index}")
        for index, path in enumerate(args.input, start=1)
    ]
    sources = [
        read_artifact(path, f"source artifact #{index}")
        for index, path in enumerate(args.source, start=1)
    ]
    oracle = read_artifact(args.oracle, "oracle output")
    recovered = read_artifact(args.recovered, "recovered output")
    difference = first_difference(oracle.data, recovered.data, args.text_encoding)
    bundle_digest = hashlib.sha256()
    for artifact in inputs:
        bundle_digest.update(len(artifact.data).to_bytes(8, byteorder="big"))
        bundle_digest.update(artifact.data)

    return {
        "schema_version": SCHEMA_VERSION,
        "label": args.label,
        "comparison": "exact-bytes",
        "normalization": "none",
        "raw_inputs": [artifact.as_report() for artifact in inputs],
        "raw_input_bundle_sha256": bundle_digest.hexdigest(),
        "source_artifacts": [artifact.as_report() for artifact in sources],
        "oracle": oracle.as_report(),
        "recovered": recovered.as_report(),
        "exact": difference is None,
        "first_difference": difference,
        "claim_boundary": (
            "This report proves exact equality only for the supplied artifacts. "
            "It does not prove raw-input integrity, implementation independence, "
            "or equivalence outside the declared experiment."
        ),
    }


def serialize_report(report: dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_report(
    path_text: str,
    content: str,
    force: bool,
    protected_paths: set[Path],
) -> None:
    path = absolute_path(path_text)
    if path in protected_paths:
        raise VerificationError(f"report path would overwrite an input artifact: {path}")
    if path.exists():
        if path.is_symlink():
            raise VerificationError(f"report path must not be a symbolic link: {path}")
        if not path.is_file():
            raise VerificationError(f"report path is not a regular file: {path}")
        if not force:
            raise VerificationError(
                f"report already exists: {path}; pass --force to replace it"
            )
    if not path.parent.is_dir():
        raise VerificationError(f"report parent directory does not exist: {path.parent}")

    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if not force:
        flags |= os.O_EXCL
    try:
        descriptor = os.open(path, flags, 0o644)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
    except FileExistsError as error:
        raise VerificationError(
            f"report already exists: {path}; pass --force to replace it"
        ) from error
    except OSError as error:
        raise VerificationError(f"cannot write report: {path}: {error}") from error


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        report = build_report(args)
        content = serialize_report(report)
        if args.report:
            protected_paths = {
                absolute_path(path)
                for path in [*args.input, *args.source, args.oracle, args.recovered]
            }
            write_report(args.report, content, args.force, protected_paths)
        else:
            sys.stdout.write(content)
        return 0 if report["exact"] else 1
    except VerificationError as error:
        print(f"verify-equivalence: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
