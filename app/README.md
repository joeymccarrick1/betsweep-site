# BetSweep app shells

betsweep.co is already an installable app (PWA): on a phone, Share → Add to Home Screen (iOS) or the install prompt (Android)
gives a full-screen app with the bottom tab bar, offline shell and home-screen icon. Nothing in this folder is needed for that.

This folder is the **store wrapper**: a Capacitor project whose native iOS / Android shells load https://betsweep.co full screen,
so the same site can be submitted to the App Store and Google Play when the time comes. It needs a Mac with Xcode (iOS) and/or
Android Studio (Android); it cannot be built from the cloud sessions that maintain the site.

## First-time setup (on your Mac)
```bash
cd app
npm install
npx cap add ios        # creates ios/   (Xcode project)
npx cap add android    # creates android/ (Android Studio project)
npx cap sync
npx cap open ios       # or: npx cap open android
```
In Xcode: set your Team under Signing & Capabilities, bump the version, Product → Archive → Distribute. App icons: use
`https://betsweep.co/app/icon-512.png` (Xcode's asset catalog wants 1024×1024 - export the logo at that size, same dark background).

## Store notes (read before submitting)
- Category: Sports. Age rating 17+ (simulated/real gambling references). Apple reviews betting-information apps case by case; the
  app does not take bets or payments - say so in the review notes, and that all betting happens in the user's own FanDuel app.
- Apple guideline 4.2 (minimum functionality) is the usual objection to a pure web wrapper. Before submitting, give the shell at
  least one native capability the website cannot have: push notifications for the Live page (leg hit / red-zone alerts) is the
  obvious one and is on the roadmap. Google Play is more lenient; a Trusted Web Activity (TWA) of the PWA is also an option there.
- Privacy: the site stores slips and pins in the device's local storage only; no accounts, no analytics beyond GitHub Pages logs.

## How it works
`capacitor.config.json` points `server.url` at the live site, so every rebuild of betsweep.co updates the app with no store release.
`www/index.html` is only a splash that redirects if the remote load is ever disabled.
