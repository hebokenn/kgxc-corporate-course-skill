#!/usr/bin/env python3
"""Measure visible subject bounds, excluding transparent padding or scene background."""
import argparse
import json
from pathlib import Path
from PIL import Image, ImageChops


def measure(image, without_subject=None, anchor_x=None, anchor_y=None, tolerance=3, threshold=12):
    with Image.open(image) as opened:
        subject = opened.convert('RGBA')
    if without_subject:
        with Image.open(without_subject) as opened:
            background = opened.convert('RGBA')
        if background.size != subject.size:
            raise ValueError('The two rendered states must have the same size')
        channels = ImageChops.difference(subject.convert('RGB'), background.convert('RGB')).split()
        mask = ImageChops.lighter(ImageChops.lighter(channels[0], channels[1]), channels[2])
        mask = mask.point(lambda value: 255 if value > threshold else 0)
        basis = 'difference between identical rendered states with and without the subject'
    else:
        alpha = subject.getchannel('A')
        if alpha.getextrema() == (255, 255):
            raise ValueError('Opaque source: supply an otherwise identical --without-subject render')
        mask = alpha.point(lambda value: 255 if value > threshold else 0)
        basis = 'visible alpha bounds; transparent source margins excluded'
    bounds = mask.getbbox()
    if bounds is None:
        raise ValueError('No visible subject pixels found')
    center = [(bounds[0]+bounds[2])/2, (bounds[1]+bounds[3])/2]
    offsets = {key: center[i]-anchor for i, (key, anchor) in enumerate([('x', anchor_x), ('y', anchor_y)]) if anchor is not None}
    return dict(bounds=list(bounds), center=center, offsets=offsets, tolerance=tolerance, basis=basis,
                status='pass' if all(abs(value)<=tolerance for value in offsets.values()) else 'misaligned',
                scope='Only a declared alignment target is checked; intentional asymmetric composition is valid')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image',type=Path);parser.add_argument('--without-subject',type=Path)
    parser.add_argument('--anchor-x',type=float);parser.add_argument('--anchor-y',type=float)
    parser.add_argument('--tolerance',type=float,default=3);parser.add_argument('--threshold',type=int,default=12)
    parser.add_argument('--out',type=Path);args=parser.parse_args()
    if args.tolerance<0 or not 0<=args.threshold<=254:parser.error('Invalid tolerance or threshold')
    result=measure(args.image,args.without_subject,args.anchor_x,args.anchor_y,args.tolerance,args.threshold)
    if args.out:args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2));raise SystemExit(result['status']!='pass')


if __name__=='__main__':main()
