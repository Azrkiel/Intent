import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..planning.contracts import PlanApproval

MAX_NOTE_BYTES = 100_000
MAX_VAULT_BYTES = 2_000_000
MAX_NOTES = 500
Kind = Literal["plan", "phase", "package", "task", "spec", "screen", "note"]


def note_path(path: str) -> str:
    parts = path.split("/")
    if (
        len(path) > 240
        or not path.lower().endswith(".md")
        or any(
            not part
            or part.startswith(".")
            or part.endswith((" ", "."))
            or re.search(r'[<>:"\\|?*\x00-\x1f\x7f]', part)
            or re.fullmatch(r"(?:CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])(?:\..*)?", part, re.I)
            for part in parts
        )
    ):
        raise ValueError("Use a relative Markdown path without hidden or special names")
    return path


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Note(StrictModel):
    id: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    path: str
    body: str = Field(max_length=MAX_NOTE_BYTES)
    kind: Kind = "note"

    @field_validator("path")
    @classmethod
    def valid_path(cls, value):
        return note_path(value)

    @field_validator("body")
    @classmethod
    def bounded_body(cls, value):
        if len(value.encode("utf-8")) > MAX_NOTE_BYTES:
            raise ValueError("A note is limited to 100 KB of UTF-8 text")
        return value


class NoteSet(StrictModel):
    notes: list[Note] = Field(min_length=1, max_length=MAX_NOTES)

    @model_validator(mode="after")
    def validate_notes(self):
        roots = [n for n in self.notes if n.id == "plan"]
        if len(roots) != 1 or roots[0].kind != "plan":
            raise ValueError("Keep one main plan note")
        if any(n.kind == "plan" and n.id != "plan" for n in self.notes):
            raise ValueError("Only the root note can have plan kind")
        if len({n.id for n in self.notes}) != len(self.notes):
            raise ValueError("Duplicate note IDs")
        if len({n.path.casefold() for n in self.notes}) != len(self.notes):
            raise ValueError("Note paths must be unique, ignoring case")
        if sum(len(n.body.encode("utf-8")) for n in self.notes) > MAX_VAULT_BYTES:
            raise ValueError("A vault is limited to 2 MB of Markdown")
        return self


class Vault(NoteSet):
    revision: int = Field(ge=0)
    source: PlanApproval | None = None
    source_status: Literal["draft", "validated"] | None = None
    demo: bool = False


class SaveRequest(NoteSet):
    expected_revision: int = Field(ge=0)


class RevisionRequest(StrictModel):
    expected_revision: int = Field(ge=0)
