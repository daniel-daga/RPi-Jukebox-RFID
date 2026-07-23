import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';

import {
  Avatar,
  Card,
  CardContent,
  CardHeader,
  Grid,
  Typography
} from '@mui/material';
import BookmarkIcon from '@mui/icons-material/Bookmark';

import Header from '../Header';
import ActionsControls from './controls/actions-controls';
import ControlsSelector from './controls/controls-selector';

const InfoNoCardSwiped = () => {
  const { t } = useTranslation();

  return (
    <Typography>
      {`⚠️ ${t('cards.form.no-card-swiped')}`}
    </Typography>
  );
};

const CardsForm = ({
  title,
  cardId,
  actionData,
  setActionData,
}) => {
  const { t } = useTranslation();
  const [spotifySourceValid, setSpotifySourceValid] = useState(false);
  const saveDisabled = actionData.action === 'spotify' && !spotifySourceValid;

  return (
    <>
      <Header title={title} backLink="/cards" />
      <Grid container>
        <Grid item xs={12}>
          <Card elevation={0}>
            <CardHeader
              avatar={
                <Avatar aria-label={t('cards.form.no-card-swiped')}>
                  <BookmarkIcon />
                </Avatar>
              }
              title={
                cardId
                  ? cardId
                  : t('cards.form.no-card-id')
              }
            />
            <CardContent>
              {cardId &&
                <>
                  <Grid container direction="row" alignItems="center">
                    <ControlsSelector
                      actionData={actionData}
                      setActionData={setActionData}
                      cardId={cardId}
                      onSpotifyValidationChange={setSpotifySourceValid}
                    />
                  </Grid>
                  <ActionsControls
                    actionData={actionData}
                    cardId={cardId}
                    saveDisabled={saveDisabled}
                  />
                </>
              }
              {!cardId && <InfoNoCardSwiped />}
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </>
  );
};



export default CardsForm;
