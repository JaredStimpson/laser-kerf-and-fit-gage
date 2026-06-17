from __future__ import annotations

import argparse
import html
import json
import math
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any, Iterable


APP_VERSION = "0.1.0"
PARAM_DIR = Path.home() / "Documents" / "Laser Tester Generator Parameters"
EXPORT_DIR = Path.home() / "Documents" / "Laser Tester Generator Exports"

Point = tuple[float, float]


@dataclass
class Polyline:
    points: list[Point]
    closed: bool = True
    layer: str = "CUT"


@dataclass
class Line:
    start: Point
    end: Point
    layer: str = "MARK"


@dataclass
class Text:
    x: float
    y: float
    text: str
    size: float = 2.5
    layer: str = "MARK"
    anchor: str = "middle"
    rotation: float = 0.0


Entity = Polyline | Line | Text


@dataclass
class Drawing:
    entities: list[Entity]
    title: str = "laser-tester"
    units: str = "mm"

    def bounds(self) -> tuple[float, float, float, float]:
        xs: list[float] = []
        ys: list[float] = []
        for entity in self.entities:
            if isinstance(entity, Polyline):
                xs.extend(point[0] for point in entity.points)
                ys.extend(point[1] for point in entity.points)
            elif isinstance(entity, Line):
                xs.extend([entity.start[0], entity.end[0]])
                ys.extend([entity.start[1], entity.end[1]])
            elif isinstance(entity, Text):
                width = max(len(entity.text) * entity.size * 0.55, entity.size)
                height = entity.size
                xs.extend([entity.x - width / 2, entity.x + width / 2])
                ys.extend([entity.y - height / 2, entity.y + height / 2])
        if not xs:
            return (0.0, 0.0, 1.0, 1.0)
        return (min(xs), min(ys), max(xs), max(ys))


@dataclass
class KerfParams:
    outer_width: float = 80.0
    outer_height: float = 70.0
    cutout_width: float = 52.0
    cutout_height: float = 34.0
    cutout_x: float = 10.0
    cutout_y: float = 26.0
    gap_scale_range: float = 2.0
    gap_scale_increment: float = 0.1
    major_tick_increment: float = 0.5
    scale_offset: float = 4.0
    minor_tick_length: float = 1.4
    major_tick_length: float = 3.4
    label_size: float = 2.2
    include_labels: bool = True


@dataclass
class FitParams:
    nominal_tab_width: float = 20.0
    tab_height: float = 24.0
    shoulder_width: float = 8.0
    body_height: float = 28.0
    slot_depth: float = 28.0
    allowance_start: float = -0.30
    allowance_stop: float = 0.30
    allowance_step: float = 0.10
    strip_height: float = 44.0
    strip_margin: float = 10.0
    slot_spacing: float = 16.0
    label_size: float = 2.4
    include_labels: bool = True


KERF_FIELD_LABELS = {
    "outer_width": "Outer width (mm)",
    "outer_height": "Outer height (mm)",
    "cutout_width": "Cutout/coupon width (mm)",
    "cutout_height": "Cutout/coupon height (mm)",
    "cutout_x": "Cutout X from left (mm)",
    "cutout_y": "Cutout Y from top (mm)",
    "gap_scale_range": "Gap scale range (mm)",
    "gap_scale_increment": "Gap tick increment (mm)",
    "major_tick_increment": "Major tick increment (mm)",
    "scale_offset": "Scale offset from cutout (mm)",
    "minor_tick_length": "Minor tick length (mm)",
    "major_tick_length": "Major tick length (mm)",
    "label_size": "Label text height (mm)",
    "include_labels": "Include engraved labels",
}


FIT_FIELD_LABELS = {
    "nominal_tab_width": "Nominal tab width (mm)",
    "tab_height": "Tab height (mm)",
    "shoulder_width": "Shoulder width each side (mm)",
    "body_height": "Coupon body height (mm)",
    "slot_depth": "Slot depth (mm)",
    "allowance_start": "Allowance start (mm)",
    "allowance_stop": "Allowance stop (mm)",
    "allowance_step": "Allowance step (mm)",
    "strip_height": "Strip height (mm)",
    "strip_margin": "Strip margin (mm)",
    "slot_spacing": "Slot spacing (mm)",
    "label_size": "Label text height (mm)",
    "include_labels": "Include engraved labels",
}


KERF_GENERAL_FIELDS = [
    "outer_width",
    "outer_height",
    "cutout_width",
    "cutout_height",
    "gap_scale_range",
    "gap_scale_increment",
    "include_labels",
]


KERF_ADVANCED_FIELDS = [
    "cutout_x",
    "cutout_y",
    "major_tick_increment",
    "scale_offset",
    "minor_tick_length",
    "major_tick_length",
    "label_size",
]


FIT_GENERAL_FIELDS = [
    "nominal_tab_width",
    "tab_height",
    "slot_depth",
    "allowance_start",
    "allowance_stop",
    "allowance_step",
    "include_labels",
]


FIT_ADVANCED_FIELDS = [
    "shoulder_width",
    "body_height",
    "strip_height",
    "strip_margin",
    "slot_spacing",
    "label_size",
]


def rect(x: float, y: float, width: float, height: float, layer: str = "CUT") -> Polyline:
    return Polyline(
        [
            (x, y),
            (x + width, y),
            (x + width, y + height),
            (x, y + height),
        ],
        closed=True,
        layer=layer,
    )


def mm(value: float) -> str:
    if abs(value) < 0.0000005:
        value = 0.0
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return text or "0"


def ensure_positive(name: str, value: float) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero.")


def is_major_tick(value: float, major_increment: float) -> bool:
    if major_increment <= 0:
        return False
    nearest = round(value / major_increment) * major_increment
    return abs(value - nearest) < 0.00001


def generate_kerf(params: KerfParams) -> Drawing:
    ensure_positive("Outer width", params.outer_width)
    ensure_positive("Outer height", params.outer_height)
    ensure_positive("Cutout width", params.cutout_width)
    ensure_positive("Cutout height", params.cutout_height)
    ensure_positive("Gap scale range", params.gap_scale_range)
    ensure_positive("Gap tick increment", params.gap_scale_increment)

    if params.cutout_x < 0 or params.cutout_y < 0:
        raise ValueError("Cutout X and Y must be zero or greater.")
    if params.cutout_x + params.cutout_width > params.outer_width:
        raise ValueError("Cutout extends past the outer width.")
    if params.cutout_y + params.cutout_height > params.outer_height:
        raise ValueError("Cutout extends past the outer height.")
    if params.cutout_y - params.gap_scale_range < 0:
        raise ValueError("Cutout Y must leave room above it for the gap scale.")

    entities: list[Entity] = [
        rect(0, 0, params.outer_width, params.outer_height),
        rect(params.cutout_x, params.cutout_y, params.cutout_width, params.cutout_height),
    ]

    ruler_x = params.cutout_x + params.cutout_width + params.scale_offset
    if ruler_x + params.major_tick_length > params.outer_width:
        ruler_x = params.cutout_x + params.cutout_width - params.scale_offset
        tick_direction = -1.0
    else:
        tick_direction = 1.0

    entities.append(
        Line(
            (ruler_x, params.cutout_y),
            (ruler_x, params.cutout_y - params.gap_scale_range),
            layer="MARK",
        )
    )

    tick_count = int(math.floor(params.gap_scale_range / params.gap_scale_increment + 0.5))
    for index in range(tick_count + 1):
        value = round(index * params.gap_scale_increment, 6)
        if value > params.gap_scale_range + 0.00001:
            continue
        y = params.cutout_y - value
        major = is_major_tick(value, params.major_tick_increment) or index == 0
        tick_length = params.major_tick_length if major else params.minor_tick_length
        entities.append(
            Line(
                (ruler_x, y),
                (ruler_x + tick_direction * tick_length, y),
                layer="MARK",
            )
        )
        if params.include_labels and major:
            label_x = ruler_x + tick_direction * (tick_length + 3.0)
            anchor = "start" if tick_direction > 0 else "end"
            entities.append(
                Text(
                    label_x,
                    y + params.label_size * 0.35,
                    f"{value:.1f}",
                    size=params.label_size,
                    anchor=anchor,
                    layer="MARK",
                )
            )

    if params.include_labels:
        entities.extend(
            [
                Text(
                    params.outer_width / 2,
                    -3.0,
                    "Kerf gauge: slide coupon to one side, read total gap",
                    size=params.label_size,
                    layer="MARK",
                ),
                Text(
                    params.outer_width + 8.0,
                    params.outer_height / 2,
                    f"{params.outer_height:g} mm reference",
                    size=params.label_size,
                    layer="MARK",
                    rotation=90.0,
                ),
                Line(
                    (params.outer_width + 3.0, 0),
                    (params.outer_width + 3.0, params.outer_height),
                    layer="MARK",
                ),
                Line(
                    (params.outer_width + 1.5, 0),
                    (params.outer_width + 4.5, 0),
                    layer="MARK",
                ),
                Line(
                    (params.outer_width + 1.5, params.outer_height),
                    (params.outer_width + 4.5, params.outer_height),
                    layer="MARK",
                ),
            ]
        )

    return Drawing(entities, title="kerf-tester")


def allowance_values(start: float, stop: float, step: float) -> list[float]:
    ensure_positive("Allowance step", step)
    if stop < start:
        raise ValueError("Allowance stop must be greater than or equal to allowance start.")
    values: list[float] = []
    current = start
    guard = 0
    while current <= stop + step * 0.25:
        values.append(round(current, 6))
        current += step
        guard += 1
        if guard > 200:
            raise ValueError("Too many allowance values. Increase the step or narrow the range.")
    return values


def generate_fit(params: FitParams) -> Drawing:
    ensure_positive("Nominal tab width", params.nominal_tab_width)
    ensure_positive("Tab height", params.tab_height)
    ensure_positive("Shoulder width", params.shoulder_width)
    ensure_positive("Body height", params.body_height)
    ensure_positive("Slot depth", params.slot_depth)
    ensure_positive("Strip height", params.strip_height)
    ensure_positive("Strip margin", params.strip_margin)
    ensure_positive("Slot spacing", params.slot_spacing)

    values = allowance_values(params.allowance_start, params.allowance_stop, params.allowance_step)
    slot_widths = [params.nominal_tab_width + value for value in values]
    if any(width <= 0 for width in slot_widths):
        raise ValueError("Allowance range creates a slot width of zero or less.")
    if params.slot_depth >= params.strip_height:
        raise ValueError("Slot depth must be smaller than strip height.")

    max_slot_width = max(slot_widths)
    slot_pitch = max_slot_width + params.slot_spacing
    strip_width = params.strip_margin * 2 + max_slot_width + (len(values) - 1) * slot_pitch
    slot_y = (params.strip_height - params.slot_depth) / 2

    entities: list[Entity] = [rect(0, 0, strip_width, params.strip_height)]

    for index, (value, slot_width) in enumerate(zip(values, slot_widths)):
        slot_center_x = params.strip_margin + max_slot_width / 2 + index * slot_pitch
        slot_x = slot_center_x - slot_width / 2
        entities.append(rect(slot_x, slot_y, slot_width, params.slot_depth))
        if params.include_labels:
            entities.append(
                Text(
                    slot_center_x,
                    params.strip_height + params.label_size + 2.0,
                    f"{value:+.2f}",
                    size=params.label_size,
                    layer="MARK",
                )
            )

    coupon_total_width = params.nominal_tab_width + 2 * params.shoulder_width
    coupon_x = params.strip_margin
    coupon_y = params.strip_height + params.label_size + 12.0
    coupon_height = params.tab_height + params.body_height
    shoulder_left = coupon_x + params.shoulder_width
    shoulder_right = shoulder_left + params.nominal_tab_width

    entities.append(
        Polyline(
            [
                (shoulder_left, coupon_y),
                (shoulder_right, coupon_y),
                (shoulder_right, coupon_y + params.tab_height),
                (coupon_x + coupon_total_width, coupon_y + params.tab_height),
                (coupon_x + coupon_total_width, coupon_y + coupon_height),
                (coupon_x, coupon_y + coupon_height),
                (coupon_x, coupon_y + params.tab_height),
                (shoulder_left, coupon_y + params.tab_height),
            ],
            closed=True,
            layer="CUT",
        )
    )

    if params.include_labels:
        entities.extend(
            [
                Text(
                    coupon_x + coupon_total_width / 2,
                    coupon_y + coupon_height + params.label_size + 2.0,
                    "matching coupon",
                    size=params.label_size,
                    layer="MARK",
                ),
                Text(
                    strip_width / 2,
                    -3.0,
                    "Fit allowance slots: slot width = nominal tab width + allowance",
                    size=params.label_size,
                    layer="MARK",
                ),
            ]
        )

    return Drawing(entities, title="fit-allowance-tester")


def layer_color(layer: str) -> str:
    return "#000000" if layer == "CUT" else "#777777"


def svg_anchor(anchor: str) -> str:
    return {"start": "start", "end": "end"}.get(anchor, "middle")


def write_svg(drawing: Drawing, path: Path, margin: float = 6.0) -> None:
    min_x, min_y, max_x, max_y = drawing.bounds()
    width = max_x - min_x + margin * 2
    height = max_y - min_y + margin * 2
    view_x = min_x - margin
    view_y = min_y - margin

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{mm(width)}mm" height="{mm(height)}mm" '
            f'viewBox="{mm(view_x)} {mm(view_y)} {mm(width)} {mm(height)}">'
        ),
        f'  <title>{html.escape(drawing.title)}</title>',
        '  <g fill="none" stroke-linecap="square" stroke-linejoin="miter">',
    ]

    for entity in drawing.entities:
        if isinstance(entity, Polyline):
            if not entity.points:
                continue
            d = [f"M {mm(entity.points[0][0])} {mm(entity.points[0][1])}"]
            for x, y in entity.points[1:]:
                d.append(f"L {mm(x)} {mm(y)}")
            if entity.closed:
                d.append("Z")
            lines.append(
                f'    <path d="{" ".join(d)}" stroke="{layer_color(entity.layer)}" '
                f'stroke-width="0.1" data-layer="{html.escape(entity.layer)}" />'
            )
        elif isinstance(entity, Line):
            lines.append(
                f'    <line x1="{mm(entity.start[0])}" y1="{mm(entity.start[1])}" '
                f'x2="{mm(entity.end[0])}" y2="{mm(entity.end[1])}" '
                f'stroke="{layer_color(entity.layer)}" stroke-width="0.08" '
                f'data-layer="{html.escape(entity.layer)}" />'
            )
        elif isinstance(entity, Text):
            transform = ""
            if entity.rotation:
                transform = f' transform="rotate({mm(entity.rotation)} {mm(entity.x)} {mm(entity.y)})"'
            lines.append(
                f'    <text x="{mm(entity.x)}" y="{mm(entity.y)}" '
                f'font-family="Arial, sans-serif" font-size="{mm(entity.size)}" '
                f'text-anchor="{svg_anchor(entity.anchor)}" fill="{layer_color(entity.layer)}" '
                f'stroke="none" data-layer="{html.escape(entity.layer)}"{transform}>'
                f'{html.escape(entity.text)}</text>'
            )

    lines.extend(["  </g>", "</svg>", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def dxf_pair(code: int, value: Any) -> list[str]:
    return [str(code), str(value)]


def dxf_line(start: Point, end: Point, layer: str) -> list[str]:
    return (
        dxf_pair(0, "LINE")
        + dxf_pair(8, layer)
        + dxf_pair(10, mm(start[0]))
        + dxf_pair(20, mm(start[1]))
        + dxf_pair(30, "0")
        + dxf_pair(11, mm(end[0]))
        + dxf_pair(21, mm(end[1]))
        + dxf_pair(31, "0")
    )


def dxf_text(entity: Text) -> list[str]:
    align_code = {"start": 0, "middle": 1, "end": 2}.get(entity.anchor, 1)
    lines = (
        dxf_pair(0, "TEXT")
        + dxf_pair(8, entity.layer)
        + dxf_pair(10, mm(entity.x))
        + dxf_pair(20, mm(entity.y))
        + dxf_pair(30, "0")
        + dxf_pair(40, mm(entity.size))
        + dxf_pair(1, entity.text)
        + dxf_pair(50, mm(-entity.rotation))
        + dxf_pair(72, align_code)
    )
    if align_code:
        lines += dxf_pair(11, mm(entity.x)) + dxf_pair(21, mm(entity.y)) + dxf_pair(31, "0")
    return lines


def write_dxf(drawing: Drawing, path: Path) -> None:
    lines: list[str] = []
    lines += dxf_pair(0, "SECTION") + dxf_pair(2, "HEADER")
    lines += dxf_pair(9, "$INSUNITS") + dxf_pair(70, "4")
    lines += dxf_pair(0, "ENDSEC")
    lines += dxf_pair(0, "SECTION") + dxf_pair(2, "TABLES")
    lines += dxf_pair(0, "TABLE") + dxf_pair(2, "LAYER") + dxf_pair(70, "2")
    for layer_name, color in [("CUT", 1), ("MARK", 8)]:
        lines += dxf_pair(0, "LAYER")
        lines += dxf_pair(2, layer_name)
        lines += dxf_pair(70, "0")
        lines += dxf_pair(62, color)
        lines += dxf_pair(6, "CONTINUOUS")
    lines += dxf_pair(0, "ENDTAB")
    lines += dxf_pair(0, "ENDSEC")
    lines += dxf_pair(0, "SECTION") + dxf_pair(2, "ENTITIES")

    for entity in drawing.entities:
        if isinstance(entity, Polyline):
            points = entity.points[:]
            if entity.closed and points:
                points.append(points[0])
            for start, end in zip(points, points[1:]):
                lines += dxf_line(start, end, entity.layer)
        elif isinstance(entity, Line):
            lines += dxf_line(entity.start, entity.end, entity.layer)
        elif isinstance(entity, Text):
            lines += dxf_text(entity)

    lines += dxf_pair(0, "ENDSEC") + dxf_pair(0, "EOF")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def params_payload(kerf: KerfParams, fit: FitParams) -> dict[str, Any]:
    return {
        "app": "laser-tester-generator",
        "version": APP_VERSION,
        "units": "mm",
        "kerf": asdict(kerf),
        "fit": asdict(fit),
    }


def from_payload(payload: dict[str, Any]) -> tuple[KerfParams, FitParams]:
    return (
        dataclass_from_dict(KerfParams, payload.get("kerf", {})),
        dataclass_from_dict(FitParams, payload.get("fit", {})),
    )


def dataclass_from_dict(cls: type[Any], data: dict[str, Any]) -> Any:
    names = {field.name for field in fields(cls)}
    values = {name: data[name] for name in names if name in data}
    return cls(**values)


def save_params(path: Path, kerf: KerfParams, fit: FitParams) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(params_payload(kerf, fit), indent=2), encoding="utf-8")


def load_params(path: Path) -> tuple[KerfParams, FitParams]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return from_payload(payload)


def export_samples(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    kerf = KerfParams()
    fit = FitParams()
    write_svg(generate_kerf(kerf), directory / "kerf-tester-sample.svg")
    write_dxf(generate_kerf(kerf), directory / "kerf-tester-sample.dxf")
    write_svg(generate_fit(fit), directory / "fit-allowance-tester-sample.svg")
    write_dxf(generate_fit(fit), directory / "fit-allowance-tester-sample.dxf")
    save_params(directory / "sample-parameters.json", kerf, fit)


def launch_gui() -> None:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    class ParameterForm(ttk.Frame):
        def __init__(
            self,
            parent: tk.Widget,
            cls: type[Any],
            labels: dict[str, str],
            general_fields: list[str],
            advanced_fields: list[str],
        ) -> None:
            super().__init__(parent)
            self.cls = cls
            self.vars: dict[str, tk.Variable] = {}
            self.field_map = {field.name: field for field in fields(cls)}

            tabs = ttk.Notebook(self)
            tabs.pack(fill="both", expand=True)

            general_frame = ttk.Frame(tabs, padding=(8, 10))
            advanced_frame = ttk.Frame(tabs, padding=(8, 10))
            tabs.add(general_frame, text="General")
            tabs.add(advanced_frame, text="Advanced")

            self._add_fields(general_frame, general_fields, labels)
            self._add_fields(advanced_frame, advanced_fields, labels)

        def _add_fields(self, parent: ttk.Frame, field_names: list[str], labels: dict[str, str]) -> None:
            defaults = self.cls()
            for row, field_name in enumerate(field_names):
                field = self.field_map[field_name]
                label_text = labels.get(field.name, field.name)
                ttk.Label(parent, text=label_text).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=3)
                default_value = getattr(defaults, field.name)
                if isinstance(default_value, bool):
                    var = tk.BooleanVar(value=default_value)
                    ttk.Checkbutton(parent, variable=var, command=self._notify_changed).grid(
                        row=row,
                        column=1,
                        sticky="w",
                        pady=3,
                    )
                else:
                    var = tk.StringVar(value=str(default_value))
                    entry = ttk.Entry(parent, textvariable=var, width=14)
                    entry.grid(row=row, column=1, sticky="ew", pady=3)
                    entry.bind("<KeyRelease>", lambda _event: self._notify_changed())
                    entry.bind("<Return>", lambda _event: self._notify_changed())
                    entry.bind("<FocusOut>", lambda _event: self._notify_changed())
                self.vars[field.name] = var
            parent.columnconfigure(1, weight=1)

        def _notify_changed(self) -> None:
            self.winfo_toplevel().event_generate("<<ParamsChanged>>")

        def get(self) -> Any:
            values: dict[str, Any] = {}
            for field in fields(self.cls):
                value = self.vars[field.name].get()
                default_value = getattr(self.cls(), field.name)
                if isinstance(default_value, bool):
                    values[field.name] = bool(value)
                else:
                    try:
                        values[field.name] = float(value)
                    except ValueError as exc:
                        raise ValueError(f"{field.name} must be a number.") from exc
            return self.cls(**values)

        def set(self, params: Any) -> None:
            for field in fields(self.cls):
                if field.name not in self.vars:
                    continue
                self.vars[field.name].set(getattr(params, field.name))

    class LaserTesterApp(tk.Tk):
        def __init__(self) -> None:
            super().__init__()
            self.title("Laser Tester Generator")
            self.geometry("1120x760")
            self.minsize(900, 620)

            style = ttk.Style(self)
            if "clam" in style.theme_names():
                style.theme_use("clam")
            style.configure("TButton", padding=(10, 5))
            style.configure("Title.TLabel", font=("Segoe UI", 12, "bold"))

            self.notebook = ttk.Notebook(self)
            self.notebook.pack(fill="both", expand=True, padx=12, pady=12)

            self.kerf_canvas: tk.Canvas
            self.fit_canvas: tk.Canvas
            self.kerf_form, self.kerf_canvas = self._build_tab(
                "Kerf / Cutter Compensation",
                KerfParams,
                KERF_FIELD_LABELS,
                KERF_GENERAL_FIELDS,
                KERF_ADVANCED_FIELDS,
            )
            self.fit_form, self.fit_canvas = self._build_tab(
                "Fit Allowance",
                FitParams,
                FIT_FIELD_LABELS,
                FIT_GENERAL_FIELDS,
                FIT_ADVANCED_FIELDS,
            )

            self.notebook.bind("<<NotebookTabChanged>>", lambda _event: self.preview_active())
            self.bind("<<ParamsChanged>>", lambda _event: self.preview_active())
            self.after(100, self.preview_active)

        def _build_tab(
            self,
            title: str,
            cls: type[Any],
            labels: dict[str, str],
            general_fields: list[str],
            advanced_fields: list[str],
        ) -> tuple[ParameterForm, tk.Canvas]:
            tab = ttk.Frame(self.notebook)
            self.notebook.add(tab, text=title)

            paned = ttk.PanedWindow(tab, orient="horizontal")
            paned.pack(fill="both", expand=True)

            controls = ttk.Frame(paned, padding=10)
            preview = ttk.Frame(paned, padding=(10, 10, 0, 10))
            paned.add(controls, weight=0)
            paned.add(preview, weight=1)

            ttk.Label(controls, text=title, style="Title.TLabel").pack(anchor="w", pady=(0, 10))
            form = ParameterForm(controls, cls, labels, general_fields, advanced_fields)
            form.pack(fill="both", expand=True)

            button_grid = ttk.Frame(controls)
            button_grid.pack(fill="x", pady=(14, 0))
            buttons = [
                ("Preview", self.preview_active),
                ("Export SVG", lambda: self.export_active("svg")),
                ("Export DXF", lambda: self.export_active("dxf")),
                ("Save Params", self.save_active_params),
                ("Load Params", self.load_params_file),
            ]
            for index, (label, command) in enumerate(buttons):
                button = ttk.Button(button_grid, text=label, command=command)
                button.grid(row=index // 2, column=index % 2, sticky="ew", padx=3, pady=3)
            button_grid.columnconfigure(0, weight=1)
            button_grid.columnconfigure(1, weight=1)

            ttk.Label(
                controls,
                text="CUT layer exports as black/red geometry. MARK layer exports as gray labels and tick marks.",
                wraplength=260,
                foreground="#555555",
            ).pack(anchor="w", pady=(14, 0))

            ttk.Label(preview, text="Preview", style="Title.TLabel").pack(anchor="w", pady=(0, 8))
            canvas = tk.Canvas(preview, bg="white", highlightthickness=1, highlightbackground="#c8c8c8")
            canvas.pack(fill="both", expand=True)
            canvas.bind("<Configure>", lambda _event: self.preview_active())
            return form, canvas

        def active_name(self) -> str:
            return "kerf" if self.notebook.index(self.notebook.select()) == 0 else "fit"

        def current_params(self) -> tuple[KerfParams, FitParams]:
            return self.kerf_form.get(), self.fit_form.get()

        def active_drawing(self) -> Drawing:
            kerf, fit = self.current_params()
            if self.active_name() == "kerf":
                return generate_kerf(kerf)
            return generate_fit(fit)

        def preview_active(self) -> None:
            canvas = self.kerf_canvas if self.active_name() == "kerf" else self.fit_canvas
            canvas.delete("all")
            try:
                drawing = self.active_drawing()
            except Exception as exc:
                canvas.create_text(
                    18,
                    18,
                    text=str(exc),
                    anchor="nw",
                    fill="#a00000",
                    font=("Segoe UI", 11),
                    width=max(canvas.winfo_width() - 36, 200),
                )
                return
            draw_on_canvas(canvas, drawing)

        def export_active(self, filetype: str) -> None:
            try:
                drawing = self.active_drawing()
            except Exception as exc:
                messagebox.showerror("Invalid parameters", str(exc))
                return

            EXPORT_DIR.mkdir(parents=True, exist_ok=True)
            default_name = f"{drawing.title}.{filetype}"
            path_text = filedialog.asksaveasfilename(
                initialdir=str(EXPORT_DIR),
                initialfile=default_name,
                defaultextension=f".{filetype}",
                filetypes=[(filetype.upper(), f"*.{filetype}"), ("All files", "*.*")],
            )
            if not path_text:
                return
            path = Path(path_text)
            try:
                if filetype == "svg":
                    write_svg(drawing, path)
                else:
                    write_dxf(drawing, path)
            except Exception as exc:
                messagebox.showerror("Export failed", str(exc))
                return
            messagebox.showinfo("Export complete", f"Saved {path}")

        def save_active_params(self) -> None:
            try:
                kerf, fit = self.current_params()
            except Exception as exc:
                messagebox.showerror("Invalid parameters", str(exc))
                return
            PARAM_DIR.mkdir(parents=True, exist_ok=True)
            path_text = filedialog.asksaveasfilename(
                initialdir=str(PARAM_DIR),
                initialfile="laser-tester-parameters.json",
                defaultextension=".json",
                filetypes=[("JSON parameter files", "*.json"), ("All files", "*.*")],
            )
            if not path_text:
                return
            try:
                save_params(Path(path_text), kerf, fit)
            except Exception as exc:
                messagebox.showerror("Save failed", str(exc))
                return
            messagebox.showinfo("Parameters saved", f"Saved {path_text}")

        def load_params_file(self) -> None:
            PARAM_DIR.mkdir(parents=True, exist_ok=True)
            path_text = filedialog.askopenfilename(
                initialdir=str(PARAM_DIR),
                filetypes=[("JSON parameter files", "*.json"), ("All files", "*.*")],
            )
            if not path_text:
                return
            try:
                kerf, fit = load_params(Path(path_text))
            except Exception as exc:
                messagebox.showerror("Load failed", str(exc))
                return
            self.kerf_form.set(kerf)
            self.fit_form.set(fit)
            self.preview_active()

    def draw_on_canvas(canvas: tk.Canvas, drawing: Drawing) -> None:
        canvas.update_idletasks()
        width = max(canvas.winfo_width(), 200)
        height = max(canvas.winfo_height(), 200)
        min_x, min_y, max_x, max_y = drawing.bounds()
        drawing_width = max(max_x - min_x, 1.0)
        drawing_height = max(max_y - min_y, 1.0)
        padding = 28.0
        scale = min((width - padding * 2) / drawing_width, (height - padding * 2) / drawing_height)
        scale = max(scale, 0.1)
        offset_x = (width - drawing_width * scale) / 2 - min_x * scale
        offset_y = (height - drawing_height * scale) / 2 - min_y * scale

        def tx(point: Point) -> Point:
            return (point[0] * scale + offset_x, point[1] * scale + offset_y)

        for entity in drawing.entities:
            color = "#111111" if entity.layer == "CUT" else "#777777"
            if isinstance(entity, Polyline):
                points = entity.points[:]
                if entity.closed and points:
                    points.append(points[0])
                coords: list[float] = []
                for point in points:
                    x, y = tx(point)
                    coords.extend([x, y])
                canvas.create_line(*coords, fill=color, width=1.4 if entity.layer == "CUT" else 1.0)
            elif isinstance(entity, Line):
                x1, y1 = tx(entity.start)
                x2, y2 = tx(entity.end)
                canvas.create_line(x1, y1, x2, y2, fill=color, width=1.0)
            elif isinstance(entity, Text):
                x, y = tx((entity.x, entity.y))
                font_size = max(int(entity.size * scale * 0.8), 7)
                anchor = {"start": "w", "end": "e"}.get(entity.anchor, "center")
                try:
                    canvas.create_text(
                        x,
                        y,
                        text=entity.text,
                        fill=color,
                        font=("Segoe UI", font_size),
                        anchor=anchor,
                        angle=-entity.rotation,
                    )
                except tk.TclError:
                    canvas.create_text(
                        x,
                        y,
                        text=entity.text,
                        fill=color,
                        font=("Segoe UI", font_size),
                        anchor=anchor,
                    )

    app = LaserTesterApp()
    app.mainloop()


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate laser kerf and fit allowance test files.")
    parser.add_argument(
        "--sample-dir",
        type=Path,
        help="Write sample SVG, DXF, and JSON parameter files to this directory instead of opening the GUI.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.sample_dir:
        export_samples(args.sample_dir)
        print(f"Wrote sample files to {args.sample_dir}")
        return 0

    launch_gui()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
