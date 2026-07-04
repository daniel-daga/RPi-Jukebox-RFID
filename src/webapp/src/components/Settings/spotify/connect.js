import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';

import {
  Box,
  Button,
  CircularProgress,
  Grid,
  Link,
  TextField,
  Typography,
} from '@mui/material';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';

import request from '../../../utils/request';

// Auth status is owned by the parent (Settings/spotify/index.js), which also
// polls while authorisation is pending. This component renders the state and
// triggers the connect / disconnect / manual-code actions.
const SpotifyConnect = ({ status, onRefreshStatus }) => {
  const { t } = useTranslation();

  const [authUrl, setAuthUrl] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [manualCode, setManualCode] = useState('');
  const [manualError, setManualError] = useState(false);
  const [isSubmittingCode, setIsSubmittingCode] = useState(false);

  const handleConnect = async () => {
    setIsLoading(true);
    const { result, error } = await request('getSpotifyAuthUrl');
    setIsLoading(false);
    if (!error && result) {
      setAuthUrl(result);
      window.open(result, '_blank', 'noopener,noreferrer');
      await onRefreshStatus();
    }
  };

  const handleDisconnect = async () => {
    setIsLoading(true);
    await request('disconnectSpotify');
    setAuthUrl(null);
    await onRefreshStatus();
    setIsLoading(false);
  };

  const handleSubmitCode = async () => {
    setIsSubmittingCode(true);
    setManualError(false);
    const { result, error } = await request('submitSpotifyAuthCode', {
      code_or_url: manualCode,
    });
    setIsSubmittingCode(false);
    if (!error && result?.success) {
      setManualCode('');
      await onRefreshStatus();
    } else {
      setManualError(true);
    }
  };

  if (!status) {
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
            disabled={isLoading}
            startIcon={isLoading ? <CircularProgress size={16} /> : null}
          >
            {t('settings.spotify.connect.connect')}
          </Button>
        )}
      </Grid>

      {/* Fallback: paste the redirect URL when Spotify's redirect cannot
          reach the jukebox (e.g. loopback redirect URI) */}
      {!authenticated && (auth_in_progress || authUrl) && (
        <Grid item>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            {t('settings.spotify.connect.manual-hint')}
          </Typography>
          <Grid container direction="row" spacing={1} alignItems="center" sx={{ mt: 0 }}>
            <Grid item xs>
              <TextField
                fullWidth
                size="small"
                label={t('settings.spotify.connect.manual-label')}
                placeholder="http://127.0.0.1:8888/callback?code=..."
                value={manualCode}
                onChange={(e) => { setManualCode(e.target.value); setManualError(false); }}
                error={manualError}
                helperText={manualError
                  ? t('settings.spotify.connect.manual-error')
                  : ''}
              />
            </Grid>
            <Grid item>
              <Button
                variant="outlined"
                size="small"
                onClick={handleSubmitCode}
                disabled={isSubmittingCode || !manualCode.trim()}
              >
                {isSubmittingCode
                  ? <CircularProgress size={16} />
                  : t('settings.spotify.connect.manual-submit')}
              </Button>
            </Grid>
          </Grid>
        </Grid>
      )}
    </Grid>
  );
};

export default SpotifyConnect;
