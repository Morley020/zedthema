# ZedThema 1.0

**Open-source, local-first, researcher-controlled qualitative research platform.**

ZedThema is a general-purpose framework for qualitative and mixed-methods research. It is not tied to particular topic, construct, one discipline, or one coding method.

The design goal is simple:

> Keep the researcher's evidence, codebook, AI suggestions, validation decisions, and audit trail together in a reproducible local workflow.

## What changed in this version

The original starter was a useful proof of concept, but it had several issues that would appear as soon as the application was used beyond a small demo. 
### Research workflow

- Project-based study management.
- Research question, method, theory and language metadata.
- True parent/child code hierarchy.
- Code definitions, inclusion/exclusion rules, examples and theory links.
- Human review of every AI coding suggestion.
- Time-coded transcript segments.
- Optional speaker diarization.
- Corpus search with optional semantic embeddings and a clearly labelled local fallback.
- Dual-model coding.
- Cohen's kappa, Krippendorff's alpha (nominal) and Jaccard agreement.
- Quantitative anomaly register for mixed-methods studies.
- Reproducibility audit trail.
- REFI-QDA Project (`.qdpx`) and Codebook (`.qdc`) export foundations.
- CSV, XLSX, JSON and DOCX exports.

### Security and collaboration

- Optional user authentication.
- Project membership and roles.
- Password hashing.
- Signed session tokens.
- Encryption of sensitive research text in SQLite when enabled.
- Automatic local encryption-key generation for simple installations.
- Optional environment-provided encryption key for managed deployments.
- File-size limits.
- Public URL import blocks private/reserved network targets by default to reduce SSRF risk.

## Architecture

```text
Browser / React
       |
       v
FastAPI REST API
       |
       +---- SQLite metadata + encrypted research text
       |
       +---- Local source storage
       |
       +---- faster-whisper ------> timestamped transcript
       |                              |
       +---- optional pyannote ------> speaker labels
       |                              |
       +---- Ollama -----------------> AI coding suggestions
       |                              |
       +---- corpus search ----------> evidence retrieval
       |                              |
       +---- agreement statistics ----> validation evidence
       |
       +---- REFI-QDA / CSV / XLSX / DOCX / JSON exports
```

The normal workflow does not require a cloud LLM. Ollama can run locally.

## Important research principle

ZedThema does **not** treat an LLM output as a validated finding.

The intended chain is:

```text
Source
  ↓
Transcript
  ↓
AI suggestion
  ↓
Researcher review
  ↓
Accepted / edited / rejected coding
  ↓
Analysis / interpretation
```

Agreement statistics measure consistency. They do not prove that a code is substantively correct.

## macOS installation

### 1. Check Python and Ollama

```bash
python3 --version
ollama --version
ollama list
```

If Ollama is running locally, confirm that your selected model is available:

```bash
ollama list
```

### 2. Start ZedThema

```bash
cd ZedThema
./start_mac.sh
```

The script creates a Python virtual environment, installs backend dependencies, creates `backend/.env` from the example file, starts FastAPI, and starts the Vite frontend.

### 3. Manual installation

Backend:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Frontend, in another terminal:

```bash
cd frontend
npm install
npm run dev
```

## Configuration

Edit `backend/.env`.

```text
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:70b
WHISPER_MODEL=small
MAX_SOURCE_MB=500
DATA_DIR=../data
AUTH_ENABLED=false
ENCRYPTION_ENABLED=true
JWT_SECRET=replace-with-a-long-random-secret
```

For a single researcher on one Mac, keep `AUTH_ENABLED=false`.

For a team deployment, enable authentication and replace `JWT_SECRET` with a long random secret.

For managed deployments, consider supplying the encryption key through a protected environment variable rather than relying on the automatically generated local key. If the encryption key is lost, encrypted research data cannot be recovered.

## Optional research features

Install the optional dependencies only when needed:

```bash
pip install -r backend/requirements-optional.txt
```

This includes:

- `pyannote.audio` for speaker diarization.
- `sentence-transformers` for semantic corpus search.
- `refio` for future deeper REFI-QDA validation/import tooling.

Speaker diarization may require a Hugging Face token and acceptance of the relevant model terms. Configure `HF_TOKEN` in `.env` when required.

## Supported source types

- Audio: MP3, M4A, WAV, AAC, FLAC, OGG, WMA.
- Video: MP4, MOV, MKV, AVI, WEBM.
- Text: TXT, Markdown, RTF.
- Documents: DOCX, PDF.
- Structured data: CSV, JSON.
- Public HTTP/HTTPS URLs.
- Local filesystem paths when the backend is running on the same computer.

## Multilingual research

The project metadata includes English, Bemba, Nyanja/Chichewa, Tonga, Lozi/Silozi, Nsenga, Kaonde, Lunda, Luvale, Swahili and Portuguese.

These selections are **not** an accuracy claim about the speech model. Actual transcription performance for Zambian languages must be measured against researcher-validated transcripts.

That creates a possible separate benchmark project:

> Zambian Multilingual Qualitative Speech Benchmark

The benchmark can compare transcription error, code-relevant meaning loss, speaker effects, and language-specific failure patterns.

## REFI-QDA interoperability

ZedThema now produces `.qdpx` and `.qdc` export foundations. The implementation follows the public REFI-QDA project/codebook structure, but researchers should validate exported files against the current official XSD before describing a particular release as fully conformant.

The project specification describes `.qdpx` as a ZIP archive containing a project XML file and source material. ZedThema follows that basic archive model.

## Tests

Run the backend test suite:

```bash
cd backend
python -m pytest -q
```

The included tests cover:

- password hashing and verification;
- agreement calculations;
- REFI-QDA archive creation;
- basic API project/code/source/search workflow;
- time-coded coding storage.

The frontend requires Node/npm and should be checked with:

```bash
cd frontend
npm install
npm run build
```

## Research validation roadmap

The software can now support a serious empirical evaluation.

### Suggested comparison

```text
Manual coding
       vs
AI-assisted coding
       vs
AI-assisted coding + human validation
       vs
Dual-model AI + human validation
```

### Outcomes

- Coding agreement.
- Time required per transcript.
- Missed relevant themes.
- Unsupported or false themes.
- Quotation fidelity.
- Construct/code mapping accuracy.
- Researcher correction rate.
- Language effects.
- Speaker-diarization effects.
- Reproducibility of the final coding matrix.

### Possible Information Systems contribution

**Evaluating AI-Assisted Qualitative Coding for Information Systems Research in Multilingual African Contexts**

The Yango interviews can be the first case, rather than the boundary of the tool.

The same engine can be used for:

- digital health;
- cybersecurity;
- e-government;
- FinTech;
- AI adoption;
- digital transformation;
- ICT4D;
- software engineering;
- education technology;
- agriculture technology;
- organisational studies;
- mixed-methods research.

## Code quality rule

Source files are deliberately kept readable and commented. Comments explain the purpose of security, ingestion, coding, agreement and export functions in plain language. When adding a new feature, preserve this standard: a researcher who is not a software engineer should be able to understand what the component does and why it exists.

## Data and ethics

ZedThema is designed for sensitive research material. Researchers remain responsible for:

- informed consent;
- lawful processing;
- participant anonymisation/pseudonymisation;
- access control;
- secure backups;
- retention periods;
- institutional ethics requirements;
- permissions for downloaded or externally hosted material.

Do not upload confidential interview data to a public URL simply to make it available to ZedThema. Use the local path or upload workflow instead.
