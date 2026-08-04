# Tests

Run the binding-aware conversion tests with the SDK version pinned by the app:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

The live end-to-end test creates an image project containing two bound Polygon
labels, converts it to one two-part Multipolygon, and converts it back to two
bound Polygon labels:

```bash
python tests/e2e_round_trip.py --workspace-id <writable-workspace-id>
```

It checks project metadata, raw annotation JSON stored by the server, binding
cardinality, part/object counts, and exact SDK geometry payloads across the full
round trip. Temporary projects are removed in `finally`; pass `--keep-projects`
only when they are needed for manual inspection.
