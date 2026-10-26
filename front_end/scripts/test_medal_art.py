"""资源预算回归：从仓库根目录运行 python -m unittest discover -s front_end/scripts -p test_medal_art.py。"""
from pathlib import Path
import unittest

from PIL import Image


EXPECTED = {
    'breakthrough.webp', 'breakthrough-nf.webp', 'speed.webp', 'speed-nf.webp', 'mastery.webp', 'mastery-nf.webp',
    'precision.webp', 'precision-nf.webp', 'precision-three.webp', 'precision-nf-three.webp',
    'registered.webp', 'reviewed.webp', 'levels.webp', 'levels-nf.webp', 'modes.webp', 'saolei.webp', 'shareholder.webp',
}


class MedalArtBudgetTests(unittest.TestCase):
    def test_shipped_images_fit_the_low_bandwidth_budget(self):
        root = Path(__file__).resolve().parents[1] / 'public' / 'assets' / 'medals'
        files = list(root.rglob('*.webp'))
        total = 0
        names = set()
        largest = 0
        for path in files:
            rel = path.relative_to(root)
            size = path.stat().st_size
            total += size
            largest = max(largest, size)
            with self.subTest(image=str(rel)):
                self.assertEqual(len(rel.parts), 1)
                self.assertLessEqual(size, 8 * 1024)
                with Image.open(path) as image:
                    self.assertEqual(image.format, 'WEBP')
                    self.assertEqual(image.size, (128, 128))
                    self.assertIn('A', image.getbands())
                    image.load()
            names.add(rel.name)
        self.assertEqual(names, EXPECTED)
        self.assertLessEqual(total, 160 * 1024)
        self.assertLessEqual(6 * largest, 44 * 1024)


if __name__ == '__main__':
    unittest.main()
