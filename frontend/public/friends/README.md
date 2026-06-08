# centralperk brand assets

Animated couch logo: `src/components/friends/CentralPerkLogo.tsx`  
Static favicon / PWA: `public/logo.svg`

Replace `public/icons/icon-192.png` and `icon-512.png` with PNG exports of the couch on purple for best iOS home-screen results (SVG favicon works in most browsers).

## Character icons (optional)

## Pinterest / Widgetsmith homescreen

- [Friends app icon layout](https://www.pinterest.com/pin/42995371440140227/)

Export individual squircle icons from the pin (or Behance) and save with the filenames below.
The UI uses iOS-style `rounded-[22%]` squircles until images are present.

## Source galleries

- [Full cast caricatures](https://www.behance.net/gallery/104319041/Caricatures)
- [Monica Geller](https://www.behance.net/gallery/126728093/Monica-Geller)
- [Phoebe Buffay](https://www.behance.net/gallery/126728127/Phoebe-Buffay)

## Expected filenames

| File | Character | Agent |
|------|-----------|-------|
| `ross.png` | Ross | Knowledge |
| `monica.png` | Monica | Health |
| `phoebe.png` | Phoebe | Wellness |
| `joey.png` | Joey | Lifestyle |
| `chandler.png` | Chandler | Finance |
| `rachel.png` | Rachel | Style |

Theme tokens live in `src/theme/friends.ts`. Wire images in `CharacterAvatar.tsx` when files exist.
