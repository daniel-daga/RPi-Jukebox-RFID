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
  const { file } = playerstatus || {};
  const isSpotify = playerstatus?.player === 'spotify';
  const spotifyArt = playerstatus?.albumart;

  const [coverImage, setCoverImage] = useState(undefined);
  const [backgroundImage, setBackgroundImage] = useState('none');

  const {
    settings,
  } = useContext(AppSettingsContext);

  const { show_covers } = settings;

  const setArt = (url) => {
    setCoverImage(url);
    setBackgroundImage([
      'linear-gradient(to bottom, rgba(18, 18, 18, 0.5), rgba(18, 18, 18, 1))',
      `url(${url})`
    ].join(','));
  };

  useEffect(() => {
    if (isSpotify) {
      if (spotifyArt) setArt(spotifyArt);
      else { setCoverImage(undefined); setBackgroundImage('none'); }
    } else if (file && show_covers) {
      request('getSingleCoverArt', { song_url: file }).then(({ result }) => {
        if (result) setArt(`/cover-cache/${result}`);
      });
    } else {
      setCoverImage(undefined);
      setBackgroundImage('none');
    }
  }, [file, isSpotify, spotifyArt]); // eslint-disable-line react-hooks/exhaustive-deps

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
