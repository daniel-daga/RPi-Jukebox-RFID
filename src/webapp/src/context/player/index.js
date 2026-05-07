import React, { useEffect, useState } from 'react';

import PlayerContext from './context';
import { initSockets } from '../../sockets';

const PlayerProvider = ({ children }) => {
  const [state, setState] = useState({});

  // Initialize sockets for player context
  useEffect(() => {
    initSockets({
      events: ['playerstatus'],
      // Wrap setState to prevent MPD status from overriding an active Spotify session.
      // MPD polls every 250ms; without this guard its stopped-state messages wipe Spotify data.
      setState: (updater) => {
        setState(prev => {
          const next = typeof updater === 'function' ? updater(prev) : updater;
          const prevPS = prev.playerstatus;
          const nextPS = next.playerstatus;
          if (nextPS && prevPS?.player === 'spotify' && prevPS?.state !== 'stop' && !nextPS.player) {
            return prev;
          }
          return next;
        });
      },
    });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const context = {
    setState,
    state,
  };

  // Should be called <PlayerFunctions.Provider />
  // and `state` should be moved to PlayerStatus.Provider

  return(
      <PlayerContext.Provider value={context}>
        { children }
      </PlayerContext.Provider>
    )
};

export default PlayerProvider;
