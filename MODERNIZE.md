# Modernization notes: convert-class-shape

Rewrite of `convert-class-shape` to the `sly-app-standard` (local pilot, not released).
Base: `origin/master` @ 4b86de6. Branch `local/modernize`, nothing committed.

## Behaviour contract (kept)

**Entry point.** Context menu of an images project → "Transform" → Convert Class Shape. GUI session
(`task_location: workspace_tasks`, `isolate: true`). The modal window (`src/modal.html`) is informational
only; the project arrives as `modal.state.slyProjectId`. Non-images projects are rejected at startup.

**GUI.** Input card (source project thumbnail), Output card (Run button, progress, result project), and
one row per class (sorted by name): class name, color and shape, and a dropdown `remain unchanged` +
the shapes the SDK allows for that class (`geometry_type.allowed_transforms()`). A class without targets
(`any`) has a disabled dropdown. Run with nothing selected → warning dialog "Please, define at least one
transformation" and nothing is created. During the run the dropdowns and Run are disabled.

**Output.** A new images project in the source project's workspace:
- name `<source name>(new shapes)` (no space; the platform appends `_001`, … on conflicts), description `new shapes`;
- meta = source meta with the selected classes switched to the new shape (same names, colors, tags, settings);
- same datasets (names, nesting), same images added by id (no pixel re-upload) with their names and image meta;
- annotations converted per class:
  - SDK geometry conversion (`Label.convert`) for every changed class; one label can become several
    (bitmap with several blobs) or none; labels keep tags and description; image tags are kept;
  - Polygon → Multipolygon: polygons of one class sharing a binding key become one Multipolygon (first
    label's tags/description/binding kept); unbound polygons become one-part Multipolygons;
  - Multipolygon → Polygon: the parts share one binding key (the original or a new uuid4 hex);
  - classes left unchanged are copied as is.
- The task output is set to the new project; workflow lineage: source project in, new project out.
- When done, the session stops by itself; its page stays readable from the tasks list (offline snapshot).
- The source project is only read.

## Intentional changes

1. **Nested datasets are copied.** The old code listed only top-level datasets
   (`dataset.get_list(project_id)` without `recursive`): nested datasets and their images were silently
   dropped, and because the progress total counted all images the GUI never reached 100 % and never showed
   the result. Verified on #1317: old result had 2 empty datasets and 0 of 22 images; new has the full tree.
2. **Dropdowns no longer offer a class's own shape** (the SDK lists `rectangle` for Rectangle and
   `oriented_bbox` for OrientedBBox). Choosing it was a no-op that still created a plain copy; it now counts
   as "remain unchanged".
3. **New UI on `sly.Application` widgets** instead of the `gui_template` page: same three sections and
   texts; the class color is shown as a dot instead of a hex code, and the class list is always sorted by
   name (no column sort toggle).
4. **A failure during conversion no longer kills the session**: the Run request fails with the error
   (in production the SDK returns it to the page as `{title, message}`), the controls unlock and the user
   can retry. The partially filled project stays (as before). Not exercised on the instance.
5. **A project without images opens** (the old preview-URL call failed on `reference_image_url = None`;
   `ProjectThumbnail` has the same problem, guarded in `ui._thumbnail_info`). By code reading and unit test.
6. **Runs on the hardened image (Python 3.14)**; `supervisely[agent]` → `supervisely` (the `agent`
   extra, protobuf, was only needed by the legacy `AppService` runtime).
7. README: the transformations list now matches what the dropdowns show (AlphaMask, OrientedBBox,
   Bitmap/AlphaMask → Multipolygon were already offered), nested datasets are mentioned, and the wrong
   "colors of new classes will be generated randomly" is fixed (colors were always kept).

Known issue kept (SDK, not app): AlphaMask → Bitmap raises "Creating a bitmap with an empty mask" when no
pixel of a mask has alpha 255 (`AlphaMask.convert` keeps only 255). Old and new fail the run the same way.

## Dropped

- `AppService` runtime, `src/gui.html`, `src/convert_class_shape.py` (module-level env reads and globals).
- `src/conversion.py` → `src/core/shapes.py` (pure) + `src/converter.py` + `src/platform_io.py`.
- `src/workflow.py` → `src/platform_io.py` (same lineage calls).
- `debug.env` (with token placeholders) → `local.env` + `~/supervisely.env`.
- `tests/test_conversion.py` (unittest) → ported into `tests/unit/test_shapes.py`;
  `tests/e2e_round_trip.py` (deleted the projects it created) → `tests/contract/` + the equivalence check below.

## Versions and image

- **Image: `supervisely/base-py-sdk-hardened:6.74.34`** (was the shared `supervisely/base-py-sdk:6.74.34`,
  Python 3.8). No deps beyond the SDK, so no per-app image. Tag checked on Docker Hub.
- **SDK stays at 6.74.34** with `min_instance_version` 6.17.22: CI allows [6.74.29, 6.74.35) for it.
  A newer SDK needs `min_instance_version` ≥ 6.18.x and drops older instances — a product decision.
- **Open decision:** `.github/workflows/release.yml` still builds `supervisely/convert-class-shape:<tag>`
  from the template on every release although `config.json` no longer uses it (same in the export-to-coco
  pilot). Left unchanged.
- README screenshots show the old UI; not retaken.

## Verification (2026-10-25, dev.internal.supervisely.com, instance 6.18.7)

- **Unit tests** 35/35 (macOS venv, Python 3.14.3) and 35/35 inside `base-py-sdk-hardened:6.74.34`
  (Python 3.14.7, amd64). `ruff check` / `ruff format --check` clean. Old unittest suite passes on old code.
- **Equivalence, generated data:** old `convert_annotation`/`build_destination_meta` (`git show origin/HEAD`)
  vs new on 400 random metas / 1014 annotations / 6062 labels covering every geometry and every allowed
  target (37 pairs), random bindings, tags, descriptions, `any` classes; compared order-independently with
  newly generated binding keys replaced by their group. **0 differences**; both raise identically on the
  AlphaMask → Bitmap SDK issue (36 cases); metas identical; "nothing selected" agrees in 50 cases.
- **Equivalence, real projects:** old `convert_project` (result redirected to the sandbox workspace) vs new on
  #46 Lemons (Annotated), #26 Lemons (Bitmap), #27 Lemons (Rectangle), #1317 Fruits Nested and a synthetic
  project #9390 (bound polygons with holes, multipolygons, polyline, point, bitmap, keypoints, nested
  dataset). Metas identical, every common image identical (objects, tags, binding groups, image meta, hash);
  the only difference is intentional change 1 (#1317: 0 vs 22 images; #9390: nested image missing in old).
  The 22 nested images of #1317 match the old conversion applied in memory.
- **Contract tests** (`cases/*.env`): #9390 3 passed; #1317 2 passed, 1 skipped (rectangles cannot become
  multipolygon/rectangle).
- **In the real image, production mode:** `uvicorn src.main:app` in `base-py-sdk-hardened:6.74.34` with
  `ENV=production` on debug task 62691, driven over HTTP like the browser: empty Run → warning dialog;
  Run with 7 conversions → project #9404 (2 datasets incl. nested, all classes converted), task output set
  to it, workflow calls without errors, offline page saved, session shut down by itself; no warnings or errors.
- Not verified: the page in a real browser on the platform, a failure mid-run (change 4), very large projects.
