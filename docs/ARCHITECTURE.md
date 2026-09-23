# ZedThema architecture

## Design principle

ZedThema separates **research evidence** from **AI interpretation**.

The source transcript remains the evidence. AI produces a suggestion. The researcher creates the validated coding decision.

## Core objects

- Project: study question, theory, method and languages.
- Code: hierarchical construct/theme with methodological guidance.
- Source: original research material and transcript.
- Segment: a timestamped or text-positioned evidence unit.
- Coding: a code assigned to a segment, with model, confidence, rationale and review state.
- Coding run: records which model produced a set of suggestions.
- Anomaly: a quantitative result that may need qualitative explanation.
- Audit event: a record of an important research action.
- Project member: researcher with a project role.

## Why the audit trail matters

A final theme should be traceable back through:

```text
Finding
  -> accepted coding
  -> AI suggestion / researcher edit
  -> transcript segment
  -> source file
  -> analysis run and model
```

This is more useful for research reproducibility than simply storing a final list of themes.
