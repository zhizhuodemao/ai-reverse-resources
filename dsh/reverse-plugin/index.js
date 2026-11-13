// Reverse-engineering toolkit bundle. Each mode preset mounts this module with
// its own skills directory, so a preset exposes that domain's skills alone.
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { parse } from 'yaml'

export const name = 'reverse-skills'

/** This bundle contributes skills, so it needs the skill registry. */
export const inject = ['skills']

const PACKAGE_ROOT = fileURLToPath(new URL('.', import.meta.url))

/** Package-relative skills directory used when a preset mounts without `dir`. */
const DEFAULT_DIR = 'skills'

/**
 * Resolve one mount's skills directory.
 * @param dir - package-relative directory whose child directories each hold a SKILL.md.
 * @returns absolute path to that skills directory.
 */
export function skillsRoot(dir = DEFAULT_DIR) {
  return join(PACKAGE_ROOT, dir)
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
 * Collect the runtime skill registrations of one mode's bundled skills.
 * @param dir - package-relative directory holding `<skill>/SKILL.md` entries.
 * @returns one registration per `<name>/SKILL.md` directory.
 */
export function collectSkills(dir = DEFAULT_DIR) {
  const root = skillsRoot(dir)
  const registrations = []
  for (const entry of readdirSync(root, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue
    const skillPath = join(root, entry.name, 'SKILL.md')
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
      resourceBase: { kind: 'directory', path: join(root, entry.name) },
      metadata: Object.fromEntries(
        Object.entries(data).filter(([key]) => !['name', 'description', 'whenToUse'].includes(key)),
      ),
    })
  }
  return registrations
}

/**
 * Register one mode's bundled skills; Cordis owns and reverses each registration.
 * @param ctx - plugin context carrying the preset's standing scope.
 * @param config - mount config; `dir` selects the package-relative skills directory.
 */
export function apply(ctx, config = {}) {
  const dir = typeof config.dir === 'string' && config.dir !== '' ? config.dir : DEFAULT_DIR
  for (const skill of collectSkills(dir)) {
    ctx.skills.register(skill)
  }
}
