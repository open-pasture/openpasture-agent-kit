"""Polygon operations for turning boundary commands into single collar rings.

V0 collars hold one ring with no holes. To send a command the gateway has to
merge rings (old paddock + corridor + new paddock during a transition) and cut
exclusions out of the boundary. This module does both with the Greiner-Hormann
clipping algorithm over simple polygons, projected to local meters.

Paddocks often share fence lines, which makes edges overlap exactly. That is a
degenerate case for the algorithm, so on a degenerate input the clip polygon is
grown outward by a small margin and the operation retried. The growth is always
toward the safe side: an exclusion gets slightly bigger, and a transition area
gets slightly bigger for its short open phase.
"""

from __future__ import annotations

import math

Point = tuple[float, float]

_PARAM_TOLERANCE = 1e-9
_DISTANCE_TOLERANCE_M = 1e-6
# Outward growth (meters) tried when the exact operation hits a degenerate case.
RETRY_MARGINS_M = (0.5, 1.5)


class RingOperationError(ValueError):
    """The operation cannot produce one simple ring."""


class _Projection:
    """Equirectangular projection around a reference point. Fine at paddock scale."""

    def __init__(self, longitude: float, latitude: float) -> None:
        self.lon0 = longitude
        self.lat0 = latitude
        self.kx = 111_320.0 * math.cos(math.radians(latitude))
        self.ky = 111_320.0

    def forward(self, ring: list[list[float]] | list[Point]) -> list[Point]:
        return [((float(p[0]) - self.lon0) * self.kx, (float(p[1]) - self.lat0) * self.ky) for p in ring]

    def inverse(self, ring: list[Point]) -> list[list[float]]:
        return [[round(self.lon0 + x / self.kx, 7), round(self.lat0 + y / self.ky, 7)] for x, y in ring]


def clean_ring(ring: list[list[float]] | list[Point]) -> list[Point]:
    """Drop the closing vertex and consecutive duplicates."""

    points: list[Point] = []
    for raw in ring:
        point = (float(raw[0]), float(raw[1]))
        if points and abs(points[-1][0] - point[0]) < 1e-12 and abs(points[-1][1] - point[1]) < 1e-12:
            continue
        points.append(point)
    while len(points) > 1 and abs(points[0][0] - points[-1][0]) < 1e-12 and abs(points[0][1] - points[-1][1]) < 1e-12:
        points.pop()
    return points


def signed_area(ring: list[Point]) -> float:
    total = 0.0
    for index, (x1, y1) in enumerate(ring):
        x2, y2 = ring[(index + 1) % len(ring)]
        total += x1 * y2 - x2 * y1
    return total / 2.0


def point_in_ring(point: Point, ring: list[Point]) -> bool:
    x, y = point
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def _segments_cross(p1: Point, p2: Point, q1: Point, q2: Point) -> bool:
    def orient(a: Point, b: Point, c: Point) -> float:
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    d1, d2 = orient(q1, q2, p1), orient(q1, q2, p2)
    d3, d4 = orient(p1, p2, q1), orient(p1, p2, q2)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))


def ring_is_simple(ring: list[list[float]] | list[Point]) -> bool:
    """True when no two non-adjacent edges cross."""

    points = clean_ring(ring)
    count = len(points)
    for i in range(count):
        a1, a2 = points[i], points[(i + 1) % count]
        for j in range(i + 1, count):
            if j == i or (j + 1) % count == i or j == (i + 1) % count:
                continue
            if _segments_cross(a1, a2, points[j], points[(j + 1) % count]):
                return False
    return True


def _distance_to_segment(point: Point, a: Point, b: Point) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return math.hypot(point[0] - a[0], point[1] - a[1])
    t = max(0.0, min(1.0, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / length_sq))
    return math.hypot(point[0] - (a[0] + t * dx), point[1] - (a[1] + t * dy))


def _on_boundary(point: Point, ring: list[Point]) -> bool:
    return any(
        _distance_to_segment(point, ring[i], ring[(i + 1) % len(ring)]) < _DISTANCE_TOLERANCE_M
        for i in range(len(ring))
    )


def offset_ring(ring: list[Point], distance: float) -> list[Point]:
    """Grow a ring outward by ``distance`` meters using mitered vertex offsets."""

    ccw = signed_area(ring) > 0
    count = len(ring)
    grown: list[Point] = []
    for i in range(count):
        prev_point, point, next_point = ring[i - 1], ring[i], ring[(i + 1) % count]
        normals = []
        for a, b in ((prev_point, point), (point, next_point)):
            dx, dy = b[0] - a[0], b[1] - a[1]
            length = math.hypot(dx, dy) or 1.0
            normals.append((dy / length, -dx / length) if ccw else (-dy / length, dx / length))
        bx, by = normals[0][0] + normals[1][0], normals[0][1] + normals[1][1]
        norm = math.hypot(bx, by)
        if norm < 1e-9:
            bx, by, norm = normals[0][0], normals[0][1], 1.0
        bx, by = bx / norm, by / norm
        cos_half = bx * normals[0][0] + by * normals[0][1]
        scale = distance / max(cos_half, 0.3)
        grown.append((point[0] + bx * scale, point[1] + by * scale))
    return grown


class _Node:
    __slots__ = ("x", "y", "next", "prev", "intersect", "entry", "neighbor", "alpha", "visited")

    def __init__(self, x: float, y: float, *, intersect: bool = False, alpha: float = 0.0) -> None:
        self.x = x
        self.y = y
        self.next: _Node = self
        self.prev: _Node = self
        self.intersect = intersect
        self.entry = False
        self.neighbor: _Node | None = None
        self.alpha = alpha
        self.visited = False

    @property
    def point(self) -> Point:
        return (self.x, self.y)


def _build(ring: list[Point]) -> list[_Node]:
    nodes = [_Node(x, y) for x, y in ring]
    for index, node in enumerate(nodes):
        node.next = nodes[(index + 1) % len(nodes)]
        node.prev = nodes[index - 1]
    return nodes


def _insert(node: _Node, start: _Node, end: _Node) -> None:
    current = start.next
    while current is not end and current.intersect and current.alpha < node.alpha:
        current = current.next
    node.next = current
    node.prev = current.prev
    current.prev.next = node
    current.prev = node


def _intersection(p1: Point, p2: Point, q1: Point, q2: Point) -> tuple[float, float, Point] | None:
    rx, ry = p2[0] - p1[0], p2[1] - p1[1]
    sx, sy = q2[0] - q1[0], q2[1] - q1[1]
    denom = rx * sy - ry * sx
    qpx, qpy = q1[0] - p1[0], q1[1] - p1[1]
    if abs(denom) < 1e-12:
        # Parallel. Overlapping collinear edges are degenerate for the algorithm.
        if abs(qpx * ry - qpy * rx) < 1e-9 and (
            _distance_to_segment(q1, p1, p2) < _DISTANCE_TOLERANCE_M
            or _distance_to_segment(q2, p1, p2) < _DISTANCE_TOLERANCE_M
            or _distance_to_segment(p1, q1, q2) < _DISTANCE_TOLERANCE_M
        ):
            raise RingOperationError("Edges overlap.")
        return None
    a = (qpx * sy - qpy * sx) / denom
    b = (qpx * ry - qpy * rx) / denom
    if a < -_PARAM_TOLERANCE or a > 1 + _PARAM_TOLERANCE or b < -_PARAM_TOLERANCE or b > 1 + _PARAM_TOLERANCE:
        return None
    if min(abs(a), abs(1 - a), abs(b), abs(1 - b)) <= _PARAM_TOLERANCE * 10:
        raise RingOperationError("Rings touch at a vertex.")
    return a, b, (p1[0] + a * rx, p1[1] + a * ry)


def _boolean(subject: list[Point], clip: list[Point], operation: str) -> list[list[Point]]:
    """Greiner-Hormann for simple polygons. ``operation`` is union or difference."""

    subject_nodes = _build(subject)
    clip_nodes = _build(clip)
    found = False
    for i, s1 in enumerate(subject_nodes):
        s2 = subject_nodes[(i + 1) % len(subject_nodes)]
        for j, c1 in enumerate(clip_nodes):
            c2 = clip_nodes[(j + 1) % len(clip_nodes)]
            hit = _intersection(s1.point, s2.point, c1.point, c2.point)
            if hit is None:
                continue
            a, b, (x, y) = hit
            s_node = _Node(x, y, intersect=True, alpha=a)
            c_node = _Node(x, y, intersect=True, alpha=b)
            s_node.neighbor, c_node.neighbor = c_node, s_node
            _insert(s_node, s1, s2)
            _insert(c_node, c1, c2)
            found = True

    if not found:
        if any(_on_boundary(point, clip) for point in subject) or any(_on_boundary(point, subject) for point in clip):
            raise RingOperationError("Rings touch without crossing.")
        subject_inside = point_in_ring(subject[0], clip)
        clip_inside = point_in_ring(clip[0], subject)
        if operation == "union":
            if subject_inside:
                return [clip]
            if clip_inside:
                return [subject]
            return [subject, clip]
        if subject_inside:
            return []
        if clip_inside:
            raise RingOperationError("hole")
        return [subject]

    # Entry/exit marking. Union flips both lists; difference flips the subject.
    for start, other, flip in (
        (subject_nodes[0], clip, True),
        (clip_nodes[0], subject, operation == "union"),
    ):
        if _on_boundary(start.point, other):
            raise RingOperationError("Vertex lies on the other ring.")
        inside = point_in_ring(start.point, other)
        node = start
        while True:
            if node.intersect:
                node.entry = (not inside) != flip
                inside = not inside
            node = node.next
            if node is start:
                break

    results: list[list[Point]] = []
    intersections = []
    node = subject_nodes[0]
    while True:
        if node.intersect:
            intersections.append(node)
        node = node.next
        if node is subject_nodes[0]:
            break
    for start in intersections:
        if start.visited:
            continue
        polygon = [start.point]
        current = start
        current.visited = True
        if current.neighbor is not None:
            current.neighbor.visited = True
        for _ in range(10_000):
            forward = current.entry
            while True:
                current = current.next if forward else current.prev
                polygon.append(current.point)
                if current.intersect:
                    break
            current.visited = True
            if current.neighbor is None:
                raise RingOperationError("Broken intersection graph.")
            current.neighbor.visited = True
            current = current.neighbor
            if current is start or current.neighbor is start:
                break
        else:
            raise RingOperationError("Clipping did not close.")
        cleaned = clean_ring(polygon)
        if len(cleaned) >= 3 and abs(signed_area(cleaned)) > 1e-6:
            results.append(cleaned)
    return results


def _with_retries(subject: list[Point], clip: list[Point], operation: str) -> list[list[Point]]:
    try:
        return _boolean(subject, clip, operation)
    except RingOperationError as exc:
        if str(exc) == "hole":
            raise
        last_error = exc
    for margin in RETRY_MARGINS_M:
        try:
            return _boolean(subject, offset_ring(clip, margin), operation)
        except RingOperationError as exc:
            if str(exc) == "hole":
                raise
            last_error = exc
    raise RingOperationError(f"Could not combine the shapes cleanly ({last_error}).")


def union_rings(rings: list[list[list[float]]]) -> list[list[float]]:
    """Merge lon/lat rings into one ring. Raises when they do not form one area."""

    cleaned = [clean_ring(ring) for ring in rings if ring]
    if not cleaned:
        raise RingOperationError("Nothing to merge.")
    projection = _Projection(*cleaned[0][0])
    merged = projection.forward(cleaned[0])
    for ring in cleaned[1:]:
        pieces = _with_retries(merged, projection.forward(ring), "union")
        if len(pieces) != 1:
            raise RingOperationError("The shapes do not join into one connected area without gaps.")
        merged = pieces[0]
    return projection.inverse(merged)


def subtract_ring(boundary: list[list[float]], exclusion: list[list[float]]) -> list[list[float]] | None:
    """Cut an exclusion out of a boundary ring.

    Returns the new ring, or None when the exclusion does not touch the
    boundary. Raises when the exclusion sits wholly inside (a hole), splits the
    boundary, or covers it.
    """

    boundary_points = clean_ring(boundary)
    projection = _Projection(*boundary_points[0])
    subject = projection.forward(boundary_points)
    clip = projection.forward(clean_ring(exclusion))
    try:
        pieces = _with_retries(subject, clip, "difference")
    except RingOperationError as exc:
        if str(exc) == "hole":
            raise RingOperationError(
                "The exclusion sits entirely inside the boundary. V0 collars cannot enforce holes yet."
            ) from exc
        raise
    if not pieces:
        raise RingOperationError("The exclusion covers the whole boundary.")
    if len(pieces) > 1:
        raise RingOperationError("The exclusion splits the boundary into separate pieces.")
    if len(pieces[0]) == len(subject) and abs(abs(signed_area(pieces[0])) - abs(signed_area(subject))) < 1e-6:
        return None
    return projection.inverse(pieces[0])
