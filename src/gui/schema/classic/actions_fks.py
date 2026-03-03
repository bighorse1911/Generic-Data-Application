from __future__ import annotations



def _refresh_fk_dropdowns(self) -> None:
    names = [t.table_name for t in self.project.tables]

    self.fk_parent_combo["values"] = names
    self.fk_child_combo["values"] = names

    if names:
        if not self.fk_parent_table_var.get():
            self.fk_parent_table_var.set(names[0])
        if not self.fk_child_table_var.get():
            self.fk_child_table_var.set(names[0])

    self._sync_fk_defaults()

def _sync_fk_defaults(self) -> None:
    child = self.fk_child_table_var.get().strip()
    if not child:
        self.fk_child_col_combo["values"] = []
        self.fk_child_column_var.set("")
        return

    int_cols = self._int_columns(child)
    self.fk_child_col_combo["values"] = int_cols

    pk = ""
    try:
        pk = self._table_pk_name(child)
    except Exception:
        pk = ""

    preferred = ""
    for c in int_cols:
        if c != pk and c.endswith("_id"):
            preferred = c
            break

    if preferred:
        self.fk_child_column_var.set(preferred)
    elif int_cols:
        non_pk = [c for c in int_cols if c != pk]
        self.fk_child_column_var.set(non_pk[0] if non_pk else int_cols[0])
    else:
        self.fk_child_column_var.set("")

def _refresh_fks_tree(self) -> None:
    for item in self.fks_tree.get_children():
        self.fks_tree.delete(item)

    for i, fk in enumerate(self.project.foreign_keys):
        dist = fk.child_count_distribution
        dist_label = ""
        if isinstance(dist, dict):
            dist_type = str(dist.get("type", "")).strip().lower()
            if dist_type == "poisson":
                dist_label = f"poisson(lambda={dist.get('lambda')})"
            elif dist_type == "zipf":
                dist_label = f"zipf(s={dist.get('s')})"
            elif dist_type == "uniform":
                dist_label = "uniform"
            elif dist_type:
                dist_label = dist_type
        self.fks_tree.insert(
            "",
            tk.END,
            values=(
                fk.parent_table,
                fk.parent_column,
                fk.child_table,
                fk.child_column,
                fk.min_children,
                fk.max_children,
                dist_label,
            ),
            tags=(str(i),),
        )

def _selected_fk_index(self) -> int | None:
    sel = self.fks_tree.selection()
    if not sel:
        return None
    return int(self.fks_tree.item(sel[0], "tags")[0])

def _add_fk(self) -> None:
    before_project = self.project
    try:
        self._apply_project_vars_to_model()

        parent = self.fk_parent_table_var.get().strip()
        child = self.fk_child_table_var.get().strip()
        child_col = self.fk_child_column_var.get().strip()

        if not parent or not child or not child_col:
            raise ValueError(
                _gui_error(
                    "Add relationship",
                    "parent table, child table, and child FK column are required",
                    "choose all three fields before adding the relationship",
                )
            )

        if parent == child:
            raise ValueError(
                _gui_error(
                    "Add relationship",
                    "parent and child tables must be different",
                    "choose two different tables",
                )
            )

        parent_pk = self._table_pk_name(parent)
        child_pk = self._table_pk_name(child)

        try:
            min_k = int(self.fk_min_children_var.get().strip())
        except (TypeError, ValueError) as exc:
            raise ValueError(
                _gui_error(
                    "Add relationship / Cardinality",
                    f"min_children '{self.fk_min_children_var.get()}' must be an integer",
                    "enter a whole number for Min children",
                )
            ) from exc
        try:
            max_k = int(self.fk_max_children_var.get().strip())
        except (TypeError, ValueError) as exc:
            raise ValueError(
                _gui_error(
                    "Add relationship / Cardinality",
                    f"max_children '{self.fk_max_children_var.get()}' must be an integer",
                    "enter a whole number for Max children",
                )
            ) from exc
        if min_k <= 0 or max_k <= 0:
            raise ValueError(
                _gui_error(
                    "Add relationship / Cardinality",
                    "min_children and max_children must be > 0",
                    "enter positive integer bounds",
                )
            )
        if min_k > max_k:
            raise ValueError(
                _gui_error(
                    "Add relationship / Cardinality",
                    "min_children cannot exceed max_children",
                    "set min_children <= max_children",
                )
            )

        parent_selection = None
        parent_selection_text = self.fk_parent_selection_var.get().strip()
        if parent_selection_text:
            try:
                parsed_parent_selection = json.loads(parent_selection_text)
            except Exception as exc:
                raise ValueError(
                    _gui_error(
                        "Add relationship / Parent selection JSON",
                        f"invalid JSON ({exc})",
                        "provide a JSON object like {\"parent_attribute\": \"segment\", \"weights\": {\"VIP\": 3, \"STD\": 1}, \"default_weight\": 1}",
                    )
                ) from exc
            if not isinstance(parsed_parent_selection, dict):
                raise ValueError(
                    _gui_error(
                        "Add relationship / Parent selection JSON",
                        "value must be a JSON object",
                        "set parent selection JSON to an object or leave it empty",
                    )
                )
            parent_selection = parsed_parent_selection

        child_count_distribution = None
        child_count_distribution_text = self.fk_child_count_distribution_var.get().strip()
        if child_count_distribution_text:
            try:
                parsed_child_count_distribution = json.loads(child_count_distribution_text)
            except Exception as exc:
                raise ValueError(
                    _gui_error(
                        "Add relationship / Child count distribution JSON",
                        f"invalid JSON ({exc})",
                        "provide a JSON object like {\"type\": \"poisson\", \"lambda\": 1.5} or {\"type\": \"zipf\", \"s\": 1.2}",
                    )
                ) from exc
            if not isinstance(parsed_child_count_distribution, dict):
                raise ValueError(
                    _gui_error(
                        "Add relationship / Child count distribution JSON",
                        "value must be a JSON object",
                        "set child count distribution JSON to an object or leave it empty",
                    )
                )
            child_count_distribution = parsed_child_count_distribution

        # # MVP constraint: child can only have one FK
        # if any(fk.child_table == child for fk in self.project.foreign_keys):
        #     raise ValueError(f"Table '{child}' already has a foreign key (MVP supports 1 FK per child table).")

        if child_col == child_pk:
            raise ValueError(
                _gui_error(
                    "Add relationship / Child FK column",
                    "child FK column cannot be the child primary key",
                    "choose a non-PK int column for the child FK",
                )
            )

        if child_col not in self._int_columns(child):
            raise ValueError(
                _gui_error(
                    "Add relationship / Child FK column",
                    "child FK column must be dtype int",
                    "choose an int column in the child table",
                )
            )

        # A child column can only be used by one FK
        if any(fk.child_table == child and fk.child_column == child_col for fk in self.project.foreign_keys):
            raise ValueError(
                _gui_error(
                    "Add relationship / Child FK column",
                    f"column '{child}.{child_col}' is already used as a foreign key",
                    "choose a different child column",
                )
            )


        fks = list(self.project.foreign_keys)
        fks.append(
            ForeignKeySpec(
                child_table=child,
                child_column=child_col,
                parent_table=parent,
                parent_column=parent_pk,
                min_children=min_k,
                max_children=max_k,
                parent_selection=parent_selection,
                child_count_distribution=child_count_distribution,
            )
        )

        new_project = SchemaProject(
            name=self.project.name,
            seed=self.project.seed,
            tables=self.project.tables,
            foreign_keys=fks,
            timeline_constraints=self.project.timeline_constraints,
            data_quality_profiles=self.project.data_quality_profiles,
            sample_profile_fits=self.project.sample_profile_fits,
            locale_identity_bundles=self.project.locale_identity_bundles,
        )
        validate_project(new_project)

        self.project = new_project
        self._refresh_fks_tree()
        self.status_var.set("Relationship added.")
        self._mark_dirty_if_project_changed(before_project, reason="relationship changes")
    except Exception as exc:
        self._show_error_dialog("Add relationship failed", str(exc))
    self._run_validation()

def _remove_selected_fk(self) -> None:
    idx = self._selected_fk_index()
    if idx is None:
        return
    before_project = self.project
    try:
        self._apply_project_vars_to_model()

        fks = list(self.project.foreign_keys)
        removed = fks[idx]
        fks.pop(idx)

        new_project = SchemaProject(
            name=self.project.name,
            seed=self.project.seed,
            tables=self.project.tables,
            foreign_keys=fks,
            timeline_constraints=self.project.timeline_constraints,
            data_quality_profiles=self.project.data_quality_profiles,
            sample_profile_fits=self.project.sample_profile_fits,
            locale_identity_bundles=self.project.locale_identity_bundles,
        )
        validate_project(new_project)

        self.project = new_project
        self._refresh_fks_tree()
        self.status_var.set(
            f"Removed relationship: {removed.parent_table}.{removed.parent_column} → {removed.child_table}.{removed.child_column}"
        )
        self._mark_dirty_if_project_changed(before_project, reason="relationship changes")
    except Exception as exc:
        self._show_error_dialog("Remove relationship failed", str(exc))
    self._run_validation()

