import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';

import {
  Box,
  Button,
  IconButton,
  Link,
  Step,
  StepContent,
  StepLabel,
  Stepper,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import CheckIcon from '@mui/icons-material/Check';

import SpotifyCredentials from './credentials';
import SpotifyConnect from './connect';
import { getSuggestedRedirectUri, LOOPBACK_REDIRECT_URI } from './utils';

const DASHBOARD_URL = 'https://developer.spotify.com/dashboard';

// Read-only URI display with a copy-to-clipboard button
const CopyableUri = ({ uri }) => {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(uri);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard unavailable (e.g. non-secure context): the field below is
      // selectable, so manual copying still works
    }
  };

  return (
    <Box display="flex" alignItems="center" gap={1}>
      <TextField
        fullWidth
        size="small"
        value={uri}
        InputProps={{ readOnly: true }}
        onFocus={(e) => e.target.select()}
      />
      <Tooltip title={copied
        ? t('settings.spotify.setup.copied')
        : t('settings.spotify.setup.copy')}>
        <IconButton size="small" onClick={handleCopy}>
          {copied
            ? <CheckIcon fontSize="small" color="success" />
            : <ContentCopyIcon fontSize="small" />}
        </IconButton>
      </Tooltip>
    </Box>
  );
};

// Guided first-time setup: create the Spotify app, enter its credentials,
// authorise the account. Shown until the jukebox is connected to Spotify.
const SpotifySetupWizard = ({ status, onStatusChange }) => {
  const { t } = useTranslation();

  // Credentials already stored → resume at the connect step
  const [activeStep, setActiveStep] = useState(status.configured ? 2 : 0);

  const steps = [
    t('settings.spotify.setup.step-app'),
    t('settings.spotify.setup.step-credentials'),
    t('settings.spotify.setup.step-connect'),
  ];

  return (
    <Box>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {t('settings.spotify.setup.intro')}
      </Typography>
      <Stepper activeStep={activeStep} orientation="vertical">
        <Step>
          <StepLabel>{steps[0]}</StepLabel>
          <StepContent>
            <Typography variant="body2" sx={{ mb: 1 }}>
              {t('settings.spotify.setup.app-instruction-1')}{' '}
              <Link href={DASHBOARD_URL} target="_blank" rel="noopener noreferrer">
                developer.spotify.com/dashboard
              </Link>
            </Typography>
            <Typography variant="body2" sx={{ mb: 1 }}>
              {t('settings.spotify.setup.app-instruction-2')}
            </Typography>
            <CopyableUri uri={getSuggestedRedirectUri()} />
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1, mb: 1 }}>
              {t('settings.spotify.setup.app-loopback-hint')}
            </Typography>
            <CopyableUri uri={LOOPBACK_REDIRECT_URI} />
            <Typography variant="body2" sx={{ mt: 1 }}>
              {t('settings.spotify.setup.app-instruction-3')}
            </Typography>
            <Box sx={{ mt: 2 }}>
              <Button variant="contained" size="small" onClick={() => setActiveStep(1)}>
                {t('settings.spotify.setup.next')}
              </Button>
            </Box>
          </StepContent>
        </Step>

        <Step>
          <StepLabel>{steps[1]}</StepLabel>
          <StepContent>
            <SpotifyCredentials
              onSaved={async () => {
                await onStatusChange();
                setActiveStep(2);
              }}
            />
            <Box sx={{ mt: 1 }}>
              <Button size="small" onClick={() => setActiveStep(0)}>
                {t('settings.spotify.setup.back')}
              </Button>
            </Box>
          </StepContent>
        </Step>

        <Step>
          <StepLabel>{steps[2]}</StepLabel>
          <StepContent>
            <SpotifyConnect status={status} onRefreshStatus={onStatusChange} />
            <Box sx={{ mt: 1 }}>
              <Button size="small" onClick={() => setActiveStep(1)}>
                {t('settings.spotify.setup.back')}
              </Button>
            </Box>
          </StepContent>
        </Step>
      </Stepper>
    </Box>
  );
};

export default SpotifySetupWizard;
