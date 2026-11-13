"""The fraudpulse-gen command: options are checked, and output is clean JSON lines."""

import json

import pytest

from fraudpulse_generator.cli import _parse_args, main


def test_rate_and_duration_are_parsed_as_numbers():
    # Regression test: a missing `return` once turned --rate and --duration into None.
    args = _parse_args(["run", "--rate", "5", "--duration", "10"])
    assert args.rate == 5.0
    assert args.duration == 10.0


@pytest.mark.parametrize(
    "bad_args",
    [
        ["--rate", "inf"],
        ["--rate", "nan"],
        ["--rate", "0"],
        ["--duration", "-1"],
        ["--fraud-rate", "0.9"],
        ["--users", "abc"],
        ["--count", "-5", "--fast"],
        ["--sink", "postgres"],
        ["--fast"],  # would never stop
    ],
)
def test_bad_options_exit_with_code_2(bad_args):
    with pytest.raises(SystemExit) as exit_info:
        _parse_args(["run", *bad_args])
    assert exit_info.value.code == 2


def test_run_writes_one_json_payment_per_line(capsys):
    assert main(["run", "--count", "5", "--fast"]) == 0
    out, err = capsys.readouterr()
    lines = out.splitlines()
    assert len(lines) == 5
    for line in lines:
        assert json.loads(line)["currency"] == "INR"
    assert "sent 5 payments" in err  # the summary goes to stderr, not into the data


def test_too_many_users_is_a_clean_error(capsys):
    assert main(["run", "--users", "200000", "--count", "1", "--fast"]) == 2
    assert "error" in capsys.readouterr().err
