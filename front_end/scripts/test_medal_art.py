"""资源预算回归：从仓库根目录运行 python -m unittest discover -s front_end/scripts -p test_medal_art.py。"""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PIL import Image

from build_medal_art import prepare


EXPECTED = {
    'breakthrough.webp', 'breakthrough-nf.webp', 'speed.webp', 'speed-nf.webp', 'mastery.webp', 'mastery-nf.webp',
    'precision.webp', 'precision-nf.webp', 'precision-three.webp', 'precision-nf-three.webp',
    'registered.webp', 'reviewed.webp', 'levels.webp', 'levels-nf.webp', 'modes.webp', 'saolei.webp', 'shareholder.webp',
}


class MedalTemplateAlphaTests(unittest.TestCase):
    def test_prepare_preserves_dark_grey_and_semitransparent_subject_pixels(self):
        colors = [(0, 0, 0, 255), (170, 170, 170, 255), (240, 200, 100, 128)]
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'subject.png'
            source = Image.new('RGBA', (3, 1))
            source.putdata(colors)
            source.save(path)
            result = prepare(path)
        self.assertEqual([result.getpixel((x, 159)) for x in range(158, 161)], colors)
        self.assertEqual(result.getpixel((0, 0)), (0, 0, 0, 0))

    def test_prepare_rejects_opaque_and_empty_templates(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'invalid.png'
            for source in [Image.new('RGB', (8, 8), 'black'), Image.new('RGBA', (8, 8), (0, 0, 0, 255)), Image.new('RGBA', (8, 8), (0, 0, 0, 0))]:
                with self.subTest(mode=source.mode, pixel=source.getpixel((0, 0))):
                    source.save(path)
                    with self.assertRaises(ValueError):
                        prepare(path)


class MedalArtBudgetTests(unittest.TestCase):
    def test_shipped_images_fit_the_low_bandwidth_budget(self):
        root = Path(__file__).resolve().parents[1] / 'public' / 'assets' / 'medals'
        files = [path for path in root.rglob('*') if path.is_file()]
        total = 0
        names = set()
        largest = 0
        for path in files:
            rel = path.relative_to(root)
            size = path.stat().st_size
            total += size
            largest = max(largest, size)
            with self.subTest(image=str(rel)):
                overlay = rel.parts[0] == 'difficulty'
                self.assertEqual(len(rel.parts), 2 if overlay else 1)
                self.assertLessEqual(size, 2048 if overlay else 8 * 1024)
                with Image.open(path) as image:
                    self.assertEqual(image.format, 'WEBP')
                    self.assertEqual(image.size, (64, 64) if overlay else (128, 128))
                    self.assertIn('A', image.getbands())
                    image.load()
            names.add(rel.as_posix())
        self.assertEqual(names, EXPECTED | {'difficulty/b.webp', 'difficulty/i.webp', 'difficulty/e.webp'})
        self.assertLessEqual(total, 160 * 1024)
        self.assertLessEqual(6 * largest, 44 * 1024)


if __name__ == '__main__':
    unittest.main()
