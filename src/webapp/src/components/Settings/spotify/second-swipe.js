import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import {
  CircularProgress,
  FormControl,
  FormControlLabel,
  Grid,
  Radio,
  RadioGroup,
  Typography,
} from '@mui/material';

import request from '../../../utils/request';

const ACTIONS = ['toggle', 'play', 'skip', 'rewind', 'none'];

const SpotifySecondSwipe = () => {
  const { t } = useTranslation();

  const [action, setAction] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const { result, error } = await request('getSpotifySecondSwipe');
      setIsLoading(false);
      if (!error) setAction(result);
    })();
  }, []);

  const handleChange = async (e) => {
    const newAction = e.target.value;
    setAction(newAction);
    await request('setSpotifySecondSwipe', { action: newAction });
  };

  return (
    <Grid container direction="column">
      <Grid item container direction="row" justifyContent="space-between" alignItems="center">
        <Typography>{t('settings.spotify.secondswipe.title')}</Typography>
        {isLoading && <CircularProgress size={20} />}
      </Grid>
      <Grid item>
        <FormControl component="fieldset" disabled={isLoading}>
          <RadioGroup value={action ?? ''} onChange={handleChange}>
            {ACTIONS.map((a) => (
              <FormControlLabel
                key={a}
                value={a}
                control={<Radio size="small" />}
                label={t(`settings.spotify.secondswipe.${a}`)}
              />
            ))}
          </RadioGroup>
        </FormControl>
      </Grid>
    </Grid>
  );
};

export default SpotifySecondSwipe;
