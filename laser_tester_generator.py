from __future__ import annotations

import argparse
import html
import json
import math
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any, Callable, Iterable


APP_VERSION = "0.2.0"
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
    discard_piece_count: float = 3.0
    margin: float = 6.0
    track_height: float = 20.0
    slide_height: float = 7.0
    label_size: float = 3.0
    tick_label_size: float = 2.0
    include_labels: bool = True


@dataclass
class FitParams:
    fit_variable_center: float = 20.0
    fit_variable_count: float = 7.0
    fit_variable_min: float = 19.70
    fit_variable_max: float = 20.30
    fit_variable_step: float = 0.0
    material_thickness: float = 3.0
    material_count: float = 3.0
    material_min: float = 2.90
    material_max: float = 3.10
    material_step: float = 0.0
    spacing_margin: float = 8.0
    shoulder_length: float = 24.0
    shoulder_width: float = 8.0
    overall_coupon_length: float = 0.0
    overall_coupon_height: float = 0.0
    known_kerf: float = 0.0
    label_size: float = 2.4
    include_labels: bool = True


KERF_FIELD_LABELS = {
    "plate_width": "Plate width (mm)",
    "plate_height": "Plate height (mm)",
    "scale_units": "Coarse scale max value",
    "scale_tick_spacing": "Coarse tick spacing (mm)",
    "vernier_divisions": "Vernier divisions",
    "piece_count": "Top-row piece count",
    "pass_count": "Equation denominator",
    "discard_piece_count": "Discard bay pieces",
    "margin": "Outer margin (mm)",
    "track_height": "Gauge track height (mm)",
    "slide_height": "Slide channel height (mm)",
    "label_size": "Label text height (mm)",
    "tick_label_size": "Scale text height (mm)",
    "include_labels": "Include engraved labels",
}


FIT_FIELD_LABELS = {
    "fit_variable_center": "Fit nominal (mm)",
    "fit_variable_count": "Fit N",
    "fit_variable_min": "Fit min (mm)",
    "fit_variable_max": "Fit max (mm)",
    "fit_variable_step": "Fit step (0 = auto)",
    "material_thickness": "Material nominal (mm)",
    "material_count": "Material N",
    "material_min": "Material min (mm)",
    "material_max": "Material max (mm)",
    "material_step": "Material step (0 = auto)",
    "spacing_margin": "Spacing margin (mm)",
    "shoulder_length": "Shoulder length (mm)",
    "shoulder_width": "Shoulder width each side (mm)",
    "overall_coupon_length": "Overall coupon length (0 = auto)",
    "overall_coupon_height": "Overall coupon height (0 = auto)",
    "known_kerf": "Known kerf for LightBurn (mm)",
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
    "discard_piece_count",
    "margin",
    "track_height",
    "slide_height",
    "label_size",
    "tick_label_size",
]


FIT_GENERAL_FIELDS = [
    "fit_variable_center",
    "fit_variable_count",
    "fit_variable_min",
    "fit_variable_max",
    "fit_variable_step",
    "material_thickness",
    "material_count",
    "material_min",
    "material_max",
    "material_step",
]


FIT_ADVANCED_FIELDS = [
    "spacing_margin",
    "shoulder_length",
    "shoulder_width",
    "overall_coupon_length",
    "overall_coupon_height",
    "known_kerf",
    "label_size",
    "include_labels",
]


FIELD_HELP = {
    "plate_width": "Overall left-to-right size of the kerf finder plate.",
    "plate_height": "Overall top-to-bottom size of the kerf finder plate.",
    "scale_units": "Largest whole-number value printed on the top coarse scale.",
    "scale_tick_spacing": "Physical spacing between neighboring coarse scale ticks.",
    "vernier_divisions": "Number of bottom vernier scale divisions engraved on the slider.",
    "piece_count": "Number of equal-width loose rectangular pieces in the top row.",
    "pass_count": "Denominator printed in the offset equation. Default 40 matches the reference style.",
    "discard_piece_count": "Number of top-row piece widths used by the lower DISCARD bay.",
    "margin": "Clearance from the outer plate edge to the gauge track.",
    "track_height": "Total vertical height used by the cut piece row and slide channel.",
    "slide_height": "Height of the lower slide channel marked SLIDE.",
    "label_size": "Height of the main engraved labels.",
    "tick_label_size": "Height of the small scale numbers.",
    "include_labels": "Turns engraved text and scale labels on or off.",
    "fit_variable_center": "Visible width of the matching pin and the center value for vertical fit-variable holes.",
    "fit_variable_count": "Number of fit-variable columns to place in the coupon.",
    "fit_variable_min": "Smallest actual fit-variable hole dimension. Used when step is 0.",
    "fit_variable_max": "Largest actual fit-variable hole dimension. Used when step is 0.",
    "fit_variable_step": "Step between fit-variable dimensions. Use 0 to derive step from min/max.",
    "material_thickness": "Nominal material thickness. The matching pin text uses this value.",
    "material_count": "Number of material-thickness variants to place vertically.",
    "material_min": "Smallest horizontal material-thickness hole dimension. Used when material step is 0.",
    "material_max": "Largest horizontal material-thickness hole dimension. Used when material step is 0.",
    "material_step": "Step between material dimensions. Use 0 to derive step from min/max.",
    "spacing_margin": "Margin around holes and spacing between neighboring holes.",
    "shoulder_length": "Non-fitting shoulder/handle length behind the matching pin.",
    "shoulder_width": "Extra side material on each side of the matching pin.",
    "overall_coupon_length": "Advanced override for coupon length. Leave 0 to auto-size from fit columns, material values, spacing, and labels.",
    "overall_coupon_height": "Advanced override for coupon height. Leave 0 to auto-size from material rows, fit values, spacing, and labels.",
    "known_kerf": "Used only for LightBurn export: holes offset inward, outside contours offset outward.",
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
    ensure_positive("Coarse scale max value", params.scale_units)
    ensure_positive("Coarse tick spacing", params.scale_tick_spacing)
    ensure_positive("Equation denominator", params.pass_count)
    ensure_positive("Outer margin", params.margin)
    ensure_positive("Gauge track height", params.track_height)
    ensure_positive("Slide channel height", params.slide_height)
    ensure_positive("Label text height", params.label_size)
    ensure_positive("Scale text height", params.tick_label_size)

    scale_units = rounded_int("Coarse scale max value", params.scale_units, minimum=5)
    vernier_divisions = rounded_int("Vernier divisions", params.vernier_divisions, minimum=5)
    piece_count = rounded_int("Top-row piece count", params.piece_count, minimum=4)
    discard_piece_count = rounded_int("Discard bay pieces", params.discard_piece_count, minimum=1)
    if discard_piece_count >= piece_count:
        raise ValueError("Discard bay pieces must be smaller than the sliding piece count.")
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
    row_width = inner_right - track_x
    cell_width = row_width / piece_count
    discard_width = discard_piece_count * cell_width
    discard_x = inner_right - discard_width
    nose_x = max(track_x + cell_width, discard_x - cell_width)
    slide_width = discard_x - track_x
    scale_length = scale_units * params.scale_tick_spacing
    top_scale_end = track_x + scale_units * params.scale_tick_spacing
    vernier_length = scale_length

    if track_bottom + 4.5 > plate_bottom - 0.5:
        raise ValueError("Plate height is too small for the track, scales, and labels.")
    if cell_width < 3.0:
        raise ValueError("Top-row pieces are too narrow. Increase plate width or reduce piece count.")
    if slide_width < row_width * 0.5:
        raise ValueError("Discard bay is too wide. Reduce discard bay pieces or increase piece count.")
    if top_scale_end > inner_right - 2.0:
        raise ValueError("Coarse scale is too long for the plate. Reduce scale max or tick spacing.")
    if nose_x <= track_x or nose_x >= discard_x:
        raise ValueError("Discard bay needs at least one full top-row piece for the slider nose.")

    return {
        "scale_units": float(scale_units),
        "vernier_divisions": float(vernier_divisions),
        "piece_count": float(piece_count),
        "discard_piece_count": float(discard_piece_count),
        "track_x": track_x,
        "track_y": track_y,
        "track_bottom": track_bottom,
        "row_height": row_height,
        "row_bottom": row_bottom,
        "slide_bottom": track_bottom,
        "inner_right": inner_right,
        "discard_x": discard_x,
        "nose_x": nose_x,
        "row_width": row_width,
        "slide_width": slide_width,
        "discard_width": discard_width,
        "cell_width": cell_width,
        "scale_length": scale_length,
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
    inner_right = layout["inner_right"]
    nose_x = layout["nose_x"]
    cell_width = layout["cell_width"]

    entities: list[Entity] = [rect(0, 0, params.plate_width, params.plate_height)]

    def add_cut(start: Point, end: Point) -> None:
        entities.append(Line(start, end, layer="CUT"))

    add_cut((track_x, track_y), (inner_right, track_y))
    add_cut((inner_right, track_y), (inner_right, track_bottom))
    add_cut((inner_right, track_bottom), (track_x, track_bottom))
    add_cut((track_x, track_bottom), (track_x, track_y))
    add_cut((track_x, row_bottom), (inner_right, row_bottom))
    add_cut((nose_x, row_bottom), (discard_x, track_bottom))

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
                    (track_x + discard_x) / 2,
                    row_bottom + params.slide_height / 2 + params.label_size * 0.35,
                    "SLIDE ->",
                    size=params.label_size,
                    layer="MARK",
                ),
                Text(
                    discard_x + layout["discard_width"] / 2,
                    row_bottom + params.slide_height / 2 + params.label_size * 0.35,
                    "DISCARD",
                    size=params.label_size,
                    layer="MARK",
                ),
            ]
        )

    return Drawing(entities, title="vernier-kerf-offset-test")


def dimension_values(
    center: float,
    count_value: float,
    min_value: float,
    max_value: float,
    step_value: float,
    label: str,
) -> list[float]:
    count = rounded_int(f"N {label} dimensions", count_value, minimum=1)
    ensure_positive(f"{label} nominal", center)
    if step_value < 0:
        raise ValueError(f"{label} step must be zero or greater.")

    if step_value > 0:
        midpoint = (count - 1) / 2
        values = [center + (index - midpoint) * step_value for index in range(count)]
    else:
        ensure_positive(f"{label} min", min_value)
        ensure_positive(f"{label} max", max_value)
        if max_value < min_value:
            raise ValueError(f"{label} max must be greater than or equal to {label} min.")
        if count == 1:
            values = [center]
        else:
            step = (max_value - min_value) / (count - 1)
            values = [min_value + index * step for index in range(count)]

    if any(value <= 0 for value in values):
        raise ValueError(f"{label} dimensions must all be greater than zero.")
    return [round(value, 6) for value in values]


def fit_variable_values(params: FitParams) -> list[float]:
    return dimension_values(
        params.fit_variable_center,
        params.fit_variable_count,
        params.fit_variable_min,
        params.fit_variable_max,
        params.fit_variable_step,
        "Fit variable",
    )


def material_values(params: FitParams) -> list[float]:
    return dimension_values(
        params.material_thickness,
        params.material_count,
        params.material_min,
        params.material_max,
        params.material_step,
        "Material",
    )


def fit_layout(params: FitParams) -> dict[str, Any]:
    ensure_positive("Fit variable center value", params.fit_variable_center)
    ensure_positive("Material thickness", params.material_thickness)
    ensure_positive("Spacing margin", params.spacing_margin)
    ensure_positive("Shoulder length", params.shoulder_length)
    ensure_positive("Shoulder width", params.shoulder_width)
    ensure_positive("Label text height", params.label_size)
    if params.overall_coupon_length < 0:
        raise ValueError("Overall coupon length must be zero or greater.")
    if params.overall_coupon_height < 0:
        raise ValueError("Overall coupon height must be zero or greater.")
    if params.known_kerf < 0:
        raise ValueError("Known kerf must be zero or greater.")

    fit_values = fit_variable_values(params)
    mat_values = material_values(params)
    max_hole_width = max(mat_values)
    max_hole_height = max(fit_values)
    label_band = params.label_size + 2.6 if params.include_labels else 0.0
    row_label_band = params.label_size * 3.2 if params.include_labels else 0.0
    cell_width = max_hole_width + params.spacing_margin
    cell_height = max_hole_height + label_band + params.spacing_margin

    auto_coupon_length = row_label_band + params.spacing_margin + len(fit_values) * cell_width
    auto_coupon_height = params.spacing_margin + len(mat_values) * cell_height
    coupon_height = params.overall_coupon_height if params.overall_coupon_height > 0 else auto_coupon_height
    if coupon_height < auto_coupon_height:
        raise ValueError("Overall coupon height is too small for the selected grid, spacing, and labels.")

    coupon_length = params.overall_coupon_length if params.overall_coupon_length > 0 else auto_coupon_length
    if coupon_length < auto_coupon_length:
        raise ValueError("Overall coupon length is too small for N, material dimensions, spacing, and labels.")

    slots: list[dict[str, float]] = []
    row_labels: list[dict[str, float | str]] = []
    grid_x = row_label_band + params.spacing_margin
    grid_y = params.spacing_margin
    for row_index, material_dimension in enumerate(mat_values):
        row_top = grid_y + row_index * cell_height
        label_y = row_top + max_hole_height + params.label_size + 0.6
        row_center_y = row_top + max_hole_height / 2
        if params.include_labels:
            row_labels.append(
                {
                    "x": max(params.label_size, row_label_band - params.label_size * 0.45),
                    "y": row_center_y + params.label_size * 0.35,
                    "text": f"{material_dimension:.2f}",
                }
            )
        for column_index, fit_dimension in enumerate(fit_values):
            cell_x = grid_x + column_index * cell_width
            x = cell_x + (max_hole_width - material_dimension) / 2
            y = row_top + (max_hole_height - fit_dimension) / 2
            slots.append(
                {
                    "x": x,
                    "y": y,
                    "width": material_dimension,
                    "height": fit_dimension,
                    "label_y": label_y,
                    "fit_dimension": fit_dimension,
                    "material_dimension": material_dimension,
                    "row": float(row_index),
                    "column": float(column_index),
                }
            )

    pin_width = params.fit_variable_center
    coupon_x = params.spacing_margin
    coupon_y = coupon_height + params.label_size + 12.0
    body_width = pin_width + 2 * params.shoulder_width
    body_height = max(params.material_thickness * 4.0, 16.0)
    pin_x = coupon_x + params.shoulder_width
    pin_y = coupon_y
    body_y = coupon_y + params.shoulder_length

    return {
        "values": fit_values,
        "fit_values": fit_values,
        "material_values": mat_values,
        "hole_width": max_hole_width,
        "hole_heights": fit_values,
        "cell_width": cell_width,
        "cell_height": cell_height,
        "grid_x": grid_x,
        "grid_y": grid_y,
        "row_label_band": row_label_band,
        "strip_width": coupon_length,
        "coupon_length": coupon_length,
        "coupon_height": coupon_height,
        "auto_coupon_length": auto_coupon_length,
        "auto_coupon_height": auto_coupon_height,
        "slots": slots,
        "row_labels": row_labels,
        "coupon_x": coupon_x,
        "coupon_y": coupon_y,
        "body_width": body_width,
        "body_height": body_height,
        "body_y": body_y,
        "pin_x": pin_x,
        "pin_y": pin_y,
        "pin_width": pin_width,
        "pin_length": params.shoulder_length,
        "pin_body_width": body_width,
        "pin_coupon_height": params.shoulder_length + body_height,
    }


def generate_fit(params: FitParams) -> Drawing:
    layout = fit_layout(params)
    strip_width = layout["strip_width"]
    strip_height = layout["coupon_height"]

    entities: list[Entity] = [rect(0, 0, strip_width, strip_height, layer="OUTSIDE")]

    for slot in layout["slots"]:
        entities.append(rect(slot["x"], slot["y"], slot["width"], slot["height"], layer="HOLES"))
        if params.include_labels:
            entities.append(
                Text(
                    slot["x"] + slot["width"] / 2,
                    slot["label_y"],
                    f"{slot['fit_dimension']:.2f}",
                    size=params.label_size,
                    layer="NUMBERS",
                )
            )

    if params.include_labels:
        for row_label in layout["row_labels"]:
            entities.append(
                Text(
                    float(row_label["x"]),
                    float(row_label["y"]),
                    str(row_label["text"]),
                    size=params.label_size,
                    layer="NUMBERS",
                    anchor="end",
                )
            )

    coupon_x = layout["coupon_x"]
    coupon_y = layout["coupon_y"]
    pin_x = layout["pin_x"]
    pin_y = layout["pin_y"]
    pin_right = pin_x + layout["pin_width"]
    body_y = layout["body_y"]
    coupon_right = coupon_x + layout["body_width"]
    coupon_bottom = body_y + layout["body_height"]

    entities.append(
        Polyline(
            [
                (pin_x, pin_y),
                (pin_right, pin_y),
                (pin_right, body_y),
                (coupon_right, body_y),
                (coupon_right, coupon_bottom),
                (coupon_x, coupon_bottom),
                (coupon_x, body_y),
                (pin_x, body_y),
            ],
            closed=True,
            layer="OUTSIDE",
        )
    )

    if params.include_labels:
        entities.extend(
            [
                Text(
                    coupon_x + layout["body_width"] / 2,
                    body_y + layout["body_height"] / 2 + params.label_size * 0.35,
                    f"{mm(params.fit_variable_center)} x {mm(params.material_thickness)} [mm]",
                    size=params.label_size,
                    layer="NUMBERS",
                ),
                Text(
                    strip_width / 2,
                    -3.0,
                    "Fit tester",
                    size=params.label_size,
                    layer="TEXT",
                ),
            ]
        )

    return Drawing(entities, title="fit-allowance-tester")


def layer_color(layer: str) -> str:
    return "#ff0000" if layer in {"CUT", "OUTSIDE", "HOLES"} else "#000000"


def layer_sort_key(layer: str) -> tuple[int, str]:
    order = {
        "OUTSIDE": 0,
        "HOLES": 1,
        "TEXT": 2,
        "NUMBERS": 3,
        "CUT": 4,
        "MARK": 5,
    }
    return (order.get(layer, 99), layer)


def drawing_layers(drawing: Drawing) -> list[str]:
    return sorted({entity.layer for entity in drawing.entities}, key=layer_sort_key)


def dxf_layer_color(layer: str) -> int:
    return 1 if layer in {"CUT", "OUTSIDE", "HOLES"} else 7


def lightburn_layer_index(layer: str) -> int:
    return {
        "OUTSIDE": 0,
        "HOLES": 1,
        "TEXT": 2,
        "NUMBERS": 3,
        "CUT": 0,
        "MARK": 2,
    }.get(layer, 0)


def lightburn_layer_settings(layer: str, kerf_offset: float) -> dict[str, str]:
    if layer == "OUTSIDE":
        return {
            "name": "OUTSIDE",
            "mode": "line",
            "type": "Cut",
            "color": "#ff0000",
            "kerfOffset": mm(kerf_offset),
            "kerfDirection": "out",
        }
    if layer == "HOLES":
        return {
            "name": "HOLES",
            "mode": "line",
            "type": "Cut",
            "color": "#ff0000",
            "kerfOffset": mm(kerf_offset),
            "kerfDirection": "in",
        }
    if layer in {"TEXT", "NUMBERS", "MARK"}:
        return {
            "name": layer,
            "mode": "fill",
            "type": "Fill",
            "color": "#000000",
            "kerfOffset": "0",
            "kerfDirection": "none",
        }
    return {
        "name": layer,
        "mode": "line",
        "type": "Cut",
        "color": layer_color(layer),
        "kerfOffset": mm(kerf_offset),
        "kerfDirection": "out",
    }


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
    layers = drawing_layers(drawing)
    lines += dxf_pair(0, "TABLE") + dxf_pair(2, "LAYER") + dxf_pair(70, len(layers))
    for layer_name in layers:
        lines += dxf_pair(0, "LAYER")
        lines += dxf_pair(2, layer_name)
        lines += dxf_pair(70, "0")
        lines += dxf_pair(62, dxf_layer_color(layer_name))
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


def lightburn_path_shape(parent: ET.Element, entity: Polyline | Line) -> None:
    layer = entity.layer
    if isinstance(entity, Line):
        points = [entity.start, entity.end]
        closed = False
    else:
        points = entity.points
        closed = entity.closed

    if not points:
        return

    shape = ET.SubElement(
        parent,
        "Shape",
        {
            "Type": "Path",
            "CutIndex": str(lightburn_layer_index(layer)),
            "Layer": layer,
            "Closed": "True" if closed else "False",
        },
    )
    ET.SubElement(shape, "XForm").text = "1 0 0 1 0 0"
    vert_list = ET.SubElement(shape, "VertList")
    for x, y in points:
        ET.SubElement(vert_list, "V", {"vx": mm(x), "vy": mm(y)})
    prim_list = ET.SubElement(shape, "PrimList")
    segment_count = len(points) if closed else len(points) - 1
    for index in range(segment_count):
        ET.SubElement(
            prim_list,
            "P",
            {
                "T": "L",
                "p0": str(index),
                "p1": str((index + 1) % len(points)),
            },
        )


def lightburn_text_shape(parent: ET.Element, entity: Text) -> None:
    shape = ET.SubElement(
        parent,
        "Shape",
        {
            "Type": "Text",
            "CutIndex": str(lightburn_layer_index(entity.layer)),
            "Layer": entity.layer,
            "Str": entity.text,
            "H": mm(entity.size),
            "Align": entity.anchor,
            "Rot": mm(entity.rotation),
        },
    )
    ET.SubElement(shape, "XForm").text = f"1 0 0 1 {mm(entity.x)} {mm(entity.y)}"


def indent_xml(element: ET.Element, level: int = 0) -> None:
    space = "\n" + level * "  "
    if len(element):
        if not element.text or not element.text.strip():
            element.text = space + "  "
        for child in element:
            indent_xml(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = space
    if level and (not element.tail or not element.tail.strip()):
        element.tail = space


def write_lightburn_fit(drawing: Drawing, path: Path, kerf_offset: float = 0.0) -> None:
    if kerf_offset < 0:
        raise ValueError("Known kerf must be zero or greater.")

    root = ET.Element(
        "LightBurnProject",
        {
            "AppVersion": "LaserTesterGenerator",
            "FormatVersion": "1",
            "MaterialHeight": "0",
            "MirrorX": "False",
            "MirrorY": "False",
            "Units": drawing.units,
        },
    )
    layers = ["OUTSIDE", "HOLES", "TEXT", "NUMBERS"]
    for index, layer in enumerate(layers):
        settings = lightburn_layer_settings(layer, kerf_offset)
        ET.SubElement(
            root,
            "CutSetting",
            {
                "index": str(index),
                "name": settings["name"],
                "type": settings["type"],
                "mode": settings["mode"],
                "color": settings["color"],
                "kerfOffset": settings["kerfOffset"],
                "kerfDirection": settings["kerfDirection"],
                "priority": str(index),
            },
        )

    metadata = ET.SubElement(root, "LayerMetadata")
    for index, layer in enumerate(layers):
        settings = lightburn_layer_settings(layer, kerf_offset)
        ET.SubElement(metadata, "Layer", {"index": str(index), **settings})

    for entity in drawing.entities:
        if isinstance(entity, (Polyline, Line)):
            lightburn_path_shape(root, entity)
        elif isinstance(entity, Text):
            lightburn_text_shape(root, entity)

    indent_xml(root)
    tree = ET.ElementTree(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(path, encoding="utf-8", xml_declaration=True)


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
    fit_drawing = generate_fit(fit)
    write_svg(fit_drawing, directory / "fit-allowance-tester-sample.svg")
    write_dxf(fit_drawing, directory / "fit-allowance-tester-sample.dxf")
    write_lightburn_fit(fit_drawing, directory / "fit-allowance-tester-sample.lbrn2", fit.known_kerf)
    save_params(directory / "sample-parameters.json", kerf, fit)


def clamped_label_position(
    x: float,
    y: float,
    text_width: float,
    text_height: float,
    canvas_width: float,
    canvas_height: float,
    margin: float = 6.0,
) -> Point:
    half_width = text_width / 2
    half_height = text_height / 2
    safe_x = min(max(x, half_width + margin), canvas_width - half_width - margin)
    safe_y = min(max(y, half_height + margin), canvas_height - half_height - margin)
    return safe_x, safe_y


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
            if tool_name == "fit":
                buttons.insert(3, ("Export LBRN2", lambda: self.export_active("lbrn2")))
            for index, (label, command) in enumerate(buttons):
                button = ttk.Button(button_grid, text=label, command=command)
                button.grid(row=index // 2, column=index % 2, sticky="ew", padx=3, pady=3)
            button_grid.columnconfigure(0, weight=1)
            button_grid.columnconfigure(1, weight=1)

            ttk.Label(
                controls,
                text="Cut geometry exports red. Text and numbers export black fill/score layers.",
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
                active_name = self.active_name()
                kerf, fit = self.current_params()
                drawing = generate_kerf(kerf) if active_name == "kerf" else generate_fit(fit)
            except Exception as exc:
                messagebox.showerror("Invalid parameters", str(exc))
                return
            if filetype == "lbrn2" and active_name != "fit":
                messagebox.showinfo("Fit only", "LightBurn LBRN2 export is available for the fit tester.")
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
                elif filetype == "dxf":
                    write_dxf(drawing, path)
                else:
                    write_lightburn_fit(drawing, path, fit.known_kerf)
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
        padding = 42.0 if highlight_field else 28.0
        scale = min((width - padding * 2) / drawing_width, (height - padding * 2) / drawing_height)
        scale = max(scale, 0.1)
        offset_x = (width - drawing_width * scale) / 2 - min_x * scale
        offset_y = (height - drawing_height * scale) / 2 - min_y * scale

        def tx(point: Point) -> Point:
            return (point[0] * scale + offset_x, point[1] * scale + offset_y)

        for entity in drawing.entities:
            color = "#ff0000" if entity.layer in {"CUT", "OUTSIDE", "HOLES"} else "#111111"
            if isinstance(entity, Polyline):
                points = entity.points[:]
                if entity.closed and points:
                    points.append(points[0])
                coords: list[float] = []
                for point in points:
                    x, y = tx(point)
                    coords.extend([x, y])
                canvas.create_line(*coords, fill=color, width=1.4 if entity.layer in {"CUT", "OUTSIDE", "HOLES"} else 1.0)
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
        label_fill = "#fff7ed"
        label = KERF_FIELD_LABELS.get(field_name) if tool_name == "kerf" else FIT_FIELD_LABELS.get(field_name)
        label = label or field_name

        def label_at(x: float, y: float, text: str, preferred: str = "above") -> None:
            canvas_width = max(canvas.winfo_width(), 200)
            canvas_height = max(canvas.winfo_height(), 200)
            text_width = max(84, min(260, len(text) * 7 + 18))
            text_height = 22
            gap = 16

            if preferred == "below":
                y += gap
            elif preferred == "left":
                x -= text_width / 2 + gap
            elif preferred == "right":
                x += text_width / 2 + gap
            elif preferred == "inside":
                y += 2
            else:
                y -= gap

            x, y = clamped_label_position(x, y, text_width, text_height, canvas_width, canvas_height)
            half_width = text_width / 2
            half_height = text_height / 2
            canvas.create_rectangle(
                x - half_width,
                y - half_height,
                x + half_width,
                y + half_height,
                fill=label_fill,
                outline=highlight,
                width=1,
            )
            canvas.create_text(
                x,
                y,
                text=text,
                fill="#9a5b00",
                font=("Segoe UI", 9, "bold"),
                width=text_width - 10,
            )

        def preferred_for_line(x1: float, y1: float, x2: float, y2: float) -> str:
            canvas_width = max(canvas.winfo_width(), 200)
            canvas_height = max(canvas.winfo_height(), 200)
            if abs(x2 - x1) >= abs(y2 - y1):
                return "below" if (y1 + y2) / 2 < 46 else "above"
            return "left" if (x1 + x2) / 2 > canvas_width - 110 else "right"

        def line(start: Point, end: Point, text: str = label, preferred: str | None = None) -> None:
            x1, y1 = tx(start)
            x2, y2 = tx(end)
            canvas.create_line(x1, y1, x2, y2, fill=highlight, width=2, arrow="both")
            label_at((x1 + x2) / 2, (y1 + y2) / 2, text, preferred or preferred_for_line(x1, y1, x2, y2))

        def box(
            x: float,
            y: float,
            width: float,
            height: float,
            text: str = label,
            preferred: str = "above",
        ) -> None:
            x1, y1 = tx((x, y))
            x2, y2 = tx((x + width, y + height))
            canvas.create_rectangle(x1, y1, x2, y2, outline=highlight, width=2, dash=(4, 2))
            top = min(y1, y2)
            bottom = max(y1, y2)
            label_anchor_y = top if preferred == "above" else bottom
            if preferred == "inside":
                label_anchor_y = top + 12
            label_at((x1 + x2) / 2, label_anchor_y, text, preferred)

        if tool_name == "kerf" and isinstance(params, KerfParams):
            layout = kerf_layout(params)
            track_x = layout["track_x"]
            track_y = layout["track_y"]
            row_bottom = layout["row_bottom"]
            track_bottom = layout["track_bottom"]
            discard_x = layout["discard_x"]
            inner_right = layout["inner_right"]
            nose_x = layout["nose_x"]
            if field_name == "plate_width":
                line((0, -2.5), (params.plate_width, -2.5), preferred="below")
            elif field_name == "plate_height":
                line((params.plate_width + 3.0, 0), (params.plate_width + 3.0, params.plate_height), preferred="left")
            elif field_name == "scale_units":
                line((track_x, track_y - 7.0), (layout["top_scale_end"], track_y - 7.0), preferred="above")
            elif field_name == "scale_tick_spacing":
                line((track_x, track_y - 6.0), (track_x + params.scale_tick_spacing, track_y - 6.0), preferred="above")
            elif field_name == "vernier_divisions":
                line((track_x, track_bottom + 7.0), (track_x + layout["vernier_length"], track_bottom + 7.0), preferred="above")
            elif field_name == "piece_count":
                box(track_x, track_y, inner_right - track_x, layout["row_height"], preferred="inside")
            elif field_name == "pass_count":
                box(params.plate_width - params.margin - 50.0, params.margin - 1.0, 47.0, params.tick_label_size + 3.0, preferred="below")
            elif field_name == "discard_piece_count":
                box(nose_x, row_bottom, inner_right - nose_x, params.slide_height, preferred="below")
            elif field_name == "margin":
                line((0, params.plate_height / 2), (params.margin, params.plate_height / 2), preferred="below")
            elif field_name == "track_height":
                line((track_x - 5.0, track_y), (track_x - 5.0, track_bottom), preferred="right")
            elif field_name == "slide_height":
                line((discard_x - 3.0, row_bottom), (discard_x - 3.0, track_bottom), preferred="left")
            elif field_name == "label_size":
                box(params.plate_width / 2 - 32.0, params.margin, 64.0, params.label_size + 2.0, preferred="below")
            elif field_name == "tick_label_size":
                box(track_x - 3.0, track_y - 9.0, layout["top_scale_end"] - track_x + 6.0, params.tick_label_size + 4.0, preferred="above")
            elif field_name == "include_labels":
                box(track_x - 5.0, params.margin - 1.0, params.plate_width - track_x - params.margin + 4.0, track_bottom + 7.0, preferred="inside")
            return

        if tool_name == "fit" and isinstance(params, FitParams):
            layout = fit_layout(params)
            slots = layout["slots"]
            fit_count = len(layout["fit_values"])
            first_slot = slots[0]
            first_fit_row = slots[:fit_count]
            first_material_column = slots[::fit_count]
            last_fit_slot = first_fit_row[-1]
            last_material_slot = first_material_column[-1]
            coupon_x = layout["coupon_x"]
            coupon_y = layout["coupon_y"]
            pin_x = layout["pin_x"]
            pin_y = layout["pin_y"]
            pin_right = pin_x + layout["pin_width"]
            body_y = layout["body_y"]
            coupon_bottom = body_y + layout["body_height"]

            if field_name == "fit_variable_center":
                line((pin_x, pin_y - 2.0), (pin_right, pin_y - 2.0), preferred="above")
            elif field_name == "fit_variable_count":
                box(
                    first_fit_row[0]["x"],
                    0,
                    last_fit_slot["x"] + last_fit_slot["width"] - first_fit_row[0]["x"],
                    layout["coupon_height"],
                    preferred="inside",
                )
            elif field_name == "fit_variable_min":
                box(first_slot["x"], first_slot["y"], first_slot["width"], first_slot["height"], preferred="inside")
            elif field_name == "fit_variable_max":
                box(last_fit_slot["x"], last_fit_slot["y"], last_fit_slot["width"], last_fit_slot["height"], preferred="inside")
            elif field_name == "fit_variable_step" and len(first_fit_row) > 1:
                line(
                    (first_slot["x"] + first_slot["width"] / 2, first_slot["label_y"] + 3.0),
                    (first_fit_row[1]["x"] + first_fit_row[1]["width"] / 2, first_fit_row[1]["label_y"] + 3.0),
                    preferred="below",
                )
            elif field_name == "material_thickness":
                line((first_slot["x"], first_slot["y"] - 3.0), (first_slot["x"] + first_slot["width"], first_slot["y"] - 3.0), preferred="above")
            elif field_name == "material_count":
                box(
                    0,
                    first_material_column[0]["y"],
                    layout["coupon_length"],
                    last_material_slot["y"] + last_material_slot["height"] - first_material_column[0]["y"],
                    preferred="inside",
                )
            elif field_name == "material_min":
                box(first_slot["x"], first_slot["y"], first_slot["width"], first_slot["height"], preferred="inside")
            elif field_name == "material_max":
                box(last_material_slot["x"], last_material_slot["y"], last_material_slot["width"], last_material_slot["height"], preferred="inside")
            elif field_name == "material_step" and len(first_material_column) > 1:
                line(
                    (first_material_column[0]["x"] - 3.0, first_material_column[0]["y"] + first_material_column[0]["height"] / 2),
                    (first_material_column[1]["x"] - 3.0, first_material_column[1]["y"] + first_material_column[1]["height"] / 2),
                    preferred="left",
                )
            elif field_name == "spacing_margin":
                line((0, layout["coupon_height"] / 2), (params.spacing_margin, layout["coupon_height"] / 2), preferred="below")
            elif field_name == "shoulder_length":
                line((pin_right + 3.0, pin_y), (pin_right + 3.0, body_y), preferred="right")
            elif field_name == "shoulder_width":
                line((coupon_x, body_y + 3.0), (pin_x, body_y + 3.0), preferred="below")
            elif field_name == "overall_coupon_length":
                line((0, -2.5), (layout["coupon_length"], -2.5), preferred="below")
            elif field_name == "overall_coupon_height":
                line((layout["coupon_length"] + 3.0, 0), (layout["coupon_length"] + 3.0, layout["coupon_height"]), preferred="left")
            elif field_name == "known_kerf":
                box(0, 0, layout["coupon_length"], layout["coupon_height"], preferred="inside")
            elif field_name == "label_size":
                box(first_slot["x"], first_slot["label_y"] - params.label_size, layout["hole_width"], params.label_size + 2.0, preferred="below")
            elif field_name == "include_labels":
                box(0, 0, layout["coupon_length"], layout["coupon_height"], preferred="inside")

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
