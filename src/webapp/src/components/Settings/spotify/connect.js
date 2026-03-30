import React, { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import {
  Box,
  Button,
  CircularProgress,
  Grid,
  Link,
  Typography,
} from '@mui/material';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';

import request from '../../../utils/request';

const POLL_INTERVAL_MS = 3000;

const SpotifyConnect = () => {
  const { t } = useTranslation();

  const [status, setStatus] = useState(null);   // null = loading
  const [authUrl, setAuthUrl] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  const fetchStatus = useCallback(async () => {
    const { result, error } = await request('getSpotifyAuthStatus');
    if (!error) setStatus(result);
  }, []);

  // Initial fetch
  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  // Poll while auth is in progress
  useEffect(() => {
    if (!status?.auth_in_progress) return;
    const id = setInterval(fetchStatus, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [status?.auth_in_progress, fetchStatus]);

  const handleConnect = async () => {
    setIsLoading(true);
    const { result, error } = await request('getSpotifyAuthUrl');
    setIsLoading(false);
    if (!error && result) {
      setAuthUrl(result);
      window.open(result, '_blank', 'noopener,noreferrer');
      await fetchStatus();
    }
  };

  const handleDisconnect = async () => {
    setIsLoading(true);
    await request('disconnectSpotify');
    setAuthUrl(null);
    await fetchStatus();
    setIsLoading(false);
  };

  if (status === null) {
    return <CircularProgress size={20} />;
  }

  const { authenticated, auth_in_progress, configured, user } = status;

  if (!configured) {
    return (
      <Typography variant="body2" color="text.secondary">
        {t('settings.spotify.connect.not-configured')}
      </Typography>
    );
  }

  return (
    <Grid container direction="column" spacing={1}>
      <Grid item>
        <Box display="flex" alignItems="center" gap={1}>
          {authenticated
            ? <CheckCircleOutlineIcon color="success" />
            : <ErrorOutlineIcon color="warning" />}
          <Typography>
            {authenticated
              ? t('settings.spotify.connect.connected-as', { user })
              : t('settings.spotify.connect.not-connected')}
          </Typography>
        </Box>
      </Grid>

      {auth_in_progress && !authenticated && (
        <Grid item>
          <Box display="flex" alignItems="center" gap={1}>
            <CircularProgress size={16} />
            <Typography variant="body2" color="text.secondary">
              {t('settings.spotify.connect.waiting')}
            </Typography>
          </Box>
          {authUrl && (
            <Typography variant="body2" sx={{ mt: 1 }}>
              {t('settings.spotify.connect.open-link')}{' '}
              <Link href={authUrl} target="_blank" rel="noopener noreferrer">
                {t('settings.spotify.connect.auth-link')}
              </Link>
            </Typography>
          )}
        </Grid>
      )}

      <Grid item>
        {authenticated ? (
          <Button
            variant="outlined"
            color="warning"
            size="small"
            onClick={handleDisconnect}
            disabled={isLoading}
          >
            {t('settings.spotify.connect.disconnect')}
          </Button>
        ) : (
          <Button
            variant="contained"
            size="small"
            onClick={handleConnect}
            disabled={isLoading || auth_in_progress}
            startIcon={isLoading ? <CircularProgress size={16} /> : null}
          >
            {t('settings.spotify.connect.connect')}
          </Button>
        )}
      </Grid>
    </Grid>
  );
};

export default SpotifyConnect;
