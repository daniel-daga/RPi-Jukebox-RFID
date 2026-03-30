import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import {
  Card,
  CardContent,
  CardHeader,
  CircularProgress,
  Divider,
  FormControl,
  FormControlLabel,
  Grid,
  Radio,
  RadioGroup,
} from '@mui/material';

import request from '../../utils/request';

const ACTIONS = ['toggle', 'play', 'skip', 'rewind', 'replay', 'replay_if_stopped', 'none'];

const SettingsSecondSwipe = () => {
  const { t } = useTranslation();

  const [action, setAction] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const { result, error } = await request('getMpdSecondSwipe');
      setIsLoading(false);
      if (!error) setAction(result);
    })();
  }, []);

  const handleChange = async (e) => {
    const newAction = e.target.value;
    setAction(newAction);
    await request('setMpdSecondSwipe', { action: newAction });
  };

  return (
    <Card>
      <CardHeader
        title={t('settings.secondswipe.title')}
        subheader={t('settings.secondswipe.description')}
        action={isLoading && <CircularProgress size={20} />}
      />
      <Divider />
      <CardContent>
        <Grid container direction="column">
          <Grid item>
            <FormControl component="fieldset" disabled={isLoading}>
              <RadioGroup value={action ?? ''} onChange={handleChange}>
                {ACTIONS.map((a) => (
                  <FormControlLabel
                    key={a}
                    value={a}
                    control={<Radio size="small" />}
                    label={t(`settings.secondswipe.${a}`)}
                  />
                ))}
              </RadioGroup>
            </FormControl>
          </Grid>
        </Grid>
      </CardContent>
    </Card>
  );
};

export default SettingsSecondSwipe;
