# UI capture, incremental batches, and resume

## Establish scope before reading messages

Require a user-selected conversation and explicit range (absolute dates/times plus timezone,
or identifiable first/last message boundaries). Record the selection, local output directory,
consent wording, capture time, baseline/incremental mode and base batch in a local working
checkpoint. Do not start a broad export when the request names only a narrow range.
Use an opaque conversation ID that stays stable in the user's local ledger; mark its origin
as generated if WeCom does not expose an ID. Do not derive identity from a display title alone.

Use the available computer-use entrypoint and read its current tool documentation before
operating the app. Work from screenshots/accessibility text exposed by that UI. No shell
inspection of WeCom support folders, SQLite, memory, network traffic, caches or tokens.
If WeCom is closed, signed out, permission-blocked or displaying a different conversation,
stop before reading message content and state the specific required user action.

## Capture observations

Read viewports oldest to newest when practical. Search/navigation within the selected
conversation is allowed only within the authorized range. Use several adjacent messages
as an overlap anchor so repeated short messages do not masquerade as a unique boundary.
Record each observation's viewport/cursor reference, position, capture time and any uncertainty.
Do not package unrelated participants or other conversation previews visible in a screenshot.
Keep any necessary full UI screenshots private outside the package and repository.

- Text: preserve original Unicode and newlines. Copy visible original content where possible;
  never substitute a summary or OCR guess. Mark collapsed/unreadable text as incomplete.
- Sender: preserve visible display name. A stable account ID remains unknown unless exposed.
- Time: keep the exact UI label. Normalize only when date and timezone are evidenced. Keep
  unknown absolute time null, including ambiguous daylight-saving times or relative dates
  that cannot be established. Do not invent timestamps to make sorting easier; use order.
- Reply: preserve the visible quote, with a resolved reference only if the target is evidenced.
  An unresolved quote is valid and must not be silently linked by matching text alone.
- Image/file/audio/video: use the UI's original download/save action. Preserve bytes, original
  filename and media kind. Record expired, blocked, not downloaded, thumbnail-only and
  uncertain originals separately. Never label a thumbnail or screenshot as original media.
- Animated stickers: explicitly inspect the sticker's right-click menu for `Save As GIF`,
  `另存为 GIF`, or `另存为`; an absent AX menu is not proof the app has no export feature.
  Check the screenshot/current window state too. If the supported UI tool still exposes no
  menu, report that exact observation and request UI assistance instead of claiming the
  animation is unavailable. Use only the observed save action and a private local path.
  Verify the saved format from bytes, retain its original animation unchanged, and report
  frames/durations only when decoded from the actual saved file. Tool screenshots are
  isolated observations, not a complete frame sequence with source timing.
- System/unsupported/deleted/recalled messages: retain what is visibly stated and record
  unknown payloads. Do not infer a recalled message's prior text or an unavailable file.
- Derived OCR/transcription: opt-in local processing only; identify method, source attachment
  and uncertainty. Keep separate from original text and maintain the original media bytes.

## Checkpoint and resume

The local working checkpoint is outside the ZIP and can hold private operator notes. Write
after every viewport; avoid overwriting the last verified checkpoint until its successor is
saved. Include scope, conversation ID, batch/base IDs, observed message sequence,
last verified viewport and anchor IDs, attachment download ledger and outstanding gaps.
The CLI preview reports machine-checkable progress; it cannot prove UI observations
are accurate or that uncaptured messages do not exist.

On resume, check the same account/conversation/scope/timezone and load the previous checkpoint
and packages. Re-find the last verified multi-message anchor in the UI. If multiple locations
match, pause the boundary decision and ask the user to disambiguate; continue independent
attachment checks if possible. A missing anchor is a gap, not license to skip ahead silently.

## Baseline and incremental semantics

A baseline is the first authorized captured range, not a claim to all historical messages.
An incremental batch names its immediate base and retains overlapping observations for
review. Preserve legitimate repeated messages as distinct ordered occurrences. Keep generated
message IDs stable within a resumed batch (persist them in the working records).

Only stable exposed source IDs or an explicitly reviewed occurrence mapping can establish
cross-batch identity. Sender/time/text equality and content hashes are insufficient.
Ambiguous candidates stay separate and are surfaced for review; never let the AI choose one
and discard the others. Declare prior-batch attachment references explicitly and supply the
prior packages to the validator; missing/deleted dependencies require a self-contained
repackage with original bytes or an explicit unavailable status, not a dangling reference.
If a missing original is later recovered, keep the earlier validated ZIP immutable. Make a
new batch identity for the corrected package and record supersedes/replacement locally;
do not silently rewrite an existing batch. A replacement baseline is not an automatic
incremental import into Slinx's active linear history.

## Review and stopping conditions

Inspect the preview for selected range, actual coverage, message/media counts, missing media,
unknown times/senders, unresolved replies, overlap ambiguity and declared dependencies.
Completeness means only the authorized visible scope was covered with no known gap. A
structurally valid partial package is still partial. Authentication/permission/download
blocks stop the affected action; record the exact action, target, reason, completed work
and whether denied/pending/uncertain. Do not retry a denied operation without materially new
authorization. Never automate upload as part of this workflow.
