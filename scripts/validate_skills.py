#!/usr/bin/env python3
"""Validate every skill in the library.

Checks:
    - Each skills/<name>/SKILL.md has valid YAML frontmatter with required fields.
    - `name` field matches the directory name.
    - `description` is non-empty and at least 40 characters.
    - `version` is valid SemVer.
    - Finding ID prefixes used in example blocks match the registry in CONVENTIONS.md.
    - Example finding blocks parse as YAML and validate against finding.schema.json.
    - No skill is missing from README.md's skill catalog (soft check).

Exits non-zero on failure.

Usage:
    python scripts/validate_skills.py [--skill <skill-name>]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.stderr.write("PyYAML is required: pip install pyyaml\n")
    sys.exit(2)

try:
    from jsonschema import Draft202012Validator
except ImportError:
    sys.stderr.write("jsonschema is required: pip install jsonschema\n")
    sys.exit(2)

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
SCHEMA_PATH = REPO_ROOT / "schemas" / "finding.schema.json"
CONVENTIONS_PATH = REPO_ROOT / "docs" / "CONVENTIONS.md"
README_PATH = REPO_ROOT / "README.md"

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
FRONTMATTER_RE = re.compile(r"^---\n(.*?\n)---\n", re.DOTALL)
EXAMPLE_BLOCK_RE = re.compile(
    r"### Example \d+[^\n]*\n+```yaml\n(.*?)\n```",
    re.DOTALL,
)
ID_REGISTRY_RE = re.compile(
    r"\|\s*([a-z0-9\-]+)\s*\|\s*`([A-Z\-]+)`\s*\|",
)


@dataclass
class Issue:
    skill: str
    severity: str
    message: str


@dataclass
class Report:
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)

    def add_error(self, skill: str, message: str) -> None:
        self.errors.append(Issue(skill, "error", message))

    def add_warning(self, skill: str, message: str) -> None:
        self.warnings.append(Issue(skill, "warn", message))


def load_schema() -> dict:
    with SCHEMA_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_id_registry() -> dict[str, str]:
    if not CONVENTIONS_PATH.exists():
        return {}
    text = CONVENTIONS_PATH.read_text(encoding="utf-8")
    registry: dict[str, str] = {}
    for match in ID_REGISTRY_RE.finditer(text):
        skill, prefix = match.group(1), match.group(2)
        registry[skill] = prefix
    return registry


def parse_frontmatter(text: str) -> tuple[dict | None, str]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None, text
    try:
        data = yaml.safe_load(m.group(1))
    except yaml.YAMLError as e:
        raise ValueError(f"frontmatter is not valid YAML: {e}") from e
    if not isinstance(data, dict):
        raise ValueError("frontmatter must be a YAML mapping")
    return data, text[m.end():]


def extract_examples(body: str) -> list[str]:
    return [m.group(1) for m in EXAMPLE_BLOCK_RE.finditer(body)]


def validate_frontmatter(skill_name: str, fm: dict, report: Report) -> tuple[str | None, str | None]:
    """Validate frontmatter and return (version, id_prefix) for downstream checks."""
    required = {"name", "description", "metadata"}
    missing = required - fm.keys()
    if missing:
        report.add_error(skill_name, f"frontmatter missing required field(s): {sorted(missing)}")
    if fm.get("name") != skill_name:
        report.add_error(
            skill_name,
            f"frontmatter name='{fm.get('name')}' does not match directory '{skill_name}'",
        )
    description = fm.get("description", "")
    if not isinstance(description, str) or len(description.strip()) < 40:
        report.add_error(skill_name, "frontmatter description must be >= 40 characters")

    metadata = fm.get("metadata", {})
    if not isinstance(metadata, dict):
        report.add_error(skill_name, "frontmatter 'metadata' must be a mapping")
        return None, None

    version = metadata.get("version", "")
    if not isinstance(version, str) or not SEMVER_RE.match(version):
        report.add_error(
            skill_name,
            f"frontmatter metadata.version '{version}' is not valid SemVer",
        )
        version = None

    id_prefix = metadata.get("id_prefix")
    if id_prefix is not None and not isinstance(id_prefix, str):
        report.add_error(skill_name, "frontmatter metadata.id_prefix must be a string")
        id_prefix = None

    license_field = fm.get("license")
    if license_field is not None and license_field != "Apache-2.0":
        report.add_warning(
            skill_name,
            f"license='{license_field}' — library-wide convention is Apache-2.0",
        )

    return version, id_prefix


def validate_examples(
    skill_name: str,
    body: str,
    validator: Draft202012Validator,
    expected_prefix: str | None,
    report: Report,
) -> None:
    examples_yaml = extract_examples(body)
    if len(examples_yaml) < 3:
        report.add_error(
            skill_name,
            f"must have at least 3 worked example findings (found {len(examples_yaml)})",
        )
    for idx, raw in enumerate(examples_yaml, 1):
        try:
            parsed = yaml.safe_load(raw)
        except yaml.YAMLError as e:
            report.add_error(skill_name, f"example {idx} is not valid YAML: {e}")
            continue
        if isinstance(parsed, list):
            items = parsed
        else:
            items = [parsed]
        for item_idx, item in enumerate(items, 1):
            if not isinstance(item, dict):
                report.add_error(
                    skill_name,
                    f"example {idx}.{item_idx} is not a mapping",
                )
                continue
            errors = list(validator.iter_errors(item))
            for err in errors:
                path = "/".join(str(p) for p in err.absolute_path) or "(root)"
                report.add_error(
                    skill_name,
                    f"example {idx}.{item_idx} schema violation at {path}: {err.message}",
                )
            if expected_prefix:
                finding_id = item.get("id", "")
                prefix = finding_id.split("-")[0] if isinstance(finding_id, str) else ""
                if expected_prefix == "REL-R":
                    if not isinstance(finding_id, str) or not finding_id.startswith("REL-R-"):
                        report.add_warning(
                            skill_name,
                            f"example {idx}.{item_idx} id='{finding_id}' "
                            f"does not match expected prefix 'REL-R-'",
                        )
                elif prefix != expected_prefix:
                    report.add_warning(
                        skill_name,
                        f"example {idx}.{item_idx} id='{finding_id}' "
                        f"does not match expected prefix '{expected_prefix}-'",
                    )


def validate_skill(skill_dir: Path, validator: Draft202012Validator, registry: dict[str, str], report: Report) -> None:
    skill_name = skill_dir.name
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        report.add_error(skill_name, f"no SKILL.md in {skill_dir}")
        return
    text = skill_md.read_text(encoding="utf-8")
    try:
        fm, body = parse_frontmatter(text)
    except ValueError as e:
        report.add_error(skill_name, str(e))
        return
    if fm is None:
        report.add_error(skill_name, "SKILL.md has no frontmatter block")
        return
    _, meta_prefix = validate_frontmatter(skill_name, fm, report)
    conv_prefix = registry.get(skill_name)
    if meta_prefix and conv_prefix and meta_prefix != conv_prefix:
        report.add_warning(
            skill_name,
            f"metadata.id_prefix='{meta_prefix}' disagrees with "
            f"CONVENTIONS.md §4 registry='{conv_prefix}'",
        )
    expected_prefix = meta_prefix or conv_prefix
    if expected_prefix is None:
        report.add_warning(
            skill_name,
            "no finding ID prefix in metadata.id_prefix or CONVENTIONS.md §4",
        )
    validate_examples(skill_name, body, validator, expected_prefix, report)


def discover_skills() -> list[Path]:
    return sorted(
        d for d in SKILLS_DIR.iterdir()
        if d.is_dir() and not d.name.startswith("_")
    )


def check_readme_lists_all(skills: list[Path], report: Report) -> None:
    if not README_PATH.exists():
        return
    readme = README_PATH.read_text(encoding="utf-8")
    for skill in skills:
        if skill.name not in readme:
            report.add_warning(
                skill.name,
                "skill not mentioned in README.md",
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill", help="Validate only this skill name")
    args = parser.parse_args()

    schema = load_schema()
    validator = Draft202012Validator(schema)
    registry = load_id_registry()

    all_skills = discover_skills()
    if args.skill:
        targets = [d for d in all_skills if d.name == args.skill]
        if not targets:
            sys.stderr.write(f"no skill named '{args.skill}'\n")
            return 2
    else:
        targets = all_skills

    report = Report()
    for skill_dir in targets:
        validate_skill(skill_dir, validator, registry, report)

    if not args.skill:
        check_readme_lists_all(all_skills, report)

    for issue in report.warnings:
        sys.stderr.write(f"warn [{issue.skill}] {issue.message}\n")
    for issue in report.errors:
        sys.stderr.write(f"ERROR [{issue.skill}] {issue.message}\n")

    if report.errors:
        sys.stderr.write(f"\n{len(report.errors)} error(s), {len(report.warnings)} warning(s)\n")
        return 1
    sys.stdout.write(
        f"OK — {len(targets)} skill(s) validated, {len(report.warnings)} warning(s)\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
