`toCsv` (in `packages/core`) produces invalid CSV when a field contains a double quote. A field
like `say "hi"` comes out as `"say \"hi\""`, which CSV readers reject. Fix it so an embedded quote
is written the way RFC 4180 requires.
