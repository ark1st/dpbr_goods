"""Separate the two supplied mascots and fit their individual acrylic pieces."""
from functools import lru_cache
from io import BytesIO

import cv2
import numpy as np
import pymupdf as fitz
from PIL import Image

from build_a3_release import ROOT, MM, polygon_of
from reference_cut_style import read_reference, reference_keyring, reference_stand, reference_star_paths


def character_image(source, side):
    """Keep the enclosed whites of each outlined sprite and remove its ground shadow."""
    rgb = np.asarray(source.convert('RGB'))
    red, _, blue = rgb.astype(np.int16).transpose(2, 0, 1)
    yy, xx = np.indices(red.shape)
    # The image has a white matte. The brown ground ellipses start below both
    # ankles and have warmer channels than either character's shoe outlines.
    shadow = (yy >= 566) & (red - blue > 3) & (red > 37)
    region = xx < 178 if side == 'red' else xx >= 178
    trace = (region & ~shadow & (rgb.min(axis=2) < 222)).astype(np.uint8)
    contours, _ = cv2.findContours(trace, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    alpha = np.zeros(red.shape, dtype=np.uint8)
    cv2.drawContours(alpha, [max(contours, key=cv2.contourArea)], -1, 255, cv2.FILLED)
    image = Image.new('RGBA', source.size)
    image.paste(source.convert('RGBA'), mask=Image.fromarray(alpha))
    return image.crop(image.getbbox())


def make_piece(ident, paths, image=None, art_rect=None):
    outer = max(map(polygon_of, paths), key=lambda polygon: polygon.area)
    art = fitz.open()
    page = art.new_page(width=120*MM, height=150*MM)
    if image is not None:
        stream = BytesIO()
        image.save(stream, format='PNG')
        page.insert_image(fitz.Rect(*(value*MM for value in art_rect)), stream=stream.getvalue())
    return dict(id=ident, paths=paths, poly=outer, bounds=outer.bounds,
                source_bounds_mm=list(outer.bounds), art=art)


@lru_cache(None)
def mascot_pieces():
    reference = read_reference(ROOT/'assets/incoming/fixed_page3.ai')
    pieces = {}
    with Image.open(ROOT/'assets/incoming/mascot_pair.png') as source:
        images = {side: character_image(source, side) for side in ('red', 'blue')}
        for side, image in images.items():
            # Share the physical pixel pitch of the supplied pair. Hole and
            # insert dimensions stay in real millimetres for both characters.
            ratio = image.height / images['blue'].height
            for kind, generate, height in [('stand', reference_stand, 51.16),
                                            ('keyring', reference_keyring, 40.)]:
                design = generate(image, reference, ink_height_mm=height * ratio)
                ident = f'mascot_{side}_{kind}'
                pieces[ident] = make_piece(ident, design['paths'], image, design['art_rect_mm'])
            ident = f'mascot_{side}_base'
            pieces[ident] = make_piece(ident, reference_star_paths(reference, (10,10)))
    return pieces
