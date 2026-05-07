import React, { useContext, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import PlayerContext from '../../context/player/context';
import {
  progressToTime,
  timeToProgress,
  toHHMMSS,
} from '../../utils/utils';

import Grid from '@mui/material/Grid';
import Slider from '@mui/material/Slider';
import Typography from '@mui/material/Typography';

import request from '../../utils/request';

const SeekBar = () => {
  const { t } = useTranslation();
  const { state } = useContext(PlayerContext);
  const { playerstatus } = state;
  const isSpotify = playerstatus?.player === 'spotify';

  const [isSeeking, setIsSeeking] = useState(false);
  const [timeElapsed, setTimeElapsed] = useState(0);
  const timeTotal = parseFloat(playerstatus?.duration) || 0;
  const progress = timeToProgress(timeTotal, timeElapsed);

  const handleSeekToPosition = (event, newPosition) => {
    setIsSeeking(true);
    setTimeElapsed(progressToTime(timeTotal, newPosition));
  };

  const playFromNewTime = () => {
    if (!isSpotify) request('seek', { new_time: timeElapsed.toFixed(3) });
    setIsSeeking(false);
  };

  // Sync elapsed from playerstatus on every update (MPD provides it; Spotify provides correction)
  useEffect(() => {
    if (!isSeeking) {
      setTimeElapsed(parseFloat(playerstatus?.elapsed) || 0);
    }
  }, [playerstatus]); // eslint-disable-line react-hooks/exhaustive-deps

  // Spotify: advance elapsed by 1s each second while playing (go-librespot has no position field)
  useEffect(() => {
    if (!isSpotify || playerstatus?.state !== 'play') return;
    const timer = setInterval(() => {
      setTimeElapsed(prev => {
        const next = prev + 1;
        return timeTotal > 0 ? Math.min(next, timeTotal) : next;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [isSpotify, playerstatus?.state, timeTotal]); // eslint-disable-line react-hooks/exhaustive-deps

  return <>
    <Grid container>
      <Grid item xs>
        <Slider
          aria-labelledby={t('player.seekbar.song-position')}
          disabled={!playerstatus?.title || isSpotify}
          onChange={handleSeekToPosition}
          onChangeCommitted={playFromNewTime}
          size="small"
          value={progress || 0}
        />
      </Grid>
    </Grid>
    <Grid
      alignItems="center"
      container
      direction="row"
      justifyContent="space-between"
      sx={ {
        marginTop: '-10px',
      }}
    >
      <Grid item>
        <Typography color="textSecondary">
          {toHHMMSS(parseInt(timeElapsed))}
        </Typography>
      </Grid>
      <Grid item>
        <Typography color="textSecondary">
          {toHHMMSS(parseInt(timeTotal))}
        </Typography>
      </Grid>
    </Grid>
  </>;
};

export default SeekBar;
