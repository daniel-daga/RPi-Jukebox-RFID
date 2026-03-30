import React from 'react';
import { useTranslation } from 'react-i18next';

import { useTheme } from '@mui/material/styles';
import {
  Card,
  CardContent,
  CardHeader,
  Divider,
  Grid,
} from '@mui/material';

import SpotifyCredentials from './credentials';
import SpotifyConnect from './connect';
import SpotifyDeviceSelect from './device-select';
import SpotifySecondSwipe from './second-swipe';

const SettingsSpotify = () => {
  const { t } = useTranslation();
  const theme = useTheme();
  const spacer = { marginBottom: theme.spacing(3) };

  return (
    <Card>
      <CardHeader title={t('settings.spotify.title')} />
      <Divider />
      <CardContent>
        <Grid
          container
          direction="column"
          sx={{ '& > .MuiGrid-root:not(:last-child)': spacer }}
        >
          <Grid item>
            <SpotifyCredentials />
          </Grid>
          <Grid item>
            <Divider />
          </Grid>
          <Grid item>
            <SpotifyConnect />
          </Grid>
          <Grid item>
            <Divider />
          </Grid>
          <Grid item>
            <SpotifyDeviceSelect />
          </Grid>
          <Grid item>
            <Divider />
          </Grid>
          <Grid item>
            <SpotifySecondSwipe />
          </Grid>
        </Grid>
      </CardContent>
    </Card>
  );
};

export default SettingsSpotify;
