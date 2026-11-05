# Research

## Source behavior

- OCI image indexes list descriptor entries for image manifests and may also reference nested indexes. Platform is optional on a descriptor. The specification describes runtime first-match guidance and OS-version and feature fields. Those runtime checks are outside this release-matrix check. [OCI image index specification](https://github.com/opencontainers/image-spec/blob/main/image-index.md#image-index-property-descriptions)
- Buildx can write `unknown` for both the OS and architecture when it pulls an attestation referrer into an index. That pair is therefore skipped as a platform candidate. The check also accepts indexes from other sources within its documented subset. [Buildx image tools source](https://github.com/docker/buildx/blob/master/util/imagetools/create.go)
- A containerd issue describes an index with a reference whose blob was unavailable in a saved image. The report illustrates the gap between platform declarations and blob availability. [containerd issue 11344](https://github.com/containerd/containerd/issues/11344)

## Workflow comparison

`docker buildx imagetools inspect` shows image details from a registry. Its `--raw` option can supply index JSON when the returned object uses the OCI index format. The CLI here compares a saved OCI index against a separately supplied release matrix and exposes the counts and descriptor positions for a CI check. [Docker Buildx inspect documentation](https://docs.docker.com/reference/cli/docker/buildx/imagetools/inspect/)

An OCI schema check can validate the document shape without comparing it against an independently defined release matrix. This CLI checks a narrower input contract for exact tuple coverage. Inference from the specification and the source behavior above led to separating this check from image validation and runtime selection. [OCI image index specification](https://github.com/opencontainers/image-spec/blob/main/image-index.md)
