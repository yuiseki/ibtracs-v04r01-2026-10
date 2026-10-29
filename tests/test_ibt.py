import ibt
import pytest


def test_missing_marker_is_a_single_space():
    assert ibt.is_missing(" ")
    assert ibt.is_missing("")
    assert not ibt.is_missing("0")
    assert not ibt.is_missing("UNNAMED")


@pytest.mark.parametrize(
    ("values", "kind"),
    [
        (["1", "-5", None], "int32"),
        (["10.9", "80", None], "float64"),
        (["0", "007"], "string"),  # a leading zero is an identifier, not a number
        (["1842298N11080", None], "string"),
        (["1842-10-25 03:00:00"], "timestamp"),
        ([None, None], "string"),
        (["1e5"], "string"),  # no exponent form in the file; do not guess
    ],
)
def test_infer_type(values, kind):
    assert ibt.infer_type(values) == kind


def test_padded_value_is_refused():
    with pytest.raises(ValueError):
        ibt.infer_type([" 12", "3"])


def test_units_row_is_paired_with_the_header():
    header = "A,B,C"
    units = " ,kts,mb"
    assert ibt.pair_units(header, units) == {"A": None, "B": "kts", "C": "mb"}
    with pytest.raises(ValueError):
        ibt.pair_units("A,B", "x")
