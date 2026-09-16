#!/usr/bin/env python3
"""Parsers for Gravity sprite formats used by the visual simulator.

- .spr  : sprite frames (indexed 8-bit with RLE + optional 32-bit RGBA), palette at end
- .act  : actions -> frames -> layers (sprite index, offset, mirror, tint, scale, rotation)
           + per-frame anchors used to attach head/headgear to the body
- .pal  : 256 x RGBA palette (alternate hair/cloth colours)

Used by tools/export_sprites.py for validation and reference; the frontend
re-implements the same parsing in TypeScript to allow palette swapping.
"""
import struct
from dataclasses import dataclass, field
from PIL import Image


@dataclass
class SprFrame:
    width: int
    height: int
    indexed: bool
    data: bytes  # indexed: width*height palette indices; rgba: width*height*4


@dataclass
class Spr:
    frames: list  # SprFrame
    palette: bytes  # 1024 bytes RGBA (index 0 = transparent)
    version: tuple

    def image(self, idx, palette=None):
        f = self.frames[idx]
        pal = palette or self.palette
        if f.indexed:
            img = Image.new('RGBA', (f.width, f.height))
            px = img.load()
            for y in range(f.height):
                for x in range(f.width):
                    i = f.data[y * f.width + x]
                    if i == 0:
                        px[x, y] = (0, 0, 0, 0)
                    else:
                        px[x, y] = (pal[i * 4], pal[i * 4 + 1], pal[i * 4 + 2], 255)
            return img
        # RGBA frames are stored bottom-up in ABGR order
        img = Image.frombytes('RGBA', (f.width, f.height), f.data)
        r, g, b, a = img.split()
        return Image.merge('RGBA', (a, b, g, r)).transpose(Image.FLIP_TOP_BOTTOM)


def parse_spr(buf: bytes) -> Spr:
    if buf[:2] != b'SP':
        raise ValueError('not a SPR file')
    minor, major = buf[2], buf[3]
    version = (major, minor)
    pos = 4
    (n_indexed,) = struct.unpack_from('<H', buf, pos); pos += 2
    n_rgba = 0
    if version >= (2, 0):
        (n_rgba,) = struct.unpack_from('<H', buf, pos); pos += 2
    frames = []
    for _ in range(n_indexed):
        w, h = struct.unpack_from('<HH', buf, pos); pos += 4
        if version >= (2, 1):  # RLE on index 0
            (size,) = struct.unpack_from('<H', buf, pos); pos += 2
            raw = buf[pos:pos + size]; pos += size
            out = bytearray()
            i = 0
            while i < len(raw):
                c = raw[i]; i += 1
                if c == 0:
                    n = raw[i]; i += 1
                    out += b'\0' * (n if n else 1)
                else:
                    out.append(c)
            data = bytes(out[:w * h]).ljust(w * h, b'\0')
        else:
            data = buf[pos:pos + w * h]; pos += w * h
        frames.append(SprFrame(w, h, True, data))
    for _ in range(n_rgba):
        w, h = struct.unpack_from('<HH', buf, pos); pos += 4
        data = buf[pos:pos + w * h * 4]; pos += w * h * 4
        frames.append(SprFrame(w, h, False, data))
    palette = buf[-1024:] if version >= (1, 1) else bytes(1024)
    return Spr(frames, palette, version)


@dataclass
class ActLayer:
    x: int
    y: int
    sprite: int      # index into spr.frames (-1 = none)
    mirror: bool
    color: tuple     # RGBA 0-255
    scale_x: float
    scale_y: float
    rotation: int
    is_rgba: bool    # sprite index refers to the RGBA frame list


@dataclass
class ActFrame:
    layers: list
    anchors: list = field(default_factory=list)  # [(x, y), ...]
    event: int = -1


@dataclass
class Act:
    actions: list  # list[list[ActFrame]]
    delays: list   # per action, in 24ms units
    events: list
    version: tuple


def parse_act(buf: bytes) -> Act:
    if buf[:2] != b'AC':
        raise ValueError('not an ACT file')
    minor, major = buf[2], buf[3]
    version = (major, minor)
    pos = 4
    (n_actions,) = struct.unpack_from('<H', buf, pos); pos += 2
    pos += 10  # reserved
    actions = []
    for _ in range(n_actions):
        (n_frames,) = struct.unpack_from('<I', buf, pos); pos += 4
        frames = []
        for _ in range(n_frames):
            pos += 32  # unused range boxes
            (n_layers,) = struct.unpack_from('<I', buf, pos); pos += 4
            layers = []
            for _ in range(n_layers):
                x, y, spr, mirror = struct.unpack_from('<iiiI', buf, pos); pos += 16
                color = (255, 255, 255, 255); sx = sy = 1.0; rot = 0; is_rgba = False
                if version >= (2, 0):
                    color = struct.unpack_from('<4B', buf, pos); pos += 4
                    (sx,) = struct.unpack_from('<f', buf, pos); pos += 4
                    sy = sx
                    if version >= (2, 4):
                        (sy,) = struct.unpack_from('<f', buf, pos); pos += 4
                    rot, typ = struct.unpack_from('<ii', buf, pos); pos += 8
                    is_rgba = typ == 1
                    if version >= (2, 5):
                        pos += 8  # width/height (unused)
                layers.append(ActLayer(x, y, spr, bool(mirror), tuple(color), sx, sy, rot, is_rgba))
            event = -1; anchors = []
            if version >= (2, 0):
                (event,) = struct.unpack_from('<i', buf, pos); pos += 4
            if version >= (2, 3):
                (n_anchors,) = struct.unpack_from('<I', buf, pos); pos += 4
                for _ in range(n_anchors):
                    pos += 4  # unknown
                    ax, ay = struct.unpack_from('<ii', buf, pos); pos += 8
                    pos += 4  # attr
                    anchors.append((ax, ay))
            frames.append(ActFrame(layers, anchors, event))
        actions.append(frames)
    events = []
    if version >= (2, 1):
        (n_events,) = struct.unpack_from('<I', buf, pos); pos += 4
        for _ in range(n_events):
            events.append(buf[pos:pos + 40].split(b'\0')[0].decode('latin-1')); pos += 40
    delays = [4.0] * n_actions
    if version >= (2, 2):
        for i in range(n_actions):
            (d,) = struct.unpack_from('<f', buf, pos); pos += 4
            delays[i] = d
    return Act(actions, delays, events, version)


def parse_pal(buf: bytes) -> bytes:
    if len(buf) < 1024:
        raise ValueError('palette too short')
    return buf[:1024]


def draw_layers(canvas: Image.Image, spr: Spr, frame: ActFrame, origin, palette=None):
    """Draw an ACT frame onto `canvas` with the frame's (0,0) at `origin`."""
    n_indexed = sum(1 for f in spr.frames if f.indexed)
    for layer in frame.layers:
        if layer.sprite < 0:
            continue
        idx = layer.sprite + (n_indexed if layer.is_rgba else 0)
        if idx >= len(spr.frames):
            continue
        img = spr.image(idx, palette)
        if layer.mirror:
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
        if layer.scale_x != 1.0 or layer.scale_y != 1.0:
            img = img.resize((max(1, round(img.width * layer.scale_x)), max(1, round(img.height * layer.scale_y))))
        if layer.rotation:
            img = img.rotate(-layer.rotation, expand=True)
        if layer.color != (255, 255, 255, 255):
            r, g, b, a = img.split()
            cr, cg, cb, ca = layer.color
            img = Image.merge('RGBA', (r.point(lambda v: v * cr // 255), g.point(lambda v: v * cg // 255), b.point(lambda v: v * cb // 255), a.point(lambda v: v * ca // 255)))
        px = origin[0] + layer.x - img.width // 2
        py = origin[1] + layer.y - img.height // 2
        canvas.alpha_composite(img, (px, py))
