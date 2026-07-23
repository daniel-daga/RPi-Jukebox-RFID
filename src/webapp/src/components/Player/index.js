import React, { useContext, useEffect, useState } from 'react';

import Grid from '@mui/material/Grid';

import Cover from './cover';
import Controls from './controls';
import Display from './display';
import SeekBar from './seekbar';
import Volume from './volume';

import AppSettingsContext from '../../context/appsettings/context';
import PlayerContext from '../../context/player/context';
import request from '../../utils/request';

const Player = () => {
  const { state: { playerstatus } } = useContext(PlayerContext);
  const { albumart, file, player } = playerstatus || {};

  const [coverImage, setCoverImage] = useState(undefined);
  const [backgroundImage, setBackgroundImage] = useState('none');

  const {
    settings,
  } = useContext(AppSettingsContext);

  const { show_covers } = settings;

  useEffect(() => {
    let cancelled = false;

    const clearCoverArt = () => {
      setCoverImage(undefined);
      setBackgroundImage('none');
    };

    const setCoverArt = (image) => {
      setCoverImage(image);
      setBackgroundImage([
        'linear-gradient(to bottom, rgba(18, 18, 18, 0.5), rgba(18, 18, 18, 1))',
        `url(${image})`
      ].join(','));
    };

    const getCoverArt = async () => {
      const response = await request('getSingleCoverArt', { song_url: file });
      if (cancelled) {
        return;
      }

      if (response?.result) {
        setCoverArt(`/cover-cache/${response.result}`);
      } else {
        clearCoverArt();
      }
    };

    if (!show_covers) {
      clearCoverArt();
    } else if (albumart) {
      setCoverArt(albumart);
    } else if (player === 'mpd' && file) {
      clearCoverArt();
      getCoverArt();
    } else {
      clearCoverArt();
    }

    return () => {
      cancelled = true;
    };
  }, [albumart, file, player, show_covers]);

  return (
    <Grid
      container
      id="player"
      sx={{
        backgroundImage,
        backgroundPosition: 'center',
      }}
    >
      <Grid
        container
        sx={{
          paddingTop: '30px',
          paddingLeft: '30px',
          paddingRight: '30px',
          minHeight: 'calc(100vh - 64px - 10px)',
          backdropFilter: 'blur(25px)',
        }}
      >
        <Grid item xs={12} sm={5}>
          <Cover coverImage={coverImage} />
        </Grid>
        <Grid item xs={12} sm={7}>
          <Display />
          <SeekBar />
          <Controls />
          <Volume />
        </Grid>
      </Grid>
    </Grid>
  );
};

export default Player;
