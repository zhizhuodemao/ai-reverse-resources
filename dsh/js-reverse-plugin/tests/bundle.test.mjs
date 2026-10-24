/** Bundle regressions that do not start MCP, a browser, or target JavaScript. */
import assert from 'node:assert/strict'
import { existsSync, mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import { parse } from 'yaml'
import { apply, collectSkills } from '../index.js'

const manifest = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8'))
const patches = manifest.dsh.bundle.patch.flatMap(path => parse(
  readFileSync(new URL(`../${path}`, import.meta.url), 'utf8'),
  { customTags: [{ tag: 'tag:yaml.org,2002:js', resolve: expression => ({ expression }) }] },
))
const declarations = patches.flatMap(patch => patch.insert ?? [])
const preset = declarations.find(row => row.id === 'preset-reverse')

test('the bundle declares a selectable reverse preset with its original analysis rules', () => {
  assert.equal(preset.name, '@deepseek-ai/dsh-agent-preset')
  assert.equal(preset.config.id, 'reverse')
  assert.equal(preset.config.name, '逆向模式')
  const persona = preset.config.plugins.find(row => row.id === 'persona')
  assert.equal(persona.config.text, undefined)
  assert.match(persona.config.prefix, /JS reverse-engineering agent/)
  assert.match(persona.config.prefix, /证据驱动/)
  assert.match(persona.config.prefix, /等价验收/)
  assert.doesNotMatch(persona.config.prefix, /\{\{cwd\}\}/)
})

test('delegation uses the current combined controls and PTC workflow provider', () => {
  const delegation = preset.config.plugins.find(row => row.id === 'delegation').config
  assert.equal(delegation.filter(row => row.name === '@deepseek-ai/dsh-tool-subagent-control').length, 1)
  assert.ok(delegation.some(row => row.name === '@deepseek-ai/dsh-workflow-ptc'))
  assert.ok(delegation.some(row => row.name === '@deepseek-ai/dsh-tool-ralph'))
  for (const row of delegation) {
    assert.notEqual(row.name, '@deepseek-ai/dsh-tool-subagent-control/list-agents')
    assert.notEqual(row.name, '@deepseek-ai/dsh-workflow-worker-thread')
    assert.equal(row.config?.backgroundMode, undefined)
  }
})

test('platform conditions remain unevaluated until Cordis activates the shell row', () => {
  const rows = preset.config.plugins
  assert.equal(rows.find(row => row.id === 'tool-bash').disabled.expression, "process.platform === 'win32'")
  assert.equal(rows.find(row => row.id === 'tool-pwsh').disabled.expression, "process.platform !== 'win32'")
})

test('the fixed MCP version and global skill registration are preserved', () => {
  const mcp = declarations.find(row => row.id === 'mcp-js-reverse')
  assert.equal(mcp.config.transport, 'stdio')
  assert.deepEqual(mcp.config.args, ['-y', 'js-reverse-mcp@4.0.1'])
  const skills = collectSkills()
  assert.deepEqual(skills.map(skill => skill.name).sort(), ['iv8-env-runtime', 'iv8-jsvmp-recovery', 'js-ast-deobfuscation'])
  for (const skill of skills) {
    assert.ok(skill.content.length > 0)
    assert.ok(existsSync(skill.path))
    assert.ok(existsSync(skill.resourceBase.path))
  }
})

test('loading skills no longer writes hidden preset files into DSH_HOME', () => {
  const home = mkdtempSync(join(tmpdir(), 'reverse-bundle-test-'))
  const previous = process.env.DSH_HOME
  const registered = []
  try {
    process.env.DSH_HOME = home
    apply({ skills: { register: skill => registered.push(skill) } })
    assert.equal(registered.length, 3)
    assert.equal(existsSync(join(home, '.agent-presets')), false)
  } finally {
    if (previous === undefined) delete process.env.DSH_HOME
    else process.env.DSH_HOME = previous
    rmSync(home, { recursive: true, force: true })
  }
})
