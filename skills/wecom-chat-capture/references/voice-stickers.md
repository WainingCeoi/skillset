# Voice messages and sticker representations

Read this when the authorized conversation contains voice messages, animated stickers or
an explicitly requested static screenshot fallback. Do not inspect another real conversation
to find a convenient test voice message; use synthetic fixtures for implementation checks.

## Voice: original audio first

Keep the voice occurrence's visible sender, original time label, order and visible duration
even when no payload can be exported. Unknown values stay unknown. A duration label belongs
to voice metadata, never the sender's original text. Do not infer words from duration, nearby
messages or conversation context.

1. Inspect only that voice message's normal UI save/download/export action. If it exposes
   original audio, save the actual file to the private local batch directory, preserve its
   exact bytes, record the real display filename and MIME type when evidenced, and hash it.
   Preserve unknown/proprietary codecs as bytes; do not transcode just to make them playable.
2. If the UI exposes a transcript or an authorized built-in `转文字` action, retain the displayed
   result as **WeCom-derived transcription**, with its UI provenance. It is not the sender's
   original typed text, not a verified verbatim quote, and not a recovered audio file. Keep
   original message text null for a voice-only bubble. Never silently correct, summarize or
   translate the displayed transcript during capture.
3. If audio or transcription is unavailable, retain the same message occurrence, visible
   duration/sender/time and explicit gap. No transcript plus no audio is still a captured
   voice occurrence with missing media, not permission to drop the message or invent text.

Do not use microphone recording, system/loopback recording, screen recording with audio,
hidden caches/databases, external transcription services, paid APIs or guessed transcriptions.
This workflow neither records playback nor sends audio to another service. If a normal UI
action is blocked, stop it and retain the gap rather than bypassing the restriction.

The deterministic helper only prepares/validates metadata and local bytes. It does not play
voice, click `转文字`, perform speech recognition, or prove that a caller-supplied transcript
actually came from WeCom. The operator must verify its displayed UI source.

## Stickers: original animation or explicit static fallback

Prefer the normal `Save As GIF`/`另存为 GIF` action where exposed. Verify the saved bytes rather
than trusting the filename. Preserve a GIF/WebP/APNG/video original unchanged; report frames,
duration or loop values only when read from the actual original file. A tool screenshot is
one observed display state, without source animation timing or a complete frame sequence.

A static fallback requires the user's explicit choice. Capture one current display frame,
crop only the sticker region, exclude surrounding chat and unrelated UI, preserve the decoded
crop pixels, and save a lossless PNG. Do not use image generation, redraw the sticker, make up
animation frames, or describe the PNG as a downloaded original. Keep any full-window temporary
capture private and remove it once the crop is verified; retain only the cropped output.

Keep the missing original inventory entry and add the static preview as a separately labeled
derived representation. Overall attachment completeness stays partial. Original message text,
occurrence order and unknown times remain unchanged. Use the canonical typed representation
described in [contract.md](contract.md); do not hide derived content inside sender text or
silently claim original recovery. Freeform notes may explain gaps but cannot establish source
identity or replace a required typed source/derived distinction.

## Corrections and compatibility

Never rewrite an already validated batch in place. Create a new batch identity and a local
replacement/supersedes note identifying the prior package and hashes. A corrected standalone
baseline is separate from Slinx's linear incremental import chain; local packaging does not
authorize import, deletion or replacement of online data.

Original-versus-derived roles, voice duration and UI transcripts must remain explicit through
normalization, preview and ZIP round trips. A derived image/transcript cannot satisfy original
media completeness or become an original message identity anchor. Test these rules using
invented images/audio/transcript strings only.
