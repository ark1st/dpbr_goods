"""Korean fonts shared by the acrylic and T-shirt guides."""

import os
from pathlib import Path
import sys

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

GUIDE_FONT = 'GuideKorean'
GUIDE_BOLD = 'GuideKoreanBold'


def register_guide_fonts():
    if sys.platform == 'darwin':
        regular = Path('/System/Library/Fonts/Supplemental/AppleGothic.ttf')
        bold = regular
    elif sys.platform.startswith('linux'):
        # WSL/Linux: read the Korean fonts from the Windows drive when present.
        fonts = Path(os.environ.get('WINFONTS', '/mnt/c/Windows/Fonts'))
        regular = fonts / 'malgun.ttf'
        bold = fonts / 'malgunbd.ttf'
    else:
        fonts = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
        regular = fonts / 'malgun.ttf'
        bold = fonts / 'malgunbd.ttf'
    for name, file in ((GUIDE_FONT, regular), (GUIDE_BOLD, bold)):
        pdfmetrics.registerFont(TTFont(name, str(file)))
    return regular
