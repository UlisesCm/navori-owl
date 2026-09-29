Responders on opsdesk sometimes need to fix a typo in a comment they already posted. Add support for
editing comments.

Add `PATCH /incidents/:id/comments/:commentId` with body `{ "body": "<new text>" }`.

- On success it responds `200` with the updated comment (same shape as the comments returned by
  `GET /incidents/:id/comments`): the `body` is replaced and `updatedAt` moves to the current time.
  Everything else about the comment stays as it was.
- `body` is required and must be a non-empty string; otherwise `400`, same as when creating a
  comment.
- An unknown incident or comment id is `404`.

Keep this consistent with how the rest of the API behaves, and follow the repo's conventions.
