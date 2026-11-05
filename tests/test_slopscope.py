"""slopscope tests. Browser tests need Playwright and Chromium (CHROMIUM_PATH or Playwright's own)."""
import importlib.util
import json
import pathlib
import re
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills' / 'slopscope'
sys.path.insert(0, str(SKILL / 'scripts'))
HAS_PLAYWRIGHT = importlib.util.find_spec('playwright') is not None
FAILING = ['M-01', 'M-02', 'M-03', 'M-04', 'M-05', 'M-06', 'M-07', 'M-08']


class Frontmatter(unittest.TestCase):
    """The Agent Skills specification (agentskills.io/specification)."""
    def test_skill_md(self):
        text = (SKILL / 'SKILL.md').read_text()
        m = re.match(r'^---\n(.*?)\n---\n', text, re.S)
        self.assertIsNotNone(m)
        fields = {}
        for line in m[1].splitlines():
            if line and not line.startswith(' '):
                key, _, value = line.partition(':'); fields[key] = value.strip()
        self.assertLessEqual(set(fields), {'name', 'description', 'license', 'compatibility', 'metadata', 'allowed-tools'})
        self.assertRegex(fields['name'], r'^[a-z0-9]+(-[a-z0-9]+)*$')
        self.assertLessEqual(len(fields['name']), 64)
        self.assertEqual(fields['name'], SKILL.name)
        self.assertTrue(0 < len(fields['description']) <= 1024)
        self.assertLessEqual(len(fields['compatibility']), 500)
        self.assertLess(len(text.splitlines()), 500)
        for ref in re.findall(r'\]\((references/[^)]+)\)', text):
            self.assertTrue((SKILL / ref).exists(), ref)


@unittest.skipUnless(HAS_PLAYWRIGHT, 'Requires Playwright and Chromium')
class Measure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import measure
        cls.sloppy = measure.measure(str(ROOT / 'examples' / 'sloppy.html'))
        cls.fixed = measure.measure(str(ROOT / 'examples' / 'fixed.html'))
        cls.tricky = measure.measure(str(ROOT / 'examples' / 'tricky.html'))

    def status(self, data):
        return {c['id']: (c['status'], len(c['findings'])) for c in data['checks']}

    def test_sloppy_page_fails_every_check(self):
        s = self.status(self.sloppy)
        for check in FAILING:
            with self.subTest(check=check):
                self.assertEqual(s[check][0], 'fail')

    def test_fixed_page_passes_every_check(self):
        s = self.status(self.fixed)
        for check in FAILING:
            with self.subTest(check=check):
                self.assertEqual(s[check], ('pass', 0))

    def test_findings_point_at_the_planted_problems(self):
        by_id = {c['id']: c for c in self.sloppy['checks']}
        self.assertEqual({f['selector'].split(' > ')[-1] for f in by_id['M-01']['findings']}, {'p.muted:nth-of-type(1)'})
        self.assertTrue(all(f['value'] == '1.98:1' for f in by_id['M-01']['findings']))
        self.assertIn('button.cta.pulse', {f['selector'].split(' > ')[-1] for f in by_id['M-02']['findings']})
        self.assertTrue(by_id['M-03']['findings'][0]['clipped_by'].endswith('div.clip:nth-of-type(1)'))
        self.assertEqual(by_id['M-04']['findings'][0]['overflow_px'], 185)
        self.assertEqual(by_id['M-05']['findings'][0]['font_px'], 13)
        self.assertEqual([f['role'] for f in by_id['M-06']['findings']], ['button'])
        self.assertEqual([f['size'] for f in by_id['M-07']['findings']], [[16, 16], [16, 16]])
        self.assertEqual([f['name'] for f in by_id['M-08']['findings']], ['pulse'])
        self.assertGreater(by_id['M-09']['variety']['text_colors']['distinct'], 5)

    def test_dark_is_measured_only_when_supported(self):
        self.assertEqual((self.fixed['dark_supported'], self.fixed['themes']), (True, ['light', 'dark']))
        self.assertEqual((self.sloppy['dark_supported'], self.sloppy['themes']), (False, ['light']))

    def test_real_site_patterns_pass(self):
        """tricky.html: patterns from real sites that 0.1.0 crashed on or misreported."""
        s = self.status(self.tricky)
        for check in ['M-02', 'M-03', 'M-04', 'M-05', 'M-07', 'M-08']:
            with self.subTest(check=check):
                self.assertEqual(s[check], ('pass', 0))
        by_id = {c['id']: c for c in self.tricky['checks']}
        # every stop is visited: skip link, 2 nav, field, checkbox, 2 cards, web component, 2 footer
        self.assertEqual(self.tricky['focus_stops'], 10)
        self.assertEqual([f['selector'] for f in by_id['M-02']['caret_only']], ['label > input.field'])

    def test_web_component_problems_are_found(self):
        by_id = {c['id']: c for c in self.tricky['checks']}
        self.assertEqual({f['selector'] for f in by_id['M-01']['findings']}, {'main#main > kumo-badge >>> p'})
        self.assertEqual([f['selector'] for f in by_id['M-06']['findings']], ['main#main > kumo-badge >>> button'])
        self.assertEqual(by_id['M-01']['by_colors'][0]['findings'], 2)  # one color pair, two viewports

    def test_compare_flags_regression(self):
        import compare
        with tempfile.TemporaryDirectory() as tmp:
            good, bad = pathlib.Path(tmp, 'good.json'), pathlib.Path(tmp, 'bad.json')
            good.write_text(json.dumps(self.fixed)); bad.write_text(json.dumps(self.sloppy))
            rows = compare.compare(compare.load(good), compare.load(bad))
            self.assertEqual({r[0] for r in rows if r[5] == 'REGRESSION'}, set(FAILING))
            self.assertEqual(compare.main([str(good), str(bad), '--out', str(pathlib.Path(tmp, 'c.md'))]), 1)
            self.assertEqual(compare.main([str(bad), str(good), '--out', str(pathlib.Path(tmp, 'c.md'))]), 0)

    def test_snapshot_is_stable(self):
        import compare, snapshot
        with tempfile.TemporaryDirectory() as tmp:
            snapshot.snapshot(str(ROOT / 'examples' / 'sloppy.html'), pathlib.Path(tmp, 'a'), (375,), ('light',))
            snapshot.snapshot(str(ROOT / 'examples' / 'sloppy.html'), pathlib.Path(tmp, 'b'), (375,), ('light',))
            self.assertEqual(compare.compare_shots(pathlib.Path(tmp, 'a'), pathlib.Path(tmp, 'b')), [('375-light.png', 'identical')])

    def test_snapshot_skips_dark_and_splits_long_pages(self):
        import snapshot
        with tempfile.TemporaryDirectory() as tmp:
            long_page = pathlib.Path(tmp, 'long.html')
            long_page.write_text('<!doctype html><meta name="viewport" content="width=device-width">'
                                 '<title>Long (fictional)</title><body style="margin:0"><div style="height:2500px">x</div>')
            written, notes = snapshot.snapshot(str(long_page), pathlib.Path(tmp, 'shots'), (375,))
            names = sorted(p.name for p in written)
            self.assertEqual(names, ['375-light-part01.png', '375-light-part02.png', '375-light-part03.png', '375-light.png'])
            self.assertTrue(any('dark' in n for n in notes))

    def test_compare_notes_different_setups(self):
        import compare
        with tempfile.TemporaryDirectory() as tmp:
            a, b = pathlib.Path(tmp, 'a.json'), pathlib.Path(tmp, 'b.json')
            a.write_text(json.dumps(self.fixed)); b.write_text(json.dumps(self.sloppy))
            self.assertEqual(len(compare.setup_notes(a, b)), 1)  # themes differ
            self.assertEqual(compare.setup_notes(a, a), [])


if __name__ == '__main__':
    unittest.main()
