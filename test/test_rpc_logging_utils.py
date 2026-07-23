from jukebox.rpc.logging_utils import (
    REDACTED,
    redact_call_arguments,
    redact_request,
)


def test_submit_auth_code_request_is_redacted_without_mutating_input():
    request = {
        'package': 'spotify',
        'plugin': 'ctrl',
        'method': 'submit_auth_code',
        'args': ['one-time-code'],
        'kwargs': {'code_or_url': 'one-time-url'},
        'id': True,
    }

    safe = redact_request(request)

    assert safe['args'] == REDACTED
    assert safe['kwargs'] == REDACTED
    assert request['args'] == ['one-time-code']
    assert request['kwargs'] == {'code_or_url': 'one-time-url'}


def test_submit_auth_code_plugin_arguments_are_redacted():
    args, kwargs = redact_call_arguments(
        'spotify', 'ctrl', 'submit_auth_code',
        ['one-time-code'], {'code_or_url': 'one-time-url'})

    assert args == REDACTED
    assert kwargs == REDACTED


def test_regular_rpc_arguments_remain_visible():
    request = {
        'package': 'player',
        'plugin': 'ctrl',
        'method': 'seek',
        'args': [12],
        'kwargs': {},
    }

    assert redact_request(request) == request
    assert redact_call_arguments(
        'player', 'ctrl', 'seek', [12], {}) == ([12], {})
