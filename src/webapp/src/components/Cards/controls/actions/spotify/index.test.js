import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';

import request from '../../../../../utils/request';
import SelectSpotify from './index';

jest.mock('../../../../../utils/request', () => jest.fn());
jest.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key, values) => values?.type ? `${key}: ${values.type}` : key,
  }),
}));

const source = {
  uri: 'spotify:playlist:canonical',
  external_url: 'https://open.spotify.com/playlist/canonical',
  type: 'playlist',
  name: 'Morning playlist',
  subtitle: 'Playlist owner',
  image_url: 'https://example.com/cover.jpg',
};

const actionData = (uri = '') => ({
  action: 'spotify',
  command: {
    name: 'play_spotify',
    args: { uri },
  },
});

const finishDebounce = async () => {
  await act(async () => {
    jest.advanceTimersByTime(350);
    await Promise.resolve();
  });
};

beforeEach(() => {
  jest.useFakeTimers();
  request.mockReset();
});

afterEach(() => {
  jest.useRealTimers();
});

test('debounces a pasted share link and stores the resolved canonical URI', async () => {
  request.mockResolvedValue({ result: source });
  const handleActionDataChange = jest.fn();
  const onValidationChange = jest.fn();

  render(
    <SelectSpotify
      actionData={actionData()}
      handleActionDataChange={handleActionDataChange}
      onValidationChange={onValidationChange}
    />
  );

  const input = screen.getByLabelText(
    'cards.controls.actions.spotify.source-label'
  );
  fireEvent.change(input, {
    target: { value: 'https://open.spotify.com/playlist/canonical?si=share' },
  });

  expect(screen.getByText(
    'cards.controls.actions.spotify.loading'
  )).toBeInTheDocument();
  expect(request).not.toHaveBeenCalled();

  await finishDebounce();

  await waitFor(() => expect(screen.getByText('Morning playlist')).toBeInTheDocument());
  expect(request).toHaveBeenCalledWith('resolveSpotifySource', {
    value: 'https://open.spotify.com/playlist/canonical?si=share',
  });
  expect(input).toHaveValue(source.uri);
  expect(handleActionDataChange).toHaveBeenLastCalledWith(
    'spotify',
    'play_spotify',
    { uri: source.uri }
  );
  expect(onValidationChange).toHaveBeenLastCalledWith(true);
  expect(screen.getByText('Playlist owner')).toBeInTheDocument();
  expect(screen.getByRole('link', {
    name: 'cards.controls.actions.spotify.open-in-spotify',
  })).toHaveAttribute('href', source.external_url);
});

test('preserves invalid input, reports invalid, and retries resolution', async () => {
  request
    .mockResolvedValueOnce({ result: { error: 'invalid_source' } })
    .mockResolvedValueOnce({ result: source });
  const onValidationChange = jest.fn();

  render(
    <SelectSpotify
      actionData={actionData()}
      handleActionDataChange={jest.fn()}
      onValidationChange={onValidationChange}
    />
  );

  const input = screen.getByLabelText(
    'cards.controls.actions.spotify.source-label'
  );
  fireEvent.change(input, { target: { value: 'not spotify' } });
  await finishDebounce();

  expect(await screen.findByText(
    'cards.controls.actions.spotify.invalid'
  )).toBeInTheDocument();
  expect(input).toHaveValue('not spotify');
  expect(onValidationChange).toHaveBeenLastCalledWith(false);

  fireEvent.click(screen.getByRole('button', {
    name: 'cards.controls.actions.spotify.retry',
  }));
  await finishDebounce();

  expect(await screen.findByText('Morning playlist')).toBeInTheDocument();
  expect(request).toHaveBeenLastCalledWith('resolveSpotifySource', {
    value: 'not spotify',
  });
});

test('auto-resolves an existing URI and reports playback feedback', async () => {
  request
    .mockResolvedValueOnce({ result: source })
    .mockResolvedValueOnce({ result: undefined });

  render(
    <SelectSpotify
      actionData={actionData(source.uri)}
      handleActionDataChange={jest.fn()}
    />
  );

  await finishDebounce();
  expect(await screen.findByText('Morning playlist')).toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', {
    name: 'cards.controls.actions.spotify.test-playback',
  }));

  expect(await screen.findByText(
    'cards.controls.actions.spotify.playback-success'
  )).toBeInTheDocument();
  expect(request).toHaveBeenLastCalledWith('play_spotify', {
    uri: source.uri,
  });
});

test('ignores a resolver response after the Spotify editor unmounts', async () => {
  let finishResolution;
  request.mockReturnValue(new Promise((resolve) => {
    finishResolution = resolve;
  }));
  const handleActionDataChange = jest.fn();

  const view = render(
    <SelectSpotify
      actionData={actionData(source.uri)}
      handleActionDataChange={handleActionDataChange}
    />
  );

  await finishDebounce();
  expect(request).toHaveBeenCalledWith('resolveSpotifySource', {
    value: source.uri,
  });

  view.unmount();
  await act(async () => {
    finishResolution({ result: source });
    await Promise.resolve();
  });

  expect(handleActionDataChange).not.toHaveBeenCalled();
});
