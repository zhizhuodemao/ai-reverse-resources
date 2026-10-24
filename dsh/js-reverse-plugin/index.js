// Bundled reverse-engineering skills. The bundle patches register the
// reverse agent preset and the js-reverse MCP server declaratively.
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { parse } from 'yaml'

export const name = 'js-reverse-plugin'

/** This bundle contributes skills, so it needs the skill registry. */
export const inject = ['skills']

const SKILLS_DIR = fileURLToPath(new URL('./skills/', import.meta.url))

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

/** Register bundled skills; Cordis owns and reverses each registration. */
export function apply(ctx) {
  for (const skill of collectSkills()) {
    ctx.skills.register(skill)
  }
}
