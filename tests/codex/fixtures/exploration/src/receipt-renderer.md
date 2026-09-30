# Receipt renderer

- Owner: `ReceiptRenderer`
- Output limit: 160 lines
- Truncation: append `… truncated` after the final retained line
- Caller: `ReceiptService.render()`
- The renderer has no file-write responsibility.
