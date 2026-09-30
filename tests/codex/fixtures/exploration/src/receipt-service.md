# Receipt service

- `ReceiptService.render()` delegates formatting to `ReceiptRenderer`.
- `ReceiptService` supplies a maximum of 160 display lines.
- Raw receipt storage is owned by `ReceiptStore`, not by the renderer.
