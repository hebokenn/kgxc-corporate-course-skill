#!/usr/bin/env python3
"""Change only KGXC course lettering on packaged approved R5/R8 Blender backgrounds (pure ffmpeg+PIL+numpy, no cv2 required)."""
from pathlib import Path
import argparse, json, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'workbench'))
try:
    from runtime import activate
    activate()
except Exception:
    pass

A = ROOT / 'assets/bookends'
W, H, FPS = 1280, 720, 24
FONT = A / 'CourseTitle.otf'
TRACK = json.loads((A / 'title-tracking.json').read_text(encoding='utf-8'))


def smooth_intro(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


def smooth_outro(x):
    x = max(0.0, min(1.0, x))
    return x * x * x * (10.0 + x * (-15.0 + 6.0 * x))


def font(n):
    return ImageFont.truetype(str(FONT), n)


def typography(title, subtitle):
    if not title or len(title) > 60:
        raise ValueError('课程名须为 1–60 字')
    lines = [title]
    size = 46
    while size > 30 and font(size).getlength(title) > 680:
        size -= 1
    if font(size).getlength(title) > 680:
        width = lambda i: max(font(32).getlength(title[:i]), font(32).getlength(title[i:]))
        split = min(range(1, len(title)), key=width)
        natural = [i for i in range(5, len(title) - 5) if title[i] in '与及和' or title[i - 1] in '：，、']
        natural = [i for i in natural if width(i) <= min(690, width(split) + 96)]
        if natural:
            split = min(natural, key=width)
        lines = [title[:split], title[split:]]
        size = 32
    if any(font(size).getlength(line) > 690 for line in lines):
        raise ValueError('课程名超出安全区，请缩短课程名')
    layer = Image.new('RGBA', (W * 2, H * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    ys = [420] if len(lines) == 1 else [408, 449]
    for text, y in zip(lines, ys):
        d.text((W, y * 2), text, font=font(size * 2), anchor='mm', fill=(69, 70, 72, 255))
    if subtitle:
        ss = 21
        while ss > 14 and font(ss).getlength(subtitle) > 680:
            ss -= 1
        if font(ss).getlength(subtitle) > 680:
            raise ValueError('副标题超出安全区')
        d.text((W, (478 if len(lines) == 1 else 491) * 2), subtitle, font=font(ss * 2), anchor='mm', fill=(119, 123, 126, 255))
    return layer.resize((W, H), Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(0.22)), lines, size


def split_title(text, size, maxwidth):
    if not text or len(text) > 60:
        raise ValueError('课程主标题须为1–60字')
    while size > 24 and font(size).getlength(text) > maxwidth:
        size -= 1
    if font(size).getlength(text) <= maxwidth:
        return [text], size
    mid = min(range(1, len(text)), key=lambda k: max(font(size).getlength(text[:k]), font(size).getlength(text[k:])))
    lines = [text[:mid], text[mid:]]
    if any(font(size).getlength(x) > maxwidth for x in lines):
        raise ValueError('主标题超出两行安全区')
    return lines, size


def lettering(title, subtitle):
    lines, size = split_title(title, 76, 1330)
    layer = Image.new('RGBA', (1600, 900), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    ys = [585] if len(lines) == 1 else [550, 630]
    for t, y in zip(lines, ys):
        d.text((800, y), t, font=font(size), anchor='mm', fill=(65, 70, 76, 255))
    if subtitle:
        ss = 38
        while ss > 23 and font(ss).getlength(subtitle) > 1300:
            ss -= 1
        if font(ss).getlength(subtitle) > 1300:
            raise ValueError('副标题超出安全区')
        d.text((800, 710 if len(lines) == 1 else 743), subtitle, font=font(ss), anchor='mm', fill=(112, 121, 128, 255))
    final = Image.new('RGBA', (W * 2, H * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(final)
    lastsize = 44
    while lastsize > 20 and font(lastsize).getlength(title) > 1000:
        lastsize -= 1
    if font(lastsize).getlength(title) > 1000:
        raise ValueError('请缩短课程名，以保持主标题和副标题两行')
    d.text((W, 490 * 2), title, font=font(lastsize * 2), anchor='mm', fill=(45, 52, 59, 255))
    if subtitle:
        ss = 24
        while ss > 16 and font(ss).getlength(subtitle) > 960:
            ss -= 1
        if font(ss).getlength(subtitle) > 960:
            raise ValueError('副标题超出单行安全区')
        d.text((W, 552 * 2), subtitle, font=font(ss * 2), anchor='mm', fill=(85, 95, 104, 255))
    return layer, final.resize((W, H), Image.Resampling.LANCZOS)


def find_perspective_coeffs(dst_pts, src_pts):
    """Solve coefficients mapping output (dst) coords to input (src) coords for PIL Image.Transform.PERSPECTIVE."""
    matrix = []
    for (x, y), (u, v) in zip(dst_pts, src_pts):
        matrix.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        matrix.append([0, 0, 0, x, y, 1, -v * x, -v * y])
    A_mat = np.array(matrix, dtype=np.float64)
    B_vec = np.array([c for pt in src_pts for c in pt], dtype=np.float64)
    return np.linalg.solve(A_mat, B_vec).tolist()


def over_rgb(bg_rgb, layer_rgba, opacity=1.0):
    if opacity <= 0.001:
        return bg_rgb
    arr = np.asarray(layer_rgba, dtype=np.float32)
    rgb = arr[:, :, :3]
    a = (arr[:, :, 3] / 255.0) * float(opacity)
    return bg_rgb * (1.0 - a[:, :, None]) + rgb * a[:, :, None]


def encode(kind, count, layer_img, final_img, out, target_fps=24):
    bg_path = A / f'{kind}-background.mkv'
    limit = 145 if kind == 'intro' else 109
    decoder = subprocess.Popen(
        ['ffmpeg', '-v', 'error', '-i', str(bg_path), '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
        stdout=subprocess.PIPE
    )
    encoder = subprocess.Popen(
        ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
         '-c:v', 'libx264', '-preset', 'medium', '-crf', '16', '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
         str(out / f'{kind}.mp4')],
        stdin=subprocess.PIPE
    )
    frame_bytes = W * H * 3
    last = None
    src_quad = [(0, 0), (layer_img.width, 0), (layer_img.width, layer_img.height), (0, layer_img.height)]
    try:
        for f in range(1, count + 1):
            if f <= limit:
                raw = decoder.stdout.read(frame_bytes)
                if len(raw) != frame_bytes:
                    raise ValueError(f'批准背景帧缺失: frame {f}')
                last = np.frombuffer(raw, dtype=np.uint8).reshape((H, W, 3))
            im = last.astype(np.float32)
            if kind == 'intro':
                op = smooth_intro(((f - 1) / 24.0 - 3.72) / 0.62)
                im = over_rgb(im, layer_img, op)
            else:
                if f <= 70 and TRACK[str(f)]['opacity'] > 0.001:
                    dst_quad = [tuple(pt) for pt in TRACK[str(f)]['quad']]
                    coeffs = find_perspective_coeffs(dst_quad, src_quad)
                    warped = layer_img.transform((W, H), Image.Transform.PERSPECTIVE, coeffs, Image.Resampling.BICUBIC)
                    im = over_rgb(im, warped, TRACK[str(f)]['opacity'])
                op = smooth_outro(((f - 1) / 24.0 - 3.7) / 0.45)
                if op > 0.001:
                    im = over_rgb(im, final_img, op)
            image = np.clip(im, 0, 255).astype(np.uint8)
            if f == count:
                Image.fromarray(image).save(out / f'{kind}-poster.png')
            encoder.stdin.write(image.tobytes())
        encoder.stdin.close()
        if encoder.wait():
            raise ValueError('品牌片段编码失败')
    finally:
        decoder.stdout.close()
        decoder.wait()
        if encoder.poll() is None:
            encoder.kill()
            encoder.wait()

    dur = count / 24.0
    for mode, vf in [('preview', None), ('1080p24', f'scale=1920:1080:flags=lanczos,fps=24'), ('1080p30', f'scale=1920:1080:flags=lanczos,fps=30')]:
        cmd = ['ffmpeg', '-v', 'error', '-y', '-i', str(out / f'{kind}.mp4'), '-i', str(A / f'{kind}-score.wav'),
               '-map', '0:v:0', '-map', '1:a:0', '-af', f'aresample=48000,aformat=channel_layouts=stereo,apad,afade=t=out:st={max(0, dur-0.35):.2f}:d=0.35', '-t', f'{dur:.3f}']
        if vf is None:
            cmd += ['-c:v', 'copy']
        else:
            cmd += ['-vf', vf, '-c:v', 'libx264', '-crf', '16', '-pix_fmt', 'yuv420p']
        cmd += ['-c:a', 'aac', '-b:a', '256k', '-movflags', '+faststart', str(out / f'{kind}-{mode}.mp4')]
        subprocess.run(cmd, check=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--title', required=True)
    p.add_argument('--subtitle', default='')
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--intro-frames', type=int, default=145, help='Total frames for intro at 24fps (default 145 = 6.04s; title fades in 3.72s-4.34s)')
    p.add_argument('--outro-frames', type=int, default=115, help='Total frames for outro at 24fps (default 115 = 4.79s)')
    p.add_argument('--overwrite', action='store_true')
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    if not a.overwrite and any(a.out.iterdir()):
        raise ValueError('目标目录非空，保留已有品牌片段；如需重生成请传 --overwrite 或新目录')
    intro_layer, _, _ = typography(a.title, a.subtitle)
    outro_layer, outro_final = lettering(a.title, a.subtitle)
    encode('intro', a.intro_frames, intro_layer, None, a.out)
    encode('outro', a.outro_frames, outro_layer, outro_final, a.out)
    print(f'Generated KGXC R5/R8 bookends in {a.out}')


if __name__ == '__main__':
    main()
