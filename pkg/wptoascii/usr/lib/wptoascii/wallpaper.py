from PIL import Image, ImageDraw, ImageFont
import argparse
import json
import os
import re
import subprocess
import sys


# ============================================================
# DEFAULT SETTINGS
# ============================================================

DEFAULT_CHARS = "@#S%?*+;:,."

QUALITY_PRESETS = {
    "low": 35,
    "medium": 60,
    "high": 90,
    "ultra": 120,
}


# ============================================================
# SCREEN DETECTION
# ============================================================

def get_screen_size():
    """
    Detect the active screen resolution.

    Priority:
      1. Hyprland (hyprctl monitors -j)
      2. xrandr
      3. xdpyinfo
      4. Windows API
      5. macOS system_profiler
    """

    # --------------------------------------------------------
    # Hyprland / Wayland
    # --------------------------------------------------------

    if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        try:
            result = subprocess.run(
                ["hyprctl", "monitors", "-j"],
                capture_output=True,
                text=True,
                check=True,
            )

            monitors = json.loads(result.stdout)

            if monitors:
                # Prefer the focused monitor.
                focused = next(
                    (
                        monitor
                        for monitor in monitors
                        if monitor.get("focused")
                    ),
                    monitors[0],
                )

                width = int(focused["width"])
                height = int(focused["height"])
                scale = float(focused.get("scale", 1))

                # Hyprland reports logical dimensions together with scale.
                # Convert to the physical pixel dimensions used by PNG.
                physical_width = round(width )
                physical_height = round(height )

                return physical_width, physical_height

        except (
            FileNotFoundError,
            subprocess.SubprocessError,
            ValueError,
            KeyError,
            json.JSONDecodeError,
        ):
            pass

    # --------------------------------------------------------
    # Linux / X11 / XWayland: xrandr
    # --------------------------------------------------------

    if sys.platform.startswith("linux"):
        try:
            result = subprocess.run(
                ["xrandr", "--current"],
                capture_output=True,
                text=True,
                check=True,
            )

            for line in result.stdout.splitlines():
                if line.startswith("Screen "):
                    marker = "current "

                    if marker in line:
                        part = line.split(
                            marker,
                            1,
                        )[1]

                        dimensions = part.split(
                            ",",
                            1,
                        )[0].strip()

                        width, height = dimensions.split(
                            " x "
                        )

                        return int(width), int(height)

        except (
            FileNotFoundError,
            subprocess.SubprocessError,
            ValueError,
        ):
            pass

        # ----------------------------------------------------
        # Linux fallback: xdpyinfo
        # ----------------------------------------------------

        try:
            result = subprocess.run(
                ["xdpyinfo"],
                capture_output=True,
                text=True,
                check=True,
            )

            for line in result.stdout.splitlines():
                if "dimensions:" in line:
                    dimensions = line.split(
                        "dimensions:",
                        1,
                    )[1].strip().split()[0]

                    width, height = dimensions.split("x")

                    return int(width), int(height)

        except (
            FileNotFoundError,
            subprocess.SubprocessError,
            ValueError,
        ):
            pass

    # --------------------------------------------------------
    # Windows
    # --------------------------------------------------------

    if sys.platform.startswith("win"):
        try:
            import ctypes

            user32 = ctypes.windll.user32

            return (
                user32.GetSystemMetrics(0),
                user32.GetSystemMetrics(1),
            )

        except Exception:
            pass

    # --------------------------------------------------------
    # macOS
    # --------------------------------------------------------

    if sys.platform == "darwin":
        try:
            result = subprocess.run(
                [
                    "system_profiler",
                    "SPDisplaysDataType",
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            match = re.search(
                r"Resolution:\s*(\d+)\s*x\s*(\d+)",
                result.stdout,
            )

            if match:
                return (
                    int(match.group(1)),
                    int(match.group(2)),
                )

        except (
            FileNotFoundError,
            subprocess.SubprocessError,
        ):
            pass

    raise RuntimeError(
        "Не удалось автоматически определить разрешение экрана.\n"
        "Используй --screen WIDTH HEIGHT"
    )


# ============================================================
# FONT DETECTION
# ============================================================

def get_monospace_fonts():
    """Find installed fonts on Linux."""
    fonts = []

    if not sys.platform.startswith("linux"):
        return fonts

    try:
        result = subprocess.run(
            [
                "fc-list",
                ":",
                "file",
                "family",
                "style",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        for line in result.stdout.splitlines():
            parts = line.split(":", 2)

            if len(parts) < 2:
                continue

            path = parts[0].strip()
            family = parts[1].strip()

            if os.path.isfile(path):
                fonts.append((family, path))

    except (
        FileNotFoundError,
        subprocess.SubprocessError,
    ):
        pass

    # Remove duplicate files.
    unique = []
    seen = set()

    for family, path in fonts:
        if path not in seen:
            seen.add(path)
            unique.append((family, path))

    # Prefer fonts that are likely monospace.
    preferred_words = (
        "mono",
        "monospace",
        "code",
        "consolas",
        "courier",
        "terminal",
        "hack",
        "jetbrains",
        "inconsolata",
    )

    preferred = []
    other = []

    for item in unique:
        family_lower = item[0].lower()

        if any(
            word in family_lower
            for word in preferred_words
        ):
            preferred.append(item)
        else:
            other.append(item)

    return preferred + other


def find_default_font():
    """Find the system monospace font."""
    if sys.platform.startswith("linux"):
        try:
            result = subprocess.run(
                [
                    "fc-match",
                    "-f",
                    "%{file}",
                    "monospace",
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            path = result.stdout.strip()

            if path and os.path.isfile(path):
                return path

        except (
            FileNotFoundError,
            subprocess.SubprocessError,
        ):
            pass

    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationMono-Regular.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
        "C:/Windows/Fonts/consola.ttf",
        "C:/Windows/Fonts/cour.ttf",
        "/System/Library/Fonts/Menlo.ttc",
    ]

    for path in candidates:
        if os.path.isfile(path):
            return path

    return None


# ============================================================
# IMAGE PROCESSING
# ============================================================

def crop_to_aspect(image, target_aspect):
    """Center-crop an image to the target aspect ratio."""

    width, height = image.size
    current_aspect = width / height

    if abs(current_aspect - target_aspect) < 1e-9:
        return image

    if current_aspect > target_aspect:
        # Too wide -> crop left/right.
        new_width = max(
            1,
            round(height * target_aspect),
        )

        left = (width - new_width) // 2

        return image.crop(
            (
                left,
                0,
                left + new_width,
                height,
            )
        )

    # Too tall -> crop top/bottom.
    new_height = max(
        1,
        round(width / target_aspect),
    )

    top = (height - new_height) // 2

    return image.crop(
        (
            0,
            top,
            width,
            top + new_height,
        )
    )


def brightness(r, g, b):
    """Perceived brightness, 0..255."""

    return (
        0.299 * r +
        0.587 * g +
        0.114 * b
    )


def load_font(font_path, size):
    try:
        return ImageFont.truetype(
            font_path,
            size,
        )
    except OSError as exc:
        raise RuntimeError(
            f"Не удалось открыть шрифт:\n"
            f"{font_path}\n\n"
            f"{exc}"
        ) from exc


# ============================================================
# ASCII RENDERER
# ============================================================

def render_ascii(
    image,
    screen_width,
    screen_height,
    rows,
    chars,
    font_path,
    colored,
    color
    
):
    """
    Convert an image into an ASCII image.

    The final PNG is exactly screen_width x screen_height.
    Each ASCII character represents an averaged source-image block.
    """

    if rows < 1:
        raise ValueError(
            "Количество строк должно быть >= 1."
        )

    if not chars:
        raise ValueError(
            "Набор символов не может быть пустым."
        )

    # --------------------------------------------------------
    # ASCII grid
    # --------------------------------------------------------

    # Approximate glyph aspect ratio for monospace fonts.
    char_aspect = 0.5

    columns = max(
        1,
        round(
            rows
            * (screen_width / screen_height)
            / char_aspect
        ),
    )

    # --------------------------------------------------------
    # Average each source block
    # --------------------------------------------------------

    small = image.resize(
        (columns, rows),
        Image.Resampling.BOX,
    )

    pixels = small.load()

    # --------------------------------------------------------
    # Full-resolution output
    # --------------------------------------------------------

    output = Image.new(
        "RGB",
        (
            screen_width,
            screen_height,
        ),
        (0, 0, 0),
    )

    draw = ImageDraw.Draw(output)

    # --------------------------------------------------------
    # Font
    # --------------------------------------------------------

    cell_width = screen_width / columns
    cell_height = screen_height / rows

    font_size = max(
        1,
        int(cell_height * 0.90),
    )

    font = load_font(
        font_path,
        font_size,
    )

    # Actual glyph metrics.
    bbox = font.getbbox("M")

    glyph_height = max(
        1,
        bbox[3] - bbox[1],
    )

    vertical_offset = (
        (cell_height - glyph_height) / 2
        - bbox[1]
    )

    # --------------------------------------------------------
    # Draw
    # --------------------------------------------------------

    for y in range(rows):
        py = y * cell_height

        for x in range(columns):
            r, g, b = pixels[x, y]

            value = brightness(
                r,
                g,
                b,
            )

            index = round(
                value / 255
                * (len(chars) - 1)
            )

            char = chars[index]

            px = x * cell_width
            text_y = py + vertical_offset

            if colored:
                fill = (r, g, b)
            else:
                if color == None:
                    gray = round(value)
                    fill = (
                        gray,
                        gray,
                        gray,
                    )
                else:
                    gray = value/255
                    fill = (round(color[0] * gray),round(color[1] * gray),round(color[2] * gray),)

            draw.text(
                (
                    round(px),
                    round(text_y),
                ),
                char,
                font=font,
                fill=fill,
            )

    return output, columns


# ============================================================
# COMMAND LINE
# ============================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Convert an image into colored or monochrome "
            "ASCII PNG."
        )
    )

    parser.add_argument(
        "image",
        help="Путь к исходной картинке.",
    )

    parser.add_argument(
        "-o",
        "--output",
        default="ascii_output.png",
        help="Путь к выходному PNG.",
    )

    parser.add_argument(
        "--mode",
        choices=("color", "mono"),
        default=None,
        help="Режим: color или mono.",
    )
    parser.add_argument(
        "--color",
        default=None,
        help="Цвет изображения при mono режиме"
    )

    parser.add_argument(
        "--quality",
        choices=tuple(QUALITY_PRESETS),
        default=None,
        help="Качество ASCII.",
    )

    parser.add_argument(
        "--rows",
        type=int,
        default=None,
        help="Точное количество строк ASCII.",
    )

    parser.add_argument(
        "--chars",
        default=None,
        help=(
            "Набор символов от тёмного к светлому."
        ),
    )

    parser.add_argument(
        "--font",
        default=None,
        help="Путь к .ttf/.otf/.ttc.",
    )

    parser.add_argument(
        "--screen",
        nargs=2,
        type=int,
        metavar=("WIDTH", "HEIGHT"),
        default=None,
        help="Ручное разрешение экрана.",
    )

    return parser.parse_args()


# ============================================================
# INTERACTIVE SETUP
# ============================================================

def ask_interactive(args, fonts):
    print()
    print("=== ASCII PNG Generator ===")
    print()

    # --------------------------------------------------------
    # Mode
    # --------------------------------------------------------

    if args.mode is None:
        while True:
            value = input(
                "Режим [1 — цветной / "
                "2 — одноцветный] (1): "
            ).strip()

            if value in ("", "1"):
                args.mode = "color"
                break

            if value == "2":
                args.mode = "mono"
                if args.color is None:
                            while True:
                                try:
                                    value = input(
                                        "Введите цвет в формате (255,255,255)  (по умолчанию генерирует ч/б): "
                                        
                                    ).strip()[1:-1].split(',')
                                    value = (int(value[0]),int(value[1]),int(value[2]))
                                except:
                                    value = None
                                args.color = value
                                break
                break

            print("Введите 1 или 2.")
    
    
    # --------------------------------------------------------
    # Quality
    # --------------------------------------------------------

    if (
        args.rows is None
        and args.quality is None
    ):
        print()
        print("Качество:")
        print("1 — низкое    (35 строк)")
        print("2 — среднее    (60 строк)")
        print("3 — высокое    (90 строк)")
        print("4 — ультра    (120 строк)")
        print("5 — своё количество строк")

        while True:
            value = input(
                "Выбор (2): "
            ).strip()

            if value in ("", "2"):
                args.quality = "medium"
                break

            if value == "1":
                args.quality = "low"
                break

            if value == "3":
                args.quality = "high"
                break

            if value == "4":
                args.quality = "ultra"
                break

            if value == "5":
                try:
                    rows = int(
                        input(
                            "Количество строк: "
                        ).strip()
                    )

                    if rows < 1:
                        raise ValueError

                    args.rows = rows
                    break

                except ValueError:
                    print(
                        "Введите целое число больше 0."
                    )
                    continue

            print(
                "Введите число от 1 до 5."
            )

    # --------------------------------------------------------
    # Character set
    # --------------------------------------------------------

    if args.chars is None:
        print()
        print(
            "Набор символов задаётся "
            "от тёмного к светлому."
        )

        value = input(
            f"Символы [{DEFAULT_CHARS}]: "
        )

        args.chars = (
            value
            if value
            else DEFAULT_CHARS
        )

    if not args.chars:
        raise ValueError(
            "Набор символов не может быть пустым."
        )

    # --------------------------------------------------------
    # Font
    # --------------------------------------------------------

    if args.font is None:
        default_font = find_default_font()

        print()
        print("Шрифт:")

        if default_font:
            print(
                f"По умолчанию: {default_font}"
            )

        if fonts:
            print(
                "Найденные шрифты:"
            )

            for i, (family, path) in enumerate(
                fonts[:10],
                1,
            ):
                print(
                    f"  {i}. {family} — {path}"
                )

        value = input(
            "Путь к шрифту "
            "(Enter = системный): "
        ).strip()

        if value:
            args.font = value
        else:
            args.font = default_font

    return args


# ============================================================
# MAIN
# ============================================================

def main():
    args = parse_args()
    # --------------------------------------------------------
    # Source image
    # --------------------------------------------------------

    if not os.path.isfile(args.image):
        print(
            f"Ошибка: файл не найден: "
            f"{args.image}"
        )
        return 1

    try:
        image = Image.open(
            args.image
        )

        # Composite transparent PNGs onto black.
        if "A" in image.getbands():
            rgba = image.convert("RGBA")

            background = Image.new(
                "RGBA",
                rgba.size,
                (0, 0, 0, 255),
            )

            background.alpha_composite(
                rgba
            )

            image = background.convert(
                "RGB"
            )

        else:
            image = image.convert(
                "RGB"
            )

    except Exception as exc:
        print(
            f"Ошибка загрузки изображения: "
            f"{exc}"
        )
        return 1

    # --------------------------------------------------------
    # Screen
    # --------------------------------------------------------

    try:
        if args.screen:
            screen_width, screen_height = (
                args.screen
            )
        else:
            screen_width, screen_height = (
                get_screen_size()
            )

    except RuntimeError as exc:
        print(
            f"Ошибка: {exc}"
        )
        return 1

    if (
        screen_width < 1
        or screen_height < 1
    ):
        print(
            "Некорректное разрешение экрана."
        )
        return 1

    # --------------------------------------------------------
    # Fonts
    # --------------------------------------------------------

    fonts = get_monospace_fonts()

    try:
        args = ask_interactive(
            args,
            fonts,
        )

        # ----------------------------------------------------
        # Rows
        # ----------------------------------------------------

        if args.rows is not None:
            rows = args.rows
        else:
            rows = QUALITY_PRESETS[
                args.quality
            ]

        if rows < 1:
            raise ValueError(
                "Количество строк должно быть >= 1."
            )

        # ----------------------------------------------------
        # Font
        # ----------------------------------------------------

        font_path = args.font

        if not font_path:
            raise ValueError(
                "Не найден моноширинный шрифт.\n"
                "Укажи его через --font."
            )

        if not os.path.isfile(
            font_path
        ):
            raise ValueError(
                "Файл шрифта не найден:\n"
                f"{font_path}"
            )

        # ----------------------------------------------------
        # Crop
        # ----------------------------------------------------

        screen_aspect = (
            screen_width
            / screen_height
        )

        cropped = crop_to_aspect(
            image,
            screen_aspect,
        )

        print()
        print(
            f"Экран: "
            f"{screen_width} × "
            f"{screen_height}"
        )

        print(
            f"Исходник: "
            f"{image.width} × "
            f"{image.height}"
        )

        print(
            f"После crop: "
            f"{cropped.width} × "
            f"{cropped.height}"
        )

        print(
            f"Строк: {rows}"
        )

        print(
            f"Шрифт: {font_path}"
        )

        print(
            "Режим: "
            + (
                "цветной"
                if args.mode == "color"
                else "одноцветный"
            )
        )

        # ----------------------------------------------------
        # Render
        # ----------------------------------------------------

        output, columns = render_ascii(
            cropped,
            screen_width,
            screen_height,
            rows,
            args.chars,
            font_path,
            args.mode == "color",
            args.color
        )

        # ----------------------------------------------------
        # Save
        # ----------------------------------------------------

        output_path = os.path.abspath(
            args.output
        )

        output_dir = os.path.dirname(
            output_path
        )

        if output_dir:
            os.makedirs(
                output_dir,
                exist_ok=True,
            )

        output.save(
            output_path,
            "PNG",
        )

        print(
            f"ASCII-сетка: "
            f"{columns} × {rows}"
        )

        print(
            f"Разрешение PNG: "
            f"{output.width} × "
            f"{output.height}"
        )

        print(
            f"Готово: {output_path}"
        )

        return 0

    except (
        ValueError,
        RuntimeError,
        OSError,
    ) as exc:
        print()
        print(
            f"Ошибка: {exc}"
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
