# OCI 平台覆盖检查

[English](README.md)

发布多平台镜像前，用本地 OCI 镜像索引核对发布矩阵中的每个平台是否恰好有一个候选清单。只需 Python 3.11 或更高版本及其标准库。

```console
python oci_platform_coverage.py fixtures/index.json fixtures/requirements-covered.json
python oci_platform_coverage.py fixtures/index.json fixtures/requirements-gap.json
```

第二条命令返回以下报告。

```json
{"covered":2,"missing":1,"ambiguous":1,"skipped":2,"requirements":[{"ordinal":1,"matches":[]},{"ordinal":2,"matches":[2,5]},{"ordinal":3,"matches":[1]}]}
```

报告按需求的输入顺序排列。`ordinal` 是需求位置，`matches` 是匹配条目在原索引中的位置，均从 1 开始。`covered` 统计有至少一个候选的需求，其中有多个候选的计入 `ambiguous`。`missing` 统计无候选的需求，`skipped` 统计跳过的索引条目。报告仅包含位置和计数。

| 退出码 | 含义 |
| --- | --- |
| `0` | 每项需求恰好一个候选。 |
| `1` | 至少一项需求缺失或有多个候选，报告写入 stdout。 |
| `2` | 用法、输入或输出错误。stderr 可写时输出固定诊断。 |

## 输入规则

- 索引对象需要整数 `schemaVersion` `2` 和 `manifests` 数组。若提供 `mediaType`，值必须是 `application/vnd.oci.image.index.v1+json`。
- 每个描述符需要字符串 `mediaType`、由 `sha256:` 和 64 位小写十六进制字符组成的 `digest`，以及范围为 `0` 到 `2**63 - 1` 的整数 `size`。
- 跳过 `mediaType` 不是 `application/vnd.oci.image.manifest.v1+json` 的描述符，也跳过缺少 `platform` 的描述符。镜像清单描述符若提供 `platform`，必须符合平台对象规则。`os` 和 `architecture` 均为 `unknown` 的描述符也会被跳过。每个跳过条目只统计一次。
- 需求是由不同平台对象组成的非空数组，每项需要 `os` 和 `architecture`，可以提供 `variant`。字段值须完整匹配 `[a-z0-9][a-z0-9_-]*`。需求对象仅允许上述键。索引、描述符及其平台对象中的额外元数据仍须通过 JSON 校验。
- 只做字面匹配，`linux/arm` 和 `linux/arm/v7` 是两个不同的需求键。`v8.1` 等超出该语法的 OCI 变体值不在输入范围内。

## 文件与匹配范围

两个输入都是上限为 1 MiB 的 UTF-8 JSON 普通文件。重复键、非有限数字、无效 UTF-8 和未配对代理码位都会触发错误，元数据也遵守相同规则。工具在访问任一文件前检查两个路径，允许相对路径和 Windows 盘符绝对路径，拒绝 URI、UNC、设备名、盘符相对路径和备用数据流。允许的路径仍可能经符号链接、目录联接或挂载指向远程存储。需要保证存储位置时，请使用自己控制的文件系统。

检查范围是给定索引的声明。运行时选择、系统版本和特性匹配、架构别名、嵌套索引展开、摘要验证、访问镜像仓库和下载镜像层均在范围之外。

[调研](RESEARCH.md) · [测试](TESTING.md) · [MIT 许可证](LICENSE)
