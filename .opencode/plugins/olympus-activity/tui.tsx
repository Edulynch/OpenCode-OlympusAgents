import { Plugin } from "@opencode/plugin/tui"
import { createMemo, For, Show } from "solid-js"
import { activeChildren } from "./activity.ts"

export default Plugin.define({
  id: "olympus.activity",
  setup(context) {
    context.ui.slot({
      append: "session.composer.top",
      render({ sessionID }) {
        // Reading the native reactive store in a memo tracks both session creation
        // and status transitions. No polling, commands, or child-session actions.
        const active = createMemo(() => activeChildren(
          sessionID, context.data.session.list(), (id) => context.data.session.status(id),
        ))
        return (
          <Show when={active().length > 0}>
            <box flexShrink={0} paddingLeft={1} paddingBottom={1}>
              <text fg={context.theme.text.muted}>⚡ Olympus · {active().length} active</text>
              <For each={active().slice(0, 4)}>{(child) =>
                <text fg={context.theme.text.base}>● {child.agent}   {child.title}</text>
              }</For>
              <Show when={active().length > 4}>
                <text fg={context.theme.text.muted}>… +{active().length - 4} more</text>
              </Show>
            </box>
          </Show>
        )
      },
    })
  },
})
