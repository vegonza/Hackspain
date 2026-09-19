from difflib import SequenceMatcher
from typing import Literal

from pydantic import BaseModel


class DiffSpan(BaseModel):
    text: str
    changed: bool


class DiffLine(BaseModel):
    kind: Literal["equal", "removed", "added"]
    text: str
    before: int | None
    after: int | None
    spans: list[DiffSpan]


def split_spans(spans: list[DiffSpan]) -> list[list[DiffSpan]]:
    lines: list[list[DiffSpan]] = [[]]
    for span in spans:
        for index, text in enumerate(span.text.split("\n")):
            if index:
                lines.append([])
            if text:
                lines[-1].append(DiffSpan(text=text, changed=span.changed))
    return lines


def inline_diff(before: list[str], after: list[str]) -> tuple[list[list[DiffSpan]], list[list[DiffSpan]]]:
    """Compare replacement blocks together so inserted lines do not shift line pairs."""
    original, merged = "\n".join(before), "\n".join(after)
    removed: list[DiffSpan] = []
    added: list[DiffSpan] = []
    for operation, start, end, new_start, new_end in SequenceMatcher(None, original, merged, autojunk=False).get_opcodes():
        if start != end:
            removed.append(DiffSpan(text=original[start:end], changed=operation != "equal"))
        if new_start != new_end:
            added.append(DiffSpan(text=merged[new_start:new_end], changed=operation != "equal"))
    return split_spans(removed), split_spans(added)


def markdown_diff(before: str, after: str) -> list[DiffLine]:
    """Compare Markdown source lines and highlight changed characters in replacements."""
    original, merged = before.splitlines(), after.splitlines()
    lines: list[DiffLine] = []
    for operation, start, end, new_start, new_end in SequenceMatcher(None, original, merged, autojunk=False).get_opcodes():
        if operation == "equal":
            lines.extend(DiffLine(kind="equal", text=original[i], before=i + 1, after=new_start + i - start + 1,
                                  spans=[DiffSpan(text=original[i], changed=False)]) for i in range(start, end))
        elif operation == "replace":
            removed, added = inline_diff(original[start:end], merged[new_start:new_end])
            lines.extend(DiffLine(kind="removed", text=original[i], before=i + 1, after=None,
                                  spans=removed[i - start]) for i in range(start, end))
            lines.extend(DiffLine(kind="added", text=merged[i], before=None, after=i + 1,
                                  spans=added[i - new_start]) for i in range(new_start, new_end))
        else:
            lines.extend(DiffLine(kind="removed", text=original[i], before=i + 1, after=None,
                                  spans=[DiffSpan(text=original[i], changed=True)]) for i in range(start, end))
            lines.extend(DiffLine(kind="added", text=merged[i], before=None, after=i + 1,
                                  spans=[DiffSpan(text=merged[i], changed=True)]) for i in range(new_start, new_end))
    return lines
