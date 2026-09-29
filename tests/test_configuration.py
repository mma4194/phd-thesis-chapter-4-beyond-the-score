"""Interpreter path normalization must retain virtual-environment identity."""
import json,tempfile,unittest
from pathlib import Path
from src.configuration import load_config,ROOT
class ConfigurationTests(unittest.TestCase):
    def test_interpreter_symlink_is_not_dereferenced(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);target=root/'system-python';target.write_text('placeholder')
            link=root/'venv-python';link.symlink_to(target)
            c=json.loads((ROOT/'config/example.json').read_text());c.update(public_python=str(link),residential_python=str(link))
            config=root/'config.json';config.write_text(json.dumps(c))
            loaded=load_config(config)
            self.assertEqual(loaded['public_python'],str(link))
            self.assertNotEqual(loaded['public_python'],str(target))
    def test_unknown_configuration_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            c=json.loads((ROOT/'config/example.json').read_text());c['workerz']=4
            p=Path(d)/'config.json';p.write_text(json.dumps(c))
            with self.assertRaises(ValueError):load_config(p)
