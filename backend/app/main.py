"""ZedThema API.

Readable API layer for the ZedThema research platform.

The API:
- validates incoming requests with Pydantic
- keeps research data local
- encrypts sensitive research text at rest
- returns decrypted research content to the authorised researcher
- records important research actions in the audit trail
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .coder import code_segments, dual_code
from .config import (
    AUTH_ENABLED,
    DATA_DIR,
    OLLAMA_MODEL,
    OLLAMA_URL,
    WHISPER_MODEL,
)
from .db import audit, conn, now, rows, init_db
from .diarize import attach_speakers, diarize
from .exports import export_all
from .ingest import copy_local, download_url, extract_text, save_upload, type_for
from .languages import LANGUAGES
from .models import (
    AnomalyIn,
    CodeIn,
    CodeUpdate,
    CompareIn,
    DualCodeIn,
    LoginIn,
    MemberIn,
    PathIn,
    ProjectIn,
    RegisterIn,
    ReviewIn,
    SearchIn,
    URLIn,
)
from .search import search
from .security import (
    create_token,
    encrypt,
    password_hash,
    password_verify,
    verify_token,
)
from .stats import compare_codings
from .transcribe import transcribe


app = FastAPI(
    title="ZedThema API",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()


# ============================================================
# Authentication / project helpers
# ============================================================

def _user(authorization: str | None = Header(default=None)):
    """Return the current user.

    Authentication can be disabled for a single-user local
    installation. In that case a local pseudo-user is returned.
    """

    if not AUTH_ENABLED:
        return {
            "sub": "local-researcher",
            "email": "local@localhost",
            "role": "owner",
        }

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Authentication required")

    try:
        return verify_token(authorization.split(" ", 1)[1])
    except ValueError as exc:
        raise HTTPException(401, str(exc)) from exc


def _project_access(pid: str, user: dict, write: bool = False):
    """Check whether the current user can access a project."""

    if not rows("SELECT id FROM projects WHERE id=?", (pid,)):
        raise HTTPException(404, "Project not found")

    if not AUTH_ENABLED:
        return

    uid = user["sub"]

    membership = rows(
        """
        SELECT role
        FROM project_members
        WHERE project_id=? AND user_id=?
        """,
        (pid, uid),
    )

    if not membership:
        raise HTTPException(
            403,
            "You are not a member of this project",
        )

    if write and membership[0]["role"] not in {
        "owner",
        "manager",
        "researcher",
    }:
        raise HTTPException(
            403,
            "You do not have permission to edit this project",
        )


# ============================================================
# Project helper
# ============================================================

def _project(pid: str):
    """Return a complete project representation."""

    p = rows(
        "SELECT * FROM projects WHERE id=?",
        (pid,),
    )

    if not p:
        raise HTTPException(404, "Project not found")

    p = p[0]

    p["codes"] = rows(
        """
        SELECT *
        FROM codes
        WHERE project_id=?
        ORDER BY name
        """,
        (pid,),
    )

    p["sources"] = rows(
        """
        SELECT
            id,
            project_id,
            name,
            source_type,
            language,
            created_at
        FROM sources
        WHERE project_id=?
        ORDER BY created_at DESC
        """,
        (pid,),
    )

    p["anomalies"] = rows(
        """
        SELECT *
        FROM anomalies
        WHERE project_id=?
        ORDER BY created_at DESC
        """,
        (pid,),
    )

    return p


# ============================================================
# Codebook helpers
# ============================================================

def _get_code(pid: str, cid: str):
    """Return a code belonging to the specified project."""

    result = rows(
        """
        SELECT *
        FROM codes
        WHERE id=? AND project_id=?
        """,
        (cid, pid),
    )

    if not result:
        raise HTTPException(404, "Code not found")

    return result[0]


def _check_parent(pid: str, parent_id: str | None):
    """Validate that a parent belongs to the same project."""

    if parent_id is None:
        return

    parent = rows(
        """
        SELECT id
        FROM codes
        WHERE id=? AND project_id=?
        """,
        (parent_id, pid),
    )

    if not parent:
        raise HTTPException(
            400,
            "Parent code does not belong to this project",
        )


def _check_duplicate_sibling(
    pid: str,
    name: str,
    parent_id: str | None,
    exclude_id: str | None = None,
):
    """Prevent duplicate code names at the same hierarchy level.

    Duplicate names are allowed under different parents.

    Example:

        Performance Expectancy
            └── Convenience

        Effort Expectancy
            └── Convenience

    is valid.

    But two 'Convenience' codes under the same parent are rejected.
    """

    if parent_id is None:
        query = """
            SELECT id
            FROM codes
            WHERE project_id=?
              AND parent_id IS NULL
              AND lower(trim(name))=lower(trim(?))
        """
        args = (pid, name)
    else:
        query = """
            SELECT id
            FROM codes
            WHERE project_id=?
              AND parent_id=?
              AND lower(trim(name))=lower(trim(?))
        """
        args = (pid, parent_id, name)

    matches = rows(query, args)

    if exclude_id:
        matches = [
            item
            for item in matches
            if item["id"] != exclude_id
        ]

    if matches:
        raise HTTPException(
            409,
            f"A code named '{name}' already exists at this hierarchy level.",
        )


def _check_no_circular_parent(
    pid: str,
    cid: str,
    proposed_parent_id: str | None,
):
    """Prevent circular code hierarchies."""

    if not proposed_parent_id:
        return

    if proposed_parent_id == cid:
        raise HTTPException(
            400,
            "A code cannot be its own parent",
        )

    seen = {cid}
    current = proposed_parent_id

    while current:
        if current in seen:
            raise HTTPException(
                400,
                "That parent would create a circular code hierarchy",
            )

        seen.add(current)

        parent = rows(
            """
            SELECT parent_id
            FROM codes
            WHERE id=? AND project_id=?
            """,
            (current, pid),
        )

        if not parent:
            raise HTTPException(
                400,
                "Parent code does not belong to this project",
            )

        current = parent[0].get("parent_id")


def _build_code_tree(pid: str):
    """Return the complete hierarchical codebook.

    db.rows() automatically decrypts encrypted research metadata.
    Therefore the API does not need to call decrypt() directly.
    """

    codes = rows(
        """
        SELECT *
        FROM codes
        WHERE project_id=?
        ORDER BY lower(name)
        """,
        (pid,),
    )

    by_parent: dict[str | None, list] = {None: []}

    for code in codes:
        by_parent.setdefault(
            code.get("parent_id"),
            [],
        ).append(code)

    def build(parent_id: str | None):
        result = []

        for code in by_parent.get(parent_id, []):
            item = dict(code)

            item["children"] = build(code["id"])

            result.append(item)

        return result

    return build(None)


# ============================================================
# Health / configuration
# ============================================================

@app.get("/api/health")
def health():
    try:
        response = httpx.get(
            f"{OLLAMA_URL}/api/tags",
            timeout=5,
        )
        ollama = response.status_code == 200
    except Exception:
        ollama = False

    return {
        "ok": True,
        "ollama": ollama,
        "model": OLLAMA_MODEL,
        "whisper_model": WHISPER_MODEL,
        "auth_enabled": AUTH_ENABLED,
    }


@app.get("/api/models")
def models():
    try:
        return httpx.get(
            f"{OLLAMA_URL}/api/tags",
            timeout=10,
        ).json()
    except Exception as exc:
        return {
            "models": [],
            "error": str(exc),
        }


@app.get("/api/languages")
def languages():
    return LANGUAGES


# ============================================================
# Authentication
# ============================================================

@app.post("/api/auth/register")
def register(x: RegisterIn):
    if not AUTH_ENABLED:
        raise HTTPException(
            400,
            "Authentication is disabled in this local installation",
        )

    email = x.email.strip().lower()
    uid = uuid.uuid4().hex[:16]

    c = conn()

    try:
        c.execute(
            "INSERT INTO users VALUES(?,?,?,?,?,?)",
            (
                uid,
                email,
                password_hash(x.password),
                x.display_name,
                "researcher",
                now(),
            ),
        )
        c.commit()
    except Exception as exc:
        c.close()
        raise HTTPException(
            409,
            "That email is already registered",
        ) from exc

    c.close()

    return {
        "token": create_token(
            uid,
            email,
            "researcher",
        ),
        "user": {
            "id": uid,
            "email": email,
            "display_name": x.display_name,
            "role": "researcher",
        },
    }


@app.post("/api/auth/login")
def login(x: LoginIn):
    if not AUTH_ENABLED:
        raise HTTPException(
            400,
            "Authentication is disabled in this local installation",
        )

    u = rows(
        "SELECT * FROM users WHERE email=?",
        (x.email.strip().lower(),),
    )

    if not u or not password_verify(
        x.password,
        u[0]["password_hash"],
    ):
        raise HTTPException(
            401,
            "Invalid email or password",
        )

    user = u[0]

    return {
        "token": create_token(
            user["id"],
            user["email"],
            user["role"],
        ),
        "user": {
            "id": user["id"],
            "email": user["email"],
            "display_name": user["display_name"],
            "role": user["role"],
        },
    }


@app.get("/api/me")
def me(user=Depends(_user)):
    return user


# ============================================================
# Projects
# ============================================================

@app.post("/api/projects")
def create_project(
    p: ProjectIn,
    user=Depends(_user),
):
    pid = uuid.uuid4().hex[:12]
    t = now()

    c = conn()

    c.execute(
        "INSERT INTO projects VALUES(?,?,?,?,?,?,?,?,?,?)",
        (
            pid,
            p.title,
            encrypt(p.description),
            encrypt(p.research_question),
            encrypt(p.framework),
            encrypt(p.method),
            json.dumps(p.languages),
            t,
            t,
            user["sub"],
        ),
    )

    if AUTH_ENABLED:
        c.execute(
            """
            INSERT INTO project_members
            VALUES(?,?,?,?)
            """,
            (
                pid,
                user["sub"],
                "owner",
                t,
            ),
        )

    c.commit()
    c.close()

    audit(
        pid,
        "project_created",
        p.model_dump(),
        user["sub"],
    )

    return {"id": pid}


@app.get("/api/projects")
def projects(user=Depends(_user)):
    if not AUTH_ENABLED:
        return rows(
            """
            SELECT *
            FROM projects
            ORDER BY updated_at DESC
            """
        )

    return rows(
        """
        SELECT p.*
        FROM projects p
        JOIN project_members m
            ON m.project_id=p.id
        WHERE m.user_id=?
        ORDER BY p.updated_at DESC
        """,
        (user["sub"],),
    )


@app.get("/api/projects/{pid}")
def project(
    pid: str,
    user=Depends(_user),
):
    _project_access(pid, user)
    return _project(pid)


# ============================================================
# Project members
# ============================================================

@app.post("/api/projects/{pid}/members")
def add_member(
    pid: str,
    x: MemberIn,
    user=Depends(_user),
):
    _project_access(pid, user, write=True)

    if not AUTH_ENABLED:
        raise HTTPException(
            400,
            "Enable authentication to use multi-researcher collaboration",
        )

    owner = rows(
        """
        SELECT role
        FROM project_members
        WHERE project_id=? AND user_id=?
        """,
        (pid, user["sub"]),
    )

    if not owner or owner[0]["role"] not in {
        "owner",
        "manager",
    }:
        raise HTTPException(
            403,
            "Only an owner or manager can add researchers",
        )

    target = rows(
        "SELECT id FROM users WHERE email=?",
        (x.email.strip().lower(),),
    )

    if not target:
        raise HTTPException(
            404,
            "Researcher must register before being added",
        )

    c = conn()

    c.execute(
        """
        INSERT OR REPLACE INTO project_members
        VALUES(?,?,?,?)
        """,
        (
            pid,
            target[0]["id"],
            x.role,
            now(),
        ),
    )

    c.commit()
    c.close()

    audit(
        pid,
        "member_added",
        {
            "email": x.email,
            "role": x.role,
        },
        user["sub"],
    )

    return {"ok": True}


@app.get("/api/projects/{pid}/members")
def members(
    pid: str,
    user=Depends(_user),
):
    _project_access(pid, user)

    return rows(
        """
        SELECT
            u.id,
            u.email,
            u.display_name,
            m.role,
            m.created_at
        FROM project_members m
        JOIN users u
            ON u.id=m.user_id
        WHERE m.project_id=?
        """,
        (pid,),
    )


# ============================================================
# CODEBOOK
# ============================================================

@app.post("/api/projects/{pid}/codes")
def add_code(
    pid: str,
    c: CodeIn,
    user=Depends(_user),
):
    """Create a code and return the complete code object."""

    _project_access(
        pid,
        user,
        write=True,
    )

    _check_parent(
        pid,
        c.parent_id,
    )

    _check_duplicate_sibling(
        pid,
        c.name,
        c.parent_id,
    )

    cid = uuid.uuid4().hex[:12]

    db = conn()

    try:
        db.execute(
            """
            INSERT INTO codes
            VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                cid,
                pid,
                c.name,
                encrypt(c.definition),
                encrypt(c.inclusion),
                encrypt(c.exclusion),
                encrypt(c.example),
                c.parent_id,
                encrypt(c.theory),
                c.color,
                now(),
            ),
        )

        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()

    audit(
        pid,
        "code_created",
        c.model_dump(),
        user["sub"],
    )

    # IMPORTANT:
    # Re-read through db.rows() so encrypted fields are decoded
    # consistently before returning them to the frontend.
    return _get_code(
        pid,
        cid,
    )


@app.patch("/api/projects/{pid}/codes/{cid}")
def update_code(
    pid: str,
    cid: str,
    c: CodeUpdate,
    user=Depends(_user),
):
    """Update a code and return the complete updated code object."""

    _project_access(
        pid,
        user,
        write=True,
    )

    existing = _get_code(
        pid,
        cid,
    )

    values = c.model_dump(
        exclude_unset=True,
    )

    if not values:
        return existing

    proposed_parent = values.get(
        "parent_id",
        existing.get("parent_id"),
    )

    proposed_name = values.get(
        "name",
        existing.get("name"),
    )

    _check_parent(
        pid,
        proposed_parent,
    )

    _check_no_circular_parent(
        pid,
        cid,
        proposed_parent,
    )

    _check_duplicate_sibling(
        pid,
        proposed_name,
        proposed_parent,
        exclude_id=cid,
    )

    encrypted_fields = {
        "definition",
        "inclusion",
        "exclusion",
        "example",
        "theory",
    }

    values = {
        key: (
            encrypt(value)
            if key in encrypted_fields
            and value is not None
            else value
        )
        for key, value in values.items()
    }

    sql = ", ".join(
        f"{key}=?"
        for key in values
    )

    db = conn()

    try:
        db.execute(
            f"""
            UPDATE codes
            SET {sql}
            WHERE id=? AND project_id=?
            """,
            (
                *values.values(),
                cid,
                pid,
            ),
        )

        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()

    audit(
        pid,
        "code_updated",
        {
            "code_id": cid,
            "changes": list(values),
        },
        user["sub"],
    )

    return _get_code(
        pid,
        cid,
    )


@app.delete("/api/projects/{pid}/codes/{cid}")
def delete_code(
    pid: str,
    cid: str,
    user=Depends(_user),
):
    """Delete a leaf code.

    Parent codes with children must be moved or deleted first.
    """

    _project_access(
        pid,
        user,
        write=True,
    )

    _get_code(
        pid,
        cid,
    )

    children = rows(
        """
        SELECT id
        FROM codes
        WHERE parent_id=? AND project_id=?
        """,
        (cid, pid),
    )

    if children:
        raise HTTPException(
            409,
            "Move or delete child codes before deleting this parent",
        )

    db = conn()

    db.execute(
        """
        DELETE FROM codes
        WHERE id=? AND project_id=?
        """,
        (cid, pid),
    )

    db.commit()
    db.close()

    audit(
        pid,
        "code_deleted",
        {"code_id": cid},
        user["sub"],
    )

    return {"ok": True}


@app.get("/api/projects/{pid}/code-tree")
def code_tree(
    pid: str,
    user=Depends(_user),
):
    """Return the complete hierarchical codebook."""

    _project_access(
        pid,
        user,
    )

    return _build_code_tree(pid)


# ============================================================
# Sources
# ============================================================

@app.post("/api/projects/{pid}/sources/upload")
async def upload(
    pid: str,
    file: UploadFile = File(...),
    language: str = "auto",
    user=Depends(_user),
):
    _project_access(
        pid,
        user,
        write=True,
    )

    try:
        path = save_upload(
            pid,
            file.filename,
            file.file,
        )
    except Exception as exc:
        raise HTTPException(
            400,
            str(exc),
        ) from exc

    sid = uuid.uuid4().hex[:12]
    text = extract_text(path)

    transcript = None

    if text:
        transcript = encrypt(
            json.dumps(
                {
                    "segments": [
                        {
                            "id": "seg_0001",
                            "start": 0,
                            "end": 0,
                            "text": text,
                        }
                    ]
                },
                ensure_ascii=False,
            )
        )

    db = conn()

    db.execute(
        """
        INSERT INTO sources
        VALUES(?,?,?,?,?,?,?,?)
        """,
        (
            sid,
            pid,
            path.name,
            str(path),
            type_for(path),
            language,
            transcript,
            now(),
        ),
    )

    db.commit()
    db.close()

    audit(
        pid,
        "source_uploaded",
        {"source": path.name},
        user["sub"],
    )

    return {
        "id": sid,
        "name": path.name,
        "type": type_for(path),
        "has_text": bool(text),
    }


@app.post("/api/projects/{pid}/source-url")
async def url_source(
    pid: str,
    x: URLIn,
    user=Depends(_user),
):
    _project_access(
        pid,
        user,
        write=True,
    )

    try:
        path = await download_url(
            pid,
            x.url,
        )
    except Exception as exc:
        raise HTTPException(
            400,
            str(exc),
        ) from exc

    sid = uuid.uuid4().hex[:12]
    text = extract_text(path)

    transcript = None

    if text:
        transcript = encrypt(
            json.dumps(
                {
                    "segments": [
                        {
                            "id": "seg_0001",
                            "start": 0,
                            "end": 0,
                            "text": text,
                        }
                    ]
                },
                ensure_ascii=False,
            )
        )

    db = conn()

    db.execute(
        """
        INSERT INTO sources
        VALUES(?,?,?,?,?,?,?,?)
        """,
        (
            sid,
            pid,
            path.name,
            str(path),
            "url",
            x.language,
            transcript,
            now(),
        ),
    )

    db.commit()
    db.close()

    audit(
        pid,
        "source_url_imported",
        {
            "url": x.url,
            "file": path.name,
        },
        user["sub"],
    )

    return {
        "id": sid,
        "name": path.name,
    }


@app.post("/api/projects/{pid}/source-path")
def path_source(
    pid: str,
    x: PathIn,
    user=Depends(_user),
):
    _project_access(
        pid,
        user,
        write=True,
    )

    try:
        path = copy_local(
            pid,
            x.path,
        )
    except Exception as exc:
        raise HTTPException(
            400,
            str(exc),
        ) from exc

    sid = uuid.uuid4().hex[:12]
    text = extract_text(path)

    transcript = None

    if text:
        transcript = encrypt(
            json.dumps(
                {
                    "segments": [
                        {
                            "id": "seg_0001",
                            "start": 0,
                            "end": 0,
                            "text": text,
                        }
                    ]
                },
                ensure_ascii=False,
            )
        )

    db = conn()

    db.execute(
        """
        INSERT INTO sources
        VALUES(?,?,?,?,?,?,?,?)
        """,
        (
            sid,
            pid,
            path.name,
            str(path),
            "local_path",
            x.language,
            transcript,
            now(),
        ),
    )

    db.commit()
    db.close()

    audit(
        pid,
        "source_path_imported",
        {"path": x.path},
        user["sub"],
    )

    return {
        "id": sid,
        "name": path.name,
    }


# ============================================================
# Transcription
# ============================================================

@app.post("/api/projects/{pid}/sources/{sid}/transcribe")
def do_transcribe(
    pid: str,
    sid: str,
    language: str = "auto",
    model: str = WHISPER_MODEL,
    user=Depends(_user),
):
    _project_access(
        pid,
        user,
        write=True,
    )

    s = rows(
        """
        SELECT *
        FROM sources
        WHERE id=? AND project_id=?
        """,
        (sid, pid),
    )

    if not s:
        raise HTTPException(
            404,
            "Source not found",
        )

    try:
        result = transcribe(
            s[0]["path"],
            model,
            language or s[0]["language"],
        )
    except Exception as exc:
        raise HTTPException(
            500,
            str(exc),
        ) from exc

    db = conn()

    db.execute(
        """
        UPDATE sources
        SET transcript=?, language=?
        WHERE id=?
        """,
        (
            encrypt(
                json.dumps(
                    result,
                    ensure_ascii=False,
                )
            ),
            result["language"],
            sid,
        ),
    )

    db.commit()
    db.close()

    audit(
        pid,
        "transcription_completed",
        {
            "source_id": sid,
            "model": model,
            "language": result["language"],
        },
        user["sub"],
    )

    return result


# ============================================================
# Speaker diarization
# ============================================================

@app.post("/api/projects/{pid}/sources/{sid}/diarize")
def do_diarize(
    pid: str,
    sid: str,
    user=Depends(_user),
):
    _project_access(
        pid,
        user,
        write=True,
    )

    s = rows(
        """
        SELECT *
        FROM sources
        WHERE id=? AND project_id=?
        """,
        (sid, pid),
    )

    if not s:
        raise HTTPException(
            404,
            "Source not found",
        )

    if not s[0].get("transcript"):
        raise HTTPException(
            400,
            "Transcribe the source before diarization",
        )

    try:
        d = diarize(
            s[0]["path"],
        )

        t = json.loads(
            s[0]["transcript"],
        )

        attach_speakers(
            t,
            d["turns"],
        )

    except Exception as exc:
        raise HTTPException(
            501,
            str(exc),
        ) from exc

    db = conn()

    db.execute(
        """
        UPDATE sources
        SET transcript=?
        WHERE id=?
        """,
        (
            encrypt(
                json.dumps(
                    t,
                    ensure_ascii=False,
                )
            ),
            sid,
        ),
    )

    db.commit()
    db.close()

    audit(
        pid,
        "speaker_diarization_completed",
        {
            "source_id": sid,
            "model": d["model"],
        },
        user["sub"],
    )

    return t


# ============================================================
# Source retrieval
# ============================================================

@app.get("/api/projects/{pid}/sources/{sid}")
def source(
    pid: str,
    sid: str,
    user=Depends(_user),
):
    _project_access(
        pid,
        user,
    )

    s = rows(
        """
        SELECT *
        FROM sources
        WHERE id=? AND project_id=?
        """,
        (sid, pid),
    )

    if not s:
        raise HTTPException(
            404,
            "Source not found",
        )

    return s[0]


@app.get("/api/projects/{pid}/sources/{sid}/segments")
def segments(
    pid: str,
    sid: str,
    user=Depends(_user),
):
    s = source(
        pid,
        sid,
        user,
    )

    t = s.get("transcript")

    if not t:
        return []

    try:
        return json.loads(t).get(
            "segments",
            [],
        )
    except Exception:
        return []


# ============================================================
# AI coding
# ============================================================

@app.post("/api/projects/{pid}/sources/{sid}/code")
def code(
    pid: str,
    sid: str,
    model: str = "",
    user=Depends(_user),
):
    _project_access(
        pid,
        user,
        write=True,
    )

    p = _project(pid)
    s = source(pid, sid, user)
    codes = p["codes"]

    if not codes:
        raise HTTPException(
            400,
            "Add at least one code to the codebook first.",
        )

    if not s.get("transcript"):
        raise HTTPException(
            400,
            "Transcribe or provide text before coding.",
        )

    t = json.loads(
        s["transcript"],
    )

    segments_data = (
        t.get("segments", [])
        if isinstance(t, dict)
        else []
    )

    context = json.dumps(
        {
            k: p[k]
            for k in [
                "title",
                "description",
                "research_question",
                "framework",
                "method",
            ]
        },
        ensure_ascii=False,
    )

    try:
        items, used = code_segments(
            segments_data,
            codes,
            context,
            model or OLLAMA_MODEL,
        )
    except Exception as exc:
        raise HTTPException(
            502,
            str(exc),
        ) from exc

    run_id = uuid.uuid4().hex[:12]

    db = conn()

    db.execute(
        """
        INSERT INTO coding_runs
        VALUES(?,?,?,?,?,?)
        """,
        (
            run_id,
            pid,
            sid,
            used,
            now(),
            "single",
        ),
    )

    output = []

    for item in items:
        cc = next(
            (
                c
                for c in codes
                if c["name"] == item.get("code_name")
            ),
            None,
        )

        if not cc or not item.get("segment_id"):
            continue

        seg = next(
            (
                z
                for z in segments_data
                if z.get("id") == item.get("segment_id")
            ),
            {},
        )

        quote = item.get(
            "quote",
            "",
        )

        if quote and quote not in seg.get(
            "text",
            "",
        ):
            continue

        coding = {
            "id": uuid.uuid4().hex[:12],
            "project_id": pid,
            "source_id": sid,
            "segment_id": item.get("segment_id"),
            "quote": quote,
            "code_id": cc["id"],
            "code_name": cc["name"],
            "confidence": float(
                item.get("confidence", 0)
            ),
            "rationale": item.get(
                "rationale",
                "",
            ),
            "status": "ai_suggested",
            "model": used,
            "created_at": now(),
            "reviewed_at": None,
            "reviewer_id": None,
            "run_id": run_id,
            "start": seg.get("start"),
            "end": seg.get("end"),
            "speaker": seg.get("speaker"),
        }

        db.execute(
            """
            INSERT INTO codings
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            tuple(coding.values()),
        )

        coding["source_name"] = s["name"]

        output.append(coding)

    db.commit()
    db.close()

    audit(
        pid,
        "ai_coding_completed",
        {
            "source_id": sid,
            "model": used,
            "count": len(output),
            "run_id": run_id,
        },
        user["sub"],
    )

    return {
        "codings": output,
        "model": used,
        "run_id": run_id,
    }


# ============================================================
# Dual-model coding
# ============================================================

@app.post("/api/projects/{pid}/sources/{sid}/dual-code")
def dual(
    pid: str,
    sid: str,
    x: DualCodeIn,
    user=Depends(_user),
):
    _project_access(
        pid,
        user,
        write=True,
    )

    p = _project(pid)
    s = source(
        pid,
        sid,
        user,
    )

    if not p["codes"]:
        raise HTTPException(
            400,
            "Add a codebook first",
        )

    if not s.get("transcript"):
        raise HTTPException(
            400,
            "Transcribe or import text first",
        )

    t = json.loads(
        s["transcript"],
    )

    segs = t.get(
        "segments",
        [],
    )

    context = json.dumps(
        {
            k: p[k]
            for k in [
                "title",
                "description",
                "research_question",
                "framework",
                "method",
            ]
        },
        ensure_ascii=False,
    )

    try:
        result = dual_code(
            segs,
            p["codes"],
            context,
            x.models,
        )
    except Exception as exc:
        raise HTTPException(
            502,
            str(exc),
        ) from exc

    audit(
        pid,
        "dual_model_coding_completed",
        {
            "source_id": sid,
            "models": x.models,
        },
        user["sub"],
    )

    return result


# ============================================================
# Coding review
# ============================================================

@app.get("/api/projects/{pid}/codings")
def codings(
    pid: str,
    status: str = "",
    user=Depends(_user),
):
    _project_access(
        pid,
        user,
    )

    query = """
        SELECT
            c.*,
            s.name source_name
        FROM codings c
        JOIN sources s
            ON s.id=c.source_id
        WHERE c.project_id=?
    """

    args = [pid]

    if status:
        query += " AND c.status=?"
        args.append(status)

    return rows(
        query,
        args,
    )


@app.patch("/api/codings/{cid}")
def review(
    cid: str,
    r: ReviewIn,
    user=Depends(_user),
):
    x = rows(
        """
        SELECT project_id
        FROM codings
        WHERE id=?
        """,
        (cid,),
    )

    if not x:
        raise HTTPException(
            404,
            "Coding not found",
        )

    pid = x[0]["project_id"]

    _project_access(
        pid,
        user,
        write=True,
    )

    if r.status not in {
        "accepted",
        "rejected",
        "edited",
        "ai_suggested",
    }:
        raise HTTPException(
            400,
            "Invalid coding status",
        )

    db = conn()

    db.execute(
        """
        UPDATE codings
        SET
            status=?,
            code_name=COALESCE(?,code_name),
            confidence=COALESCE(?,confidence),
            rationale=COALESCE(?,rationale),
            reviewed_at=?,
            reviewer_id=?
        WHERE id=?
        """,
        (
            r.status,
            r.code_name,
            r.confidence,
            encrypt(r.rationale)
            if r.rationale is not None
            else None,
            now(),
            user["sub"],
            cid,
        ),
    )

    db.commit()
    db.close()

    audit(
        pid,
        "coding_reviewed",
        {
            "coding_id": cid,
            "status": r.status,
        },
        user["sub"],
    )

    return {"ok": True}


# ============================================================
# Search
# ============================================================

@app.post("/api/projects/{pid}/search")
def corpus_search(
    pid: str,
    x: SearchIn,
    user=Depends(_user),
):
    _project_access(
        pid,
        user,
    )

    result = search(
        pid,
        x.query,
        x.limit,
    )

    audit(
        pid,
        "corpus_search",
        {
            "query": x.query,
            "mode": result.get("mode"),
        },
        user["sub"],
    )

    return result


# ============================================================
# Quantitative anomalies
# ============================================================

@app.post("/api/projects/{pid}/anomalies")
def anomaly(
    pid: str,
    x: AnomalyIn,
    user=Depends(_user),
):
    _project_access(
        pid,
        user,
        write=True,
    )

    aid = uuid.uuid4().hex[:12]

    db = conn()

    db.execute(
        """
        INSERT INTO anomalies
        VALUES(?,?,?,?,?,?,?,?)
        """,
        (
            aid,
            pid,
            x.label,
            encrypt(x.description),
            x.metric,
            x.value,
            encrypt(x.context),
            now(),
        ),
    )

    db.commit()
    db.close()

    audit(
        pid,
        "quantitative_anomaly_added",
        x.model_dump(),
        user["sub"],
    )

    return {"id": aid}


# ============================================================
# Audit
# ============================================================

@app.get("/api/projects/{pid}/audit")
def audits(
    pid: str,
    user=Depends(_user),
):
    _project_access(
        pid,
        user,
    )

    return rows(
        """
        SELECT *
        FROM audit
        WHERE project_id=?
        ORDER BY id DESC
        """,
        (pid,),
    )


# ============================================================
# Export
# ============================================================

@app.post("/api/projects/{pid}/export")
def export(
    pid: str,
    user=Depends(_user),
):
    _project_access(
        pid,
        user,
        write=True,
    )

    p = _project(pid)
    coding_data = codings(
        pid,
        user=user,
    )
    audit_data = audits(
        pid,
        user=user,
    )

    out = export_all(
        DATA_DIR / "projects" / pid,
        p,
        coding_data,
        p["codes"],
        rows(
            """
            SELECT *
            FROM sources
            WHERE project_id=?
            """,
            (pid,),
        ),
        audit_data,
    )

    audit(
        pid,
        "export_created",
        {
            "directory": str(out),
        },
        user["sub"],
    )

    return {
        "directory": str(out),
        "files": [
            x.name
            for x in out.iterdir()
        ],
    }


@app.get("/api/projects/{pid}/export/{filename}")
def download_export(
    pid: str,
    filename: str,
    user=Depends(_user),
):
    _project_access(
        pid,
        user,
    )

    safe = Path(filename).name

    target = (
        DATA_DIR
        / "projects"
        / pid
        / "exports"
        / safe
    ).resolve()

    root = (
        DATA_DIR
        / "projects"
        / pid
        / "exports"
    ).resolve()

    if (
        root not in target.parents
        or not target.exists()
    ):
        raise HTTPException(
            404,
            "Export not found",
        )

    return FileResponse(target)


# ============================================================
# Agreement comparison
# ============================================================

@app.post("/api/compare")
def compare(payload: CompareIn):
    return compare_codings(
        payload.a,
        payload.b,
    )
