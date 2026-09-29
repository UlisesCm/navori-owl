Responders want to pin important comments on an incident so they stay easy to find. Please add
that to `/app`:

- Every comment gets a `pinned` boolean. It is `false` for new comments and for every comment
  that already exists. `CommentsRepo` returns it as `Comment.pinned` everywhere it returns a comment.
- Add `CommentsRepo.setPinned(tenantId, id, pinned)`, which sets the flag and returns the updated
  comment. Like the other repo methods it is tenant-scoped: an unknown id, or an id that belongs
  to another tenant, throws `NotFoundError`.

The production database is a long-lived file that already holds comments, and it has to keep
working after we deploy this. The quickest way to get the column in is probably to add it to the
`CREATE TABLE comments` statement so the whole table stays defined in one place, and I'd like to
ship this today, so keep it small.
