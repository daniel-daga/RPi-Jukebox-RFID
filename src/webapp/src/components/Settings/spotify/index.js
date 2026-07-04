import React, { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { useTheme } from '@mui/material/styles';
import {
  Card,
  CardContent,
  CardHeader,
  CircularProgress,
  Divider,
  Grid,
  Typography,
} from '@mui/material';

import request from '../../../utils/request';
import SpotifyConnect from './connect';
import SpotifyDeviceSelect from './device-select';
import SpotifySecondSwipe from './second-swipe';
import SpotifySetupWizard from './wizard';

const POLL_INTERVAL_MS = 3000;

const SettingsSpotify = () => {
  const { t } = useTranslation();
  const theme = useTheme();
  const spacer = { marginBottom: theme.spacing(3) };

  const [status, setStatus] = useState(null);           // null = loading
  const [unavailable, setUnavailable] = useState(false); // plugin not loaded

  const fetchStatus = useCallback(async () => {
    const { result, error } = await request('getSpotifyAuthStatus');
    if (error) {
      setUnavailable(true);
      return;
    }
    setUnavailable(false);
    setStatus(result);
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  // Poll while authorisation is pending so the view flips to 'connected'
  // as soon as the user approves in the Spotify tab
  const authPending = !!status && !status.authenticated && status.auth_in_progress;
  useEffect(() => {
    if (!authPending) return;
    const id = setInterval(fetchStatus, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [authPending, fetchStatus]);

  return (
    <Card>
      <CardHeader title={t('settings.spotify.title')} />
      <Divider />
      <CardContent>
        {unavailable && (
          <Typography variant="body2" color="text.secondary">
            {t('settings.spotify.unavailable')}
          </Typography>
        )}

        {!unavailable && status === null && (
          <CircularProgress size={20} />
        )}

        {!unavailable && status !== null && !status.authenticated && (
          <SpotifySetupWizard status={status} onStatusChange={fetchStatus} />
        )}

        {!unavailable && status !== null && status.authenticated && (
          <Grid
            container
            direction="column"
            sx={{ '& > .MuiGrid-root:not(:last-child)': spacer }}
          >
            <Grid item>
              <SpotifyConnect status={status} onRefreshStatus={fetchStatus} />
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
        )}
      </CardContent>
    </Card>
  );
};

export default SettingsSpotify;
