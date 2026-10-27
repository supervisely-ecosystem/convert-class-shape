# convert-class-shape

GUI transform app: images project → new project `<name>(new shapes)` in the same workspace with the
classes the user picked converted to another shape. `MODERNIZE.md` has the behaviour contract and the
intentional changes versus the pre-2026 (AppService) version.

- Entry: `uvicorn src.main:app` (`config.json` `entrypoint`); modules import each other as `src.*`.
  `src/main.py` is the composition root (env → Api → GUI); creating `app` at import is required by uvicorn.
- `src/ui.py` (`ShapeConversionGui`): widgets + Run handler; platform side effects arrive as callbacks
  from `main.py` (convert, set task output / workflow / `app.stop()`).
- `src/converter.py` orchestrates the copy (dataset tree incl. nested, batches of 50); `src/platform_io.py`
  is the only module calling the API; `src/core/shapes.py` is the pure conversion (unit-tested, proven
  equivalent to the old `conversion.py` on generated and real data).
- Conversion itself is the SDK's (`Label.convert`); the app only adds binding-aware Polygon↔Multipolygon.
  The dropdowns list `geometry_type.allowed_transforms()` minus the class's own shape.

Runtime: bare `supervisely/base-py-sdk-hardened:<sdk>` (Python 3.14), no per-app image because
`dev_requirements.txt` holds only the SDK. SDK must stay within the range `supervisely/versions.json`
allows for `min_instance_version`.

Keep: `config.json` `name`/`context_menu`, the result name suffix `(new shapes)`, project description
"new shapes", and that the source project is only read.

Gotchas: `ProjectThumbnail` crashes on a project without images (`_thumbnail_info` guards it).
`app.stop()` sends SIGINT to the process, so never call the real `finished` callback in tests.
SDK: AlphaMask → Bitmap raises when no pixel has alpha 255 (whole run fails, same as before).

Tests: `pytest` (unit, offline; includes the GUI through `Application.test_client` and the copy against a
fake API) · `SLY_CONTRACT_TESTS=1 SLY_CONTRACT_PROJECT_ID=<id> SLY_CONTRACT_WORKSPACE_ID=<test ws> pytest -m contract tests/contract`
(creates one project per `cases/*.env` in the test workspace, deletes nothing).
