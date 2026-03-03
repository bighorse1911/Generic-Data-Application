from __future__ import annotations


def _column_spec_from_editor(self, *, action_prefix: str) -> ColumnSpec:
    name = self.col_name_var.get().strip()
    dtype = self.col_dtype_var.get().strip()

    if dtype == "float":
        raise ValueError(
            f"{action_prefix} / Type: dtype 'float' is deprecated for new GUI columns. "
            "Fix: choose dtype='decimal' for new columns; keep legacy float only in loaded JSON."
        )
    if dtype not in DTYPES:
        allowed = ", ".join(DTYPES)
        raise ValueError(
            f"{action_prefix} / Type: unsupported dtype '{dtype}'. "
            f"Fix: choose one of: {allowed}."
        )

    if not name:
        raise ValueError(
            _gui_error(
                f"{action_prefix} / Name",
                "column name cannot be empty",
                "enter a non-empty column name",
            )
        )

    nullable = bool(self.col_nullable_var.get())
    pk = bool(self.col_pk_var.get())
    unique = bool(self.col_unique_var.get())

    min_s = self.col_min_var.get().strip()
    max_s = self.col_max_var.get().strip()
    try:
        min_v = float(min_s) if min_s != "" else None
    except (TypeError, ValueError) as exc:
        raise ValueError(
            _gui_error(
                f"{action_prefix} / Min value",
                f"min value '{self.col_min_var.get()}' must be numeric",
                "enter a numeric min value or leave it empty",
            )
        ) from exc
    try:
        max_v = float(max_s) if max_s != "" else None
    except (TypeError, ValueError) as exc:
        raise ValueError(
            _gui_error(
                f"{action_prefix} / Max value",
                f"max value '{self.col_max_var.get()}' must be numeric",
                "enter a numeric max value or leave it empty",
            )
        ) from exc

    choices_s = self.col_choices_var.get().strip()
    choices = [c.strip() for c in choices_s.split(",") if c.strip()] if choices_s else None
    pattern = self.col_pattern_var.get().strip() or None

    gen_name = self.col_generator_var.get().strip() or None
    if gen_name is not None:
        valid_generators = valid_generators_for_dtype(dtype)
        if gen_name not in valid_generators:
            allowed = [g for g in valid_generators if g]
            allowed_display = ", ".join(allowed) if allowed else "(none)"
            raise ValueError(
                _gui_error(
                    f"{action_prefix} / Generator",
                    f"generator '{gen_name}' is not valid for dtype '{dtype}'",
                    f"choose one of: {allowed_display}",
                )
            )
    params_text = self.col_params_var.get().strip()
    params = None
    if params_text:
        try:
            obj = json.loads(params_text)
            if not isinstance(obj, dict):
                raise ValueError(
                    _gui_error(
                        f"{action_prefix} / Params JSON",
                        "value must be a JSON object",
                        "use an object like {\"path\": \"...\", \"column_index\": 0}",
                    )
                )
            params = obj
        except Exception as exc:
            raise ValueError(
                _gui_error(
                    f"{action_prefix} / Params JSON",
                    f"invalid JSON ({exc})",
                    "provide valid JSON object syntax or leave Params JSON empty",
                )
            ) from exc

    depends_on = self._parse_column_name_csv(
        self.col_depends_var.get(),
        location=action_prefix,
        field_name="depends_on",
    )
    depends_on_list = list(depends_on or [])

    if gen_name == "derived_expr":
        if params is None:
            raise ValueError(
                _gui_error(
                    f"{action_prefix} / Derived expression",
                    "params.expression is required",
                    "set Params JSON to an object like {\"expression\": \"a + b\"}",
                )
            )
        expression_raw = params.get("expression")
        if not isinstance(expression_raw, str) or expression_raw.strip() == "":
            raise ValueError(
                _gui_error(
                    f"{action_prefix} / Derived expression",
                    "params.expression must be a non-empty string",
                    "set params.expression to a valid derived expression",
                )
            )
        try:
            referenced_columns = list(
                extract_derived_expression_references(
                    expression_raw,
                    location=f"{action_prefix} / Derived expression",
                )
            )
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        for ref_name in referenced_columns:
            if ref_name == name:
                raise ValueError(
                    _gui_error(
                        f"{action_prefix} / Derived expression",
                        "expression cannot reference the target column itself",
                        "remove self references from params.expression",
                    )
                )
            if ref_name not in depends_on_list:
                depends_on_list.append(ref_name)
        self.col_depends_var.set(", ".join(depends_on_list))

    depends_on_out = depends_on_list or None

    return ColumnSpec(
        name=name,
        dtype=dtype,
        nullable=nullable,
        primary_key=pk,
        unique=unique,
        min_value=min_v,
        max_value=max_v,
        choices=choices,
        pattern=pattern,
        generator=gen_name,
        params=params,
        depends_on=depends_on_out,
    )

def _parse_column_name_csv(
    self,
    raw_value: str,
    *,
    location: str,
    field_name: str,
) -> list[str] | None:
    value = raw_value.strip()
    if value == "":
        return None
    names = [part.strip() for part in value.split(",")]
    if any(name == "" for name in names):
        raise ValueError(
            f"{location}: {field_name} contains an empty column name. "
            "Fix: remove extra commas and provide comma-separated column names."
        )
    if len(set(names)) != len(names):
        raise ValueError(
            f"{location}: {field_name} contains duplicate column names. "
            "Fix: list each column only once."
        )
    return names

def _parse_optional_column_name(
    self,
    raw_value: str,
    *,
    location: str,
    field_name: str,
) -> str | None:
    value = raw_value.strip()
    if value == "":
        return None
    if "," in value:
        raise ValueError(
            f"{location}: {field_name} must contain exactly one column name. "
            f"Fix: provide one name or leave {field_name} empty."
        )
    return value

def _table_pk_name(self, table_name: str) -> str:
    for t in self.project.tables:
        if t.table_name == table_name:
            for c in t.columns:
                if c.primary_key:
                    return c.name
    raise ValueError(
        _gui_error(
            f"Table '{table_name}'",
            "no primary key column was found",
            "add or keep one column with primary_key=true",
        )
    )

def _int_columns(self, table_name: str) -> list[str]:
    for t in self.project.tables:
        if t.table_name == table_name:
            return [c.name for c in t.columns if c.dtype == "int"]
    return []


