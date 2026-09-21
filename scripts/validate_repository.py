#!/usr/bin/env python3
"""Validate the repository structure without executing target JavaScript."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MARKETPLACE_PATH = ROOT / ".agents" / "plugins" / "marketplace.json"
CLAUDE_MARKETPLACE_PATH = ROOT / ".claude-plugin" / "marketplace.json"
PLUGIN_NAME = "js-reverse-plugin"
PLUGIN_VERSION = "0.2.0"
PLUGIN_ROOT = ROOT / "plugins" / PLUGIN_NAME
PLUGIN_MANIFEST_PATH = PLUGIN_ROOT / ".codex-plugin" / "plugin.json"
CLAUDE_PLUGIN_MANIFEST_PATH = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
MCP_PATH = PLUGIN_ROOT / ".mcp.json"
CLAUDE_MCP_PATH = PLUGIN_ROOT / ".claude-mcp.json"
REQUIRED_SKILLS = {
    "js-ast-deobfuscation",
    "iv8-env-runtime",
    "iv8-jsvmp-recovery",
}
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
SKILL_NAME = re.compile(r"^name:\s*([^\s#]+)\s*$", re.MULTILINE)
SKILL_DESCRIPTION = re.compile(
    r"^description:\s*(?:>-\s*\n(?P<folded>(?:^[ \t]+.*\n?)+)|(?P<plain>.+))",
    re.MULTILINE,
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_json(path: Path) -> dict:
    require(path.is_file(), f"missing JSON file: {path.relative_to(ROOT)}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise AssertionError(f"invalid JSON {path.relative_to(ROOT)}: {error}") from error
    require(isinstance(value, dict), f"expected JSON object: {path.relative_to(ROOT)}")
    return value


def validate_marketplace() -> None:
    marketplace = load_json(MARKETPLACE_PATH)
    require(marketplace.get("name") == "ai-reverse-resources", "wrong marketplace name")
    require(
        marketplace.get("interface", {}).get("displayName") == "AI Reverse Resources",
        "wrong marketplace display name",
    )
    plugins = marketplace.get("plugins")
    require(isinstance(plugins, list), "marketplace plugins must be an array")
    matches = [item for item in plugins if item.get("name") == PLUGIN_NAME]
    require(len(matches) == 1, f"expected one {PLUGIN_NAME} marketplace entry")
    entry = matches[0]
    require(
        entry.get("source") == {
            "source": "local",
            "path": f"./plugins/{PLUGIN_NAME}",
        },
        "wrong marketplace source",
    )
    require(
        entry.get("policy") == {
            "installation": "AVAILABLE",
            "authentication": "ON_INSTALL",
        },
        "wrong marketplace policy",
    )
    require(entry.get("category") == "Developer Tools", "wrong marketplace category")


def validate_plugin_manifest() -> None:
    manifest = load_json(PLUGIN_MANIFEST_PATH)
    require(manifest.get("name") == PLUGIN_NAME, "plugin name does not match folder")
    require(bool(SEMVER.fullmatch(str(manifest.get("version", "")))), "invalid semver")
    require(manifest.get("version") == PLUGIN_VERSION, "wrong Codex plugin version")
    require(bool(manifest.get("description")), "plugin description is empty")
    require(manifest.get("skills") == "./skills/", "wrong skills path")
    require(manifest.get("mcpServers") == "./.mcp.json", "wrong MCP path")
    require(manifest.get("author", {}).get("name") == "zhizhuodemao", "wrong author")
    interface = manifest.get("interface")
    require(isinstance(interface, dict), "plugin interface is missing")
    for field in (
        "displayName",
        "shortDescription",
        "longDescription",
        "developerName",
        "category",
        "capabilities",
        "defaultPrompt",
    ):
        require(interface.get(field), f"plugin interface.{field} is empty")
    prompts = interface["defaultPrompt"]
    require(isinstance(prompts, list) and 1 <= len(prompts) <= 3, "invalid default prompts")
    require(all(isinstance(item, str) and len(item) <= 128 for item in prompts), "invalid prompt")
    serialized = json.dumps(manifest, ensure_ascii=False)
    require("[TODO:" not in serialized, "plugin manifest contains TODO placeholder")


def validate_mcp() -> None:
    config = load_json(MCP_PATH)
    require(set(config) == {"js-reverse"}, "expected exactly one js-reverse MCP server")
    server = config["js-reverse"]
    require(isinstance(server, dict), "js-reverse MCP server must be an object")
    require(server.get("command") == "npx", "js-reverse command must be npx")
    require(
        server.get("args") == ["-y", "js-reverse-mcp@4.0.5"],
        "js-reverse MCP must remain pinned to 4.0.5",
    )


def validate_claude_marketplace() -> None:
    marketplace = load_json(CLAUDE_MARKETPLACE_PATH)
    require(marketplace.get("name") == "ai-reverse-resources", "wrong Claude marketplace name")
    require(
        marketplace.get("owner") == {"name": "zhizhuodemao"},
        "wrong Claude marketplace owner",
    )
    require(bool(marketplace.get("description")), "Claude marketplace description is empty")
    plugins = marketplace.get("plugins")
    require(isinstance(plugins, list), "Claude marketplace plugins must be an array")
    matches = [item for item in plugins if item.get("name") == PLUGIN_NAME]
    require(len(matches) == 1, f"expected one {PLUGIN_NAME} Claude marketplace entry")
    entry = matches[0]
    require(entry.get("source") == f"./plugins/{PLUGIN_NAME}", "wrong Claude plugin source")
    require(entry.get("version") == PLUGIN_VERSION, "wrong Claude marketplace version")
    require(bool(entry.get("description")), "Claude marketplace description is empty")


def validate_claude_plugin() -> None:
    manifest = load_json(CLAUDE_PLUGIN_MANIFEST_PATH)
    require(manifest.get("name") == PLUGIN_NAME, "wrong Claude plugin name")
    require(manifest.get("version") == PLUGIN_VERSION, "wrong Claude plugin version")
    require(manifest.get("mcpServers") == "./.claude-mcp.json", "wrong Claude MCP path")
    require(bool(manifest.get("description")), "Claude plugin description is empty")

    config = load_json(CLAUDE_MCP_PATH)
    require(set(config) == {"mcpServers"}, "Claude MCP must use the mcpServers wrapper")
    servers = config["mcpServers"]
    require(isinstance(servers, dict), "Claude mcpServers must be an object")
    require(set(servers) == {"js-reverse"}, "expected one Claude js-reverse server")
    server = servers["js-reverse"]
    require(isinstance(server, dict), "Claude js-reverse server must be an object")
    require(server.get("command") == "npx", "Claude js-reverse command must be npx")
    require(
        server.get("args") == ["-y", "js-reverse-mcp@4.0.5"],
        "Claude js-reverse MCP must remain pinned to 4.0.5",
    )


def validate_skill(path: Path) -> None:
    skill_file = path / "SKILL.md"
    require(skill_file.is_file(), f"missing {path.name}/SKILL.md")
    text = skill_file.read_text(encoding="utf-8")
    require(text.startswith("---\n"), f"{path.name}: missing YAML frontmatter")
    frontmatter_end = text.find("\n---\n", 4)
    require(frontmatter_end > 4, f"{path.name}: unclosed YAML frontmatter")
    frontmatter = text[4:frontmatter_end]
    name_match = SKILL_NAME.search(frontmatter)
    require(name_match is not None, f"{path.name}: missing name")
    require(name_match.group(1) == path.name, f"{path.name}: frontmatter name mismatch")
    description_match = SKILL_DESCRIPTION.search(frontmatter + "\n")
    require(description_match is not None, f"{path.name}: missing description")
    description = description_match.group("folded") or description_match.group("plain") or ""
    require(bool(description.strip()), f"{path.name}: empty description")
    require("[TODO:" not in text, f"{path.name}: TODO placeholder remains")


def validate_skills() -> None:
    skills_root = PLUGIN_ROOT / "skills"
    require(skills_root.is_dir(), "missing plugin skills directory")
    actual = {path.name for path in skills_root.iterdir() if path.is_dir()}
    require(actual == REQUIRED_SKILLS, f"unexpected skill set: {sorted(actual)}")
    for name in sorted(REQUIRED_SKILLS):
        validate_skill(skills_root / name)


def validate_evals() -> None:
    eval_root = ROOT / "evals" / PLUGIN_NAME
    expected = {"js-ast-deobfuscation", "iv8-jsvmp-recovery"}
    actual = {path.name for path in eval_root.iterdir() if path.is_dir()}
    require(actual == expected, f"unexpected eval set: {sorted(actual)}")

    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    for name in sorted(expected):
        validator = eval_root / name / "validate_assets.py"
        require(validator.is_file(), f"missing eval validator: {validator.relative_to(ROOT)}")
        subprocess.run(
            [sys.executable, str(validator)],
            cwd=validator.parent,
            env=environment,
            check=True,
        )


def main() -> None:
    validate_marketplace()
    validate_claude_marketplace()
    validate_plugin_manifest()
    validate_mcp()
    validate_claude_plugin()
    validate_skills()
    validate_evals()
    print(
        "OK: Codex and Claude marketplaces, js-reverse-plugin, 3 skills, "
        "js-reverse-mcp@4.0.5, and 2 eval suites"
    )


if __name__ == "__main__":
    main()
