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

SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
SKILL_NAME = re.compile(r"^name:\s*([^\s#]+)\s*$", re.MULTILINE)
SKILL_DESCRIPTION = re.compile(
    r"^description:\s*(?:>-\s*\n(?P<folded>(?:^[ \t]+.*\n?)+)|(?P<plain>.+))",
    re.MULTILINE,
)

# One row per Codex/Claude plugin. The DSH package consumes these skill trees.
PLUGINS = [
    {
        "name": "js-reverse-plugin",
        "version": "0.2.0",
        "skills": {"js-ast-deobfuscation", "iv8-env-runtime", "iv8-jsvmp-recovery"},
        "evals": {"js-ast-deobfuscation", "iv8-jsvmp-recovery"},
        "mcp_servers": {"js-reverse": {"command": "npx", "args": ["-y", "js-reverse-mcp@4.0.1"]}},
    },
    {
        "name": "ios-reverse-plugin",
        "version": "0.1.0",
        "skills": {"ios-device-bridge"},
        "evals": set(),
        "mcp_servers": {},
    },
]

# The DSH bundle: one npm package carrying every reverse mode preset.
DSH_PACKAGE = {
    "dir": "reverse-plugin",
    "name": "dsh-reverse-plugin",
    "pkg_version": "0.3.2",
    "patches": ["./preset/reverse.patch.yml"],
    "modes": [
        {
            "dir": "skills/js",
            "preset_id": "reverse",
            "preset_name": "逆向模式",
            "skills_from": "js-reverse-plugin",
        },
        {
            "dir": "skills/ios",
            "preset_id": "reverse",
            "preset_name": "逆向模式",
            "skills_from": "ios-reverse-plugin",
        },
    ],
}


def plugin_root(name: str) -> Path:
    return ROOT / "plugins" / name


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
    for plugin in PLUGINS:
        name = plugin["name"]
        matches = [item for item in plugins if item.get("name") == name]
        require(len(matches) == 1, f"expected one {name} marketplace entry")
        entry = matches[0]
        require(
            entry.get("source") == {"source": "local", "path": f"./plugins/{name}"},
            f"wrong marketplace source for {name}",
        )
        require(
            entry.get("policy") == {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
            f"wrong marketplace policy for {name}",
        )
        require(entry.get("category") == "Developer Tools", f"wrong marketplace category for {name}")


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
    for plugin in PLUGINS:
        name = plugin["name"]
        matches = [item for item in plugins if item.get("name") == name]
        require(len(matches) == 1, f"expected one {name} Claude marketplace entry")
        entry = matches[0]
        require(entry.get("source") == f"./plugins/{name}", f"wrong Claude plugin source for {name}")
        require(entry.get("version") == plugin["version"], f"wrong Claude marketplace version for {name}")
        require(bool(entry.get("description")), f"Claude marketplace description is empty for {name}")


def validate_plugin_manifest(plugin: dict) -> None:
    name = plugin["name"]
    root = plugin_root(name)
    manifest = load_json(root / ".codex-plugin" / "plugin.json")
    require(manifest.get("name") == name, f"{name}: plugin name does not match folder")
    require(bool(SEMVER.fullmatch(str(manifest.get("version", "")))), f"{name}: invalid semver")
    require(manifest.get("version") == plugin["version"], f"{name}: wrong Codex plugin version")
    require(bool(manifest.get("description")), f"{name}: plugin description is empty")
    require(manifest.get("skills") == "./skills/", f"{name}: wrong skills path")
    require(manifest.get("mcpServers") == "./.mcp.json", f"{name}: wrong MCP path")
    require(manifest.get("author", {}).get("name") == "zhizhuodemao", f"{name}: wrong author")
    interface = manifest.get("interface")
    require(isinstance(interface, dict), f"{name}: plugin interface is missing")
    for field in (
        "displayName",
        "shortDescription",
        "longDescription",
        "developerName",
        "category",
        "capabilities",
        "defaultPrompt",
    ):
        require(interface.get(field), f"{name}: plugin interface.{field} is empty")
    prompts = interface["defaultPrompt"]
    require(isinstance(prompts, list) and 1 <= len(prompts) <= 3, f"{name}: invalid default prompts")
    require(all(isinstance(item, str) and len(item) <= 128 for item in prompts), f"{name}: invalid prompt")
    serialized = json.dumps(manifest, ensure_ascii=False)
    require("[TODO:" not in serialized, f"{name}: plugin manifest contains TODO placeholder")


def validate_mcp(plugin: dict) -> None:
    name = plugin["name"]
    config = load_json(plugin_root(name) / ".mcp.json")
    expected = plugin["mcp_servers"]
    require(set(config) == set(expected), f"{name}: unexpected MCP server set {sorted(config)}")
    for server_name, fields in expected.items():
        server = config[server_name]
        require(isinstance(server, dict), f"{name}: {server_name} MCP server must be an object")
        require(server.get("command") == fields["command"], f"{name}: wrong {server_name} command")
        require(server.get("args") == fields["args"], f"{name}: {server_name} MCP must stay pinned")


def validate_claude_plugin(plugin: dict) -> None:
    name = plugin["name"]
    root = plugin_root(name)
    manifest = load_json(root / ".claude-plugin" / "plugin.json")
    require(manifest.get("name") == name, f"{name}: wrong Claude plugin name")
    require(manifest.get("version") == plugin["version"], f"{name}: wrong Claude plugin version")
    require(manifest.get("mcpServers") == "./.claude-mcp.json", f"{name}: wrong Claude MCP path")
    require(bool(manifest.get("description")), f"{name}: Claude plugin description is empty")

    config = load_json(root / ".claude-mcp.json")
    require(set(config) == {"mcpServers"}, f"{name}: Claude MCP must use the mcpServers wrapper")
    servers = config["mcpServers"]
    require(isinstance(servers, dict), f"{name}: Claude mcpServers must be an object")
    require(set(servers) == set(plugin["mcp_servers"]), f"{name}: unexpected Claude MCP server set")
    for server_name, fields in plugin["mcp_servers"].items():
        server = servers[server_name]
        require(isinstance(server, dict), f"{name}: Claude {server_name} server must be an object")
        require(server.get("command") == fields["command"], f"{name}: wrong Claude {server_name} command")
        require(server.get("args") == fields["args"], f"{name}: Claude {server_name} MCP must stay pinned")


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


def validate_skills(plugin: dict) -> None:
    name = plugin["name"]
    skills_root = plugin_root(name) / "skills"
    require(skills_root.is_dir(), f"{name}: missing plugin skills directory")
    actual = {path.name for path in skills_root.iterdir() if path.is_dir()}
    require(actual == plugin["skills"], f"{name}: unexpected skill set: {sorted(actual)}")
    for skill in sorted(plugin["skills"]):
        validate_skill(skills_root / skill)


def validate_dsh_package() -> None:
    package_root = ROOT / "dsh" / DSH_PACKAGE["dir"]
    manifest = load_json(package_root / "package.json")
    require(manifest.get("name") == DSH_PACKAGE["name"], "wrong DSH package name")
    patches = manifest.get("dsh", {}).get("bundle", {}).get("patch")
    require(isinstance(patches, list) and bool(patches), "DSH bundle must declare its patch layers")
    require(patches == DSH_PACKAGE["patches"], f"unexpected DSH patch layers: {patches}")
    for patch in patches:
        require(isinstance(patch, str) and (package_root / patch).is_file(), f"missing DSH patch: {patch}")
    require(bool(manifest.get("engines", {}).get("dsh")), "missing DSH compatibility range")
    repository = manifest.get("repository", {})
    require(repository.get("directory") == f"dsh/{DSH_PACKAGE['dir']}", "wrong DSH repository directory")

    for mode in DSH_PACKAGE["modes"]:
        patch = package_root / "preset" / f"{mode['preset_id']}.patch.yml"
        require(patch.is_file(), f"missing preset file for {mode['preset_id']}")
        text = patch.read_text(encoding="utf-8")
        require(f"id: {mode['preset_id']}" in text, f"{mode['preset_id']}: preset id missing")
        require(mode["preset_name"] in text, f"{mode['preset_id']}: preset name missing")
        require(f"dir: {mode['dir']}" in text, f"{mode['preset_id']}: skills dir missing")
        source = plugin_root(mode["skills_from"]) / "skills"
        require(source.is_dir(), f"{mode['preset_id']}: skills source missing for {mode['skills_from']}")


def validate_evals(plugin: dict) -> None:
    name = plugin["name"]
    eval_root = ROOT / "evals" / name
    expected = plugin["evals"]
    if not expected and not eval_root.exists():
        return
    actual = {path.name for path in eval_root.iterdir() if path.is_dir()}
    require(actual == expected, f"{name}: unexpected eval set: {sorted(actual)}")

    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    for name_ in sorted(expected):
        validator = eval_root / name_ / "validate_assets.py"
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
    for plugin in PLUGINS:
        validate_plugin_manifest(plugin)
        validate_mcp(plugin)
        validate_claude_plugin(plugin)
        validate_skills(plugin)
        validate_evals(plugin)
    validate_dsh_package()
    names = ", ".join(plugin["name"] for plugin in PLUGINS)
    print(f"OK: Codex and Claude marketplaces, {names}, {DSH_PACKAGE['name']} presets, and eval suites")


if __name__ == "__main__":
    main()
