# 082 - P13 Scalable Search/Filter Pipeline

## Context
- Priority P13 in `NEXT_DECISIONS.md` required better search responsiveness for large schema authoring sessions.
- Existing `schema_project_v2` search behavior filtered columns/FKs by detaching and reattaching all Treeview rows on each query change.
- This full-row-pass detach/reattach approach increased keystroke latency as row counts grew.

## Decision
- Replace detach/reattach filtering in `SchemaEditorBaseScreen` with an indexed + paged pipeline:
  - build cached searchable row indexes for columns and relationships,
  - apply tokenized query matching against cached lowercase search text,
  - render only the active page (`FILTER_PAGE_SIZE`) into the Treeview.
- Add explicit page controls (`Prev page`/`Next page`) and row-range status text for both columns and relationships.
- Preserve source-row identity by carrying original row indexes in Treeview tags, so edit/remove/select behavior remains compatible with existing callbacks.
- Validation-jump flows now clear active column/FK filters when needed and page directly to the target source row.

## Consequences
- Search updates no longer perform full detach/reattach passes across all rows on each keystroke.
- Large tables/FK lists keep bounded render cost per query update because only one page is inserted into the Treeview.
- Existing authoring actions that depend on source indexes (`_selected_column_index`, `_selected_fk_index`) remain stable.
- Regression coverage in `tests/test_gui_search_filter_pipeline.py` validates paging behavior and source-index correctness for columns and relationships.
