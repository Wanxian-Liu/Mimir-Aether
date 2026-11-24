# [DORMANT] computer-use

**沉寂时间**: 2026-11-22T02:34:59.481705+00:00
**原始分类**: autonomous-ai-agents
**描述**: Drive the desktop background-first; escalate on signal.
**触发阈值**: 60天未触碰

---

## 技能要点

# Computer Use (universal, any-model, cross-platform)

You have a `computer_use` tool that drives the user's desktop in the
**background** — your actions do NOT move the user's cursor, steal
keyboard focus, or switch virtual desktops / Spaces. The user can keep
typing in their editor while you click around in a browser in another
window. This is the opposite of pyautogui-style automation.

Everything here works with any tool-capable model — Claude, GPT, Gemini,
or an open model on a local OpenAI-compatible endpoint. There is no
Anthropic-native schema to learn.

Hermes drives [cua-driver](https://github.com/trycua/cua) under the hood.
This skill teaches the Hermes `computer_use` **action vocabulary**, which is
NOT the driver's raw MCP vocabulary. Call the actions documented below and
never the driver's tools by name: `capture` is a Hermes action that maps to
the driver's `get_window_state`; `element=N` is a Hermes argument that the
wrapper translates into the driver's `element_token` handle. If you see a
driver-side error mentioning `snapshot_id`, `element_token`, or "no reviewed
risk classification", you (or a stale description) called the raw driver
vocabulary — go back to the actions below.

## The canonical workflow

**Step 1 — Capture first.** Almost every task starts with:

```
computer_use(action="capture", mode="som", app="<the app you're driving>")
```

Returns a screenshot plus an indexed element list like:

```
#1  AXButton 'Back' @ (12, 80, 28, 28) [Chrome]
#2  AXTextField 'Address bar' @ (80, 80, 900, 32) [Chrome]
#7  Link 'Sign In' @ (900, 420, 80, 24) [Chrome]
...
```

The `#N` index is the ONLY element handle you use. Behind it the wrapper
keeps this snapshot's opaque per-element token and sends it with every
`element=N` action, so a click on an index from a superseded snapshot is
refused explicitly (`stale`) instead of landing on the wrong control.
Re-capture after anything that changes the screen; indices do not survive it.

The role names match th

... (truncated)

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("computer-use")` 即可自动唤醒。
