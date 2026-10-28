# Participant PWA Design

## Goal

Make the participant experience feel like a focused mobile app while keeping
the existing Cedz visual theme. The admin portal remains a normal website.

## Participant navigation

The authenticated participant area has four client-side tabs, addressable by
hash and usable without a page reload:

- `#home`: latest revelation, then the current bonus question and its answer
  action.
- `#revelations`: all sent revelations.
- `#answers`: completed questionnaire answers and completed bonus answers.
- `#profile`: global/discipline rankings, password controls, and prior bonus
  questions that are still unanswered.

A mobile bottom navigation selects these tabs. Desktop retains the existing
header but uses the same tab state. No participant content is duplicated
between tabs.

When the current bonus question has been answered and unanswered prior bonus
questions remain, Home shows a clear catch-up panel with their count and a
button opening `#profile`. Answering a prior question removes it from Profile
and places its answer in Mes réponses.

## PWA boundaries

Only public shell assets are cached: CSS, JavaScript, manifest, icons, logo and
an offline page. Participant HTML, API responses, answers, revelations,
sessions, and admin content are always fetched from the network and are never
stored by the service worker. The app is installable on HTTPS and detects a new
service-worker version without exposing cached private information.

Admin pages intentionally receive no install prompt, participant bottom menu,
or offline-data behavior.

## Push notifications

After a participant's first successful login, Home displays an explainer and
an explicit “Activer les notifications” button. The browser permission request
is only made after that click. A declined permission is not repeatedly prompted;
Profile keeps a control to retry through browser settings where possible.

The server stores a Web Push subscription per participant and device. A valid
subscription receives two events:

- when a revelation transitions to `sent`: title `Une révélation t’attend.` and
  a link to that revelation;
- when the admin manually sends a bonus-question batch: the same subject used
  by its email and a link to the participant home question.

Subscriptions returning gone/not-found are removed. VAPID private keys exist
only as Railway environment variables. Failed push delivery never rolls back
the mail/revelation/question transaction.

## Non-goals

- Offline submission and later synchronization of answers.
- Push notifications for admin accounts.
- Changing email delivery behavior.

## Acceptance criteria

- A participant can install the app; admin cannot be prompted to install it.
- A participant can reach all four areas through the app navigation and a
  reload preserves the selected tab.
- Home puts the latest revelation above the current bonus question.
- Unanswered historical bonus questions appear in Profile; answered ones appear
  in Mes réponses.
- The catch-up panel appears only after today's question is answered and one or
  more historical questions remain.
- Private API responses are absent from service-worker caches.
- A participant can opt in from first login; sending a revelation or bonus
  question triggers the corresponding push payload for active subscriptions.
