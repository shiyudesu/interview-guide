# Git 提交消息 Hook

首次克隆仓库后执行：

```bash
git config core.hooksPath .githooks
```

提交消息格式：

```text
feat: 中文标题

- 分条说明具体改动
- 分条说明验证或兼容性影响
```

允许的类型为 `feat`、`fix`、`refactor`、`perf`、`test`、`docs`、`chore`、`build`、`ci`、`revert`，可使用英文 scope，例如 `fix(question): 修复题目导入失败`。

本地验证：

```bash
bash scripts/test-commit-msg-hook.sh
```
