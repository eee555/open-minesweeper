"""Inspect base-color separation; this is a design diagnostic, not an accessibility certificate."""
from pathlib import Path
import itertools
import json
import math

ROOT = Path(__file__).resolve().parent
MATRICES = {
    'normal': [1, 0, 0, 0, 1, 0, 0, 0, 1],
    'protanopia': [.152286, 1.052583, -.204868, .114503, .786281, .099216, -.003882, -.048116, 1.051998],
    'deuteranopia': [.367322, .860646, -.227968, .280085, .672501, .047413, -.011820, .042940, .968881],
    'tritanopia': [1.255528, -.076749, -.178779, -.078411, .930809, .147602, .004733, .691367, .303900],
}


def linear_rgb(color):
    rgb = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in rgb]


def lab(rgb):
    r, g, b = rgb
    xyz = ((.4124564 * r + .3575761 * g + .1804375 * b) / .95047,
           .2126729 * r + .7151522 * g + .072175 * b,
           (.0193339 * r + .119192 * g + .9503041 * b) / 1.08883)
    f = lambda v: v ** (1 / 3) if v > (6 / 29) ** 3 else v / (3 * (6 / 29) ** 2) + 4 / 29
    x, y, z = map(f, xyz)
    return [116 * y - 16, 500 * (x - y), 200 * (y - z)]


data = json.loads((ROOT / 'review.json').read_text(encoding='utf8'))
colors = data['default_palette']['colors']
results = {}
for mode, matrix in MATRICES.items():
    points = []
    for color in colors:
        rgb = linear_rgb(color)
        simulated = [max(0, min(1, sum(matrix[row * 3 + k] * rgb[k] for k in range(3)))) for row in range(3)]
        points.append(lab(simulated))
    pairs = sorted(({'tiers': [a + 1, b + 1], 'delta_e_76': round(math.dist(points[a], points[b]), 2)}
                    for a, b in itertools.combinations(range(5), 2)), key=lambda pair: pair['delta_e_76'])
    results[mode] = {'closest_pair': pairs[0], 'all_pairs': pairs}
report = {'palette': colors, 'simulation': 'Machado et al. 2009 severity 1.0, linear RGB, clipping to display gamut',
          'metric': 'Euclidean CIELAB distance (Delta E 76), D65',
          'scope': 'base colors only; excludes metal highlights, tiny glyphs and individual vision; no normative pass threshold',
          'modes': results}
(ROOT / 'palette-check.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf8')
print(json.dumps({mode: result['closest_pair'] for mode, result in results.items()}))
