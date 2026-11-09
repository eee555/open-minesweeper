from dataclasses import FrozenInstanceError

from django.test import SimpleTestCase

from config.text_choices import Medal_TextChoices
from .definitions import all_definitions, DEFINITIONS, get_definition
from .services import active_definitions
from .utils import basic_definitions, NOVICE_MODES


class StaticDefinitionTests(SimpleTestCase):
    def test_catalog_and_lookup_do_not_access_database(self):
        self.assertTrue(active_definitions())
        self.assertEqual(dict(get_definition(NOVICE_MODES).scope), {})
        self.assertIsNone(get_definition('unknown'))

    def test_rules_and_containers_cannot_be_mutated(self):
        rule = get_definition(NOVICE_MODES)
        with self.assertRaises(FrozenInstanceError):
            rule.active = False
        with self.assertRaises(TypeError):
            rule.scope['modes'] = ('00',)
        with self.assertRaises(TypeError):
            DEFINITIONS['other'] = rule
        self.assertIsInstance(rule.thresholds, tuple)

    def test_unique_codes_threshold_order_and_composite_dependencies(self):
        rules = all_definitions()
        self.assertEqual(len(rules), len({row['code'] for row in basic_definitions()}) + 1)
        for rule in rules:
            with self.subTest(code=rule.code):
                self.assertTrue(all(isinstance(value, int) and value > 0 for value in rule.thresholds))
                self.assertEqual(rule.thresholds, tuple(sorted(set(rule.thresholds), reverse=rule.direction == Medal_TextChoices.Direction.DESC)))
                for code in rule.depends_on:
                    dependency = get_definition(code)
                    self.assertIsNotNone(dependency)
                    self.assertEqual(dependency.kind, Medal_TextChoices.Kind.PB)
                    self.assertEqual(dependency.style, rule.style)
