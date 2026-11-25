# Office Manager (Flutter: Android, Tablet, Web)

One Flutter codebase for the React `admin-web` panel. Same backend, same endpoints (`lib/api/api_url.dart`).

## Setup (needs the Flutter SDK, stable >= 3.27)
1. `./setup.sh`  - creates `android/` and `web/`, adds INTERNET + cleartext HTTP on Android, runs `flutter pub get`.
2. `flutter analyze` and `flutter test`.

## Run
- Web:     `flutter run -d chrome --dart-define=API_BASE_URL=http://localhost:8000/`
- Android: `flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000/`  (emulator; for a phone use your PC's LAN IP)
- Builds:  `flutter build web --dart-define=API_BASE_URL=https://api.example.com/`, `flutter build apk --release --dart-define=...`
- Default when no define is given: `lib/config/app_config.dart`.

## Web notes
- The browser enforces CORS: the backend must allow your web origin (backend setting; not changed here).
- Tokens use `flutter_secure_storage` (WebCrypto in browsers; needs HTTPS or localhost).
- URLs use the hash style (`/#/employees`), so refresh and deep links work on any static host.

## Layout
`lib/api` Dio client, interceptor, URLs - `lib/config` build settings - `lib/services` one method per endpoint -
`lib/providers` auth/theme - `lib/screens` pages (generic CRUD framework in `screens/generic`) -
`lib/widgets` shared UI - `lib/routes` go_router + permission guard - `lib/constants/app_menu.dart` menu + permissions -
`lib/utils` validators, formatters, responsive helper, error handler, file saver (web/Android).

## Responsive
>= 1100 px: permanent sidebar. 700-1100 px (tablet) and phones: drawer. Content is centred (max 1280 px, forms 760 px),
stat grids use 2/3/4 columns, tables scroll horizontally.
