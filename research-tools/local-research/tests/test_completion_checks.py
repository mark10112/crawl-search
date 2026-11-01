import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('completion_checks',Path(__file__).resolve().parents[1]/'services/completion_checks.py')
checks=importlib.util.module_from_spec(spec);spec.loader.exec_module(checks)
TEXT='The committee reviewed the public revenue and expenditure accounts.'

class CompletionTests(unittest.TestCase):
    def test_normal_completion_is_not_rejected(self):
        self.assertEqual(checks.completion_flags(TEXT,[{'finish_reason':'stop'}]),[])
    def test_token_limit_and_missing_reason_fail(self):
        for calls in [[],[{'finish_reason':'length'}],[{}]]:
            self.assertIn('Recognition did not explicitly finish normally',checks.completion_flags(TEXT,calls))
    def test_repetition_and_unclosed_table_fail(self):
        self.assertIn('Excessive repeated text',checks.completion_flags('abcdef '*30,[{'finish_reason':'stop'}]))
        self.assertIn('Unclosed table',checks.completion_flags('<TABLE><tr><td>'+TEXT,[{'finish_reason':'stop'}]))
