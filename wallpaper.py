from PIL import Image, ImageDraw, ImageFont
import argparse
import json
import os
import re
import subprocess
import sys


DEFAULT_CHARS = "@#S%?*+;:,."

QUALITY_PRESETS = {
    "low": 35,
    "medium": 60,
    "high": 90,
    "ultra": 120,
}


def get_screen_size():


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
        "Could not detect the screen resolution automatically.\n"
        "Use --screen WIDTH HEIGHT"
    )


def get_monospace_fonts():
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

    unique = []
    seen = set()

    for family, path in fonts:
        if path not in seen:
            seen.add(path)
            unique.append((family, path))

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


def crop_to_aspect(image, target_aspect):

    width, height = image.size
    current_aspect = width / height

    if abs(current_aspect - target_aspect) < 1e-9:
        return image

    if current_aspect > target_aspect:
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
            f"Could not open font:\n"
            f"{font_path}\n\n"
            f"{exc}"
        ) from exc


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

    if rows < 1:
        raise ValueError(
            "Number of rows must be >= 1."
        )

    if not chars:
        raise ValueError(
            "The character set cannot be empty."
        )


    char_aspect = 0.5

    columns = max(
        1,
        round(
            rows
            * (screen_width / screen_height)
            / char_aspect
        ),
    )


    small = image.resize(
        (columns, rows),
        Image.Resampling.BOX,
    )

    pixels = small.load()


    output = Image.new(
        "RGB",
        (
            screen_width,
            screen_height,
        ),
        (0, 0, 0),
    )

    draw = ImageDraw.Draw(output)


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

    bbox = font.getbbox("M")

    glyph_height = max(
        1,
        bbox[3] - bbox[1],
    )

    vertical_offset = (
        (cell_height - glyph_height) / 2
        - bbox[1]
    )


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


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Convert an image into colored or monochrome "
            "ASCII PNG."
        )
    )

    parser.add_argument(
        "image",
        help="Path to the source image.",
    )

    parser.add_argument(
        "-o",
        "--output",
        default="ascii_output.png",
        help="Path to the output PNG.",
    )

    parser.add_argument(
        "--mode",
        choices=("color", "mono"),
        default=None,
        help="Mode: color or mono.",
    )
    parser.add_argument(
        "--color",
        default=None,
        help="Image color in mono mode, in the format '(255,255,255)'"
    )

    parser.add_argument(
        "--quality",
        choices=tuple(QUALITY_PRESETS),
        default=None,
        help="ASCII quality.",
    )

    parser.add_argument(
        "--rows",
        type=int,
        default=None,
        help="Exact number of ASCII rows.",
    )

    parser.add_argument(
        "--chars",
        default=None,
        help=(
            "Character set from dark to light."
        ),
    )

    parser.add_argument(
        "--font",
        default=None,
        help="Path to a .ttf/.otf/.ttc font.",
    )

    parser.add_argument(
        "--screen",
        nargs=2,
        type=int,
        metavar=("WIDTH", "HEIGHT"),
        default=None,
        help="Manual screen resolution.",
    )

    return parser.parse_args()


def ask_interactive(args, fonts):
    print()
    print("=== ASCII PNG Generator ===")
    print()


    if args.mode is None:
        while True:
            value = input(
                "Mode [1 — color / "
                "2 — monochrome] (1): "
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
                                        "Enter a color in the format (255,255,255)  (default: grayscale): "

                                    ).strip()[1:-1].split(',')
                                    value = (int(value[0]),int(value[1]),int(value[2]))
                                except:
                                    value = None
                                args.color = value
                                break
                break

            print("Enter 1 or 2.")


    if (
        args.rows is None
        and args.quality is None
    ):
        print()
        print("Quality:")
        print("1 — low       (35 rows)")
        print("2 — medium    (60 rows)")
        print("3 — high      (90 rows)")
        print("4 — ultra     (120 rows)")
        print("5 — custom number of rows")

        while True:
            value = input(
                "Choice (2): "
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
                            "Number of rows: "
                        ).strip()
                    )

                    if rows < 1:
                        raise ValueError

                    args.rows = rows
                    break

                except ValueError:
                    print(
                        "Enter an integer greater than 0."
                    )
                    continue

            print(
                "Enter a number from 1 to 5."
            )


    if args.chars is None:
        print()
        print(
            "The character set is given "
            "from dark to light."
        )

        value = input(
            f"Characters [{DEFAULT_CHARS}]: "
        )

        args.chars = (
            value
            if value
            else DEFAULT_CHARS
        )

    if not args.chars:
        raise ValueError(
            "The character set cannot be empty."
        )


    if args.font is None:
        default_font = find_default_font()

        print()
        print("Font:")

        if default_font:
            print(
                f"Default: {default_font}"
            )

        if fonts:
            print(
                "Fonts found:"
            )

            for i, (family, path) in enumerate(
                fonts[:10],
                1,
            ):
                print(
                    f"  {i}. {family} — {path}"
                )

        value = input(
            "Path to font "
            "(Enter = system default): "
        ).strip()

        if value:
            args.font = value
        else:
            args.font = default_font

    return args


def main():
    args = parse_args()

    if not os.path.isfile(args.image):
        print(
            f"Error: file not found: "
            f"{args.image}"
        )
        return 1

    try:
        image = Image.open(
            args.image
        )

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
            f"Error loading image: "
            f"{exc}"
        )
        return 1


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
            f"Error: {exc}"
        )
        return 1

    if (
        screen_width < 1
        or screen_height < 1
    ):
        print(
            "Invalid screen resolution."
        )
        return 1


    fonts = get_monospace_fonts()

    try:
        args = ask_interactive(
            args,
            fonts,
        )


        if args.rows is not None:
            rows = args.rows
        else:
            rows = QUALITY_PRESETS[
                args.quality
            ]

        if rows < 1:
            raise ValueError(
                "Number of rows must be >= 1."
            )


        font_path = args.font

        if not font_path:
            raise ValueError(
                "No monospace font found.\n"
                "Specify one with --font."
            )

        if not os.path.isfile(
            font_path
        ):
            raise ValueError(
                "Font file not found:\n"
                f"{font_path}"
            )


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
            f"Screen: "
            f"{screen_width} × "
            f"{screen_height}"
        )

        print(
            f"Source: "
            f"{image.width} × "
            f"{image.height}"
        )

        print(
            f"After crop: "
            f"{cropped.width} × "
            f"{cropped.height}"
        )

        print(
            f"Rows: {rows}"
        )

        print(
            f"Font: {font_path}"
        )

        print(
            "Mode: "
            + (
                "color"
                if args.mode == "color"
                else "monochrome"
            )
        )


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
            f"ASCII grid: "
            f"{columns} × {rows}"
        )

        print(
            f"PNG resolution: "
            f"{output.width} × "
            f"{output.height}"
        )

        print(
            f"Done: {output_path}"
        )

        return 0

    except (
        ValueError,
        RuntimeError,
        OSError,
    ) as exc:
        print()
        print(
            f"Error: {exc}"
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
