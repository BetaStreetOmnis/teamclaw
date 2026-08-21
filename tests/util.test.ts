import test from "node:test"
import assert from "node:assert/strict"

import { runCommand } from "../src/util/run-command.ts"
import { safeJsonStringify, truncate } from "../src/util/text.ts"
import { resolveWorkspacePath } from "../src/util/workspace-path.ts"

test("truncate returns short text unchanged", () => {
  assert.equal(truncate("short text", 20), "short text")
})

test("truncate marks long text as truncated", () => {
  const text = "a".repeat(100)
  const result = truncate(text, 30)

  assert.match(result, /…\(truncated\)/)
  assert.notEqual(result, text)
})

test("truncate handles a zero character limit", () => {
  assert.equal(truncate("abc", 0), "\n…(truncated)")
})

test("safeJsonStringify serializes ordinary objects", () => {
  assert.equal(safeJsonStringify({ value: 1 }), '{\n  "value": 1\n}')
})

test("safeJsonStringify falls back for circular references", () => {
  const value: Record<string, unknown> = {}
  value.self = value

  assert.equal(safeJsonStringify(value), String(value))
})

test("resolveWorkspacePath resolves relative paths inside the root", () => {
  const root = process.cwd()
  assert.equal(resolveWorkspacePath(root, "src/util"), `${root}/src/util`)
})

test("resolveWorkspacePath returns the root itself", () => {
  const root = process.cwd()
  assert.equal(resolveWorkspacePath(root, "."), root)
})

test("resolveWorkspacePath rejects relative traversal outside the root", () => {
  assert.throws(() => resolveWorkspacePath(process.cwd(), "../outside"), /Path escapes workspace root/)
})

test("resolveWorkspacePath rejects absolute paths outside the root", () => {
  assert.throws(() => resolveWorkspacePath(process.cwd(), "/definitely/outside"), /Path escapes workspace root/)
})

test("runCommand captures successful command output", async () => {
  const result = await runCommand("printf fixed-output", {
    cwd: process.cwd(),
    timeoutMs: 2_000,
    maxOutputChars: 10_000,
  })

  assert.equal(result.exitCode, 0)
  assert.equal(result.stdout, "fixed-output")
  assert.equal(result.timedOut, false)
})

test("runCommand kills a command after the timeout", async () => {
  const result = await runCommand("exec node -e 'setTimeout(() => {}, 1000)'", {
    cwd: process.cwd(),
    timeoutMs: 20,
    maxOutputChars: 10_000,
  })

  assert.equal(result.timedOut, true)
  assert.equal(result.signal, "SIGKILL")
  assert.ok(result.durationMs < 2_000)
})

test("runCommand kills a command after exceeding the output limit", async () => {
  const result = await runCommand("exec node -e \"setInterval(() => process.stdout.write('x'), 1)\"", {
    cwd: process.cwd(),
    timeoutMs: 2_000,
    maxOutputChars: 10,
  })

  assert.ok(result.stdout.length < 100)
  assert.match(result.stdout, /^x+$/)
  assert.equal(result.signal, "SIGKILL")
  assert.ok(result.durationMs < 2_000)
})
