import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { test } from "node:test"
import { activeChildren } from "../../.opencode/plugins/olympus-activity/activity.ts"

const root = { id: "root", agent: "kael" }
const child = (id, agent, title = "Inspect repository", parentID = "root") =>
  ({ id, parentID, agent, title })
const status = (running) => (id) => running.includes(id) ? "running" : "idle"

test("H4 root-only and direct children only", () => {
  const sessions = [root, child("a", "orin"), child("nested", "nox", "Validate", "a")]
  assert.deepEqual(activeChildren("a", sessions, status(["nested"])), [])
  assert.deepEqual(activeChildren("root", sessions, status(["nested"])), [])
  assert.deepEqual(activeChildren("missing", sessions, status(["a"])), [])
})

test("H5 running direct children appear and disappear on native status transitions", () => {
  const sessions = [root, child("a", "orin"), child("b", "kovan")]
  assert.deepEqual(activeChildren("root", sessions, status(["a"])).map((row) => row.agent), ["Orin"])
  assert.deepEqual(activeChildren("root", sessions, status(["b"])).map((row) => row.agent), ["Kovan"])
  assert.deepEqual(activeChildren("root", sessions, status([])), [])
})

test("H6 duplicate sessions remain distinct rows", () => {
  const rows = activeChildren("root", [root, child("a", "maintenance"), child("b", "maintenance")], status(["a", "b"]))
  assert.deepEqual(rows.map((row) => row.id), ["a", "b"])
  assert.deepEqual(rows.map((row) => row.agent), ["Maintenance", "Maintenance"])
})

test("H7 Maintenance, fallback, truncation and Olympus display names", () => {
  const rows = activeChildren("root", [root, child("a", "maintenance", "New session"), child("b", "veyra", "x".repeat(90))], status(["a", "b"]))
  assert.equal(rows[0].title, "Maintenance task")
  assert.equal(rows[1].agent, "Veyra")
  assert.ok(rows[1].title.length <= 64)
})

test("H8 slot is passive and only reads native state", () => {
  const view = readFileSync(new URL("../../.opencode/plugins/olympus-activity/tui.tsx", import.meta.url), "utf8")
  assert.match(view, /append: "session\.composer\.top"/)
  assert.match(view, /context\.data\.session\.list\(\)/)
  assert.match(view, /context\.data\.session\.status\(id\)/)
  assert.doesNotMatch(view, /\b(?:onMouse\w*|onKey\w*|keymap|navigate|interrupt|cancel|setInterval|setTimeout|client\.)\b/)
  assert.match(view, /slice\(0, 4\)/)
})
