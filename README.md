# OCI Platform Coverage

[![tests](https://github.com/maomao-1937/oci-platform-coverage/actions/workflows/tests.yml/badge.svg)](https://github.com/maomao-1937/oci-platform-coverage/actions/workflows/tests.yml)

[简体中文](README.zh-CN.md)

Check whether each platform in a release matrix has exactly one matching image manifest in a local OCI image index. The CLI uses Python 3.11 or later with only the standard library.

```console
python oci_platform_coverage.py fixtures/index.json fixtures/requirements-covered.json
```

```json
{"covered":1,"missing":0,"ambiguous":0,"skipped":2,"requirements":[{"ordinal":1,"matches":[1]}]}
```

For a missing variant and duplicate candidates, run the same index against a broader matrix.

```console
python oci_platform_coverage.py fixtures/index.json fixtures/requirements-gap.json
```

```json
{"covered":2,"missing":1,"ambiguous":1,"skipped":2,"requirements":[{"ordinal":1,"matches":[]},{"ordinal":2,"matches":[2,5]},{"ordinal":3,"matches":[1]}]}
```

Each row corresponds to a requirement in input order. `ordinal` and the descriptor positions in `matches` are one-based. `covered` counts requirements with one or more candidates. `ambiguous` counts the covered requirements with multiple candidates. `missing` counts requirements with zero candidates, and `skipped` counts descriptors excluded from matching. Reports contain positions and counts only.

| Exit | Meaning |
| --- | --- |
| `0` | Each requirement has exactly one candidate. |
| `1` | At least one requirement is missing or ambiguous. The report is on stdout. |
| `2` | Usage, input, or output error. A fixed diagnostic goes to stderr when writable. |

## Input contract

- `INDEX` is an object with integer `schemaVersion` `2`, a `manifests` array, and optional `mediaType` set to `application/vnd.oci.image.index.v1+json`.
- Every descriptor supplies a string `mediaType`, a `digest` of `sha256:` followed by 64 lowercase hexadecimal digits, and an integer `size` from `0` to `2**63 - 1`.
- A descriptor is skipped if its media type differs from `application/vnd.oci.image.manifest.v1+json` or it omits `platform`. An image manifest with a `platform` must supply a valid platform object. A valid `unknown` OS and `unknown` architecture pair is also skipped. Each excluded descriptor is counted once.
- `REQUIREMENTS` is a nonempty array of distinct platform objects. Each has `os`, `architecture`, and optionally `variant`. Each field matches `[a-z0-9][a-z0-9_-]*` in full. Platform objects in requirements have exactly those keys. Index, descriptor, and descriptor-platform metadata are ignored after JSON validation.
- Matching compares the literal OS, architecture, and optional variant. For example, `linux/arm` and `linux/arm/v7` form separate keys. OCI values outside the stated grammar, such as `v8.1`, are outside this tool's input subset.

## File and matching boundaries

Each input is a regular file of at most 1 MiB, parsed as UTF-8 JSON. The parser rejects duplicate keys, nonfinite numbers, UTF-8 errors, and unpaired surrogates even in ignored metadata. The CLI checks both path strings before any input file access. Relative paths and absolute drive paths are accepted. URI, UNC, device names, drive-relative names, and Windows alternate streams are rejected. A permitted path can still resolve through a symlink, junction, or mount to remote storage. Use files from a filesystem you control when storage locality matters.

The release check covers declarations in the supplied index. Runtime selection, OS-version and feature matching, architecture aliases, nested indexes, digest verification, and registry or layer access are outside its scope.

[Research](RESEARCH.md) · [Testing](TESTING.md) · [MIT License](LICENSE)
