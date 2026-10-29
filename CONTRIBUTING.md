# Contribution workflow

Use this workflow for fixes, features, and documentation. You do not need to
know how to code a solution to open an issue.

**One problem per issue. One focused change per pull request. Review before merge.**

## 1. Open an issue

Search existing issues and pull requests first to avoid duplicate work.

Describe the challenge in plain language:

```text
Problem: What is difficult, missing, or broken?
Expected result: What should a user be able to do?
Example: A small input, expected output, or steps to reproduce the bug.
Done when:
- [ ] A clear, checkable outcome.
Out of scope: What should this change NOT do?
```

Explain the problem before proposing a solution. Only share music examples
you created or have permission to distribute.

## 2. Label and separate the work

Apply an existing label, or ask a maintainer to do so:

| Label | Use for |
| --- | --- |
| `bug` | Existing behavior is wrong |
| `enhancement` | A new capability |
| `documentation` | Instructions or explanations |
| `question` | Something needs clarification |

Use `help wanted` for available work and `good first issue` for a small,
well-defined newcomer task.

If changes can be reviewed and delivered independently, give them separate
issues. Link dependencies. Use a parent issue with a checklist for larger
work, such as separate notation-to-tab and tab-to-notation tasks.

## 3. Agree on the scope

Comment before starting so others know you are working on it. For larger
changes, agree with the maintainer on the smallest useful version and what
counts as done. Put unrelated ideas in separate issues.

## 4. Work on a feature branch

Start from the original repository's latest `main`. Use a new branch such as
`fix/2-key-signature` or `feat/8-guitar-tab`. Do not work directly on `main`.

Without write access, push to your own fork and open a PR back to the original
repository. Prefer waiting for prerequisite PRs to merge. Otherwise, name the
dependency and keep the dependent PR in draft.

## 5. Make and test the change

Avoid unrelated cleanup. Keep input parsing, musical conversion, and output
generation separate where practical.

Add tests for changed behavior and invalid inputs, then run the available
tests. Compile generated music with LilyPond when available and check pitches,
rhythm, and notation. Record anything you could not test. Update instructions
and limitations.

## 6. Open a pull request and review it

Explain what changed, why, and how to test it. Report test results and anything
not tested. Use `Fixes #N` only when the PR fully resolves that issue. Reference
parent issues without closing them prematurely.

Keep incomplete work in draft. When ready, request a maintainer's review of
scope, correctness, tests, documentation, and compatibility. Address feedback
and rerun affected tests. Get another person's review where possible.

## 7. Merge and close the loop

A maintainer merges after review, requested changes, and relevant checks are
complete, dependencies are merged, and conflicts are resolved.

Confirm the linked issue is closed. Close a parent only when its required
tasks are complete. File follow-up issues and remove the merged feature branch
when it is no longer needed.
