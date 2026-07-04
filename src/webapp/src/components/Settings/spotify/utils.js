// Redirect URI helpers for the Spotify setup wizard

// The URI the OAuth callback server on the jukebox listens on, derived from
// the address the web UI is currently served from
export const getSuggestedRedirectUri = () =>
  `http://${window.location.hostname}:8888/callback`;

// Loopback variant: Spotify's dashboard accepts plain http only for loopback
// addresses, so this is the fallback when the jukebox address is rejected.
// The redirect then lands on the user's own machine and the resulting URL
// must be pasted into the UI manually.
export const LOOPBACK_REDIRECT_URI = 'http://127.0.0.1:8888/callback';

// True if the stored redirect URI is unset or still the shipped default,
// i.e. was never deliberately chosen by the user
export const isDefaultRedirectUri = (uri) =>
  !uri || uri === 'http://localhost:8888/callback';
