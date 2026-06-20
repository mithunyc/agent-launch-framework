# Eval Matrix

## Purpose

The framework must grade whether an agent pack is safe, useful, and portable before it is installed or automated.

## V0 Matrix

| Capability | Required Evidence | V0 Check | Failure Mode |
|---|---|---|---|
| Installable in Codex | Skill folders have valid `SKILL.md` frontmatter | `validate_agent_pack.py` | Slash command hidden or broken |
| Portable contract | `agent.yaml` avoids runtime-only claims | `validate_agent_pack.py` | Claude/Codex lock-in hidden in prompt |
| Definition of done | `dod.md` has measurable criteria | `validate_agent_pack.py` | Agent declares success without scoring |
| Adversarial coverage | Eval cases include expected behaviors and failure modes | `run_pack_eval.py` | Eval only checks happy path |
| Codex behavior baitset | Codex JSONL, structured final output, and mechanical checks | `run_codex_behavior_eval.py` | Skill looks valid but fails under Codex |
| Hidden semantic rubric | Case-specific rubric grades final JSON after the prompt is answered | `semantic_evaluator.py` | Keyword checks pass while the answer is unsafe or weak |
| Second-opinion evaluator | Case-independent safety and usefulness invariants grade every final JSON | `second_opinion_evaluator.py` | A case rubric passes while the answer still overclaims, lacks evidence, or asks too many human questions |
| Managed behavior gate | Static eval, all selected behavior cases, job policy, aggregate receipt | `run_behavior_gate.py` | One green case is mistaken for platform readiness |
| Repeated-run variance gate | Same full behavior gate runs repeatedly and compares semantic score, second-opinion score, status, safe verdict family, count, and fingerprint drift | `run_variance_gate.py` | One lucky pass is mistaken for stable behavior |
| Disposable plugin packaging gate | Pack fingerprint-bound variance receipt, plugin manifest, marketplace metadata, negative plugin fixtures, temp-`CODEX_HOME` install, prompt-input discovery | `run_plugin_packaging_gate.py` | A valid-looking folder is mistaken for an installable Codex plugin |
| Plugin packaging variance gate | Same packaging gate runs repeatedly and compares package fingerprint, marketplace fingerprint, CLI install output, and prompt-input discovery digest | `run_plugin_packaging_variance_gate.py` | One disposable package pass is mistaken for stable plugin distribution |
| Harness self-test | Positive control plus broken skill, eval, claim, job, semantic, and variance fixtures | `run_harness_selftest.py` | Bad packs or bad answers pass because the gate itself was never tested |
| Safety policy | Read/write/secret policies exist | `validate_agent_pack.py` | Agent takes unsafe action by default |
| Receiptability | Receipt template has evidence, checks, risk, rollback | `validate_agent_pack.py` | Work cannot be audited later |
| Memory hygiene | Memory rules require source/confidence/expiry | `validate_agent_pack.py` | Bad lessons become permanent |
| Self-improvement safety | Proposals are gated by evals and approval | `validate_agent_pack.py` | Agent mutates its own instructions unchecked |

## Runtime Matrix

| Runtime | Autonomy | Offline PC Support | Mobile/Web Support | V0 Role |
|---|---:|---:|---:|---|
| Codex app skill | Low | No | Host-dependent | Primary manual use |
| Codex CLI `exec` | Medium | No | Script/CI dependent | Future runner |
| Codex app automation | Medium | No | Host must be online | Future scheduled local runs |
| Codex cloud | High | Yes for cloud task | Yes | Future cloud adapter |
| GitHub Action | High | Yes | Web repo dependent | Future CI runner |
| Local OSS model | Medium | Yes locally | No | Future offline adapter |

## Acceptance Threshold For A New Agent Pack

A pack is installable only if:

- validator passes
- eval runner passes
- no policy file is missing
- no skill frontmatter is malformed
- receipt template is present
- rollback path is documented

V1 adds:

- at least one Codex-native behavior case passes through `codex exec`
- raw JSONL and final structured output are captured
- no global Codex skill directory is mutated during behavior eval
- failed or blocked Codex auth/model/runtime states are recorded as evidence
- hidden deterministic semantic rubrics grade each final answer after generation
- harness self-tests prove selected broken fixtures fail before behavior evidence is trusted

V2 adds:

- a managed job contract exists for the behavior gate
- the behavior gate runs all cases by default
- the behavior gate defaults to clean-room Codex execution without user config, user rules, plugin cache, or global skills
- aggregate receipts include job metadata, policy decision, static eval, Codex behavior eval, semantic eval, risks, and rollback
- aggregate receipts include second-opinion scores in addition to semantic scores
- repeated-run variance receipts include semantic score stability, second-opinion score stability, bounded structural count drift, recorded self-grade drift, and bounded answer-fingerprint drift
- plugin packaging receipts include current pack fingerprint binding, package and marketplace fingerprints, marketplace validation, negative plugin fixtures, temp-`CODEX_HOME` install evidence, and prompt-input discovery evidence
- plugin packaging variance receipts show stable package fingerprints, marketplace fingerprints, CLI install behavior, and prompt-input discovery digests across repeated runs
- a gate pass is not treated as proof of cloud/mobile readiness or provider agnosticism
