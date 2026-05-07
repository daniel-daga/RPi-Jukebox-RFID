import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import {
  Box,
  CircularProgress,
  Grid,
  Typography,
} from '@mui/material';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';

import request from '../../../utils/request';

const SpotifyStatus = () => {
  const { t } = useTranslation();
  const [status, setStatus] = useState(null);

  useEffect(() => {
    request('getSpotifyAuthStatus').then(({ result }) => {
      if (result) setStatus(result);
    });
  }, []);

  if (status === null) return <CircularProgress size={20} />;

  return (
    <Grid container direction="column" spacing={1}>
      <Grid item>
        <Box display="flex" alignItems="center" gap={1}>
          {status.authenticated
            ? <CheckCircleOutlineIcon color="success" />
            : <ErrorOutlineIcon color="warning" />}
          <Typography>
            {status.authenticated
              ? t('settings.spotify.status.connected-as', { user: status.username, device: status.device_name })
              : t('settings.spotify.status.not-connected')}
          </Typography>
        </Box>
      </Grid>
      {!status.authenticated && (
        <Grid item>
          <Typography variant="body2" color="text.secondary">
            {t('settings.spotify.status.reauth-hint')}
          </Typography>
        </Grid>
      )}
    </Grid>
  );
};

export default SpotifyStatus;
