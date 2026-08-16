# Git Hooks

Enable the repository hooks after cloning:

```bash
git config core.hooksPath .githooks
```

Commit subjects follow Conventional Commits:

```text
feat: add resume parsing baseline
fix(api): preserve the legacy error response
docs(migration): 更新迁移检查清单
```

Allowed types are `feat`, `fix`, `refactor`, `perf`, `test`, `docs`, `chore`,
`build`, `ci`, and `revert`. A scope and breaking-change marker are optional.
The summary may use any language.

The body is optional. When present, leave one blank line after the subject.
Bullets, paragraphs, issue references, and Git trailers are all accepted.

Run the hook tests with:

```bash
bash scripts/test-commit-msg-hook.sh
```
