import importlib.util
import itertools
import json
import math
from pathlib import Path
import tempfile
import shutil
import unittest

ROOT = Path(__file__).resolve().parents[2]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


calculator = module('course_compute', 'skills/statistics-probability/scripts/compute.py')
validator = module('skill_validator', 'scripts/validate_skills.py')


class RuntimeSkillsTests(unittest.TestCase):
    def request(self, values):
        return dict(operation='describe', values=values, context=dict(
            dataset_id='synthetic-latency', dataset_version='1', observation_unit='request',
            units='ms', variable_type='quantitative', scope='sample'))

    def test_sample_scope_and_original_units(self):
        result = calculator.compute(self.request([100, 110, 120, 130, 140, 300]))
        self.assertEqual((result['mean'], result['median'], result['variance']), (150, 125, 5600))
        self.assertAlmostEqual(result['sd'], math.sqrt(5600))

    def test_population_scope_changes_denominator(self):
        request = self.request([2, 4, 6])
        self.assertEqual(calculator.compute(request)['variance'], 4)
        request['context']['scope'] = 'population'
        self.assertAlmostEqual(calculator.compute(request)['variance'], 8/3)

    def test_missing_context_rejected(self):
        for key in ('dataset_id', 'dataset_version', 'scope', 'observation_unit', 'units'):
            request = self.request([1, 2])
            del request['context'][key]
            with self.assertRaises(ValueError):
                calculator.compute(request)

    def test_invalid_or_nominal_values_rejected(self):
        for values in ([True, 2], [None], [float('nan')], [float('inf')], ['x'], []):
            with self.assertRaises(ValueError):
                calculator.compute(self.request(values))
        request = self.request([1, 2]); request['context']['variable_type'] = 'nominal'
        with self.assertRaises(ValueError):
            calculator.compute(request)

    def test_undefined_sample_and_constant_data(self):
        self.assertIsNone(calculator.compute(self.request([7]))['variance'])
        self.assertEqual(calculator.compute(self.request([7]))['modes'], [7])
        self.assertEqual(calculator.compute(self.request([7, 7]))['sd'], 0)

    def test_modes_and_outlier_sensitive_center(self):
        result = calculator.compute(self.request([120, 180, 180, 200, 260, 310, 900]))
        self.assertEqual(result['modes'], [180])
        self.assertEqual(result['median'], 200)
        self.assertAlmostEqual(result['mean'], 2150/7)
        self.assertEqual(calculator.compute(self.request([1, 1, 2, 2]))['modes'], [1, 2])

    def test_count_models_against_exhaustive_spaces(self):
        for n in range(6):
            for r in range(n+1):
                for model, iterator in [('ordered-distinct', itertools.permutations(range(n), r)),
                                        ('unordered-distinct', itertools.combinations(range(n), r)),
                                        ('ordered-replacement', itertools.product(range(n), repeat=r))]:
                    result = calculator.compute(dict(operation='count', model=model, n=n, r=r))
                    self.assertEqual(result['count'], sum(1 for _ in iterator))

    def test_bad_count_models_and_sizes(self):
        for n, r, model in [(2, 3, 'ordered-distinct'), (True, 1, 'unordered-distinct'),
                            (-1, 0, 'unordered-distinct'), (2, 1, 'guess')]:
            with self.assertRaises(ValueError):
                calculator.compute(dict(operation='count', model=model, n=n, r=r))

    def test_package_and_provenance(self):
        self.assertEqual(validator.validate()['skills'], 9)

    def test_cycles_and_unnecessary_nesting_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / 'statistics-probability'
            shutil.copytree(validator.PACKAGE, package)
            path = package / 'references/manifest.json'
            manifest = json.loads(path.read_text())
            manifest['skills'][0]['prerequisites'] = [manifest['skills'][0]['name']]
            path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'Circular'):
                validator.validate(package)
            manifest['skills'][0]['prerequisites'] = []
            path.write_text(json.dumps(manifest))
            nested = package / 'subskills/extra/deeper/SKILL.md'
            nested.parent.mkdir(parents=True); nested.write_text('unregistered')
            with self.assertRaisesRegex(ValueError, 'nesting'):
                validator.validate(package)

    def test_modified_provenance_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / 'statistics-probability'
            shutil.copytree(validator.PACKAGE, package)
            path = package / 'references/data-foundations-evidence.json'
            data = json.loads(path.read_text(encoding='utf-8'))
            data[0]['units'][0]['evidence'][0]['quote'] = 'Invented quotation'
            path.write_text(json.dumps(data), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Evidence differs'):
                validator.validate(package)

    def test_source_revision_drift_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / 'statistics-probability'
            shutil.copytree(validator.PACKAGE, package)
            path = package / 'references/sources.json'
            data = json.loads(path.read_text(encoding='utf-8'))
            data['sources']['D1']['sha256'] = '0' * 64
            path.write_text(json.dumps(data), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'revision drift'):
                validator.validate(package)


if __name__ == '__main__':
    unittest.main()
