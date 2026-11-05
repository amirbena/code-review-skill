"""Minimal in-memory GitHub PR for publication tests (#844).

Models only what GitHub itself enforces on review submission: permission,
the author's inability to approve or request changes on their own PR, inline
anchors that must lie on changed lines, and atomic submission. It holds no
Skill policy.
"""

from __future__ import annotations

from dataclasses import dataclass, field


class Forbidden(Exception):
    pass


class UnprocessableAnchor(Exception):
    pass


@dataclass
class FakePr:
    author: str = "alice"
    viewer: str = "reviewer"
    head_sha: str = "a" * 40
    can_review: bool = True
    changed: dict[str, set[int]] = field(default_factory=lambda: {"src/a.py": {10, 11}})
    reviews: list[dict] = field(default_factory=list)
    writes: int = 0

    def get_head(self) -> str:
        return self.head_sha

    def submit_review(self, *, event: str, body: str, comments: list[dict], commit_id: str) -> dict:
        if not self.can_review:
            raise Forbidden("viewer cannot submit reviews")
        if event != "COMMENT" and self.viewer == self.author:
            raise Forbidden("cannot approve or request changes on your own pull request")
        for c in comments:
            if c["line"] not in self.changed.get(c["path"], ()):
                raise UnprocessableAnchor(f"{c['path']}:{c['line']} is not in the diff")
        review = {"event": event, "body": body, "comments": list(comments), "commit_id": commit_id}
        self.reviews.append(review)
        self.writes += 1
        return review
