from __future__ import annotations

import argparse
import html
import json
import math
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any, Callable, Iterable


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
    plate_width: float = 160.0
    plate_height: float = 44.0
    scale_units: float = 15.0
    scale_tick_spacing: float = 2.0
    vernier_divisions: float = 20.0
    piece_count: float = 20.0
    pass_count: float = 40.0
    discard_width: float = 16.0
    margin: float = 6.0
    track_height: float = 20.0
    slide_height: float = 7.0
    label_size: float = 3.0
    tick_label_size: float = 2.0
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
    "plate_width": "Plate width (mm)",
    "plate_height": "Plate height (mm)",
    "scale_units": "D scale max value",
    "scale_tick_spacing": "D tick spacing (mm)",
    "vernier_divisions": "E vernier divisions",
    "piece_count": "Sliding piece count",
    "pass_count": "Equation denominator",
    "discard_width": "Discard tab width (mm)",
    "margin": "Outer margin (mm)",
    "track_height": "Gauge track height (mm)",
    "slide_height": "Slide channel height (mm)",
    "label_size": "Label text height (mm)",
    "tick_label_size": "Scale text height (mm)",
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
    "plate_width",
    "plate_height",
    "scale_units",
    "vernier_divisions",
    "piece_count",
    "pass_count",
    "include_labels",
]


KERF_ADVANCED_FIELDS = [
    "scale_tick_spacing",
    "discard_width",
    "margin",
    "track_height",
    "slide_height",
    "label_size",
    "tick_label_size",
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


FIELD_HELP = {
    "plate_width": "Overall left-to-right size of the kerf finder plate.",
    "plate_height": "Overall top-to-bottom size of the kerf finder plate.",
    "scale_units": "Largest whole-number value printed on the top D scale.",
    "scale_tick_spacing": "Physical spacing between neighboring whole-number D ticks.",
    "vernier_divisions": "Number of bottom E scale divisions used to read the decimal digit.",
    "piece_count": "Number of loose rectangular pieces that slide right after cutting.",
    "pass_count": "Denominator printed in the offset equation. Default 40 matches the reference style.",
    "discard_width": "Width of the right-hand piece marked DISCARD.",
    "margin": "Clearance from the outer plate edge to the gauge track.",
    "track_height": "Total vertical height used by the cut piece row and slide channel.",
    "slide_height": "Height of the lower slide channel marked SLIDE.",
    "label_size": "Height of the main engraved labels.",
    "tick_label_size": "Height of the small scale numbers.",
    "include_labels": "Turns engraved text and scale labels on or off.",
    "nominal_tab_width": "Base tab width used by the fit allowance slots.",
    "tab_height": "Height of the male coupon tab that enters each slot.",
    "shoulder_width": "Width of each shoulder beside the male coupon tab.",
    "body_height": "Height of the wider body below the male coupon tab.",
    "slot_depth": "How deep each fit allowance slot is cut into the strip.",
    "allowance_start": "Smallest fit allowance value in the slot series.",
    "allowance_stop": "Largest fit allowance value in the slot series.",
    "allowance_step": "Difference between neighboring fit allowance slots.",
    "strip_height": "Height of the strip that contains all fit allowance slots.",
    "strip_margin": "Clear margin around the first and last fit slots.",
    "slot_spacing": "Gap between neighboring fit allowance slots.",
}


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


def rounded_int(name: str, value: float, minimum: int = 1) -> int:
    rounded = int(round(value))
    if rounded < minimum:
        raise ValueError(f"{name} must be at least {minimum}.")
    return rounded


def kerf_layout(params: KerfParams) -> dict[str, float]:
    ensure_positive("Plate width", params.plate_width)
    ensure_positive("Plate height", params.plate_height)
    ensure_positive("D scale max value", params.scale_units)
    ensure_positive("D tick spacing", params.scale_tick_spacing)
    ensure_positive("Equation denominator", params.pass_count)
    ensure_positive("Discard tab width", params.discard_width)
    ensure_positive("Outer margin", params.margin)
    ensure_positive("Gauge track height", params.track_height)
    ensure_positive("Slide channel height", params.slide_height)
    ensure_positive("Label text height", params.label_size)
    ensure_positive("Scale text height", params.tick_label_size)

    scale_units = rounded_int("D scale max value", params.scale_units, minimum=5)
    vernier_divisions = rounded_int("E vernier divisions", params.vernier_divisions, minimum=5)
    piece_count = rounded_int("Sliding piece count", params.piece_count, minimum=4)
    if params.slide_height >= params.track_height:
        raise ValueError("Slide channel height must be smaller than gauge track height.")

    track_x = params.margin + 8.0
    track_y = max(params.margin + params.label_size + 5.0, params.margin + 8.0)
    track_bottom = track_y + params.track_height
    row_height = params.track_height - params.slide_height
    row_bottom = track_y + row_height
    plate_right = params.plate_width
    plate_bottom = params.plate_height
    inner_right = plate_right - params.margin
    discard_x = inner_right - params.discard_width
    gauge_width = discard_x - track_x
    top_scale_end = track_x + scale_units * params.scale_tick_spacing
    vernier_length = scale_units * params.scale_tick_spacing * 0.92

    if track_bottom + 4.5 > plate_bottom - 0.5:
        raise ValueError("Plate height is too small for the track, scales, and labels.")
    if gauge_width < piece_count * 2.5:
        raise ValueError("Plate width is too small for this piece count and discard width.")
    if top_scale_end > discard_x - 2.0:
        raise ValueError("D scale is too long for the plate. Reduce scale max or tick spacing.")

    return {
        "scale_units": float(scale_units),
        "vernier_divisions": float(vernier_divisions),
        "piece_count": float(piece_count),
        "track_x": track_x,
        "track_y": track_y,
        "track_bottom": track_bottom,
        "row_height": row_height,
        "row_bottom": row_bottom,
        "slide_bottom": track_bottom,
        "inner_right": inner_right,
        "discard_x": discard_x,
        "gauge_width": gauge_width,
        "cell_width": gauge_width / piece_count,
        "top_scale_end": top_scale_end,
        "vernier_length": vernier_length,
    }


def generate_kerf(params: KerfParams) -> Drawing:
    layout = kerf_layout(params)
    scale_units = int(layout["scale_units"])
    vernier_divisions = int(layout["vernier_divisions"])
    piece_count = int(layout["piece_count"])
    track_x = layout["track_x"]
    track_y = layout["track_y"]
    row_bottom = layout["row_bottom"]
    track_bottom = layout["track_bottom"]
    discard_x = layout["discard_x"]
    cell_width = layout["cell_width"]

    entities: list[Entity] = [
        rect(0, 0, params.plate_width, params.plate_height),
        rect(track_x, track_y, discard_x - track_x, layout["row_height"]),
        rect(track_x, row_bottom, discard_x - track_x, params.slide_height),
        rect(discard_x, row_bottom, params.discard_width, params.slide_height),
    ]

    for index in range(1, piece_count):
        x = track_x + index * cell_width
        entities.append(Line((x, track_y), (x, row_bottom), layer="CUT"))

    for index in range(scale_units + 1):
        x = track_x + index * params.scale_tick_spacing
        major = index % 5 == 0
        tick_top = track_y - (4.2 if major else 2.6)
        entities.append(Line((x, track_y), (x, tick_top), layer="MARK"))
        if params.include_labels and major:
            entities.append(
                Text(
                    x,
                    tick_top - 0.6,
                    str(index),
                    size=params.tick_label_size,
                    layer="MARK",
                )
            )

    vernier_spacing = layout["vernier_length"] / vernier_divisions
    for index in range(vernier_divisions + 1):
        x = track_x + index * vernier_spacing
        major = index % 5 == 0
        tick_bottom = track_bottom + (4.2 if major else 3.0)
        entities.append(Line((x, track_bottom), (x, tick_bottom), layer="MARK"))
        if params.include_labels and major:
            entities.append(
                Text(
                    x,
                    tick_bottom + params.tick_label_size + 0.2,
                    str(index),
                    size=params.tick_label_size,
                    layer="MARK",
                )
            )

    entities.append(
        Line(
            (track_x, row_bottom + params.slide_height / 2),
            (discard_x - 5.0, row_bottom + params.slide_height / 2),
            layer="MARK",
        )
    )

    if params.include_labels:
        pass_count = rounded_int("Equation denominator", params.pass_count, minimum=1)
        entities.extend(
            [
                Text(
                    params.plate_width / 2,
                    params.margin + params.label_size,
                    "Vernier Kerf Offset Test",
                    size=params.label_size,
                    layer="MARK",
                ),
                Text(
                    params.plate_width - params.margin - 24.0,
                    params.margin + params.tick_label_size,
                    f"Kerf offset = D.E / {pass_count}",
                    size=params.tick_label_size,
                    layer="MARK",
                ),
                Text(
                    track_x - 1.8,
                    track_y + layout["row_height"] / 2,
                    "D",
                    size=params.label_size,
                    anchor="end",
                    layer="MARK",
                ),
                Text(
                    track_x + layout["vernier_length"] * 0.42,
                    track_bottom + params.tick_label_size + 0.2,
                    "E",
                    size=params.label_size,
                    anchor="start",
                    layer="MARK",
                ),
                Text(
                    (track_x + discard_x) / 2,
                    row_bottom + params.slide_height / 2 + params.label_size * 0.35,
                    "SLIDE ->",
                    size=params.label_size,
                    layer="MARK",
                ),
                Text(
                    discard_x + params.discard_width / 2,
                    row_bottom + params.slide_height / 2 + params.label_size * 0.35,
                    "DISCARD",
                    size=params.label_size,
                    layer="MARK",
                ),
            ]
        )

    return Drawing(entities, title="vernier-kerf-offset-test")


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
    return "#ff0000" if layer == "CUT" else "#000000"


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
    for layer_name, color in [("CUT", 1), ("MARK", 7)]:
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
            on_field_focus: Callable[[str | None], None],
        ) -> None:
            super().__init__(parent)
            self.cls = cls
            self.vars: dict[str, tk.Variable] = {}
            self.field_map = {field.name: field for field in fields(cls)}
            self.on_field_focus = on_field_focus
            self.focused_field: str | None = None

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
                label = ttk.Label(parent, text=label_text)
                label.grid(row=row, column=0, sticky="w", padx=(0, 8), pady=3)
                self._bind_field_widget(label, field.name)
                default_value = getattr(defaults, field.name)
                if isinstance(default_value, bool):
                    var = tk.BooleanVar(value=default_value)
                    control = ttk.Checkbutton(parent, variable=var, command=self._notify_changed)
                    control.grid(
                        row=row,
                        column=1,
                        sticky="w",
                        pady=3,
                    )
                    self._bind_field_widget(control, field.name)
                else:
                    var = tk.StringVar(value=str(default_value))
                    entry = ttk.Entry(parent, textvariable=var, width=14)
                    entry.grid(row=row, column=1, sticky="ew", pady=3)
                    self._bind_field_widget(entry, field.name)
                    entry.bind("<KeyRelease>", lambda _event: self._notify_changed())
                self.vars[field.name] = var
            parent.columnconfigure(1, weight=1)

        def _bind_field_widget(self, widget: tk.Widget, field_name: str) -> None:
            widget.bind("<Enter>", lambda _event, name=field_name: self._show_field(name), add="+")
            widget.bind("<Leave>", lambda _event, name=field_name: self._leave_field(name), add="+")
            widget.bind("<FocusIn>", lambda _event, name=field_name: self._focus_field(name), add="+")
            widget.bind("<FocusOut>", lambda _event, name=field_name: self._blur_field(name), add="+")

        def _show_field(self, field_name: str) -> None:
            self.on_field_focus(field_name)

        def _leave_field(self, field_name: str) -> None:
            if self.focused_field != field_name:
                self.on_field_focus(None)

        def _focus_field(self, field_name: str) -> None:
            self.focused_field = field_name
            self.on_field_focus(field_name)

        def _blur_field(self, field_name: str) -> None:
            if self.focused_field == field_name:
                self.focused_field = None
            self._notify_changed()
            self.on_field_focus(None)

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
            self.active_fields: dict[str, str | None] = {"kerf": None, "fit": None}
            self.help_vars: dict[str, tk.StringVar] = {}
            self.kerf_form, self.kerf_canvas = self._build_tab(
                "kerf",
                "Kerf / Cutter Compensation",
                KerfParams,
                KERF_FIELD_LABELS,
                KERF_GENERAL_FIELDS,
                KERF_ADVANCED_FIELDS,
            )
            self.fit_form, self.fit_canvas = self._build_tab(
                "fit",
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
            tool_name: str,
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
            form = ParameterForm(
                controls,
                cls,
                labels,
                general_fields,
                advanced_fields,
                lambda field_name, name=tool_name: self.set_active_field(name, field_name),
            )
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
                text="CUT layer exports as red geometry. MARK layer exports as black score/text geometry.",
                wraplength=260,
                foreground="#555555",
            ).pack(anchor="w", pady=(14, 0))
            help_var = tk.StringVar(value="Hover or focus a setting to see the dimension it changes.")
            self.help_vars[tool_name] = help_var
            ttk.Label(
                controls,
                textvariable=help_var,
                wraplength=280,
                foreground="#333333",
            ).pack(anchor="w", fill="x", pady=(10, 0))

            ttk.Label(preview, text="Preview", style="Title.TLabel").pack(anchor="w", pady=(0, 8))
            canvas = tk.Canvas(preview, bg="white", highlightthickness=1, highlightbackground="#c8c8c8")
            canvas.pack(fill="both", expand=True)
            canvas.bind("<Configure>", lambda _event: self.preview_active())
            return form, canvas

        def set_active_field(self, tool_name: str, field_name: str | None) -> None:
            self.active_fields[tool_name] = field_name
            if field_name:
                self.help_vars[tool_name].set(FIELD_HELP.get(field_name, "This setting changes the highlighted dimension."))
            else:
                self.help_vars[tool_name].set("Hover or focus a setting to see the dimension it changes.")
            if tool_name == self.active_name():
                self.preview_active()

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
            active_name = self.active_name()
            canvas = self.kerf_canvas if active_name == "kerf" else self.fit_canvas
            canvas.delete("all")
            try:
                kerf, fit = self.current_params()
                drawing = generate_kerf(kerf) if active_name == "kerf" else generate_fit(fit)
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
            params = kerf if active_name == "kerf" else fit
            draw_on_canvas(canvas, drawing, active_name, params, self.active_fields[active_name])

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

    def draw_on_canvas(
        canvas: tk.Canvas,
        drawing: Drawing,
        tool_name: str,
        params: KerfParams | FitParams,
        highlight_field: str | None,
    ) -> None:
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
            color = "#ff0000" if entity.layer == "CUT" else "#111111"
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

        draw_dimension_highlight(canvas, tx, tool_name, params, highlight_field)

    def draw_dimension_highlight(
        canvas: tk.Canvas,
        tx: Callable[[Point], Point],
        tool_name: str,
        params: KerfParams | FitParams,
        field_name: str | None,
    ) -> None:
        if not field_name:
            return

        highlight = "#f59e0b"
        label = KERF_FIELD_LABELS.get(field_name) if tool_name == "kerf" else FIT_FIELD_LABELS.get(field_name)
        label = label or field_name

        def line(start: Point, end: Point, text: str = label) -> None:
            x1, y1 = tx(start)
            x2, y2 = tx(end)
            canvas.create_line(x1, y1, x2, y2, fill=highlight, width=2, arrow="both")
            canvas.create_text(
                (x1 + x2) / 2,
                (y1 + y2) / 2 - 10,
                text=text,
                fill=highlight,
                font=("Segoe UI", 10, "bold"),
            )

        def box(x: float, y: float, width: float, height: float, text: str = label) -> None:
            x1, y1 = tx((x, y))
            x2, y2 = tx((x + width, y + height))
            canvas.create_rectangle(x1, y1, x2, y2, outline=highlight, width=2, dash=(4, 2))
            canvas.create_text(
                (x1 + x2) / 2,
                min(y1, y2) - 10,
                text=text,
                fill=highlight,
                font=("Segoe UI", 10, "bold"),
            )

        if tool_name == "kerf" and isinstance(params, KerfParams):
            layout = kerf_layout(params)
            track_x = layout["track_x"]
            track_y = layout["track_y"]
            row_bottom = layout["row_bottom"]
            track_bottom = layout["track_bottom"]
            discard_x = layout["discard_x"]
            if field_name == "plate_width":
                line((0, -2.5), (params.plate_width, -2.5))
            elif field_name == "plate_height":
                line((params.plate_width + 3.0, 0), (params.plate_width + 3.0, params.plate_height))
            elif field_name == "scale_units":
                line((track_x, track_y - 7.0), (layout["top_scale_end"], track_y - 7.0))
            elif field_name == "scale_tick_spacing":
                line((track_x, track_y - 6.0), (track_x + params.scale_tick_spacing, track_y - 6.0))
            elif field_name == "vernier_divisions":
                line((track_x, track_bottom + 7.0), (track_x + layout["vernier_length"], track_bottom + 7.0))
            elif field_name == "piece_count":
                box(track_x, track_y, discard_x - track_x, layout["row_height"])
            elif field_name == "pass_count":
                box(params.plate_width - params.margin - 50.0, params.margin - 1.0, 47.0, params.tick_label_size + 3.0)
            elif field_name == "discard_width":
                box(discard_x, row_bottom, params.discard_width, params.slide_height)
            elif field_name == "margin":
                line((0, params.plate_height / 2), (params.margin, params.plate_height / 2))
            elif field_name == "track_height":
                line((track_x - 5.0, track_y), (track_x - 5.0, track_bottom))
            elif field_name == "slide_height":
                line((discard_x - 3.0, row_bottom), (discard_x - 3.0, track_bottom))
            elif field_name == "label_size":
                box(params.plate_width / 2 - 32.0, params.margin, 64.0, params.label_size + 2.0)
            elif field_name == "tick_label_size":
                box(track_x - 3.0, track_y - 9.0, layout["top_scale_end"] - track_x + 6.0, params.tick_label_size + 4.0)
            elif field_name == "include_labels":
                box(track_x - 5.0, params.margin - 1.0, params.plate_width - track_x - params.margin + 4.0, track_bottom + 7.0)
            return

        if tool_name == "fit" and isinstance(params, FitParams):
            values = allowance_values(params.allowance_start, params.allowance_stop, params.allowance_step)
            slot_widths = [params.nominal_tab_width + value for value in values]
            max_slot_width = max(slot_widths)
            slot_pitch = max_slot_width + params.slot_spacing
            strip_width = params.strip_margin * 2 + max_slot_width + (len(values) - 1) * slot_pitch
            slot_y = (params.strip_height - params.slot_depth) / 2
            first_center = params.strip_margin + max_slot_width / 2
            first_slot_x = first_center - slot_widths[0] / 2
            first_slot_right = first_slot_x + slot_widths[0]
            coupon_total_width = params.nominal_tab_width + 2 * params.shoulder_width
            coupon_x = params.strip_margin
            coupon_y = params.strip_height + params.label_size + 12.0
            tab_left = coupon_x + params.shoulder_width
            tab_right = tab_left + params.nominal_tab_width
            body_top = coupon_y + params.tab_height
            coupon_bottom = coupon_y + params.tab_height + params.body_height

            if field_name == "nominal_tab_width":
                line((tab_left, coupon_y - 2.0), (tab_right, coupon_y - 2.0))
            elif field_name == "tab_height":
                line((tab_right + 3.0, coupon_y), (tab_right + 3.0, body_top))
            elif field_name == "shoulder_width":
                line((coupon_x, body_top + 3.0), (tab_left, body_top + 3.0))
            elif field_name == "body_height":
                line((coupon_x - 3.0, body_top), (coupon_x - 3.0, coupon_bottom))
            elif field_name == "slot_depth":
                line((first_slot_right + 3.0, slot_y), (first_slot_right + 3.0, slot_y + params.slot_depth))
            elif field_name == "allowance_start":
                box(first_slot_x, slot_y, slot_widths[0], params.slot_depth)
            elif field_name == "allowance_stop":
                last_center = params.strip_margin + max_slot_width / 2 + (len(values) - 1) * slot_pitch
                last_width = slot_widths[-1]
                box(last_center - last_width / 2, slot_y, last_width, params.slot_depth)
            elif field_name == "allowance_step" and len(values) > 1:
                second_center = params.strip_margin + max_slot_width / 2 + slot_pitch
                line((first_center, params.strip_height + 7.0), (second_center, params.strip_height + 7.0))
            elif field_name == "strip_height":
                line((strip_width + 3.0, 0), (strip_width + 3.0, params.strip_height))
            elif field_name == "strip_margin":
                line((0, params.strip_height / 2), (params.strip_margin, params.strip_height / 2))
            elif field_name == "slot_spacing" and len(values) > 1:
                second_center = params.strip_margin + max_slot_width / 2 + slot_pitch
                second_slot_x = second_center - slot_widths[1] / 2
                line((first_slot_right, slot_y - 3.0), (second_slot_x, slot_y - 3.0))
            elif field_name == "label_size":
                box(params.strip_margin, params.strip_height + 1.0, max_slot_width, params.label_size + 4.0)
            elif field_name == "include_labels":
                box(0, params.strip_height, strip_width, params.label_size + 8.0)

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
