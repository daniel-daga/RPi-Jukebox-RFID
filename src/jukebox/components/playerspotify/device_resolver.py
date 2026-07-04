# -*- coding: utf-8 -*-
"""Spotify Connect device resolution by name

Kept free of jukebox imports so it can be unit tested without the
daemon dependencies (spotipy, zmq, ...).
"""


def resolve_device_id(devices: list, device_name: str):
    """Return the id of the Spotify Connect device matching :attr:`device_name`

    The match is case-insensitive and ignores surrounding whitespace.

    :param devices: device list as returned by the Web API ('devices' array)
    :param device_name: the device name to look for
    :return: the device id, or None if no device matches
    """
    if not device_name:
        return None
    wanted = device_name.strip().casefold()
    for device in devices or []:
        name = (device.get('name') or '').strip().casefold()
        if name == wanted:
            return device.get('id')
    return None
