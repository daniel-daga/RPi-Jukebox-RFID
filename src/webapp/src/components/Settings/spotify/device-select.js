import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import {
  Button,
  CircularProgress,
  FormControl,
  Grid,
  InputLabel,
  MenuItem,
  Select,
  Typography,
} from '@mui/material';

import request from '../../../utils/request';

const SpotifyDeviceSelect = () => {
  const { t } = useTranslation();

  const [devices, setDevices] = useState([]);
  const [selected, setSelected] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isError, setIsError] = useState(false);

  const fetchDevices = async () => {
    setIsLoading(true);
    setIsError(false);
    const { result, error } = await request('getSpotifyDevices');
    setIsLoading(false);
    if (error) { setIsError(true); return; }
    setDevices(result || []);
  };

  useEffect(() => { fetchDevices(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSave = async () => {
    setIsSaving(true);
    await request('setSpotifyDevice', { device_id: selected || null });
    setIsSaving(false);
  };

  return (
    <Grid container direction="column" spacing={1}>
      <Grid item>
        <Grid container direction="row" justifyContent="space-between" alignItems="center">
          <Typography>{t('settings.spotify.device.title')}</Typography>
          <Button size="small" onClick={fetchDevices} disabled={isLoading}>
            {t('settings.spotify.device.refresh')}
          </Button>
        </Grid>
      </Grid>

      {isLoading && (
        <Grid item><CircularProgress size={20} /></Grid>
      )}

      {isError && (
        <Grid item>
          <Typography variant="body2" color="error">
            {t('settings.spotify.device.error')}
          </Typography>
        </Grid>
      )}

      {!isLoading && !isError && (
        <>
          <Grid item>
            <Typography variant="body2" color="text.secondary">
              {t('settings.spotify.device.hint')}
            </Typography>
          </Grid>
          <Grid item container direction="row" spacing={1} alignItems="center">
            <Grid item xs>
              <FormControl fullWidth size="small">
                <InputLabel>{t('settings.spotify.device.label')}</InputLabel>
                <Select
                  value={selected}
                  label={t('settings.spotify.device.label')}
                  onChange={(e) => setSelected(e.target.value)}
                >
                  <MenuItem value="">
                    <em>{t('settings.spotify.device.active-device')}</em>
                  </MenuItem>
                  {devices.map((d) => (
                    <MenuItem key={d.id} value={d.id}>
                      {d.name} ({d.type})
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item>
              <Button
                variant="contained"
                size="small"
                onClick={handleSave}
                disabled={isSaving}
              >
                {isSaving
                  ? <CircularProgress size={16} />
                  : t('general.buttons.save')}
              </Button>
            </Grid>
          </Grid>
        </>
      )}
    </Grid>
  );
};

export default SpotifyDeviceSelect;
