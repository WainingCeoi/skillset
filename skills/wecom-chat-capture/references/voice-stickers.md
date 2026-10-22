# Voice messages and sticker representations

Read this when the authorized conversation contains voice messages or stickers. Do not
inspect another real conversation to find a convenient test voice message; use synthetic fixtures for implementation checks.

## Voice: UI transcript by default, retain voice origin

Keep the voice occurrence's visible sender, original time label, order and visible duration
even when no payload can be exported. Unknown values stay unknown. A duration label belongs
to voice metadata, never the sender's original text. Do not infer words from duration, nearby
messages or conversation context.

1. Read the existing displayed transcript, or use the voice occurrence's normal built-in
   `转文字` action within the authorized capture scope. Retain the displayed result verbatim
   as **WeCom-derived transcription**, with its UI provenance. Do not inspect or try audio
   save/download/export actions by default, even when transcription is unavailable.
2. Keep the occurrence marked `type:"voice"` with original `text:null`. Store the transcript
   in `voice.transcripts[]`, labeled `source:"wecom_ui"`; preserve the visible sender,
   timestamp label, order and duration. The transcript is derived from voice, not original
   typed text or verified verbatim audio. Never correct, summarize or translate it during capture.
3. Use a missing-original audio inventory entry with no payload file. Record the reason as
   intentional omission, for example `Audio not captured: transcript-only voice capture;
   audio export not attempted.` Do not claim export failed or WeCom forbids export when it
   was not tried. Original attachment completeness remains partial; the omitted audio does
   not block ZIP delivery when the requested transcript has been captured. Include the
   intentional omission and lack of an export attempt in manifest completeness notes too.
4. If `转文字` is absent, blocked, fails, or yields unreadable/truncated content, retain the
   voice occurrence and an explicit transcript gap; keep unknown transcript content absent.
   Use `transcripts:[]` when no readable UI result exists.
   Do not substitute an audio export attempt, guess words or silently drop the occurrence.

Only if the user explicitly requests original audio, inspect that occurrence's normal UI
save/download/export action. Preserve any saved original bytes unchanged, with evidenced
filename/MIME metadata; never transcode them. This exception does not change the default.

Do not use microphone recording, system/loopback recording, screen recording with audio,
hidden caches/databases, external transcription services, paid APIs or guessed transcriptions.
This workflow neither records playback nor sends audio to another service. If a normal UI
action is blocked, stop it and retain the gap rather than bypassing the restriction.

The deterministic helper only prepares/validates metadata and local bytes. It does not play
voice, click `转文字`, perform speech recognition, or prove that a caller-supplied transcript
actually came from WeCom. The operator must verify its displayed UI source.

## Stickers: original first, visible crop when unavailable

Prefer the normal `Save As GIF`/`另存为 GIF` action where exposed. Verify the saved bytes rather
than trusting the filename. Preserve a GIF/WebP/APNG/video original unchanged; report frames,
duration or loop values only when read from the actual original file. A tool screenshot is
one observed display state, without source animation timing or a complete frame sequence.

Capturing visible sticker artwork is part of authorized capture unless screenshots were
excluded. Try the normal visible export action; if it is absent, blocked or unsuccessful,
record the precise outcome and capture one current display frame. Do not leave only a
missing-file record while readable artwork remains visible. Do not repeatedly probe an
unavailable export or require the user to operate a menu just to proceed with a visible crop.

Use the computer-use tool's supported screenshot/crop operation. If a tool only returns
an inline image without a usable local file or crop API, use another available documented
UI screenshot capability; do not invent an attachment path or claim bytes were saved.
If no supported route can save the pixels, retain an explicit visual gap.
When a full screenshot PNG is saved but the tool has no crop operation, use
`crop_preview.py` as shown in [usage.md](usage.md#prepare-stickers-without-dropping-visible-artwork).
Crop only the sticker region, exclude surrounding chat and unrelated UI, preserve the decoded
crop pixels, and save a lossless PNG. Do not use image generation, redraw the sticker, make up
animation frames, or describe the PNG as a downloaded original. Keep any full-window temporary
capture private and remove it once the crop is verified; retain only the cropped output.
The preview must be static PNG, never APNG or another animation, including a one-frame APNG.
Use noninterlaced 8-bit RGB/RGBA crops for the local helper; total local previews are bounded
to 16,777,216 decoded pixels and each dimension to 16,384.

Before saving the crop, dismiss context menus and hover overlays and wait for the sticker
to load. Use coordinates in the actual screenshot's pixel space, accounting for display
scaling and any tool-resized image; do not reuse UI point coordinates as pixels blindly.
Inspect the saved PNG: the whole visible artwork must be present, legible, and from the
correct occurrence, with no surrounding participants or unrelated messages. Do not resize
or upscale to invent detail, remove a background, or edit the artwork. If the current frame
is blank or a loading state, retry a visible observation, without stitching frames into a
fabricated animation. If no readable frame is available, report that visual gap.

Keep the missing original inventory entry and add the static preview as a separately labeled
derived representation. Overall attachment completeness stays partial. Original message text,
occurrence order and unknown times remain unchanged. Use the canonical typed representation
described in [contract.md](contract.md); do not hide derived content inside sender text or
silently claim original recovery. Freeform notes may explain gaps but cannot establish source
identity or replace a required typed source/derived distinction.

## Corrections and compatibility

Never rewrite an already validated batch in place. Create a new batch identity and a local
replacement/supersedes note identifying the prior package and hashes. A corrected standalone
baseline is a separate local package; ZIP delivery does not authorize import, deletion or
replacement of online data.

Original-versus-derived roles, voice duration and UI transcripts must remain explicit through
normalization, preview and ZIP round trips. A derived image/transcript cannot satisfy original
media completeness or become an original message identity anchor. Test these rules using
invented images/audio/transcript strings only.

Use `voice-record` and the invented examples in [usage.md](usage.md#voice-and-static-preview-examples)
to prepare the typed voice states. Transcript-only is the default; retain a missing original
audio reference for intentionally omitted audio, including when the transcript is also missing.
The original-audio example covers an explicit user request only. This is metadata preparation,
not an audio capture or transcription command.
