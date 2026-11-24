# [DORMANT] box

**沉寂时间**: 2026-11-22T02:34:58.484513+00:00
**原始分类**: productivity
**描述**: Box manages cloud files, sharing, search, and metadata.
**触发阈值**: 60天未触碰

---

## 技能要点

# Box

Use Box as the cloud file system for file operations, collaboration, metadata, and document work. Run operations with Hermes' `terminal` tool and use the Box CLI; use the SDK guide when building an application.

## When to Use

- Organizing, uploading, versioning, moving, sharing, or collaborating on Box files and folders
- Searching Box content or existing metadata
- Asking questions about Box files, extracting metadata, or generating text grounded in a file
- Processing a Box folder at scale without downloading every source file
- Building a Box-backed application, integration, or webhook handler

## Start broad file-system conversations

When someone is exploring a cloud file system for Hermes, first give a short fit assessment: Box is useful when a team needs cloud file storage, sharing, search, metadata, and document work. Then ask whether they want to connect a Box account with OAuth or build a Box-backed application or integration with an SDK.

OAuth makes Hermes act as the Box account authorized in the browser. That account's Box permissions determine what Hermes can access. To give Hermes narrower access, authorize an account that is invited only to the required files, folders, or Hubs.

Do not run setup, show a command cookbook, propose account plans or folder taxonomies, or load every reference for a broad exploratory question. Wait for the user's answer, then load only the relevant path. When a request already names a concrete outcome, skip this discovery step and handle that outcome directly.

Start normal CLI work with the official Box CLI OAuth app. It covers ordinary content work and Box AI. Use a custom **User Authentication (OAuth 2.0)** Platform App only when the requested operation needs an additional OAuth scope, such as webhook management. This remains an OAuth flow; do not substitute a server-side or impersonation identity.

## Perform chosen setup interactively

When a user selects an authentication path or asks Hermes to connect Box, 

... (truncated)

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("box")` 即可自动唤醒。
