import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import {
  Alert,
  Button,
  CircularProgress,
  Grid,
  InputAdornment,
  TextField,
  Typography,
} from '@mui/material';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';

import request from '../../../utils/request';

const SpotifyCredentials = () => {
  const { t } = useTranslation();

  const [config, setConfig] = useState(null);  // null = loading
  const [pluginMissing, setPluginMissing] = useState(false);
  const [clientId, setClientId] = useState('');
  const [clientSecret, setClientSecret] = useState('');
  const [redirectUri, setRedirectUri] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const load = async () => {
      const { result, error } = await request('getSpotifyConfig');
      if (!error && result) {
        setConfig(result);
        setClientId(result.client_id || '');
        setRedirectUri(result.redirect_uri || '');
      } else {
        setPluginMissing(true);
        setConfig({ client_id: '', has_client_secret: false, redirect_uri: 'http://localhost:8888/callback' });
      }
    };
    load();
  }, []);

  const handleSave = async () => {
    setIsSaving(true);
    setSaved(false);
    await request('setSpotifyConfig', {
      client_id: clientId,
      client_secret: clientSecret,
      redirect_uri: redirectUri,
    });
    // Reload config so has_client_secret reflects the new state
    const { result } = await request('getSpotifyConfig');
    if (result) {
      setConfig(result);
      setClientId(result.client_id || '');
      setRedirectUri(result.redirect_uri || '');
    }
    setClientSecret('');
    setIsSaving(false);
    setSaved(true);
  };

  if (config === null) {
    return <CircularProgress size={20} />;
  }

  return (
    <Grid container direction="column" spacing={2}>
      {pluginMissing && (
        <Grid item>
          <Alert severity="warning">
            {t('settings.spotify.credentials.plugin-missing')}
          </Alert>
        </Grid>
      )}
      <Grid item>
        <Typography variant="subtitle2">
          {t('settings.spotify.credentials.title')}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {t('settings.spotify.credentials.hint')}
        </Typography>
      </Grid>

      <Grid item>
        <TextField
          label={t('settings.spotify.credentials.client-id')}
          value={clientId}
          onChange={(e) => setClientId(e.target.value)}
          size="small"
          fullWidth
        />
      </Grid>

      <Grid item>
        <TextField
          label={t('settings.spotify.credentials.client-secret')}
          value={clientSecret}
          onChange={(e) => setClientSecret(e.target.value)}
          type="password"
          size="small"
          fullWidth
          placeholder={config.has_client_secret
            ? t('settings.spotify.credentials.secret-set')
            : ''}
          InputProps={config.has_client_secret && !clientSecret ? {
            startAdornment: (
              <InputAdornment position="start">
                <CheckCircleOutlineIcon color="success" fontSize="small" />
              </InputAdornment>
            ),
          } : undefined}
          helperText={config.has_client_secret && !clientSecret
            ? t('settings.spotify.credentials.secret-unchanged')
            : ''}
        />
      </Grid>

      <Grid item>
        <TextField
          label={t('settings.spotify.credentials.redirect-uri')}
          value={redirectUri}
          onChange={(e) => setRedirectUri(e.target.value)}
          size="small"
          fullWidth
          helperText={t('settings.spotify.credentials.redirect-uri-hint')}
        />
      </Grid>

      <Grid item>
        <Button
          variant="contained"
          size="small"
          onClick={handleSave}
          disabled={isSaving || !clientId}
        >
          {isSaving
            ? <CircularProgress size={16} />
            : saved
              ? t('settings.spotify.credentials.saved')
              : t('general.buttons.save')}
        </Button>
      </Grid>
    </Grid>
  );
};

export default SpotifyCredentials;
