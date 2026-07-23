import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import ActionsControls from './actions-controls';

jest.mock('../../../utils/request', () => jest.fn());
jest.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key) => key }),
}));

const renderControls = (saveDisabled) => render(
  <MemoryRouter>
    <ActionsControls
      actionData={{
        action: 'spotify',
        command: {
          name: 'play_spotify',
          args: { uri: 'spotify:track:11dFghVXANMlKmJXsNCbNl' },
        },
      }}
      cardId="1234"
      saveDisabled={saveDisabled}
    />
  </MemoryRouter>
);

test('disables Save while the selected Spotify source is unresolved', () => {
  renderControls(true);

  expect(screen.getByRole('button', {
    name: 'general.buttons.save',
  })).toBeDisabled();
});

test('enables Save after the selected Spotify source resolves', () => {
  renderControls(false);

  expect(screen.getByRole('button', {
    name: 'general.buttons.save',
  })).toBeEnabled();
});
