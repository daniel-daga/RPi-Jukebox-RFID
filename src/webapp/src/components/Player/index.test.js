import React from 'react';
import { act, render, screen, waitFor } from '@testing-library/react';

import AppSettingsContext from '../../context/appsettings/context';
import PlayerContext from '../../context/player/context';
import request from '../../utils/request';
import Player from './index';

jest.mock('../../utils/request', () => jest.fn());

jest.mock('./cover', () => ({ coverImage }) => (
  coverImage ? <img alt="cover" src={coverImage} /> : <span>no cover</span>
));
jest.mock('./controls', () => () => null);
jest.mock('./display', () => () => null);
jest.mock('./seekbar', () => () => null);
jest.mock('./volume', () => () => null);

const renderPlayer = ({
  playerstatus = {},
  showCovers = true,
} = {}) => render(
  <AppSettingsContext.Provider value={{ settings: { show_covers: showCovers } }}>
    <PlayerContext.Provider value={{ state: { playerstatus } }}>
      <Player />
    </PlayerContext.Provider>
  </AppSettingsContext.Provider>
);

const rerenderPlayer = (view, {
  playerstatus = {},
  showCovers = true,
} = {}) => view.rerender(
  <AppSettingsContext.Provider value={{ settings: { show_covers: showCovers } }}>
    <PlayerContext.Provider value={{ state: { playerstatus } }}>
      <Player />
    </PlayerContext.Provider>
  </AppSettingsContext.Provider>
);

beforeEach(() => {
  request.mockReset();
});

test('uses published album art directly without requesting local cover art', () => {
  const albumart = 'https://i.scdn.co/image/spotify-cover';

  renderPlayer({ playerstatus: { albumart, file: 'spotify:track:123' } });

  expect(screen.getByAltText('cover')).toHaveAttribute('src', albumart);
  expect(document.querySelector('#player')).toHaveStyle(
    `background-image: linear-gradient(to bottom, rgba(18, 18, 18, 0.5), rgba(18, 18, 18, 1)),url(${albumart})`
  );
  expect(request).not.toHaveBeenCalled();
});

test('falls back to cached cover art for a local file', async () => {
  request.mockResolvedValue({ result: 'artist/album.jpg' });

  renderPlayer({ playerstatus: { player: 'mpd', file: 'Artist/Album/song.mp3' } });

  expect(request).toHaveBeenCalledWith('getSingleCoverArt', {
    song_url: 'Artist/Album/song.mp3',
  });
  await waitFor(() => expect(screen.getByAltText('cover')).toHaveAttribute(
    'src',
    '/cover-cache/artist/album.jpg'
  ));
});

test('does not request local cover art for a Spotify episode without album art', () => {
  renderPlayer({
    playerstatus: { player: 'spotify', file: 'spotify:episode:x', albumart: '' },
  });

  expect(request).not.toHaveBeenCalled();
  expect(screen.queryByAltText('cover')).not.toBeInTheDocument();
});

test('clears stale cover and background when the next status has no art source', () => {
  const view = renderPlayer({
    playerstatus: { albumart: 'https://example.com/old.jpg' },
  });

  expect(screen.getByAltText('cover')).toBeInTheDocument();

  rerenderPlayer(view, { playerstatus: {} });

  expect(screen.queryByAltText('cover')).not.toBeInTheDocument();
  expect(document.querySelector('#player')).toHaveStyle('background-image: none');
});

test('disabling covers clears current art and skips cover lookups', () => {
  const view = renderPlayer({
    playerstatus: { albumart: 'https://example.com/old.jpg' },
  });

  rerenderPlayer(view, {
    playerstatus: { player: 'mpd', file: 'Artist/Album/song.mp3' },
    showCovers: false,
  });

  expect(screen.queryByAltText('cover')).not.toBeInTheDocument();
  expect(document.querySelector('#player')).toHaveStyle('background-image: none');
  expect(request).not.toHaveBeenCalled();
});

test('ignores a late local-cover response after a newer status publishes album art', async () => {
  let resolveRequest;
  request.mockReturnValue(new Promise((resolve) => {
    resolveRequest = resolve;
  }));
  const view = renderPlayer({
    playerstatus: { player: 'mpd', file: 'Artist/Album/old.mp3' },
  });

  rerenderPlayer(view, {
    playerstatus: { albumart: 'https://example.com/new.jpg' },
  });

  await act(async () => {
    resolveRequest({ result: 'old.jpg' });
  });

  expect(screen.getByAltText('cover')).toHaveAttribute(
    'src',
    'https://example.com/new.jpg'
  );
});
