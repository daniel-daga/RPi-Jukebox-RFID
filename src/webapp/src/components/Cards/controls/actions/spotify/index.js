import React, { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import {
  Box,
  Button,
  CircularProgress,
  Grid,
  TextField,
  Typography,
} from '@mui/material';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import RefreshIcon from '@mui/icons-material/Refresh';

import request from '../../../../../utils/request';
import { getActionAndCommand, getArgsValues } from '../../../utils';

const RESOLVE_DEBOUNCE_MS = 350;

const ERROR_TRANSLATIONS = {
  invalid_source: 'invalid',
  authentication_unavailable: 'authentication-unavailable',
  authentication_disconnected: 'authentication-disconnected',
  not_found: 'not-found',
  spotify_unavailable: 'transient-unavailable',
};

const SelectSpotify = ({
  actionData,
  handleActionDataChange,
  onValidationChange,
}) => {
  const { t } = useTranslation();
  const { action } = getActionAndCommand(actionData);
  const [storedUri = ''] = getArgsValues(actionData);

  const [inputValue, setInputValue] = useState(storedUri || '');
  const [resolutionState, setResolutionState] = useState('idle');
  const [resolvedSource, setResolvedSource] = useState(null);
  const [resolutionError, setResolutionError] = useState(null);
  const [retryCount, setRetryCount] = useState(0);
  const [playbackState, setPlaybackState] = useState('idle');
  const resolutionSequence = useRef(0);

  // Keep the editor in sync when a different card is loaded into this control.
  useEffect(() => {
    setInputValue(storedUri || '');
  }, [storedUri]);

  useEffect(() => {
    if (onValidationChange) {
      onValidationChange(resolutionState === 'resolved');
    }
  }, [onValidationChange, resolutionState]);

  useEffect(() => {
    const value = inputValue.trim();
    const sequence = ++resolutionSequence.current;

    if (!value) {
      setResolutionState('idle');
      setResolvedSource(null);
      setResolutionError(null);
      return undefined;
    }

    // Canonicalising a pasted share URL updates the field. The canonical URI
    // has already been resolved, so it must not cause a second request.
    if (resolvedSource?.uri === value && resolutionState === 'resolved') {
      return undefined;
    }

    setResolutionState('loading');
    setResolvedSource(null);
    setResolutionError(null);

    const timeout = setTimeout(async () => {
      try {
        const { result, error } = await request('resolveSpotifySource', { value });
        if (sequence !== resolutionSequence.current) return;

        const errorCode = error ? 'spotify_unavailable' : result?.error;
        if (errorCode || !result?.uri) {
          setResolutionError(errorCode || 'spotify_unavailable');
          setResolutionState('error');
          return;
        }

        setResolvedSource(result);
        setResolutionState('resolved');
        setInputValue(result.uri);
        handleActionDataChange(action, 'play_spotify', { uri: result.uri });
      } catch {
        if (sequence !== resolutionSequence.current) return;
        setResolutionError('spotify_unavailable');
        setResolutionState('error');
      }
    }, RESOLVE_DEBOUNCE_MS);

    return () => {
      clearTimeout(timeout);
      if (resolutionSequence.current === sequence) {
        resolutionSequence.current += 1;
      }
    };
    // retryCount deliberately re-runs resolution without changing the input.
    // resolvedSource/state are inspected only to prevent canonical re-resolution.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [action, handleActionDataChange, inputValue, retryCount]);

  const handleChange = (event) => {
    const value = event.target.value;
    setInputValue(value);
    setResolutionState(value.trim() ? 'loading' : 'idle');
    setResolvedSource(null);
    setResolutionError(null);
    setPlaybackState('idle');
    handleActionDataChange(action, 'play_spotify', { uri: value });
  };

  const retryResolution = () => {
    setPlaybackState('idle');
    setRetryCount((count) => count + 1);
  };

  const testPlayback = async () => {
    if (!resolvedSource?.uri) return;

    setPlaybackState('loading');
    try {
      const { result, error } = await request('play_spotify', {
        uri: resolvedSource.uri,
      });
      setPlaybackState(error || result?.error ? 'error' : 'success');
    } catch {
      setPlaybackState('error');
    }
  };

  const errorTranslation = ERROR_TRANSLATIONS[resolutionError]
    || 'transient-unavailable';

  return (
    <Grid container direction="column" spacing={1}>
      <Grid item>
        <TextField
          fullWidth
          size="small"
          label={t('cards.controls.actions.spotify.source-label')}
          placeholder="https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"
          value={inputValue}
          onChange={handleChange}
          error={resolutionState === 'error'}
          helperText={t('cards.controls.actions.spotify.source-hint')}
        />
      </Grid>

      {resolutionState === 'loading' && (
        <Grid item>
          <Box display="flex" alignItems="center" gap={1}>
            <CircularProgress size={18} />
            <Typography variant="body2" color="text.secondary">
              {t('cards.controls.actions.spotify.loading')}
            </Typography>
          </Box>
        </Grid>
      )}

      {resolutionState === 'error' && (
        <Grid item>
          <Box display="flex" alignItems="center" gap={1} flexWrap="wrap">
            <Typography variant="body2" color="error">
              {t(`cards.controls.actions.spotify.${errorTranslation}`)}
            </Typography>
            <Button
              size="small"
              startIcon={<RefreshIcon />}
              onClick={retryResolution}
            >
              {t('cards.controls.actions.spotify.retry')}
            </Button>
          </Box>
        </Grid>
      )}

      {resolutionState === 'resolved' && resolvedSource && (
        <Grid item>
          <Box
            aria-label={t('cards.controls.actions.spotify.preview-label')}
            display="flex"
            gap={2}
            sx={{
              border: 1,
              borderColor: 'divider',
              borderRadius: 1,
              p: 1.5,
            }}
          >
            {resolvedSource.image_url ? (
              <Box
                component="img"
                src={resolvedSource.image_url}
                alt={t('cards.controls.actions.spotify.preview-image-alt', {
                  name: resolvedSource.name,
                })}
                sx={{
                  borderRadius: 1,
                  height: 80,
                  objectFit: 'cover',
                  width: 80,
                }}
              />
            ) : (
              <Box
                alignItems="center"
                bgcolor="action.hover"
                borderRadius={1}
                color="text.secondary"
                display="flex"
                flexShrink={0}
                height={80}
                justifyContent="center"
                textAlign="center"
                width={80}
              >
                <Typography variant="caption">
                  {t('cards.controls.actions.spotify.preview-image-unavailable')}
                </Typography>
              </Box>
            )}
            <Box minWidth={0}>
              <Typography variant="caption" color="text.secondary">
                {t('cards.controls.actions.spotify.source-type', {
                  type: resolvedSource.type,
                })}
              </Typography>
              <Typography variant="subtitle1">
                {resolvedSource.name}
              </Typography>
              {resolvedSource.subtitle && (
                <Typography variant="body2" color="text.secondary">
                  {resolvedSource.subtitle}
                </Typography>
              )}
              <Box display="flex" gap={1} flexWrap="wrap" mt={1}>
                <Button
                  component="a"
                  href={resolvedSource.external_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  size="small"
                  startIcon={<OpenInNewIcon />}
                >
                  {t('cards.controls.actions.spotify.open-in-spotify')}
                </Button>
                <Button
                  size="small"
                  onClick={testPlayback}
                  disabled={playbackState === 'loading'}
                  startIcon={playbackState === 'loading'
                    ? <CircularProgress size={16} />
                    : <PlayArrowIcon />}
                >
                  {playbackState === 'loading'
                    ? t('cards.controls.actions.spotify.playback-testing')
                    : t('cards.controls.actions.spotify.test-playback')}
                </Button>
              </Box>
              {playbackState === 'success' && (
                <Typography variant="body2" color="success.main">
                  {t('cards.controls.actions.spotify.playback-success')}
                </Typography>
              )}
              {playbackState === 'error' && (
                <Typography variant="body2" color="error">
                  {t('cards.controls.actions.spotify.playback-error')}
                </Typography>
              )}
            </Box>
          </Box>
        </Grid>
      )}
    </Grid>
  );
};

export default SelectSpotify;
