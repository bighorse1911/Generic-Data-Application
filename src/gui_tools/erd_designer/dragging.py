from __future__ import annotations

def _table_name_at_canvas_point(self, x: float, y: float) -> str | None:
        for table_name in reversed(self._node_draw_order):
            bounds = self._node_bounds.get(table_name)
            if bounds is None:
                continue
            x1, y1, x2, y2 = bounds
            if x1 <= x <= x2 and y1 <= y <= y2:
                return table_name
        return None


def _on_erd_drag_start(self, event: tk.Event) -> None:
        if self.project is None:
            return
        canvas_x = float(self.erd_canvas.canvasx(event.x))
        canvas_y = float(self.erd_canvas.canvasy(event.y))
        table_name = self._table_name_at_canvas_point(canvas_x, canvas_y)
        if table_name is None:
            self._drag_table_name = None
            self._drag_offset = None
            return
        bounds = self._node_bounds.get(table_name)
        if bounds is None:
            return
        self._drag_table_name = table_name
        self._drag_offset = (canvas_x - bounds[0], canvas_y - bounds[1])


def _on_erd_drag_motion(self, event: tk.Event) -> None:
        if self._drag_table_name is None or self._drag_offset is None:
            return
        canvas_x = float(self.erd_canvas.canvasx(event.x))
        canvas_y = float(self.erd_canvas.canvasy(event.y))
        next_x = max(16, int(canvas_x - self._drag_offset[0]))
        next_y = max(16, int(canvas_y - self._drag_offset[1]))
        self._node_positions[self._drag_table_name] = (next_x, next_y)
        self._draw_erd()


def _on_erd_drag_end(self, _event: tk.Event) -> None:
        self._drag_table_name = None
        self._drag_offset = None
