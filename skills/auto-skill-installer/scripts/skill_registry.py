#!/usr/bin/env python3
"""Search and install AI agent skills from local folders and GitHub registries."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


DEFAULT_TIMEOUT = 20
USER_AGENT = "auto-skill-installer"
ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class SourceSpec:
    name: str
    repo: str
    path: str
    ref: str = "main"
    tags: tuple[str, ...] = ()


@dataclass
class SkillCandidate:
    name: str
    description: str
    location: str
    source_name: str
    installed: bool
    score: int = 0
    repo: str | None = None
    ref: str | None = None
    repo_path: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "description": self.description,
            "location": self.location,
            "source_name": self.source_name,
            "installed": self.installed,
            "score": self.score,
            "repo": self.repo,
            "ref": self.ref,
            "repo_path": self.repo_path,
            "tags": list(self.tags),
        }


class RegistryError(RuntimeError):
    """Raised for recoverable registry failures."""


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()


def skills_root() -> Path:
    return codex_home() / "skills"


def user_sources_path() -> Path:
    return codex_home() / "auto-skill-installer" / "sources.json"


def local_skill_roots() -> list[Path]:
    home = Path.home()
    return [
        skills_root(),
        codex_home() / "skills" / ".system",
        home / ".agents" / "skills",
    ]


def built_in_sources_path() -> Path:
    return ROOT / "assets" / "registry-sources.json"


def read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_sources() -> list[SourceSpec]:
    raw_sources: list[dict[str, object]] = []
    for path in (built_in_sources_path(), user_sources_path()):
        payload = read_json(path)
        raw_sources.extend(payload.get("sources", []))

    sources: list[SourceSpec] = []
    seen: set[tuple[str, str, str, str]] = set()
    for entry in raw_sources:
        name = str(entry["name"]).strip()
        repo = str(entry["repo"]).strip()
        repo_path = str(entry["path"]).strip().strip("/")
        ref = str(entry.get("ref", "main")).strip()
        tags = tuple(str(tag).strip() for tag in entry.get("tags", []))
        key = (name, repo, repo_path, ref)
        if key in seen:
            continue
        seen.add(key)
        sources.append(SourceSpec(name=name, repo=repo, path=repo_path, ref=ref, tags=tags))
    return sources


def save_user_sources(sources: Iterable[SourceSpec]) -> Path:
    path = user_sources_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "sources": [
            {
                "name": source.name,
                "repo": source.repo,
                "path": source.path,
                "ref": source.ref,
                "tags": list(source.tags),
            }
            for source in sources
        ]
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def github_request(url: str) -> bytes:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": USER_AGENT,
    }
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=DEFAULT_TIMEOUT) as response:
        return response.read()


def github_contents_url(repo: str, path: str, ref: str) -> str:
    encoded_path = urllib.parse.quote(path)
    return f"https://api.github.com/repos/{repo}/contents/{encoded_path}?ref={urllib.parse.quote(ref)}"


def github_raw_url(repo: str, path: str, ref: str) -> str:
    return f"https://raw.githubusercontent.com/{repo}/{ref}/{path}"


def parse_frontmatter(text: str) -> tuple[str, str]:
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return "", ""
    block = match.group(1)
    name_match = re.search(r"^name:\s*(.+)$", block, re.MULTILINE)
    desc_match = re.search(r"^description:\s*(.+)$", block, re.MULTILINE)
    name = name_match.group(1).strip().strip("\"'") if name_match else ""
    description = desc_match.group(1).strip().strip("\"'") if desc_match else ""
    return name, description


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def score_candidate(candidate: SkillCandidate, need: str) -> int:
    query_tokens = tokenize(need)
    if not query_tokens:
        return 0

    haystack = " ".join(
        [
            candidate.name,
            candidate.description,
            candidate.source_name,
            " ".join(candidate.tags),
        ]
    ).lower()
    score = 0
    for token in query_tokens:
        if token in candidate.name.lower():
            score += 6
        if token in candidate.description.lower():
            score += 4
        if token in haystack:
            score += 2
    if need.lower() in candidate.description.lower():
        score += 10
    if candidate.installed:
        score += 3
    if "official" in candidate.tags:
        score += 1
    return score


def _iter_skill_dirs(root: Path) -> Iterable[Path]:
    if not root.exists():
        return []
    return [path for path in root.iterdir() if path.is_dir() and (path / "SKILL.md").exists()]


def local_candidates() -> list[SkillCandidate]:
    candidates: list[SkillCandidate] = []
    for root in local_skill_roots():
        for skill_dir in _iter_skill_dirs(root):
            text = (skill_dir / "SKILL.md").read_text(encoding="utf-8", errors="ignore")
            name, description = parse_frontmatter(text)
            candidate = SkillCandidate(
                name=name or skill_dir.name,
                description=description,
                location=str(skill_dir),
                source_name=f"local:{root.name}",
                installed=True,
            )
            candidates.append(candidate)
    return candidates


def remote_candidates(source: SourceSpec) -> list[SkillCandidate]:
    try:
        listing = json.loads(github_request(github_contents_url(source.repo, source.path, source.ref)).decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RegistryError(f"{source.name}: HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RegistryError(f"{source.name}: {exc.reason}") from exc

    if not isinstance(listing, list):
        raise RegistryError(f"{source.name}: unexpected listing response")

    candidates: list[SkillCandidate] = []
    for item in listing:
        if item.get("type") != "dir":
            continue
        skill_name = str(item["name"])
        skill_path = f"{source.path}/{skill_name}/SKILL.md"
        try:
            raw = github_request(github_raw_url(source.repo, skill_path, source.ref)).decode("utf-8")
        except (urllib.error.HTTPError, urllib.error.URLError):
            continue
        name, description = parse_frontmatter(raw)
        candidates.append(
            SkillCandidate(
                name=name or skill_name,
                description=description,
                location=f"https://github.com/{source.repo}/tree/{source.ref}/{source.path}/{skill_name}",
                source_name=source.name,
                installed=(skills_root() / skill_name).exists(),
                repo=source.repo,
                ref=source.ref,
                repo_path=f"{source.path}/{skill_name}",
                tags=source.tags,
            )
        )
    return candidates


def search(need: str, limit: int = 8) -> tuple[list[SkillCandidate], list[str]]:
    candidates = local_candidates()
    warnings: list[str] = []
    for source in load_sources():
        try:
            candidates.extend(remote_candidates(source))
        except RegistryError as exc:
            warnings.append(str(exc))

    deduped: dict[str, SkillCandidate] = {}
    for candidate in candidates:
        candidate.score = score_candidate(candidate, need)
        existing = deduped.get(candidate.name)
        if existing is None or candidate.score > existing.score or (candidate.installed and not existing.installed):
            deduped[candidate.name] = candidate

    ranked = sorted(
        (candidate for candidate in deduped.values() if candidate.score > 0),
        key=lambda item: (-item.score, not item.installed, item.name),
    )
    return ranked[:limit], warnings


def _safe_extract_zip(zip_file: zipfile.ZipFile, dest_dir: Path) -> None:
    dest_root = dest_dir.resolve()
    for info in zip_file.infolist():
        target = (dest_dir / info.filename).resolve()
        if target == dest_root or str(target).startswith(str(dest_root) + os.sep):
            continue
        raise RegistryError("archive contains files outside the destination")
    zip_file.extractall(dest_dir)


def install_candidate(candidate: SkillCandidate, dest_root: Path | None = None) -> Path:
    local_path = Path(candidate.location)
    if candidate.installed and local_path.exists():
        return local_path
    if not candidate.repo or not candidate.repo_path or not candidate.ref:
        raise RegistryError("candidate does not include a remote install source")

    destination_root = dest_root or skills_root()
    destination_root.mkdir(parents=True, exist_ok=True)
    destination = destination_root / candidate.name
    if destination.exists():
        raise RegistryError(f"destination already exists: {destination}")

    tmp_dir = Path(tempfile.mkdtemp(prefix="auto-skill-", dir=tempfile.gettempdir()))
    try:
        zip_url = f"https://codeload.github.com/{candidate.repo}/zip/{candidate.ref}"
        archive_path = tmp_dir / "repo.zip"
        try:
            archive_path.write_bytes(github_request(zip_url))
        except urllib.error.URLError as exc:
            raise RegistryError(f"download failed: {exc.reason}") from exc
        with zipfile.ZipFile(archive_path, "r") as zip_file:
            _safe_extract_zip(zip_file, tmp_dir)
            top_levels = {name.split("/")[0] for name in zip_file.namelist() if name}
        if len(top_levels) != 1:
            raise RegistryError("unexpected archive layout")
        repo_root = tmp_dir / next(iter(top_levels))
        source_dir = repo_root / candidate.repo_path
        skill_md = source_dir / "SKILL.md"
        if not skill_md.exists():
            raise RegistryError("selected directory does not contain SKILL.md")
        shutil.copytree(source_dir, destination)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return destination
