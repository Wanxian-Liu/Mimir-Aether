# [DORMANT] humanizer

**沉寂时间**: 2026-11-22T02:34:57.172227+00:00
**原始分类**: creative
**描述**: Humanize text: strip AI-isms and add real voice.
**触发阈值**: 60天未触碰

---

## 技能要点

# Humanizer: Remove AI Writing Patterns

Identify and remove signs of AI-generated text to make writing sound natural and human. Based on Wikipedia's "Signs of AI writing" guide (maintained by WikiProject AI Cleanup), derived from observations of thousands of AI-generated text instances.

**Key insight:** LLMs use statistical algorithms to guess what should come next. The result tends toward the most statistically likely completion, which is how the telltale patterns below get baked in.

## When to use this skill

Load this skill whenever the user asks to:
- "humanize", "de-AI", "de-slop", or "un-ChatGPT" a piece of text
- rewrite something so it doesn't sound like it was written by an LLM
- edit a draft (blog post, essay, PR description, docs, memo, email, tweet, resume bullet) to sound more natural
- match their voice in writing they're producing
- review text for AI tells before publishing

Also apply this skill to **your own** output when writing user-facing prose such as release notes, PR descriptions, docs, and summaries. Hermes's baseline voice already strips most of these, but a focused pass catches what slips through.

## How to use it in Hermes

The text usually arrives one of three ways:
1. **Inline.** The user pastes the text into the message. Work on it in place and reply with the rewrite.
2. **File.** The user points at a file. Use `read_file` to load it, then `patch` or `write_file` to apply edits. For a markdown doc in a repo, a targeted `patch` per section is cleaner than rewriting the whole file.
3. **Voice calibration sample.** The user provides a sample of their own writing (inline or by file path) and asks you to match it. Read the sample first, then rewrite. See the Voice Calibration section below.

Always show the rewrite to the user. For file edits, show a diff or the changed section instead of silently overwriting.

## Your task

When given text to humanize:

1. **Identify AI patterns.** Scan for the 34 patterns listed below.
2. **Rewrite pr

... (truncated)

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("humanizer")` 即可自动唤醒。
