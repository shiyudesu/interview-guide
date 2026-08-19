# Git Hooks

克隆仓库后启用提交钩子：

```bash
git config core.hooksPath .githooks
```

Commit subject 使用 Conventional Commits：

```text
feat(resume): add reanalysis endpoint
fix(worker): reclaim pending evaluation
docs: refresh deployment guide
```

允许的类型：

```text
feat fix refactor perf test docs chore build ci revert
```

scope 和 `!` 可选，subject 可以使用中文或英文。需要 body 时，subject 后留一个空行。
Issue 引用和 Git trailer 可以放在 body 末尾。

运行钩子测试：

```bash
bash scripts/test-commit-msg-hook.sh
```
