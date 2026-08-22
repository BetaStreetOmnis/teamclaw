import test from "node:test"
import assert from "node:assert/strict"
import { spawnSync } from "node:child_process"
import process from "node:process"

function runCli(...args: string[]) {
  return spawnSync("node", ["--import", "tsx", "src/cli.ts", ...args], {
    cwd: process.cwd(),
    encoding: "utf8",
  })
}

test("--help prints usage and commands", () => {
  const result = runCli("--help")

  assert.equal(result.status, 0)
  assert.match(result.stdout, /Usage:/)
  for (const command of ["run", "chat", "gateway", "connect"]) {
    assert.match(result.stdout, new RegExp(`\\b${command}\\b`))
  }
})

test("--version prints the package version", () => {
  const result = runCli("--version")

  assert.equal(result.status, 0)
  assert.match(result.stdout, /0\.1\.0/)
})

test("run --help prints common and run options", () => {
  const result = runCli("run", "--help")

  assert.equal(result.status, 0)
  assert.match(result.stdout, /--provider <provider>/)
  assert.match(result.stdout, /--model <model>/)
  assert.match(result.stdout, /--role <role>/)
})

test("an unknown command fails with an error", () => {
  const result = runCli("foobar")

  assert.notEqual(result.status, 0)
  assert.match(`${result.stdout}${result.stderr}`, /unknown command/i)
})

test("run fails when the required task is missing", () => {
  const result = runCli("run")

  assert.notEqual(result.status, 0)
})

test("run uses the offline mock provider", () => {
  const result = runCli("run", "--provider", "mock", "你好")

  assert.equal(result.status, 0)
  assert.match(result.stdout, /mock/)
})
