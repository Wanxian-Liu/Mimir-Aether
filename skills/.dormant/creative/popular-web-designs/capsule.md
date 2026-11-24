# [DORMANT] popular-web-designs

**沉寂时间**: 2026-11-22T02:34:56.434536+00:00
**原始分类**: creative
**描述**: 54 real design systems (Stripe, Linear, Vercel) as HTML/CSS.
**触发阈值**: 60天未触碰

---

## 技能要点

# Popular Web Designs

54 real-world design systems ready for use when generating HTML/CSS. Each template captures a
site's complete visual language: color palette, typography hierarchy, component styles, spacing
system, shadows, responsive behavior, and practical agent prompts with exact CSS values.

## Related design skills

- **`claude-design`** — use for the design *process and taste* (scoping a brief,
  producing variants, verifying a local HTML artifact, avoiding AI-design slop).
  Pair it with this skill when the user wants a thoughtfully-designed page styled
  after a known brand: `claude-design` drives the workflow, this skill supplies
  the visual vocabulary.
- **`design-md`** — use when the deliverable is a formal DESIGN.md token spec
  file, not a rendered artifact.

## How to Use

1. Pick a design from the catalog below
2. Load it: `skill_view(name="popular-web-designs", file_path="templates/<site>.md")`
3. Use the design tokens and component specs when generating HTML
4. Pair with the `generative-widgets` skill to serve the result via cloudflared tunnel

Each template includes a **Hermes Implementation Notes** block at the top with:
- CDN font substitute and Google Fonts `<link>` tag (ready to paste)
- CSS font-family stacks for primary and monospace
- Reminders to use `write_file` for HTML creation and `browser_vision` for verification

## HTML Generation Pattern

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Page Title</title>
  <!-- Paste the Google Fonts <link> from the template's Hermes notes -->
  <link href="https://fonts.googleapis.com/css2?family=..." rel="stylesheet">
  <style>
    /* Apply the template's color palette as CSS custom properties */
    :root {
      --color-bg: #ffffff;
      --color-text: #171717;
      --color-accent: #533afd;
      /* ... more from template Section 2 */
    }
    /* Apply typography from template Sect

... (truncated)

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("popular-web-designs")` 即可自动唤醒。
