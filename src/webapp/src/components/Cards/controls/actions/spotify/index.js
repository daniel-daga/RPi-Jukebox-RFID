import React from 'react';
import { useTranslation } from 'react-i18next';

import {
  Grid,
  TextField,
  Typography,
} from '@mui/material';

import { getActionAndCommand, getArgsValues } from '../../../utils';

// Detect the URI type from a spotify: URI string
const getUriType = (uri = '') => {
  const parts = uri.split(':');
  if (parts.length >= 2 && parts[0] === 'spotify') return parts[1];
  return null;
};

const SelectSpotify = ({
  actionData,
  handleActionDataChange,
}) => {
  const { t } = useTranslation();
  const { action } = getActionAndCommand(actionData);
  const [uri = ''] = getArgsValues(actionData);

  const uriType = getUriType(uri);

  const handleChange = (event) => {
    handleActionDataChange(action, 'play_spotify', { uri: event.target.value });
  };

  return (
    <Grid container direction="column" spacing={1}>
      <Grid item>
        <TextField
          fullWidth
          size="small"
          label={t('cards.controls.actions.spotify.uri-label')}
          placeholder="spotify:playlist:37i9dQZF1DXcBWIGoYBM5M"
          value={uri}
          onChange={handleChange}
          helperText={
            uriType
              ? t('cards.controls.actions.spotify.uri-type', { type: uriType })
              : t('cards.controls.actions.spotify.uri-hint')
          }
        />
      </Grid>
      {!uriType && uri.length > 0 && (
        <Grid item>
          <Typography variant="body2" color="error">
            {t('cards.controls.actions.spotify.uri-invalid')}
          </Typography>
        </Grid>
      )}
    </Grid>
  );
};

export default SelectSpotify;
