#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ASCII Wallpaper — графический интерфейс для wallpaper.py

Положите этот файл рядом с wallpaper.py.

Зависимости (Arch Linux):
    sudo pacman -S python-pyqt6 python-pillow qt6-wayland

Запуск:
    python wallpaper_gui.py [картинка]
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from string import Template

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))



def detect_language() -> str:
    """'ru' или 'en' — по локали системы (LC_ALL / LC_MESSAGES / LANGUAGE / LANG)."""
    for var in ("LC_ALL", "LC_MESSAGES", "LANGUAGE", "LANG"):
        value = os.environ.get(var, "").strip()
        if value and value not in ("C", "POSIX"):
            first = value.split(":")[0].strip().lower()  # LANGUAGE бывает "ru:en"
            if first:
                return "ru" if first.startswith("ru") else "en"
    try:
        import locale
        loc = (locale.getlocale()[0] or "").lower()
        return "ru" if loc.startswith("ru") else "en"
    except Exception:
        return "en"


LANG = detect_language()


def L(ru: str, en: str) -> str:
    """Строка на языке системы."""
    return ru if LANG == "ru" else en


try:
    import wallpaper as core
except ImportError:
    sys.exit(L("Не найден wallpaper.py — положите его рядом с wallpaper_gui.py",
               "wallpaper.py not found — put it next to wallpaper_gui.py"))

from PIL import Image, ImageDraw, ImageFont

from PyQt6.QtCore import (
    QObject, QPointF, QRect, QRectF, QRunnable, QSettings, Qt, QThreadPool,
    QTimer, pyqtSignal,
)
from PyQt6.QtGui import (
    QBrush, QColor, QCursor, QFont, QFontInfo, QGuiApplication, QFontMetrics, QImage, QKeySequence,
    QLinearGradient, QPainter, QPainterPath, QPalette, QPen, QPixmap,
    QShortcut,
)
from PyQt6.QtWidgets import (
    QAbstractSpinBox, QApplication, QBoxLayout, QButtonGroup, QCheckBox,
    QColorDialog, QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QListView, QMainWindow, QPushButton, QScrollArea,
    QSizePolicy, QSlider, QSpinBox, QStackedWidget, QVBoxLayout, QWidget,
)


# ============================================================
# ДИЗАЙН
# ============================================================
# Тёмная «чернильная» гамма и один янтарный акцент — отсылка к
# старым фосфорным мониторам. Вся «яркость» сосредоточена на
# превью, остальной интерфейс намеренно сдержанный.

C = dict(
    ink="#10121b",       # фон окна
    stage="#0a0c13",     # фон сцены с превью
    panel="#161925",     # боковая панель
    inset="#0e1019",     # поля ввода
    lift="#1e2231",      # кнопки
    lift2="#272c40",     # кнопки при наведении
    line="#2a2f45",
    line2="#3d4563",
    text="#e2e5f1",
    muted="#8b93ae",
    muted2="#5a6280",
    amber="#f2b24d",
    amber_hi="#f7c470",
    amber_dim="#3a2d17",
    danger="#ef6f6c",
)

UI_FAMILIES = ["Inter", "Noto Sans", "Cantarell", "Roboto", "DejaVu Sans", "sans-serif"]
MONO_FAMILIES = ["JetBrains Mono", "JetBrainsMono Nerd Font", "Iosevka", "Fira Code",
                 "Hack", "DejaVu Sans Mono", "monospace"]

QSS = Template("""
QToolTip { background: $lift; color: $text; border: 1px solid $line2; padding: 4px 8px; }

#root { background: $ink; }
#header { background: $ink; border-bottom: 1px solid $line; }
#title { font-size: 15px; font-weight: 600; color: $text; }
#fileLabel { color: $muted; font-size: 13px; }

#sideScroll { background: $panel; border: none; border-left: 1px solid $line; }
#sideInner { background: $panel; }
#h2 { font-size: 13px; font-weight: 600; color: $text; }
#muted { color: $muted; font-size: 12px; }
#hline { background: $line; border: none; min-height: 1px; max-height: 1px; }
#status { color: $muted; font-size: 12px; }
#status[error="true"] { color: $danger; }

QScrollBar:vertical { background: transparent; width: 10px; margin: 2px 2px 2px 0; }
QScrollBar::handle:vertical { background: $line2; border-radius: 3px; min-height: 36px; }
QScrollBar::handle:vertical:hover { background: $muted2; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }

QPushButton { background: $lift; border: 1px solid $line; border-radius: 8px;
              padding: 7px 16px; color: $text; }
QPushButton:hover { background: $lift2; border-color: $line2; }
QPushButton:pressed { background: $line; }
QPushButton:focus { border-color: $line2; }
QPushButton:disabled { color: $muted2; background: $panel; }

QPushButton#primary { background: $amber; border: 1px solid $amber; color: #1c1508; font-weight: 600; }
QPushButton#primary:hover { background: $amber_hi; border-color: $amber_hi; }
QPushButton#primary:pressed { background: $amber; }
QPushButton#primary:disabled { background: $amber_dim; border-color: $amber_dim; color: $muted; }

QPushButton#chip { padding: 5px 6px; font-size: 12px; border-radius: 7px; }
QPushButton#ghost { background: transparent; border: 1px solid transparent; color: $muted; padding: 5px 2px; }
QPushButton#ghost:hover { color: $text; background: transparent; border-color: transparent; }

#segFrame { background: $inset; border: 1px solid $line; border-radius: 9px; }
QPushButton#seg { background: transparent; border: none; border-radius: 6px; padding: 6px 4px; color: $muted; }
QPushButton#seg:hover { color: $text; background: transparent; }
QPushButton#seg:checked { background: $amber_dim; color: $amber; }

QLineEdit { background: $inset; border: 1px solid $line; border-radius: 8px; padding: 7px 10px;
            color: $text; selection-background-color: $amber; selection-color: #1c1508; }
QLineEdit:focus { border-color: $amber; }
QLineEdit[invalid="true"] { border-color: $danger; }

QSpinBox { background: $inset; border: 1px solid $line; border-radius: 8px; padding: 5px 6px;
           color: $text; selection-background-color: $amber; selection-color: #1c1508; }
QSpinBox:focus { border-color: $amber; }

QComboBox { background: $inset; border: 1px solid $line; border-radius: 8px;
            padding: 6px 28px 6px 10px; color: $text; }
QComboBox:hover { border-color: $line2; }
QComboBox:on { border-color: $amber; }
QComboBox::drop-down { border: none; width: 0px; }
QComboBox::down-arrow { image: none; width: 0px; height: 0px; }
QComboBox QAbstractItemView { background: $lift; border: 1px solid $line2; color: $text;
            selection-background-color: $amber_dim; selection-color: $amber; outline: 0; padding: 4px; }
QComboBox QAbstractItemView::item { min-height: 24px; padding: 2px 8px; }

QSlider { min-height: 22px; }
QSlider::groove:horizontal { height: 4px; background: $line; border-radius: 2px; }
QSlider::sub-page:horizontal { background: $amber; border-radius: 2px; }
QSlider::handle:horizontal { background: $amber; width: 14px; height: 14px; margin: -5px 0;
                             border-radius: 7px; border: none; }
QSlider::handle:horizontal:hover { background: $amber_hi; }

QCheckBox { color: $muted; spacing: 8px; font-size: 12px; }
QCheckBox:hover { color: $text; }

#toast { background: $lift; border: 1px solid $line2; border-radius: 10px;
         padding: 10px 16px; color: $text; }
#toast[error="true"] { border-color: $danger; color: $danger; }
""").substitute(C)


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")

    pal = QPalette()
    roles = {
        QPalette.ColorRole.Window: C["ink"],
        QPalette.ColorRole.WindowText: C["text"],
        QPalette.ColorRole.Base: C["inset"],
        QPalette.ColorRole.AlternateBase: C["lift"],
        QPalette.ColorRole.ToolTipBase: C["lift"],
        QPalette.ColorRole.ToolTipText: C["text"],
        QPalette.ColorRole.Text: C["text"],
        QPalette.ColorRole.Button: C["lift"],
        QPalette.ColorRole.ButtonText: C["text"],
        QPalette.ColorRole.BrightText: "#ffffff",
        QPalette.ColorRole.Highlight: C["amber"],
        QPalette.ColorRole.HighlightedText: "#1c1508",
        QPalette.ColorRole.PlaceholderText: C["muted2"],
        QPalette.ColorRole.Link: C["amber"],
    }
    for role, color in roles.items():
        pal.setColor(role, QColor(color))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText,
                 QPalette.ColorRole.WindowText):
        pal.setColor(QPalette.ColorGroup.Disabled, role, QColor(C["muted2"]))
    app.setPalette(pal)

    font = QFont()
    font.setFamilies(UI_FAMILIES)
    font.setPointSizeF(10)
    app.setFont(font)

    app.setStyleSheet(QSS)


def repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


# ============================================================
# ЛОГИКА (без Qt)
# ============================================================

CHAR_ASPECT = 0.5  # как в wallpaper.render_ascii

QUALITY_LABELS = {"low": L("Низкая", "Low"), "medium": L("Средняя", "Medium"),
                  "high": L("Высокая", "High"), "ultra": L("Ультра", "Ultra")}

CHAR_PRESETS = [
    (L("Стандарт", "Default"), core.DEFAULT_CHARS),
    (L("Плотные", "Dense"), " .:-=+*#%@"),
    (L("Блоки", "Blocks"), " ░▒▓█"),
    (L("Бинарные", "Binary"), "01"),
    (L("Короткие", "Short"), " .oO@"),
]

COLOR_PRESETS = [
    (L("Оттенки серого", "Grayscale"), None),
    (L("Янтарь", "Amber"), (242, 178, 77)),
    (L("Мята", "Mint"), (124, 255, 178)),
    (L("Лазурь", "Azure"), (111, 211, 255)),
    (L("Сирень", "Lilac"), (185, 162, 255)),
    (L("Роза", "Rose"), (255, 143, 177)),
    (L("Белый", "White"), (244, 244, 245)),
]


@dataclass
class Params:
    colored: bool
    color: tuple | None
    rows: int
    chars: str
    font: str
    screen: tuple


def grid_columns(rows: int, screen_w: int, screen_h: int) -> int:
    """Количество колонок — та же формула, что в wallpaper.render_ascii."""
    return max(1, round(rows * (screen_w / screen_h) / CHAR_ASPECT))


def crop_box(w: int, h: int, aspect: float):
    """Те же вычисления, что в wallpaper.crop_to_aspect → (l, t, r, b)."""
    cur = w / h
    if abs(cur - aspect) < 1e-9:
        return 0, 0, w, h
    if cur > aspect:
        nw = max(1, round(h * aspect))
        left = (w - nw) // 2
        return left, 0, left + nw, h
    nh = max(1, round(w / aspect))
    top = (h - nh) // 2
    return 0, top, w, top + nh


def read_source(path: str) -> Image.Image:
    """Загрузка как в wallpaper.main(): прозрачность → на чёрный фон."""
    image = Image.open(path)
    if "A" in image.getbands():
        rgba = image.convert("RGBA")
        bg = Image.new("RGBA", rgba.size, (0, 0, 0, 255))
        bg.alpha_composite(rgba)
        return bg.convert("RGB")
    return image.convert("RGB")


def pil_to_qimage(img: Image.Image) -> QImage:
    if img.mode != "RGB":
        img = img.convert("RGB")
    data = img.tobytes("raw", "RGB")
    qimg = QImage(data, img.width, img.height, img.width * 3, QImage.Format.Format_RGB888)
    return qimg.copy()  # отвязываем от буфера data


def render_fast(image, out_w, out_h, aspect, rows, chars, font_path, colored, color):
    """
    Быстрая версия wallpaper.render_ascii для предпросмотра.

    Алгоритм и округления те же, но маска каждого символа строится один раз
    и затем вставляется через paste. Результат попиксельно совпадает с
    оригиналом (проверено), но считается примерно в 10 раз быстрее.
    `aspect` — реальное соотношение сторон экрана (из него считаются колонки).
    """
    columns = max(1, round(rows * aspect / CHAR_ASPECT))
    small = image.resize((columns, rows), Image.Resampling.BOX)
    pix = small.load()

    output = Image.new("RGB", (out_w, out_h), (0, 0, 0))
    cell_w = out_w / columns
    cell_h = out_h / rows
    font = ImageFont.truetype(font_path, max(1, int(cell_h * 0.90)))
    bbox = font.getbbox("M")
    glyph_h = max(1, bbox[3] - bbox[1])
    voff = (cell_h - glyph_h) / 2 - bbox[1]

    masks = {}
    for ch in set(chars):
        l, t, r, b = font.getbbox(ch)
        pad = 4 + max(0, -l, -t)
        m = Image.new("L", (max(r, 1) + 2 * pad, max(b, 1) + 2 * pad), 0)
        ImageDraw.Draw(m).text((pad, pad), ch, font=font, fill=255)
        masks[ch] = (m, pad) if m.getbbox() else None

    n = len(chars) - 1
    xs = [round(x * cell_w) for x in range(columns)]
    paste = output.paste
    for y in range(rows):
        ty = round(y * cell_h + voff)
        for x in range(columns):
            r, g, b = pix[x, y]
            value = 0.299 * r + 0.587 * g + 0.114 * b
            entry = masks[chars[round(value / 255 * n)]]
            if entry is None:
                continue
            if colored:
                fill = (r, g, b)
            elif color is None:
                gv = round(value)
                fill = (gv, gv, gv)
            else:
                gv = value / 255
                fill = (round(color[0] * gv), round(color[1] * gv), round(color[2] * gv))
            m, pad = entry
            paste(fill, (xs[x] - pad, ty - pad), m)
    return output, columns


FC_FORMAT = r"%{file}|%{family[0]}|%{style[0]}\n"
FONT_SUFFIXES = (".ttf", ".otf", ".ttc", ".otc")
REGULAR_STYLES = {"regular", "book", "roman", "medium", "normal"}


MONO_HINTS = ("mono", "consol", "cour", "lucon", "code", "cascadia", "hack",
              "jetbrains", "inconsolata", "iosevka", "terminal", "fira")


def _list_fonts_windows(mono_only: bool):
    """Шрифты Windows: системная папка и пользовательская."""
    dirs = [Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"]
    local = os.environ.get("LOCALAPPDATA")
    if local:
        dirs.append(Path(local) / "Microsoft" / "Windows" / "Fonts")
    rows = []
    for d in dirs:
        if not d.is_dir():
            continue
        for f in d.iterdir():
            if f.suffix.lower() not in FONT_SUFFIXES:
                continue
            if mono_only and not any(h in f.stem.lower() for h in MONO_HINTS):
                continue
            try:
                family, style = ImageFont.truetype(str(f), 12).getname()
            except Exception:  # noqa: BLE001
                continue
            is_regular = style.lower() in REGULAR_STYLES or not style
            label = family if is_regular else f"{family} {style}"
            rows.append((family.lower(), 0 if is_regular else 1, style.lower(),
                         label, f.as_posix()))
    rows.sort()
    return [(label, path) for *_, label, path in rows]


def list_fonts(mono_only: bool = True):
    """[(подпись, путь)] — установленные шрифты (fontconfig на Linux, папки Fonts на Windows)."""
    if sys.platform.startswith("win"):
        return _list_fonts_windows(mono_only)
    cmd = ["fc-list", "-f", FC_FORMAT]
    if mono_only:
        cmd.append(":spacing=100")
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
        lines = res.stdout.splitlines()
    except (OSError, subprocess.SubprocessError):
        lines = []

    seen, rows = set(), []
    for line in lines:
        parts = line.split("|")
        if len(parts) < 3:
            continue
        path, family, style = (p.strip() for p in parts[:3])
        if not path.lower().endswith(FONT_SUFFIXES) or path in seen or not os.path.isfile(path):
            continue
        seen.add(path)
        is_regular = style.lower() in REGULAR_STYLES or not style
        label = family if is_regular else f"{family} {style}"
        rows.append((family.lower(), 0 if is_regular else 1, style.lower(), label, path))
    rows.sort()
    return [(label, path) for *_, label, path in rows]


def detect_monitors():
    """[(имя, ширина, высота, активный)] — Hyprland, иначе экраны Qt, иначе wallpaper.py."""
    mons = []
    if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        try:
            res = subprocess.run(["hyprctl", "monitors", "-j"], capture_output=True,
                                 text=True, check=True, timeout=5)
            for m in json.loads(res.stdout):
                mons.append((str(m.get("name", "?")), int(m["width"]), int(m["height"]),
                             bool(m.get("focused"))))
        except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
            mons = []
    if not mons:
        try:
            primary = QGuiApplication.primaryScreen()
            for i, scr in enumerate(QGuiApplication.screens()):
                geo, dpr = scr.geometry(), scr.devicePixelRatio()
                mons.append((L(f"Монитор {i + 1}", f"Monitor {i + 1}"), round(geo.width() * dpr),
                             round(geo.height() * dpr), scr == primary))
        except Exception:  # noqa: BLE001
            mons = []
    if not mons:
        try:
            w, h = core.get_screen_size()
            mons.append((L("Экран", "Screen"), int(w), int(h), True))
        except Exception:
            pass
    return mons


# ============================================================
# ФОНОВЫЕ ЗАДАЧИ
# ============================================================

class TaskSignals(QObject):
    done = pyqtSignal(int, QImage, int, float)   # seq, картинка, колонок, секунд
    saved = pyqtSignal(str, int, int, float)     # путь, ширина, высота, секунд
    failed = pyqtSignal(str, str)                # вид задачи, текст ошибки


class PreviewTask(QRunnable):
    def __init__(self, seq: int, image: Image.Image, params: Params, max_w: int = 1600):
        super().__init__()
        self.signals = TaskSignals()
        self.seq, self.image, self.p, self.max_w = seq, image, params, max_w

    def run(self):
        try:
            t0 = time.perf_counter()
            p = self.p
            sw, sh = p.screen
            scale = min(1.0, self.max_w / sw)
            ow, oh = max(1, round(sw * scale)), max(1, round(sh * scale))
            cropped = core.crop_to_aspect(self.image, sw / sh)
            out, cols = render_fast(cropped, ow, oh, sw / sh, p.rows, p.chars,
                                    p.font, p.colored, p.color)
            self.signals.done.emit(self.seq, pil_to_qimage(out), cols,
                                   time.perf_counter() - t0)
        except Exception as exc:  # noqa: BLE001
            self.signals.failed.emit("preview", str(exc))


class SaveTask(QRunnable):
    """Финальный рендер — именно функцией из вашего wallpaper.py."""

    def __init__(self, image: Image.Image, params: Params, path: str):
        super().__init__()
        self.signals = TaskSignals()
        self.image, self.p, self.path = image, params, path

    def run(self):
        try:
            t0 = time.perf_counter()
            p = self.p
            sw, sh = p.screen
            cropped = core.crop_to_aspect(self.image, sw / sh)
            out, _ = core.render_ascii(cropped, sw, sh, p.rows, p.chars,
                                       p.font, p.colored, p.color)
            folder = os.path.dirname(self.path)
            if folder:
                os.makedirs(folder, exist_ok=True)
            out.save(self.path, "PNG")
            self.signals.saved.emit(self.path, out.width, out.height,
                                    time.perf_counter() - t0)
        except Exception as exc:  # noqa: BLE001
            self.signals.failed.emit("save", str(exc))


# ============================================================
# СОБСТВЕННЫЕ ВИДЖЕТЫ
# ============================================================

def fit_int_rect(w: int, h: int, box: QRectF) -> QRect:
    if w <= 0 or h <= 0:
        return box.toRect()
    s = min(box.width() / w, box.height() / h)
    fw, fh = max(1, round(w * s)), max(1, round(h * s))
    x = round(box.x() + (box.width() - fw) / 2)
    y = round(box.y() + (box.height() - fh) / 2)
    return QRect(x, y, fw, fh)


class ScaledCache:
    """Кэш уменьшенной копии: Qt-масштабирование «на лету» даёт муар на тексте."""

    def __init__(self):
        self.src: QPixmap | None = None
        self._key = None
        self._pm: QPixmap | None = None

    def set_source(self, pm: QPixmap | None):
        self.src, self._key, self._pm = pm, None, None

    def get(self, w: int, h: int, dpr: float = 1.0) -> QPixmap:
        key = (w, h, dpr)
        if key != self._key:
            pw, ph = max(1, round(w * dpr)), max(1, round(h * dpr))
            if (pw, ph) == (self.src.width(), self.src.height()):
                pm = QPixmap(self.src)
            else:
                pm = self.src.scaled(pw, ph, Qt.AspectRatioMode.IgnoreAspectRatio,
                                     Qt.TransformationMode.SmoothTransformation)
            pm.setDevicePixelRatio(dpr)
            self._pm, self._key = pm, key
        return self._pm


def draw_stage_bg(p: QPainter, rect: QRect) -> None:
    r = QRectF(rect).adjusted(0.5, 0.5, -0.5, -0.5)
    path = QPainterPath()
    path.addRoundedRect(r, 14, 14)
    p.fillPath(path, QBrush(QColor(C["stage"])))
    p.setPen(QPen(QColor(C["line"]), 1))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(path)


def draw_pill(p: QPainter, text: str, x: float, y: float, right: bool = False) -> None:
    p.save()
    f = QFont(p.font())
    f.setPointSizeF(9.5)
    p.setFont(f)
    fm = QFontMetrics(f)
    w = fm.horizontalAdvance(text) + 20
    h = fm.height() + 8
    rect = QRectF(x - w if right else x, y, w, h)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(QColor(8, 10, 17, 210)))
    p.drawRoundedRect(rect, h / 2, h / 2)
    p.setPen(QColor(C["text"]))
    p.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
    p.restore()


class Segmented(QFrame):
    """Переключатель-сегмент. index() == -1, если ничего не выбрано."""

    changed = pyqtSignal(int)

    def __init__(self, labels, parent=None):
        super().__init__(parent)
        self.setObjectName("segFrame")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(3, 3, 3, 3)
        lay.setSpacing(2)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons = []
        for i, text in enumerate(labels):
            b = QPushButton(text)
            b.setObjectName("seg")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self._group.addButton(b, i)
            lay.addWidget(b)
            self._buttons.append(b)
        self._group.idClicked.connect(lambda i: self.changed.emit(i))

    def index(self) -> int:
        return self._group.checkedId()

    def set_index(self, i: int) -> None:
        if i < 0:
            self._group.setExclusive(False)
            for b in self._buttons:
                b.setChecked(False)
            self._group.setExclusive(True)
        else:
            self._buttons[i].setChecked(True)


class Combo(QComboBox):
    """QComboBox со своей стрелкой (стандартная пропадает при стилизации)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setView(QListView())
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.setMinimumContentsLength(10)

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(C["muted"]), 1.6, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        cx, cy = self.width() - 16, self.height() / 2
        p.drawLine(QPointF(cx - 4, cy - 2), QPointF(cx, cy + 2))
        p.drawLine(QPointF(cx, cy + 2), QPointF(cx + 4, cy - 2))


class RowsControl(QWidget):
    """Ползунок + числовое поле."""

    valueChanged = pyqtSignal(int)

    def __init__(self, lo: int, hi: int, value: int, mono_font: QFont, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(lo, hi)
        self.slider.setValue(value)
        self.spin = QSpinBox()
        self.spin.setRange(lo, hi)
        self.spin.setValue(value)
        self.spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spin.setFixedWidth(58)
        self.spin.setFont(mono_font)
        lay.addWidget(self.slider, 1)
        lay.addWidget(self.spin)
        self.slider.valueChanged.connect(self._from_slider)
        self.spin.valueChanged.connect(self._from_spin)

    def _from_slider(self, v: int):
        self.spin.blockSignals(True)
        self.spin.setValue(v)
        self.spin.blockSignals(False)
        self.valueChanged.emit(v)

    def _from_spin(self, v: int):
        self.slider.blockSignals(True)
        self.slider.setValue(v)
        self.slider.blockSignals(False)
        self.valueChanged.emit(v)

    def value(self) -> int:
        return self.slider.value()

    def set_value(self, v: int) -> None:
        self.slider.setValue(v)


class Swatch(QWidget):
    clicked = pyqtSignal()

    def __init__(self, rgb, tooltip: str, custom: bool = False):
        super().__init__()
        self.rgb = rgb
        self.custom = custom
        self.plus = custom and rgb is None
        self.selected = False
        self._hover = False
        self.setFixedSize(28, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tooltip)

    def set_rgb(self, rgb):
        self.rgb, self.plus = rgb, False
        self.update()

    def set_selected(self, v: bool):
        self.selected = v
        self.update()

    def enterEvent(self, event):
        self._hover = True
        self.update()

    def leaveEvent(self, event):
        self._hover = False
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect())
        if self.selected or self._hover:
            p.setPen(QPen(QColor(C["amber"] if self.selected else C["line2"]), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(r.adjusted(1, 1, -1, -1))
        inner = r.adjusted(5, 5, -5, -5)
        if self.plus:
            p.setPen(QPen(QColor(C["muted"]), 1.4))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(inner)
            c = inner.center()
            p.drawLine(QPointF(c.x() - 3.5, c.y()), QPointF(c.x() + 3.5, c.y()))
            p.drawLine(QPointF(c.x(), c.y() - 3.5), QPointF(c.x(), c.y() + 3.5))
        elif self.rgb is None:
            g = QLinearGradient(inner.topLeft(), inner.bottomRight())
            g.setColorAt(0.0, QColor("#1a1a1a"))
            g.setColorAt(1.0, QColor("#f0f0f0"))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(g))
            p.drawEllipse(inner)
        else:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(*self.rgb)))
            p.drawEllipse(inner)


class BusyBar(QWidget):
    """Тонкая бегущая полоска над превью."""

    def __init__(self):
        super().__init__()
        self.setFixedHeight(2)
        self._active = False
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self.update)

    def set_active(self, active: bool):
        if active == self._active:
            return
        self._active = active
        if active:
            self._timer.start()
        else:
            self._timer.stop()
        self.update()

    def paintEvent(self, event):
        if not self._active:
            return
        p = QPainter(self)
        w = self.width()
        seg = max(90.0, w * 0.22)
        x = -seg + ((time.monotonic() * 0.9) % 1.0) * (w + seg)
        g = QLinearGradient(x, 0, x + seg, 0)
        g.setColorAt(0.0, QColor(242, 178, 77, 0))
        g.setColorAt(0.5, QColor(242, 178, 77, 255))
        g.setColorAt(1.0, QColor(242, 178, 77, 0))
        p.fillRect(QRectF(x, 0, seg, self.height()), QBrush(g))


class ImageView(QWidget):
    """Одна картинка по центру сцены + подпись; опционально затемняет область, которая будет обрезана."""

    def __init__(self, caption: str, parent=None):
        super().__init__(parent)
        self._caption = caption
        self._cache = ScaledCache()
        self._crop: QRectF | None = None
        self._placeholder = ""
        self.setMinimumSize(160, 100)

    def set_pixmap(self, pm: QPixmap | None):
        self._cache.set_source(pm)
        self.update()

    def set_crop(self, rect: QRectF | None):
        self._crop = rect
        self.update()

    def set_placeholder(self, text: str):
        self._placeholder = text
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        draw_stage_bg(p, self.rect())
        src = self._cache.src
        if src is None:
            if self._placeholder:
                p.setPen(QColor(C["muted2"]))
                p.drawText(QRectF(self.rect()), Qt.AlignmentFlag.AlignCenter, self._placeholder)
        else:
            area = QRectF(self.rect()).adjusted(12, 12, -12, -12)
            ti = fit_int_rect(src.width(), src.height(), area)
            pm = self._cache.get(ti.width(), ti.height(), self.devicePixelRatioF())
            clip = QPainterPath()
            clip.addRoundedRect(QRectF(ti), 8, 8)
            p.save()
            p.setClipPath(clip)
            p.drawPixmap(ti.topLeft(), pm)
            if self._crop is not None and self._crop != QRectF(0, 0, 1, 1):
                cr = QRectF(ti.x() + self._crop.x() * ti.width(),
                            ti.y() + self._crop.y() * ti.height(),
                            self._crop.width() * ti.width(),
                            self._crop.height() * ti.height())
                dim = QPainterPath()
                dim.addRect(QRectF(ti))
                keep = QPainterPath()
                keep.addRect(cr)
                p.fillPath(dim.subtracted(keep), QBrush(QColor(6, 7, 12, 175)))
                p.setPen(QPen(QColor(C["amber"]), 1.5))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRect(cr)
            p.restore()
        draw_pill(p, self._caption, 22, 22)


class CompareView(QWidget):
    """Оригинал и результат в одном кадре, граница двигается мышью."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._orig = ScaledCache()
        self._res = ScaledCache()
        self._split = 0.5
        self._drag = False
        self.setMinimumSize(200, 120)
        self.setCursor(Qt.CursorShape.SplitHCursor)

    def set_original(self, pm: QPixmap | None):
        self._orig.set_source(pm)
        self.update()

    def set_result(self, pm: QPixmap | None):
        self._res.set_source(pm)
        self.update()

    def _target(self) -> QRect:
        area = QRectF(self.rect()).adjusted(12, 12, -12, -12)
        ref = self._res.src if self._res.src is not None else self._orig.src
        if ref is None:
            return area.toRect()
        return fit_int_rect(ref.width(), ref.height(), area)

    def _set_from_x(self, x: float):
        t = self._target()
        if t.width() > 0:
            self._split = min(1.0, max(0.0, (x - t.left()) / t.width()))
            self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag = True
            self._set_from_x(event.position().x())

    def mouseMoveEvent(self, event):
        if self._drag:
            self._set_from_x(event.position().x())

    def mouseReleaseEvent(self, event):
        self._drag = False

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        draw_stage_bg(p, self.rect())
        if self._orig.src is None and self._res.src is None:
            return
        t = self._target()
        dpr = self.devicePixelRatioF()
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(t), 8, 8)
        sx = t.left() + t.width() * self._split

        p.save()
        p.setClipPath(clip)
        if self._res.src is not None:
            p.drawPixmap(t.topLeft(), self._res.get(t.width(), t.height(), dpr))
        if self._orig.src is not None:
            p.setClipRect(QRectF(t.left(), t.top(), sx - t.left(), t.height()),
                          Qt.ClipOperation.IntersectClip)
            p.drawPixmap(t.topLeft(), self._orig.get(t.width(), t.height(), dpr))
        p.restore()

        if self._orig.src is not None and self._res.src is not None:
            p.setPen(QPen(QColor(C["amber"]), 2))
            p.drawLine(QPointF(sx, t.top()), QPointF(sx, t.bottom()))
            cy = t.center().y()
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(C["amber"])))
            p.drawEllipse(QPointF(sx, cy), 15, 15)
            p.setPen(QPen(QColor("#1c1508"), 2, Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.drawLine(QPointF(sx - 3, cy - 5), QPointF(sx - 8, cy))
            p.drawLine(QPointF(sx - 8, cy), QPointF(sx - 3, cy + 5))
            p.drawLine(QPointF(sx + 3, cy - 5), QPointF(sx + 8, cy))
            p.drawLine(QPointF(sx + 8, cy), QPointF(sx + 3, cy + 5))
            draw_pill(p, L("Оригинал", "Original"), t.left() + 12, t.top() + 12)
            draw_pill(p, L("Результат", "Result"), t.right() - 12, t.top() + 12, right=True)


class SideBySide(QWidget):
    """Два превью рядом; раскладка (в строку / в столбец) выбирается так, чтобы картинки были крупнее."""

    GAP = 12

    def __init__(self, parent=None):
        super().__init__(parent)
        self.aspect = 16 / 9
        self.lay = QBoxLayout(QBoxLayout.Direction.LeftToRight, self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(self.GAP)
        self.orig = ImageView(L("Оригинал", "Original"))
        self.res = ImageView(L("Результат", "Result"))
        self.lay.addWidget(self.orig, 1)
        self.lay.addWidget(self.res, 1)

    def set_aspect(self, a: float):
        self.aspect = a
        self._relayout()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._relayout()

    def _relayout(self):
        w, h = max(1, self.width()), max(1, self.height())
        horiz = min((w - self.GAP) / 2, h * self.aspect)
        vert = min(w, (h - self.GAP) / 2 * self.aspect)
        d = QBoxLayout.Direction.LeftToRight if horiz >= vert else QBoxLayout.Direction.TopToBottom
        if self.lay.direction() != d:
            self.lay.setDirection(d)


class DropZone(QWidget):
    """Пустое состояние: зона для перетаскивания файла."""

    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hover = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def enterEvent(self, event):
        self._hover = True
        self.update()

    def leaveEvent(self, event):
        self._hover = False
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(C["stage"])))
        p.drawRoundedRect(r, 14, 14)
        p.setPen(QPen(QColor(C["amber"] if self._hover else C["line2"]), 1.5, Qt.PenStyle.DashLine))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(r.adjusted(10, 10, -10, -10), 12, 12)

        cx, cy = r.center().x(), r.center().y()

        # полоска символов от плотного к лёгкому — как градиент в ASCII-арте
        mono = QFont(self.font())
        mono.setFamilies(MONO_FAMILIES)
        mono.setPixelSize(34)
        p.setFont(mono)
        chars = core.DEFAULT_CHARS
        adv = QFontMetrics(mono).horizontalAdvance("M") * 1.3
        x0 = cx - adv * len(chars) / 2
        for i, ch in enumerate(chars):
            col = QColor(C["amber"])
            col.setAlpha(int(255 - 215 * i / max(1, len(chars) - 1)))
            p.setPen(col)
            p.drawText(QRectF(x0 + i * adv, cy - 96, adv, 48), Qt.AlignmentFlag.AlignCenter, ch)

        title = QFont(self.font())
        title.setPixelSize(20)
        title.setWeight(QFont.Weight.DemiBold)
        p.setFont(title)
        p.setPen(QColor(C["text"]))
        p.drawText(QRectF(cx - 320, cy - 22, 640, 36), Qt.AlignmentFlag.AlignCenter,
                   L("Перетащите изображение сюда", "Drop an image here"))

        sub = QFont(self.font())
        sub.setPixelSize(13)
        p.setFont(sub)
        p.setPen(QColor(C["muted"]))
        p.drawText(QRectF(cx - 320, cy + 18, 640, 24), Qt.AlignmentFlag.AlignCenter,
                   L("или нажмите, чтобы выбрать файл", "or click to choose a file"))
        sub.setPixelSize(12)
        p.setFont(sub)
        p.setPen(QColor(C["muted2"]))
        p.drawText(QRectF(cx - 320, cy + 46, 640, 22), Qt.AlignmentFlag.AlignCenter,
                   "PNG, JPEG, WebP, BMP, TIFF")


class Toast(QLabel):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("toast")
        self.hide()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def show_message(self, text: str, error: bool = False, tooltip: str = ""):
        self.setProperty("error", error)
        repolish(self)
        self.setText(text)
        self.setToolTip(tooltip)
        self.adjustSize()
        self.reposition()
        self.show()
        self.raise_()
        self._timer.start(5200 if error else 3600)

    def reposition(self):
        parent = self.parentWidget()
        if parent is not None:
            self.move((parent.width() - self.width()) // 2,
                      parent.height() - self.height() - 28)


class Stage(QWidget):
    """Центральная область: заглушка + три режима просмотра."""

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        lay.addWidget(self.stack)

        self.drop = DropZone()
        self.single = ImageView(L("Результат", "Result"))
        self.sbs = SideBySide()
        self.cmp = CompareView()
        for w in (self.drop, self.single, self.sbs, self.cmp):
            self.stack.addWidget(w)

        self.toast = Toast(self)

    def show_mode(self, has_image: bool, mode: int):
        self.stack.setCurrentIndex(1 + mode if has_image else 0)

    def set_aspect(self, aspect: float):
        self.sbs.set_aspect(aspect)

    def set_original(self, full: QImage, crop_norm: QRectF, cropped: QImage):
        self.sbs.orig.set_pixmap(QPixmap.fromImage(full))
        self.sbs.orig.set_crop(crop_norm)
        self.cmp.set_original(QPixmap.fromImage(cropped))

    def set_result(self, img: QImage | None):
        pm = QPixmap.fromImage(img) if img is not None else None
        self.single.set_pixmap(pm)
        self.sbs.res.set_pixmap(pm)
        self.cmp.set_result(pm)
        text = "" if pm is not None else L("Рендер…", "Rendering…")
        self.single.set_placeholder(text)
        self.sbs.res.set_placeholder(text)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.toast.reposition()


# ============================================================
# ГЛАВНОЕ ОКНО
# ============================================================

class MainWindow(QMainWindow):
    def __init__(self, initial_path: str | None = None):
        super().__init__()
        self.setWindowTitle("ASCII Wallpaper")
        self.resize(1340, 840)
        self.setMinimumSize(1000, 660)
        self.setAcceptDrops(True)

        self._ready = False
        self.settings = QSettings("ascii-wallpaper", "gui")

        self.full: Image.Image | None = None     # исходник целиком — для сохранения
        self.proxy: Image.Image | None = None    # уменьшенная копия — для предпросмотра
        self.orig_qimg: QImage | None = None
        self.path: str | None = None
        self.font_path: str | None = None
        self.mono_color: tuple | None = None
        self.monitors: list = []

        mono = QFont()
        mono.setFamilies(MONO_FAMILIES)
        mono.setStyleHint(QFont.StyleHint.Monospace)
        mono.setPointSizeF(10)
        self.mono = mono
        self.mono_family = QFontInfo(mono).family()

        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.save_pool = QThreadPool(self)
        self.save_pool.setMaxThreadCount(1)
        self._seq = 0
        self._running = False
        self._dirty = False
        self._saving = False
        self._slow = False

        self.debounce = QTimer(self)
        self.debounce.setSingleShot(True)
        self.debounce.setInterval(80)
        self.debounce.timeout.connect(self._kick)

        self.slow_timer = QTimer(self)
        self.slow_timer.setSingleShot(True)
        self.slow_timer.setInterval(220)
        self.slow_timer.timeout.connect(self._mark_slow)

        self._build_ui()
        self._populate_fonts(True, None)
        self._detect_screens()
        self._load_settings()
        self._sync_derived()

        QShortcut(QKeySequence("Ctrl+O"), self).activated.connect(self.open_dialog)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.save_dialog)

        self._ready = True
        if initial_path:
            QTimer.singleShot(0, lambda: self.load_image(initial_path))

    # --------------------------------------------------------
    # Построение интерфейса
    # --------------------------------------------------------

    def _button(self, text: str, name: str | None = None) -> QPushButton:
        b = QPushButton(text)
        if name:
            b.setObjectName(name)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        return b

    def _build_ui(self):
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ---- шапка
        header = QFrame()
        header.setObjectName("header")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 12, 16, 12)
        hl.setSpacing(12)
        title = QLabel("ASCII Wallpaper")
        title.setObjectName("title")
        self.lbl_file = QLabel(L("Файл не выбран", "No file selected"))
        self.lbl_file.setObjectName("fileLabel")
        hl.addWidget(title)
        hl.addSpacing(6)
        hl.addWidget(self.lbl_file)
        hl.addStretch(1)
        self.view_seg = Segmented([L("Результат", "Result"), L("Рядом", "Side by side"), L("Сравнение", "Compare")])
        self.view_seg.setFixedWidth(300)
        self.view_seg.set_index(1)
        self.view_seg.changed.connect(lambda _i: self._refresh_stage())
        hl.addWidget(self.view_seg)
        hl.addSpacing(8)
        btn_open = self._button(L("Открыть", "Open"))
        btn_open.clicked.connect(self.open_dialog)
        self.btn_save = self._button(L("Сохранить", "Save"), "primary")
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self.save_dialog)
        hl.addWidget(btn_open)
        hl.addWidget(self.btn_save)
        outer.addWidget(header)

        # ---- тело
        body = QWidget()
        bl = QHBoxLayout(body)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(0)
        outer.addWidget(body, 1)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(16, 10, 16, 12)
        ll.setSpacing(8)
        self.busy = BusyBar()
        self.stage = Stage()
        self.stage.drop.clicked.connect(self.open_dialog)
        ll.addWidget(self.busy)
        ll.addWidget(self.stage, 1)

        status_row = QHBoxLayout()
        status_row.setContentsMargins(4, 0, 4, 0)
        self.lbl_status = QLabel(L("Откройте изображение, чтобы начать", "Open an image to get started"))
        self.lbl_status.setObjectName("status")
        self.lbl_meta = QLabel("")
        self.lbl_meta.setObjectName("status")
        self.lbl_meta.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        status_row.addWidget(self.lbl_status, 1)
        status_row.addWidget(self.lbl_meta)
        ll.addLayout(status_row)
        bl.addWidget(left, 1)

        # ---- боковая панель
        scroll = QScrollArea()
        scroll.setObjectName("sideScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFixedWidth(352)
        inner = QWidget()
        inner.setObjectName("sideInner")
        self.side = QVBoxLayout(inner)
        self.side.setContentsMargins(22, 20, 22, 20)
        self.side.setSpacing(0)
        scroll.setWidget(inner)
        bl.addWidget(scroll)

        self._build_color_section()
        self._build_detail_section()
        self._build_chars_section()
        self._build_font_section()
        self._build_screen_section()

        self.side.addStretch(1)
        self.side.addSpacing(16)
        reset = self._button(L("Сбросить настройки", "Reset settings"), "ghost")
        reset.clicked.connect(self.reset_defaults)
        row = QHBoxLayout()
        row.addWidget(reset)
        row.addStretch(1)
        self.side.addLayout(row)

    def _section(self, title: str, first: bool = False):
        if not first:
            self.side.addSpacing(20)
            line = QFrame()
            line.setObjectName("hline")
            line.setFixedHeight(1)
            self.side.addWidget(line)
            self.side.addSpacing(20)
        h = QLabel(title)
        h.setObjectName("h2")
        self.side.addWidget(h)
        self.side.addSpacing(10)

    def _muted(self, text: str = "") -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("muted")
        return lbl

    # ---- Цвет
    def _build_color_section(self):
        self._section(L("Цвет символов", "Character color"), first=True)
        self.color_seg = Segmented([L("Цветной", "Color"), L("Одноцветный", "Monochrome")])
        self.color_seg.set_index(0)
        self.color_seg.changed.connect(self._on_mode)
        self.side.addWidget(self.color_seg)

        self.mono_box = QWidget()
        mb = QVBoxLayout(self.mono_box)
        mb.setContentsMargins(0, 12, 0, 0)
        mb.setSpacing(8)
        row = QHBoxLayout()
        row.setSpacing(6)
        row.setContentsMargins(0, 0, 0, 0)
        self.swatches: list[Swatch] = []
        for name, rgb in COLOR_PRESETS:
            sw = Swatch(rgb, name)
            sw.clicked.connect(lambda s=sw: self._on_swatch(s))
            self.swatches.append(sw)
            row.addWidget(sw)
        self.custom_swatch = Swatch(None, L("Свой цвет…", "Custom color…"), custom=True)
        self.custom_swatch.clicked.connect(lambda: self._on_swatch(self.custom_swatch))
        self.swatches.append(self.custom_swatch)
        row.addWidget(self.custom_swatch)
        row.addStretch(1)
        mb.addLayout(row)
        self.lbl_color = self._muted(L("Оттенки серого", "Grayscale"))
        mb.addWidget(self.lbl_color)
        self.side.addWidget(self.mono_box)
        self.mono_box.setVisible(False)
        self.swatches[0].set_selected(True)

    # ---- Детализация
    def _build_detail_section(self):
        self._section(L("Детализация", "Detail"))
        self.q_names = list(core.QUALITY_PRESETS.keys())
        self.q_values = list(core.QUALITY_PRESETS.values())
        self.q_seg = Segmented([QUALITY_LABELS.get(k, k) for k in self.q_names])
        self.q_seg.changed.connect(lambda i: self.rows.set_value(self.q_values[i]))
        self.side.addWidget(self.q_seg)
        self.side.addSpacing(12)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        row.addWidget(self._muted(L("Строк", "Rows")))
        self.rows = RowsControl(10, 300, core.QUALITY_PRESETS.get("medium", 60), self.mono)
        self.rows.valueChanged.connect(self._on_rows)
        row.addWidget(self.rows, 1)
        self.side.addLayout(row)
        self.side.addSpacing(6)
        self.lbl_grid = self._muted("")
        self.lbl_grid.setFont(self.mono)
        self.side.addWidget(self.lbl_grid)

    # ---- Символы
    def _build_chars_section(self):
        self._section(L("Набор символов", "Character set"))
        self.chars_edit = QLineEdit(core.DEFAULT_CHARS)
        self.chars_edit.setFont(self.mono)
        self.chars_edit.setPlaceholderText(L("от тёмного к светлому", "dark to light"))
        self.chars_edit.setToolTip(L("Символы задаются от тёмного к светлому", "Characters are ordered from dark to light"))
        self.chars_edit.textChanged.connect(self._on_chars)
        self.side.addWidget(self.chars_edit)
        self.side.addSpacing(10)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)
        for i, (name, chars) in enumerate(CHAR_PRESETS):
            b = self._button(name, "chip")
            b.setToolTip(f"«{chars}»")
            b.clicked.connect(lambda _=False, c=chars: self.chars_edit.setText(c))
            grid.addWidget(b, i // 3, i % 3)
        rev = self._button(L("Обратить", "Reverse"), "chip")
        rev.setToolTip(L("Развернуть порядок символов", "Reverse the character order"))
        rev.clicked.connect(lambda: self.chars_edit.setText(self.chars_edit.text()[::-1]))
        n = len(CHAR_PRESETS)
        grid.addWidget(rev, n // 3, n % 3)
        for c in range(3):
            grid.setColumnStretch(c, 1)
        self.side.addLayout(grid)

    # ---- Шрифт
    def _build_font_section(self):
        self._section(L("Шрифт", "Font"))
        self.combo_font = Combo()
        self.combo_font.currentIndexChanged.connect(self._on_font)
        self.side.addWidget(self.combo_font)
        self.side.addSpacing(10)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        self.chk_mono = QCheckBox(L("Только моноширинные", "Monospace only"))
        self.chk_mono.setChecked(True)
        self.chk_mono.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chk_mono.toggled.connect(self._on_mono_only)
        btn = self._button(L("Файл…", "File…"), "chip")
        btn.clicked.connect(self._choose_font_file)
        row.addWidget(self.chk_mono)
        row.addStretch(1)
        row.addWidget(btn)
        self.side.addLayout(row)

    # ---- Экран
    def _build_screen_section(self):
        self._section(L("Размер обоев", "Wallpaper size"))
        self.combo_screen = Combo()
        self.side.addWidget(self.combo_screen)
        self.side.addSpacing(10)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self.spin_w = QSpinBox()
        self.spin_h = QSpinBox()
        for s in (self.spin_w, self.spin_h):
            s.setRange(64, 16384)
            s.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
            s.setAlignment(Qt.AlignmentFlag.AlignCenter)
            s.setFont(self.mono)
            s.valueChanged.connect(self._on_screen_spin)
        self.spin_w.setValue(1920)
        self.spin_h.setValue(1080)
        row.addWidget(self.spin_w, 1)
        row.addWidget(self._muted("×"))
        row.addWidget(self.spin_h, 1)
        self.side.addLayout(row)

    # --------------------------------------------------------
    # Экран / мониторы
    # --------------------------------------------------------

    def _detect_screens(self):
        self.monitors = detect_monitors()
        self.combo_screen.blockSignals(True)
        self.combo_screen.clear()
        for name, w, h, _focused in self.monitors:
            self.combo_screen.addItem(f"{name}   {w}×{h}")
        self.combo_screen.addItem(L("Свой размер", "Custom size"))
        idx = next((i for i, m in enumerate(self.monitors) if m[3]), 0)
        self.combo_screen.setCurrentIndex(idx)
        self.combo_screen.blockSignals(False)
        self.combo_screen.currentIndexChanged.connect(self._on_screen_combo)
        self._on_screen_combo(idx)  # заполнить поля размера явно

    def _on_screen_combo(self, i: int):
        if 0 <= i < len(self.monitors):
            _n, w, h, _f = self.monitors[i]
            for spin, v in ((self.spin_w, w), (self.spin_h, h)):
                spin.blockSignals(True)
                spin.setValue(v)
                spin.blockSignals(False)
        self._screen_changed()

    def _on_screen_spin(self, _v: int):
        custom = len(self.monitors)
        if self.combo_screen.currentIndex() != custom:
            self.combo_screen.blockSignals(True)
            self.combo_screen.setCurrentIndex(custom)
            self.combo_screen.blockSignals(False)
        self._screen_changed()

    def _screen_size(self) -> tuple:
        return self.spin_w.value(), self.spin_h.value()

    def _screen_changed(self):
        self._update_grid_label()
        self._apply_original()
        self._update_meta()
        self.request_preview()

    # --------------------------------------------------------
    # Шрифты
    # --------------------------------------------------------

    def _populate_fonts(self, mono_only: bool, select_path: str | None):
        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        try:
            fonts = list_fonts(mono_only)
        finally:
            QApplication.restoreOverrideCursor()
        default = core.find_default_font()
        if default and os.path.normcase(os.path.normpath(default)) not in {
                os.path.normcase(os.path.normpath(p)) for _l, p in fonts}:
            fonts.insert(0, (L("Системный моноширинный", "System monospace"), default))

        self.combo_font.blockSignals(True)
        self.combo_font.clear()
        for label, path in fonts:
            self.combo_font.addItem(label, path)
            self.combo_font.setItemData(self.combo_font.count() - 1, path,
                                        Qt.ItemDataRole.ToolTipRole)
        target = select_path or default
        idx = self.combo_font.findData(target) if target else -1
        if idx < 0 and target and os.path.isfile(target):
            self.combo_font.insertItem(0, Path(target).stem, target)
            idx = 0
        self.combo_font.setCurrentIndex(max(idx, 0))
        self.combo_font.blockSignals(False)
        self.font_path = self.combo_font.currentData()

    def _on_font(self, i: int):
        self.font_path = self.combo_font.itemData(i)
        self.request_preview()

    def _on_mono_only(self, checked: bool):
        self._populate_fonts(checked, self.font_path)
        self.request_preview()

    def _choose_font_file(self):
        start = str(Path(self.font_path).parent) if self.font_path else str(Path.home())
        path, _ = QFileDialog.getOpenFileName(self, L("Выберите файл шрифта", "Choose a font file"), start,
                                              L("Шрифты (*.ttf *.otf *.ttc *.otc);;Все файлы (*)",
                                              "Fonts (*.ttf *.otf *.ttc *.otc);;All files (*)"))
        if not path:
            return
        i = self.combo_font.findData(path)
        self.combo_font.blockSignals(True)
        if i < 0:
            self.combo_font.insertItem(0, Path(path).stem, path)
            self.combo_font.setItemData(0, path, Qt.ItemDataRole.ToolTipRole)
            i = 0
        self.combo_font.setCurrentIndex(i)
        self.combo_font.blockSignals(False)
        self.font_path = path
        self.request_preview()

    # --------------------------------------------------------
    # Обработчики параметров
    # --------------------------------------------------------

    def _on_mode(self, i: int):
        self.mono_box.setVisible(i == 1)
        self.request_preview()

    def _select_swatch(self, rgb):
        self.mono_color = rgb
        matched = False
        for s in self.swatches:
            if s.custom:
                continue
            sel = s.rgb == rgb
            s.set_selected(sel)
            matched = matched or sel
        if rgb is not None and not matched:
            self.custom_swatch.set_rgb(rgb)
            self.custom_swatch.set_selected(True)
        else:
            self.custom_swatch.set_selected(False)
        self.lbl_color.setText(L("Оттенки серого", "Grayscale") if rgb is None else "#%02x%02x%02x" % rgb)

    def _on_swatch(self, sw: Swatch):
        if sw.custom:
            initial = QColor(*(sw.rgb or self.mono_color or (242, 178, 77)))
            col = QColorDialog.getColor(initial, self, L("Цвет символов", "Character color"))
            if not col.isValid():
                return
            self._select_swatch((col.red(), col.green(), col.blue()))
        else:
            self._select_swatch(sw.rgb)
        self.request_preview()

    def _on_rows(self, v: int):
        self.q_seg.set_index(self.q_values.index(v) if v in self.q_values else -1)
        self._update_grid_label()
        self.request_preview()

    def _on_chars(self, text: str):
        self.chars_edit.setProperty("invalid", not text)
        repolish(self.chars_edit)
        self.request_preview()

    def _update_grid_label(self):
        w, h = self._screen_size()
        rows = self.rows.value()
        self.lbl_grid.setText(L(f"Сетка {grid_columns(rows, w, h)} × {rows} символов",
                         f"Grid {grid_columns(rows, w, h)} × {rows} characters"))

    def reset_defaults(self):
        self.color_seg.set_index(0)
        self._on_mode(0)
        self._select_swatch(None)
        self.rows.set_value(core.QUALITY_PRESETS.get("medium", 60))
        self.chars_edit.setText(core.DEFAULT_CHARS)
        self.chk_mono.blockSignals(True)
        self.chk_mono.setChecked(True)
        self.chk_mono.blockSignals(False)
        self._populate_fonts(True, core.find_default_font())
        self.request_preview()

    def _sync_derived(self):
        self._on_mode(self.color_seg.index())
        self._on_rows(self.rows.value())
        self._update_grid_label()
        self._update_meta()

    # --------------------------------------------------------
    # Настройки между запусками
    # --------------------------------------------------------

    def _load_settings(self):
        s = self.settings
        try:
            chars = s.value("chars", core.DEFAULT_CHARS, type=str)
            self.chars_edit.setText(chars or core.DEFAULT_CHARS)
            self.rows.set_value(s.value("rows", self.rows.value(), type=int))
            self.color_seg.set_index(1 if s.value("mode", 0, type=int) == 1 else 0)
            hexcol = s.value("mono_color", "", type=str)
            if hexcol:
                c = QColor(hexcol)
                if c.isValid():
                    self._select_swatch((c.red(), c.green(), c.blue()))
            mono_only = s.value("mono_only", True, type=bool)
            font = s.value("font", "", type=str)
            if font and os.path.isfile(font):
                self.chk_mono.blockSignals(True)
                self.chk_mono.setChecked(mono_only)
                self.chk_mono.blockSignals(False)
                self._populate_fonts(mono_only, font)
            view = s.value("view", 1, type=int)
            self.view_seg.set_index(view if view in (0, 1, 2) else 1)
        except (TypeError, ValueError):
            pass

    def closeEvent(self, event):
        s = self.settings
        s.setValue("chars", self.chars_edit.text())
        s.setValue("rows", self.rows.value())
        s.setValue("mode", self.color_seg.index())
        mc = self.mono_color
        s.setValue("mono_color", "" if mc is None else "#%02x%02x%02x" % mc)
        s.setValue("mono_only", self.chk_mono.isChecked())
        s.setValue("font", self.font_path or "")
        s.setValue("view", self.view_seg.index())
        super().closeEvent(event)

    # --------------------------------------------------------
    # Загрузка изображения
    # --------------------------------------------------------

    def dragEnterEvent(self, event):
        md = event.mimeData()
        if md.hasUrls() and any(u.isLocalFile() for u in md.urls()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        for u in event.mimeData().urls():
            if u.isLocalFile():
                self.load_image(u.toLocalFile())
                break

    def open_dialog(self):
        start = self.settings.value("last_dir", str(Path.home()), type=str)
        path, _ = QFileDialog.getOpenFileName(
            self, L("Выберите изображение", "Choose an image"), start,
            L("Изображения (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff *.gif);;Все файлы (*)",
              "Images (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff *.gif);;All files (*)"))
        if path:
            self.load_image(path)

    def load_image(self, path: str):
        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        try:
            full = read_source(path)
        except Exception as exc:  # noqa: BLE001
            self.stage.toast.show_message(L(f"Не удалось открыть изображение: {exc}", f"Could not open image: {exc}"), error=True)
            return
        finally:
            QApplication.restoreOverrideCursor()

        self.full, self.path = full, path
        longest = max(full.size)
        if longest > 3200:
            k = 3200 / longest
            self.proxy = full.resize((max(1, round(full.width * k)),
                                      max(1, round(full.height * k))),
                                     Image.Resampling.BOX)
        else:
            self.proxy = full
        self.orig_qimg = pil_to_qimage(self.proxy)

        name = Path(path).name
        fm = QFontMetrics(self.lbl_file.font())
        self.lbl_file.setText(fm.elidedText(name, Qt.TextElideMode.ElideMiddle, 360))
        self.lbl_file.setToolTip(path)
        self.settings.setValue("last_dir", str(Path(path).parent))

        self.btn_save.setEnabled(not self._saving)
        self.stage.set_result(None)
        self._apply_original()
        self._refresh_stage()
        self._update_meta()
        self.set_status(L("Рендер…", "Rendering…"))
        self.request_preview(now=True)

    def _refresh_stage(self):
        self.stage.show_mode(self.proxy is not None, max(0, self.view_seg.index()))

    def _apply_original(self):
        if self.proxy is None or self.orig_qimg is None:
            return
        sw, sh = self._screen_size()
        aspect = sw / sh
        pw, ph = self.proxy.size
        l, t, r, b = crop_box(pw, ph, aspect)
        norm = QRectF(l / pw, t / ph, (r - l) / pw, (b - t) / ph)
        cropped = self.orig_qimg.copy(QRect(l, t, r - l, b - t))
        self.stage.set_aspect(aspect)
        self.stage.set_original(self.orig_qimg, norm, cropped)

    # --------------------------------------------------------
    # Предпросмотр
    # --------------------------------------------------------

    def collect(self) -> Params:
        chars = self.chars_edit.text()
        if not chars:
            raise ValueError(L("Набор символов не может быть пустым.", "The character set cannot be empty."))
        if not self.font_path or not os.path.isfile(self.font_path):
            raise ValueError(L("Выберите моноширинный шрифт.", "Choose a monospace font."))
        return Params(colored=self.color_seg.index() != 1, color=self.mono_color,
                      rows=self.rows.value(), chars=chars, font=self.font_path,
                      screen=self._screen_size())

    def request_preview(self, now: bool = False):
        if not self._ready or self.proxy is None:
            return
        if now:
            self.debounce.stop()
            self._kick()
        else:
            self.debounce.start()

    def _kick(self):
        if self.proxy is None:
            return
        if self._running:
            self._dirty = True
            return
        try:
            params = self.collect()
        except ValueError as exc:
            self.set_status(str(exc), error=True)
            return
        self._running, self._dirty, self._slow = True, False, False
        self._seq += 1
        task = PreviewTask(self._seq, self.proxy, params)
        task.signals.done.connect(self._on_preview_done)
        task.signals.failed.connect(self._on_failed)
        self.pool.start(task)
        self.slow_timer.start()

    def _mark_slow(self):
        self._slow = True
        self._update_busy()

    def _update_busy(self):
        self.busy.set_active(self._saving or (self._running and self._slow))

    def _finish_preview(self):
        self._running, self._slow = False, False
        self.slow_timer.stop()
        self._update_busy()

    def _on_preview_done(self, _seq: int, img: QImage, _cols: int, dt: float):
        self._finish_preview()
        self.stage.set_result(img)
        self.set_status(L(f"Обновлено за {dt * 1000:.0f} мс", f"Updated in {dt * 1000:.0f} ms"))
        if self._dirty:
            self._kick()

    def _on_failed(self, kind: str, message: str):
        short = message.strip().splitlines()[0] if message.strip() else L("неизвестная ошибка", "unknown error")
        if kind == "preview":
            self._finish_preview()
            self.set_status(L(f"Ошибка: {short}", f"Error: {short}"), error=True)
            if self._dirty:
                self._kick()
        else:
            self._saving = False
            self.btn_save.setText(L("Сохранить", "Save"))
            self.btn_save.setEnabled(self.full is not None)
            self._update_busy()
            self.stage.toast.show_message(L(f"Не удалось сохранить: {short}", f"Could not save: {short}"), error=True)

    # --------------------------------------------------------
    # Сохранение
    # --------------------------------------------------------

    def save_dialog(self):
        if self.full is None or self._saving:
            if self.full is None:
                self.stage.toast.show_message(L("Сначала откройте изображение", "Open an image first"))
            return
        try:
            params = self.collect()
        except ValueError as exc:
            self.stage.toast.show_message(str(exc), error=True)
            return

        start_dir = self.settings.value("save_dir", "", type=str) or str(Path(self.path).parent)
        default = str(Path(start_dir) / f"{Path(self.path).stem}_ascii.png")
        path, _ = QFileDialog.getSaveFileName(self, L("Сохранить обработанное изображение", "Save processed image"),
                                              default, "PNG (*.png)")
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        self.settings.setValue("save_dir", str(Path(path).parent))

        self._saving = True
        self.btn_save.setEnabled(False)
        self.btn_save.setText(L("Сохранение…", "Saving…"))
        self._update_busy()
        task = SaveTask(self.full, params, path)
        task.signals.saved.connect(self._on_saved)
        task.signals.failed.connect(self._on_failed)
        self.save_pool.start(task)

    def _on_saved(self, path: str, w: int, h: int, dt: float):
        self._saving = False
        self.btn_save.setText(L("Сохранить", "Save"))
        self.btn_save.setEnabled(True)
        self._update_busy()
        self.stage.toast.show_message(L(f"Сохранено: {Path(path).name}  ({w}×{h}, {dt:.1f} с)",
                                      f"Saved: {Path(path).name}  ({w}×{h}, {dt:.1f} s)"),
                                      tooltip=path)

    # --------------------------------------------------------
    # Статус
    # --------------------------------------------------------

    def set_status(self, text: str, error: bool = False):
        self.lbl_status.setProperty("error", error)
        repolish(self.lbl_status)
        self.lbl_status.setText(text)

    def _update_meta(self):
        sw, sh = self._screen_size()
        items = [(L("Экран", "Screen"), f"{sw}×{sh}")]
        if self.full is not None:
            fw, fh = self.full.size
            l, t, r, b = crop_box(fw, fh, sw / sh)
            items.append((L("Исходник", "Source"), f"{fw}×{fh}"))
            items.append((L("Кадр", "Frame"), f"{r - l}×{b - t}"))
        parts = [f'<span style="color:{C["muted"]}">{k}</span>&nbsp;'
                 f'<span style="font-family:\'{self.mono_family}\'">{v}</span>'
                 for k, v in items]
        self.lbl_meta.setText("&nbsp;&nbsp;&nbsp;&nbsp;".join(parts))


# ============================================================
# ЗАПУСК
# ============================================================

def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("ascii-wallpaper")
    app.setDesktopFileName("ascii-wallpaper")  # app_id окна в Hyprland
    apply_theme(app)

    initial = sys.argv[1] if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]) else None
    win = MainWindow(initial)
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
