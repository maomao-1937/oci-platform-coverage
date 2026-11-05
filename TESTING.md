# Testing

From the project root, run the standard-library test suite.

```console
python -B -m unittest discover -s tests -v
```

The tests check unique, missing, and multiple candidates, exact variant matching, original descriptor positions, and skipped descriptors. Input checks cover invalid schema types, duplicate requirements and JSON keys, invalid UTF-8, nonfinite numbers, unpaired surrogates, and oversized files. The path probe blocks both `stat` and `open` while exercising disallowed path forms in each argument position. An output test launches the CLI with the read end of its stdout pipe already closed.

| Example | Exit |
| --- | --- |
| `python oci_platform_coverage.py fixtures/index.json fixtures/requirements-covered.json` | `0` |
| `python oci_platform_coverage.py fixtures/index.json fixtures/requirements-gap.json` | `1` |
| `python oci_platform_coverage.py fixtures/index.json fixtures/requirements-invalid.json` | `2` |
| `python oci_platform_coverage.py --help` | `0` |

The fixtures use synthetic descriptor digests and sizes. The cases cover local JSON and CLI behavior. Container image fetching and runtime execution are outside this suite's scope.
