# Package contract — alignment draft

Slinx owns the canonical v1 importer contract. Field names in this draft are proposals;
do not claim importer compatibility until the canonical contract is aligned and tested.

One ZIP per conversation/batch. Its only root entries are `manifest.json`, `messages.jsonl`
and `media/` (an empty media directory is permitted). Original media bytes remain unchanged.
All JSON is UTF-8. No media base64 in messages. Paths are safe relative paths under media/;
original display filenames are metadata, never trusted as paths.

Proposed manifest: version, conversation/batch/base IDs, range with timezone, message/media
counts, attachment inventory with SHA256/size/path/original display names, file hashes and
completeness with explicit gaps. Prior media references identify source batch and SHA256
and must resolve against validated supplied packages.

Proposed messages: stable or explicitly generated ID, provenance, sender, timestamp and
original time label, chronological occurrence order, message type, original text, reply
reference and attachment refs. Preserve repeated identical legitimate occurrences.
Keep OCR/transcription under labeled derived metadata, never original fields.

Incremental anchors identify observed occurrences and candidate prior occurrences with a
review state. No automatic merging on content hashes or sender/time/text fingerprints.
An unavailable stable source ID must remain unknown rather than disguised as a generated one.
