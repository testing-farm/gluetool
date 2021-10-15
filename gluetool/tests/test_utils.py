import string

import pytest
from hypothesis import given, strategies as st

import gluetool


# generate lists of dictionaries with mixture of keys values selected from random strings and integers
@given(dicts=st.lists(st.dictionaries(st.integers() | st.text(string.printable),
                                      st.integers() | st.text(string.printable))))
def test_dict_update(dicts):
    merged = {}
    for d in dicts:
        merged.update(d)
    assert merged == gluetool.utils.dict_update({}, *dicts)


def test_regex_replace():
    # By default, '^' matches only at the beginning of the string. When re.MULTILINE is used, '^'
    # matches at the beginning of the string and at the beginning of each line
    # https://docs.python.org/3/library/re.html#re.MULTILINE

    # Try to replace a mis-matching case string without ignorecase.
    original = 'Lorem ipsum dolor sit amet, consectetur adipiscing elit, \nloop do eiusmod tempor incididunt ut labore et dolore magna aliqua.'
    find = " ALIQUA."
    replace = " nulla."
    mod = gluetool.utils.regex_replace(original, find, replace)
    assert mod == original
    # Replace a mis-matching case string using ignorecase.
    mod = gluetool.utils.regex_replace(original, find, replace, True)
    assert mod == "Lorem ipsum dolor sit amet, consectetur adipiscing elit, \nloop do eiusmod tempor incididunt ut labore et dolore magna nulla."
    # Use ignorecase not multiline.
    mod = gluetool.utils.regex_replace(original, "^LO", "XX", True, False)
    assert mod == "XXrem ipsum dolor sit amet, consectetur adipiscing elit, \nloop do eiusmod tempor incididunt ut labore et dolore magna aliqua."
    # Use ignorecase and multiline.
    mod = gluetool.utils.regex_replace(original, "^LO", "XX", True, True)
    assert mod == "XXrem ipsum dolor sit amet, consectetur adipiscing elit, \nXXop do eiusmod tempor incididunt ut labore et dolore magna aliqua."
    # Use multiline not ignorecase.
    mod = gluetool.utils.regex_replace(original, "^lo", "XX", False, True)
    assert mod == "Lorem ipsum dolor sit amet, consectetur adipiscing elit, \nXXop do eiusmod tempor incididunt ut labore et dolore magna aliqua."
    # Check that all instances are replaced when not using '^' or '$'
    mod = gluetool.utils.regex_replace(original, "et", "XX")
    assert mod == "Lorem ipsum dolor sit amXX, consectXXur adipiscing elit, \nloop do eiusmod tempor incididunt ut labore XX dolore magna aliqua."


def test_regex_escape():
    # Python 3.7 and higher behave differently with regards to escaping regex strings.
    # Since this behaviour is not part of gluetool, we will only do a rudimentary test.
    # '.' is escaped in all Python re versions. So we'll use that as a test.
    assert gluetool.utils.regex_escape("www.redhat.com") == r"www\.redhat\.com"
