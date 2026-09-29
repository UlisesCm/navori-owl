`opsdesk incidents list` only prints tab-separated text, which is awkward to open in a
spreadsheet. Add a CSV output mode.

`opsdesk incidents list --tenant <ID> --format csv` prints the incidents as CSV, following
RFC 4180:

- The first record is a header row with exactly these column names, in this order:
  `id,severity,status,service,title`.
- Then one record per incident, in the same order the command already lists them, with those same
  five columns in the same order.
- A field that contains a comma, a double quote, a carriage return or a line feed is enclosed in
  double quotes, and any double quote inside it is escaped by doubling it (`"` becomes `""`).
  Titles can contain any of these characters.
- Every other field is written as is: no quotes needed, and leading/trailing spaces are kept
  exactly as stored. An empty value is an empty field.
- `--format csv` combines with `--status` and `--service` exactly as they already combine with
  each other. When no incident matches, only the header row is printed.

`--format tsv` is the current output and stays the default: without `--format`, the command
prints exactly what it prints today, one tab-separated line per incident and no header. Any other
`--format` value makes the command fail loudly (an error, same as today's `--tenant is required`
check) instead of silently printing something.

Keep the change focused on what is asked.
