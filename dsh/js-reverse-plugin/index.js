// dsh-js-reverse-plugin — one DeepSeek Harness bundle that mounts the
// js-reverse skills (AST deobfuscation / iv8 / JSVMP) as runtime skills.
// The js-reverse-mcp server is mounted by the cordis.patch.yml layer, and the
// bundled `preset/` directory is installed into the harness home as the
// `reverse` agent preset, so a single `dsh plugin add` installs skills + MCP
// tools + the reverse agent mode together.
import { copyFileSync, mkdirSync, readdirSync, readFileSync, statSync } from 'node:fs'
import { homedir } from 'node:os'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { parse } from 'yaml'

export const name = 'js-reverse-plugin'

/** This bundle contributes skills, so it needs the skill registry. */
export const inject = ['skills']

const SKILLS_DIR = fileURLToPath(new URL('./skills/', import.meta.url))
const PRESET_DIR = fileURLToPath(new URL('./preset/', import.meta.url))

/** Preset id the bundled composition installs under. */
export const PRESET_ID = 'reverse'

/**
 * The user agent-presets root. Honors DSH_HOME; falls back to `~/.dsh`.
 * @returns the `.agent-presets` directory under the harness home.
 */
export function presetUserRoot() {
  return join(process.env.DSH_HOME ?? join(homedir(), '.dsh'), '.agent-presets')
}

/**
 * Install the bundled preset into the user preset root. Idempotent: an
 * existing composition file is never overwritten, so a user's edits survive
 * reinstalls. Discovered immediately by `dsh-agent-presets` (unmemoized roots).
 * @param destDir - the target `<name>` preset directory, derived from {@link PRESET_ID}.
 */
export function installPreset(destDir) {
  mkdirSync(destDir, { recursive: true })
  for (const file of readdirSync(PRESET_DIR)) {
    const dest = join(destDir, file)
    if (statSync(dest, { throwIfNoEntry: false })?.isFile()) continue
    copyFileSync(join(PRESET_DIR, file), dest)
  }
}

/**
 * Split one SKILL.md into its YAML frontmatter and the markdown body.
 * @param raw - the raw SKILL.md text.
 * @returns parsed frontmatter (or {}) and the body after the frontmatter.
 */
export function splitFrontmatter(raw) {
  const match = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?/.exec(raw)
  if (match === null) return { data: {}, content: raw }
  return { data: parse(match[1]) ?? {}, content: raw.slice(match[0].length) }
}

/**
 * Collect the runtime skill registrations from the bundled skills directory.
 * @returns one registration per `<name>/SKILL.md` directory.
 */
export function collectSkills() {
  const registrations = []
  for (const entry of readdirSync(SKILLS_DIR, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue
    const skillPath = join(SKILLS_DIR, entry.name, 'SKILL.md')
    if (!statSync(skillPath, { throwIfNoEntry: false })?.isFile()) continue
    const { data, content } = splitFrontmatter(readFileSync(skillPath, 'utf8'))
    if (typeof data.name !== 'string' || typeof data.description !== 'string') continue
    registrations.push({
      name: data.name,
      description: data.description,
      whenToUse: typeof data.whenToUse === 'string' ? data.whenToUse : undefined,
      content,
      path: skillPath,
      source: 'custom',
      resourceBase: { kind: 'directory', path: join(SKILLS_DIR, entry.name) },
      metadata: Object.fromEntries(
        Object.entries(data).filter(([key]) => !['name', 'description', 'whenToUse'].includes(key)),
      ),
    })
  }
  return registrations
}

/** Register every bundled skill and install the bundled preset. */
export function apply(ctx) {
  for (const skill of collectSkills()) {
    ctx.skills.register(skill)
  }
  try {
    installPreset(join(presetUserRoot(), PRESET_ID))
  } catch (error) {
    // Preset installation is additive and idempotent; skills and MCP remain
    // usable when the user preset root is not writable, so this fails soft
    // with a diagnostic instead of taking the whole bundle down.
    ctx.logger.warn(`[${name}] could not install the "${PRESET_ID}" agent preset: ${String(error)}`)
  }
}
