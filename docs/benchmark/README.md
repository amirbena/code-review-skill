# Code-Review Quality Benchmark

Repository-development contracts for the measurable code-review quality
benchmark (parent [#40](https://github.com/amirbena/code-review-skill/issues/40)):
a repeatable way to tell whether a Skill change improved or regressed
review quality against a fixed corpus.

Like [`../findings/`](../findings/README.md) and
[`../runtime-parallelism.md`](../runtime-parallelism.md), these are
repository-development docs — **not** packaged into either Skill archive,
and no packaged Skill resource depends on them. The normative rule for each
concern lives in the file named for it.

## Document map

| Document | Owns | Issue |
| --- | --- | --- |
| [`fixture-format.md`](fixture-format.md) | The canonical machine-readable format for a single benchmark case — case identity, input (inline patch or repository reference), expected findings, expected severity, expected location detail, the four typed variance constructs (same-defect alternatives, alternative findings, optional findings, permitted severity variance), optional metadata, schema/versioning, and fail-closed validation. | [#50](https://github.com/amirbena/code-review-skill/issues/50) |

Not yet written (tracked on #40): the corpus and case-selection rationale
([#51](https://github.com/amirbena/code-review-skill/issues/51)), the
runner ([#52](https://github.com/amirbena/code-review-skill/issues/52)),
and regression reporting
([#53](https://github.com/amirbena/code-review-skill/issues/53)).

## Worked example

[`examples/example-case.yaml`](examples/example-case.yaml) is one complete,
validated `benchmark-case/v1` fixture referenced by `fixture-format.md`
§12. It is an illustrative reference for the format, **not** a corpus case
(the corpus is #51). Its automated validation and the negative tests for
the format's rejection rules live in
[`../../tests/unit/test_benchmark_fixture.py`](../../tests/unit/test_benchmark_fixture.py).

## Related

The architecture map is [`../ARCHITECTURE.md`](../ARCHITECTURE.md).
