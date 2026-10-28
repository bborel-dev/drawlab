import re

PATH_ELEMENT = re.compile(r"<path ([^>]*)/>")
ATTRIBUTE = re.compile(r'([a-z-]+)="([^"]*)"')
TRANSLATE = re.compile(r"translate\(\s*(-?[\d.]+)[\s,]+(-?[\d.]+)\s*\)")
PATH_TOKEN = re.compile(r"[A-Za-z]|-?(?:\d+\.?\d*|\.\d+)(?:e-?\d+)?")
SEAM_ATTRIBUTES = ' stroke-width="1" stroke-linejoin="round"'
COLOR_GROUP_OPEN = 'data-pass="color"'
COMMAND_SIZES = {"M": 2, "L": 2, "C": 6, "Z": 0}
STRAIGHT_TOLERANCE = 1.5
UNITS_PER_PIXEL = 10

Point = tuple[int, int]


def compact_markup(markup: str) -> str:
    compacted = PATH_ELEMENT.sub(lambda match: compact_path(match.group(1)), markup)
    if SEAM_ATTRIBUTES not in compacted:
        return compacted
    return compacted.replace(SEAM_ATTRIBUTES, "").replace(COLOR_GROUP_OPEN, COLOR_GROUP_OPEN + SEAM_ATTRIBUTES)


def compact_path(attributes: str) -> str:
    values = dict(ATTRIBUTE.findall(attributes))
    offset = translation(values.pop("transform", ""))
    if offset is None:
        return f"<path {attributes}/>"
    data = compact_data(values.pop("d", ""), offset)
    if data is None:
        return f"<path {attributes}/>"
    if not data:
        return ""
    rest = "".join(f' {name}="{value}"' for name, value in values.items())
    return f'<path d="{data}"{rest}/>'


def translation(transform: str) -> tuple[float, float] | None:
    if not transform:
        return (0.0, 0.0)
    match = TRANSLATE.fullmatch(transform.strip())
    return (float(match.group(1)), float(match.group(2))) if match else None


def compact_data(data: str, offset: tuple[float, float]) -> str | None:
    segments = parse_segments(data)
    if segments is None:
        return None
    writer = RelativePathWriter()
    for command, numbers in segments:
        points = [to_units(numbers[index] + offset[0], numbers[index + 1] + offset[1]) for index in range(0, len(numbers), 2)]
        writer.add(command, points)
    return writer.text()


def parse_segments(data: str) -> list[tuple[str, list[float]]] | None:
    tokens = PATH_TOKEN.findall(data)
    segments: list[tuple[str, list[float]]] = []
    index = 0
    while index < len(tokens):
        command = tokens[index]
        size = COMMAND_SIZES.get(command)
        if size is None:
            return None
        operands = tokens[index + 1 : index + 1 + size]
        if len(operands) != size or any(token.isalpha() for token in operands):
            return None
        segments.append((command, [float(token) for token in operands]))
        index += 1 + size
    return segments


def to_units(x: float, y: float) -> Point:
    return (round(x * UNITS_PER_PIXEL), round(y * UNITS_PER_PIXEL))


class RelativePathWriter:
    def __init__(self) -> None:
        self.parts: list[str] = []
        self.last_command = ""
        self.current: Point = (0, 0)
        self.subpath_start: Point = (0, 0)
        self.has_drawing = False

    def add(self, command: str, points: list[Point]) -> None:
        if command == "M":
            self.move(points[0])
        elif command == "L":
            self.line(points[0])
        elif command == "C":
            self.curve(points)
        else:
            self.close()

    def move(self, target: Point) -> None:
        letter = "M" if not self.parts else "m"
        self.emit(letter, [self.delta(target) if letter == "m" else target])
        self.current = self.subpath_start = target

    def line(self, target: Point) -> None:
        if target != self.current:
            self.emit("l", [self.delta(target)])
            self.current = target
            self.has_drawing = True

    def curve(self, points: list[Point]) -> None:
        first, second, target = points
        if is_straight(self.current, first, second, target):
            self.line(target)
            return
        self.emit("c", [self.delta(first), self.delta(second), self.delta(target)])
        self.current = target
        self.has_drawing = True

    def close(self) -> None:
        self.emit("z", [])
        self.current = self.subpath_start

    def delta(self, point: Point) -> Point:
        return (point[0] - self.current[0], point[1] - self.current[1])

    def emit(self, letter: str, points: list[Point]) -> None:
        numbers = [format_units(value) for point in points for value in point]
        repeated = letter == self.last_command and letter in "lc"
        self.parts.append(("" if repeated else letter) + join_numbers(numbers, leading_space=repeated))
        self.last_command = {"z": "", "M": "L", "m": "l"}.get(letter, letter)

    def text(self) -> str:
        return "".join(self.parts) if self.has_drawing else ""


def is_straight(start: Point, first: Point, second: Point, end: Point) -> bool:
    dx, dy = end[0] - start[0], end[1] - start[1]
    length_squared = dx * dx + dy * dy
    if length_squared == 0:
        return first == start and second == start
    for x, y in (first, second):
        cross = (x - start[0]) * dy - (y - start[1]) * dx
        if cross * cross > STRAIGHT_TOLERANCE * STRAIGHT_TOLERANCE * length_squared:
            return False
        along = (x - start[0]) * dx + (y - start[1]) * dy
        if along < 0 or along > length_squared:
            return False
    return True


def format_units(value: int) -> str:
    sign = "-" if value < 0 else ""
    whole, tenths = divmod(abs(value), UNITS_PER_PIXEL)
    if tenths == 0:
        return f"{sign}{whole}"
    return f"{sign}{whole if whole else ''}.{tenths}"


def join_numbers(numbers: list[str], leading_space: bool) -> str:
    text = ""
    for index, number in enumerate(numbers):
        needs_space = (index > 0 or leading_space) and not number.startswith("-")
        text += (" " if needs_space else "") + number
    return text
