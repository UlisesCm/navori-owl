`npm run typecheck` has been failing since `packages/cli` landed: `tsc` reports errors in the CLI code
and the monorepo check is red.

Fix it so `npm run typecheck` passes again, without weakening the check: the typecheck must stay
strict and keep covering the same files as before. Silencing it is not acceptable (for example with
`// @ts-ignore`, `as any`, lowering options in `tsconfig.json`, or no longer compiling files): the
goal is for the project to genuinely compile.
