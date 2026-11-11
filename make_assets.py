import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).parent
ASSETS = ROOT / 'assets'
ASSETS.mkdir(exist_ok=True)

BG = (5, 5, 10, 255)
NEON_GREEN = (154, 255, 24, 255)
DEEP_GREEN = (0, 220, 120, 255)
EDGE_GREEN = (212, 255, 138, 255)


def petal_points(r0: float, rt: float, D: float, n: int = 48):
    """Boundary of one leaf: base arc (radius r0 at origin) + tangents + rounded tip arc."""
    d = D - rt
    h = math.sqrt(d * d - (r0 - rt) ** 2)
    xt, yt = r0 * (r0 - rt) / d, r0 * h / d
    x2, y2 = d + rt * (r0 - rt) / d, rt * h / d
    ang = math.atan2(yt, xt)
    phi = math.atan2(y2, x2 - d)
    pts = [(-r0, 0)]
    for i in range(1, n + 1):
        a = math.pi - (math.pi - ang) * i / n
        pts.append((r0 * math.cos(a), r0 * math.sin(a)))
    pts.append((x2, y2))
    for i in range(1, n + 1):
        a = phi * (1 - i / n)
        pts.append((d + rt * math.cos(a), rt * math.sin(a)))
    for i in range(1, n + 1):
        a = -phi * i / n
        pts.append((d + rt * math.cos(a), rt * math.sin(a)))
    pts.append((xt, -yt))
    for i in range(1, n + 1):
        a = -(math.pi - ang) + (math.pi - ang) * i / n
        pts.append((r0 * math.cos(a), r0 * math.sin(a)))
    pts.append((-r0, 0))
    return pts


def draw_clover(size: int = 2048, highlight: bool = True) -> Image.Image:
    """Draw a clean flat 4-leaf clover (4chan-style) procedurally."""
    canvas = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    cx = cy = size / 2
    Rc = size * 0.40
    r0 = 0.34 * Rc
    k = 0.60

    def r_leaf(theta):
        return Rc * (math.cos(2 * theta) + k) / (1 + k)

    theta_h = math.acos(max(-1.0, min(1.0, r0 * (1 + k) / Rc - k))) / 2

    boundary = []
    for i in range(4):
        base = i * math.pi / 2
        for j in range(61):
            th = -theta_h + 2 * theta_h * j / 60
            rr = r_leaf(th)
            a = base + th
            boundary.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
        for j in range(1, 16):
            a = base + theta_h + (math.pi / 2 - 2 * theta_h) * j / 16
            boundary.append((cx + r0 * math.cos(a), cy + r0 * math.sin(a)))
    ImageDraw.Draw(canvas).polygon([(int(x), int(y)) for x, y in boundary], fill=NEON_GREEN)

    alpha = canvas.getchannel('A')
    punch = Image.new('L', (size, size), 0)
    pd = ImageDraw.Draw(punch)
    rn = 0.17 * Rc
    for i in range(4):
        rad = i * math.pi / 2
        px, py = cx + Rc * math.cos(rad), cy + Rc * math.sin(rad)
        pd.ellipse([px - rn, py - rn, px + rn, py + rn], fill=255)
    from PIL import ImageChops
    alpha = ImageChops.subtract(alpha, punch)
    canvas.putalpha(alpha)

    alpha = canvas.getchannel('A')
    if highlight:
        edge = alpha.filter(ImageFilter.FIND_EDGES).point(lambda v: 255 if v > 60 else 0)
        h = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        h.paste(EDGE_GREEN, (0, 0), edge)
        canvas = Image.alpha_composite(canvas, h)

    preview = Image.new('RGBA', (size, size), BG)
    preview.alpha_composite(canvas)
    preview.convert('RGB').save(ASSETS / 'preview_dark.png')
    return canvas


def extract_clover() -> Image.Image:
    clover = draw_clover()
    clover.save(ASSETS / 'clover.png')
    print('clover:', clover.size)
    return clover


def glow_layer(clover: Image.Image, size: int, radius: int, color) -> Image.Image:
    base = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    w = clover.width
    scaled = clover.resize((w, w), Image.LANCZOS)
    pos = ((size - w) // 2, (size - w) // 2)
    solid = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    solid.paste(color, pos, scaled.getchannel('A'))
    return solid.filter(ImageFilter.GaussianBlur(radius))


def make_splash_gif(clover: Image.Image):
    size = 460
    clover_scaled = clover.resize((340, 340), Image.LANCZOS)
    frames = []
    n_frames = 40
    for i in range(n_frames):
        t = i / n_frames
        pulse = (math.sin(t * 2 * math.pi) + 1) / 2

        frame = Image.new('RGB', (size, size), (5, 5, 10))

        bloom = glow_layer(clover_scaled, size, radius=int(34 + 26 * pulse), color=(0, 255, 70, 150))
        frame = Image.alpha_composite(frame.convert('RGBA'), bloom).convert('RGB')

        halo = glow_layer(clover_scaled, size, radius=int(8 + 20 * pulse), color=(60, 255, 120, 190))
        frame = Image.alpha_composite(frame.convert('RGBA'), halo).convert('RGB')

        pos = ((size - clover_scaled.width) // 2, (size - clover_scaled.height) // 2)
        glow = clover_scaled.copy()
        glow.putalpha(clover_scaled.getchannel('A').point(lambda v: int(v * (0.70 + 0.30 * pulse))))
        frame.paste(NEON_GREEN[:3], pos, glow.getchannel('A'))

        core = clover_scaled.copy()
        core.putalpha(core.getchannel('A').point(lambda v: int(v * (0.35 + 0.65 * pulse))))
        frame.paste(DEEP_GREEN[:3], pos, core.getchannel('A'))

        d = ImageDraw.Draw(frame)
        for y in range(0, size, 4):
            d.line([(0, y), (size, y)], fill=(3, 3, 7))

        frames.append(frame.convert('P', palette=Image.ADAPTIVE, colors=256, dither=Image.FLOYDSTEINBERG))

    frames[0].save(
        ASSETS / 'splash.gif',
        save_all=True,
        append_images=frames[1:],
        duration=45,
        loop=0,
        disposal=2,
    )
    frames[10].convert('RGB').save(ASSETS / 'preview_splash.png')
    print('splash.gif:', len(frames), 'frames @', size)


def make_icon(clover: Image.Image):
    render = 2048
    canvas = Image.new('RGBA', (render, render), (0, 0, 0, 0))
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle([12, 12, render - 13, render - 13], radius=448, fill=BG)
    d.rounded_rectangle([12, 12, render - 13, render - 13], radius=448, outline=(0, 255, 120, 255), width=44)
    w = int(render * 0.72)
    scaled = clover.resize((w, w), Image.LANCZOS)
    pos = ((render - w) // 2, (render - w) // 2)
    canvas.paste(scaled, pos, scaled.getchannel('A'))
    out = canvas.resize((256, 256), Image.LANCZOS)
    out = out.filter(ImageFilter.GaussianBlur(0.5))
    out.save(ASSETS / 'icon.png')
    out.save(ASSETS / 'icon.ico', sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    print('icon.ico written')


if __name__ == '__main__':
    clover = extract_clover()
    flat = draw_clover(size=4096, highlight=False)
    flat.save(ASSETS / 'clover_flat.png')
    make_splash_gif(clover)
    make_icon(flat)
    print('done ->', ASSETS)
