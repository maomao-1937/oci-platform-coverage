"""Report exact platform coverage from an OCI index and a requirements list."""

import json
import math
import os
import re
import stat
import sys


INDEX_MEDIA_TYPE = "application/vnd.oci.image.index.v1+json"
MANIFEST_MEDIA_TYPE = "application/vnd.oci.image.manifest.v1+json"
MAX_BYTES = 2**20
MAX_SIZE = 2**63 - 1
USAGE = b"usage: oci_platform_coverage.py INDEX REQUIREMENTS\n"
PLATFORM_KEYS = {"os", "architecture", "variant"}
TOKEN = re.compile(r"[a-z0-9][a-z0-9_-]*")
DIGEST = re.compile(r"sha256:[a-f0-9]{64}")
SURROGATE = re.compile(r"[\ud800-\udfff]")
WINDOWS_DEVICE = re.compile(r"CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|CLOCK\$|(?:COM|LPT)[1-9¹²³]")
NATIVE_ROOTS = {"??", "device", "dosdevices", "global??", "systemroot", "globalroot"}


def check_path(path):
    normalized = path.replace("\\", "/")
    if not normalized or normalized == "-" or "\0" in normalized:
        raise ValueError
    if normalized.startswith("//"):
        raise ValueError
    if normalized.startswith("/") and normalized[1:].partition("/")[0].lower() in NATIVE_ROOTS:
        raise ValueError
    tail = normalized[3:] if re.match(r"^[a-zA-Z]:/", normalized) else normalized
    if ":" in tail or any(
        WINDOWS_DEVICE.fullmatch(part.partition(".")[0].rstrip(" ").upper())
        for part in tail.split("/")
    ):
        raise ValueError


def check_file(info):
    if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES:
        raise ValueError


def read_local_bytes(path):
    check_file(os.stat(path))
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0)
    descriptor = os.open(path, flags)
    try:
        check_file(os.fstat(descriptor))
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            data = stream.read(MAX_BYTES + 1)
    finally:
        os.close(descriptor)
    if len(data) > MAX_BYTES:
        raise ValueError
    return data


def json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result or SURROGATE.search(key):
            raise ValueError
        result[key] = value
    return result


def json_int(value):
    # Bigger integers can occur in ignored metadata. No supported field accepts them.
    return int(value) if len(value) <= 20 else object()


def json_float(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError
    return number


def read_json(path):
    value = json.loads(read_local_bytes(path).decode("utf-8"), object_pairs_hook=json_object,
                       parse_int=json_int, parse_float=json_float, parse_constant=json_float)
    pending = [value]
    while pending:
        item = pending.pop()
        if isinstance(item, str) and SURROGATE.search(item):
            raise ValueError
        if isinstance(item, list):
            pending.extend(item)
        elif isinstance(item, dict):
            pending.extend(item.values())
    return value


def platform_tuple(platform, exact=False):
    if not isinstance(platform, dict) or (exact and platform.keys() - PLATFORM_KEYS):
        raise ValueError
    values = [platform.get("os"), platform.get("architecture")]
    if "variant" in platform:
        values.append(platform["variant"])
    if any(not isinstance(value, str) or not TOKEN.fullmatch(value) for value in values):
        raise ValueError
    return tuple(values)


def index_platforms(index):
    if not isinstance(index, dict):
        raise ValueError
    version = index.get("schemaVersion")
    manifests = index.get("manifests")
    if (type(version) is not int or version != 2
            or index.get("mediaType", INDEX_MEDIA_TYPE) != INDEX_MEDIA_TYPE
            or not isinstance(manifests, list)):
        raise ValueError

    platforms = {}
    skipped = 0
    for ordinal, descriptor in enumerate(manifests, start=1):
        if not isinstance(descriptor, dict):
            raise ValueError
        media_type = descriptor.get("mediaType")
        digest = descriptor.get("digest")
        size = descriptor.get("size")
        if (not isinstance(media_type, str) or not isinstance(digest, str)
                or not DIGEST.fullmatch(digest) or type(size) is not int
                or not 0 <= size <= MAX_SIZE):
            raise ValueError

        if media_type != MANIFEST_MEDIA_TYPE or "platform" not in descriptor:
            skipped += 1
            continue
        platform = platform_tuple(descriptor["platform"])
        if platform[:2] == ("unknown", "unknown"):
            skipped += 1
            continue
        platforms.setdefault(platform, []).append(ordinal)
    return platforms, skipped


def coverage_report(index, requirements):
    platforms, skipped = index_platforms(index)
    if not isinstance(requirements, list) or not requirements:
        raise ValueError

    seen = set()
    rows = []
    missing = ambiguous = 0
    for ordinal, requirement in enumerate(requirements, start=1):
        platform = platform_tuple(requirement, exact=True)
        if platform in seen:
            raise ValueError
        seen.add(platform)
        matches = platforms.get(platform, [])
        missing += len(matches) == 0
        ambiguous += len(matches) > 1
        rows.append({"ordinal": ordinal, "matches": matches})
    return {"covered": len(rows) - missing, "missing": missing, "ambiguous": ambiguous,
            "skipped": skipped, "requirements": rows}


def write_output(descriptor, data):
    remaining = memoryview(data)
    try:
        while remaining:
            count = os.write(descriptor, remaining)
            if count == 0:
                return False
            remaining = remaining[count:]
    except OSError:
        return False
    return True


def main(arguments=None):
    if arguments is None:
        arguments = sys.argv[1:]
    if arguments in (["-h"], ["--help"]):
        output = USAGE
        status = 0
    elif len(arguments) != 2:
        write_output(2, USAGE)
        return 2
    else:
        try:
            index_path, requirements_path = arguments
            check_path(index_path)
            check_path(requirements_path)
            report = coverage_report(read_json(index_path), read_json(requirements_path))
        except (OSError, ValueError, RecursionError):
            write_output(2, b"error: invalid input\n")
            return 2
        output = (json.dumps(report, separators=(",", ":")) + "\n").encode("ascii")
        status = int(bool(report["missing"] or report["ambiguous"]))

    if not write_output(1, output):
        write_output(2, b"error: output failed\n")
        return 2
    return status


if __name__ == "__main__":
    raise SystemExit(main())
