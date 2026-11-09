from dataclasses import fields
from types import SimpleNamespace
from unittest.mock import patch

from . import definitions


class DefinitionFixture:
    """每个测试独立覆盖代码规则；不创建数据库配置记录。"""

    def install_definitions(self):
        self.rule_map = dict(definitions.DEFINITIONS)
        scope = patch.object(definitions, 'DEFINITIONS', self.rule_map)
        scope.start()
        self.addCleanup(scope.stop)

    def add_definition(self, **values):
        rule = definitions.MedalRule(**values)
        self.rule_map[rule.code] = rule
        return self.get_definition(rule.code)

    def get_definition(self, code=None, pk=None):
        rule = self.rule_map[code or pk]
        values = {field.name: getattr(rule, field.name) for field in fields(rule)}
        values['thresholds'] = list(rule.thresholds)
        values['depends_on'] = list(rule.depends_on)
        values['scope'] = {
            key: list(value) if isinstance(value, tuple) else value
            for key, value in rule.scope.items()
        }
        return SimpleNamespace(**values)

    def replace_definition(self, rule):
        self.rule_map[rule.code] = definitions.MedalRule(**vars(rule))

    def remove_definition(self, rule):
        self.rule_map.pop(rule.code)
