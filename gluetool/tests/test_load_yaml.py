import re

import pytest
import attrs
import cattrs

import gluetool
from gluetool import GlueError
from gluetool.log import format_dict
from gluetool.utils import load_yaml, from_yaml, create_cattrs_unserializer

from typing import List

from . import create_yaml


@attrs.define
class Bar:
    nested_a: str
    nested_b: List[int]

@attrs.define
class Foo:
    aaa: int
    bbb: Bar


def test_missing_file(tmpdir):
    filepath = '{}.foo'.format(str(tmpdir.join('not-found.yml')))

    with pytest.raises(GlueError, match=r"File '{}' does not exist".format(re.escape(filepath))):
        load_yaml(filepath)


def test_sanity(log, tmpdir):
    data = {
        'some-key': [
            1, 2, 3, 5, 7
        ],
        'some-other-key': {
            'yet-another-key': [
                9, 11, 13
            ]
        }
    }

    filepath = str(create_yaml(tmpdir, 'sanity', data))

    loaded = load_yaml(filepath)

    assert data == loaded
    assert log.records[-1].message == "loaded YAML data from '{}':\n{}".format(filepath, format_dict(data))


def test_invalid_path():
    with pytest.raises(GlueError, match=r'File path is not valid: None'):
        load_yaml(None)

    with pytest.raises(GlueError, match=r'File path is not valid: \[\]'):
        load_yaml([])


def test_bad_yaml(tmpdir):
    f = tmpdir.join('test.yml')
    f.write('{')

    filepath = str(f)

    with pytest.raises(GlueError,
                       match=r"(?ms)Unable to load YAML file '{}': .*? line 1, column 2".format(re.escape(filepath))):
        load_yaml(filepath)


def test_import_variables(tmpdir, logger):
    g = tmpdir.join('vars.yaml')
    g.write("""---

FOO: bar
""")

    f = tmpdir.join('test.yml')
    f.write("""---

# !import-variables {}

- dummy: "{{{{ FOO }}}}"
""".format(str(g)))


    mapping = gluetool.utils.PatternMap(str(f), logger=logger, allow_variables=True)
    assert mapping.match('dummy') == 'bar'


def test_cattrs_unserializer(tmpdir):
    f = tmpdir.join('test.yml')
    f.write("""---
aaa: 123
bbb:
  nested_a: hello
  nested_b:
    - 1
    - 2
    - 3
""")
    structure = load_yaml(str(f), unserializer=create_cattrs_unserializer(Foo))
    assert structure.aaa == 123
    assert structure.bbb.nested_a == 'hello'
    assert structure.bbb.nested_b == [1, 2, 3]


def test_cattrs_unserializer_converters(tmpdir):
    yaml = """---
aaa: '123'
bbb:
  nested_a: 1
  nested_b:
    - 1.0
    - '2'
    - True"""
    f = tmpdir.join('test.yml')
    f.write(yaml)
    # Use our gluetool Converter
    structure1 = load_yaml(str(f), unserializer=create_cattrs_unserializer(Foo))
    # Use default cattrs Converter
    structure2 = load_yaml(str(f), unserializer=create_cattrs_unserializer(Foo, converter=cattrs.global_converter))

    assert structure1 == from_yaml(yaml, unserializer=create_cattrs_unserializer(Foo))
    assert structure2 == from_yaml(
        yaml,
        unserializer=create_cattrs_unserializer(Foo, converter=cattrs.global_converter)
    )

    # Gluetool Converter keeps the data types as they are in the source yaml file, possibly violating type annotations
    assert structure1.aaa == '123'
    assert structure1.bbb.nested_a == 1
    assert structure1.bbb.nested_b == [1.0, '2', True]
    assert isinstance(structure1.bbb.nested_b[0], float)

    # Default cattrs converter forces conversion of primitive data types when structuring
    assert structure2.aaa == 123
    assert structure2.bbb.nested_a == '1'
    assert structure2.bbb.nested_b == [1, 2, 1]
    assert isinstance(structure2.bbb.nested_b[0], int)
