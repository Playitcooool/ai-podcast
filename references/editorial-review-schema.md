# Editorial review schema

Create `02-editorial-review.json` after the script and evidence are final. Review
the actual text and sources; do not mark a check passed merely because required
fields exist.

```json
{
  "review_schema_version": 1,
  "reviewed_at": "2026-07-29T00:00:00+08:00",
  "script_sha256": "SHA-256 of 02-script.json",
  "evidence_sha256": "SHA-256 of 01-evidence.json",
  "checks": {
    "opening_transition_semantics": {
      "status": "passed",
      "notes": "How the transition responds, frames difficulty, and avoids a verdict."
    },
    "turn_length_exceptions": {
      "status": "passed",
      "notes": "Why every 121–180-character turn must remain unsplit."
    },
    "semantic_progression": {
      "status": "passed",
      "notes": "How paraphrased repetition was removed and each turn advances."
    },
    "fact_source_alignment": {
      "status": "passed",
      "notes": "How every fact matches the cited evidence and inference stays bounded."
    },
    "tts_text_accuracy": {
      "status": "passed",
      "notes": "How spoken forms preserve names, abbreviations, and numeric meaning."
    },
    "closing_language": {
      "status": "passed",
      "notes": "How the ending stays nuanced, non-preachy, specific, and avoids generic calls."
    }
  }
}
```

Every check must use `status: "passed"` and non-empty, check-specific notes. Any
uncertainty requires revising the script or evidence before synthesis. Compute the
two hashes after the files are final. Any later script or evidence change invalidates
the review and requires reviewing again with new hashes.
