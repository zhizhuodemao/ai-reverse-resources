import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { parse } from 'yaml'
import { apply, collectSkills } from '../index.js'

// Preserve Loader expressions as data; validation must never execute them.
const customTags = [{ tag: 'tag:yaml.org,2002:js', resolve: expression => ({ expression }) }]
const read = path => readFileSync(new URL(path, import.meta.url), 'utf8')
const yaml = path => parse(read(path), { customTags })
const walk = rows => rows.flatMap(row => [row, ...(row.group ? walk(row.config) : [])])

test('the published bundle declares reverse without relying on a legacy directory', () => {
  const manifest = JSON.parse(read('../package.json'))
  const rows = manifest.dsh.bundle.patch.flatMap(path => yaml(`../${path}`).flatMap(patch => patch.insert ?? []))
  const declarations = rows.filter(row => row.name === '@deepseek-ai/dsh-agent-preset')
  assert.equal(declarations.length, 1)
  assert.equal(declarations[0].config.id, 'reverse')
  assert.equal(declarations[0].config.name, '逆向模式')
  assert.equal(rows.filter(row => row.id === 'js-reverse-plugin').length, 1)
  assert.deepEqual(rows.find(row => row.id === 'mcp-js-reverse').config.args, ['-y', 'js-reverse-mcp@4.0.1'])
})

test('reverse uses the current persona and workflow APIs and keeps platform conditions', () => {
  const preset = yaml('../preset/cordis.patch.yml')[0].insert[0].config
  const rows = walk(preset.plugins)
  const persona = rows.find(row => row.id === 'persona').config
  assert.match(persona.prefix, /JS reverse-engineering agent/)
  assert.match(persona.prefix, /保护原始输入/)
  assert.equal(persona.text, undefined)
  assert.equal(rows.find(row => row.id === 'workflow-ptc').name, '@deepseek-ai/dsh-workflow-ptc')
  assert.equal(rows.some(row => row.name === '@deepseek-ai/dsh-workflow-worker-thread'), false)
  assert.deepEqual(rows.find(row => row.id === 'tool-bash').disabled, { expression: "process.platform === 'win32'" })
  assert.deepEqual(rows.find(row => row.id === 'tool-pwsh').disabled, { expression: "process.platform !== 'win32'" })
})

test('all three skills can unload and reload without duplicate registrations', () => {
  const registered = new Map()
  let effects = []
  const ctx = {
    skills: {
      register(skill) {
        assert.equal(registered.has(skill.name), false, `duplicate skill: ${skill.name}`)
        registered.set(skill.name, skill)
        return () => registered.delete(skill.name)
      },
    },
    effect(callback) { effects.push(callback()) },
  }
  const expected = ['iv8-env-runtime', 'iv8-jsvmp-recovery', 'js-ast-deobfuscation']
  assert.deepEqual(collectSkills().map(skill => skill.name).sort(), expected)
  for (let generation = 0; generation < 2; generation++) {
    apply(ctx)
    assert.deepEqual([...registered.keys()].sort(), expected)
    for (const dispose of effects) dispose()
    effects = []
    assert.equal(registered.size, 0)
  }
})
