#!/usr/bin/env bash
# One-time setup: generates the android/ folder, then allows plain-HTTP to your LAN backend.
# Needs the Flutter SDK (flutter doctor) on PATH.
set -e
cp lib/main.dart /tmp/om_main.dart.bak
flutter create . --org com.officemanager --project-name office_management --platforms android,web
cp /tmp/om_main.dart.bak lib/main.dart      # keep our main.dart
rm -f test/widget_test.dart                  # template test references the default MyApp
MANIFEST=android/app/src/main/AndroidManifest.xml
grep -q 'android.permission.INTERNET' $MANIFEST || sed -i 's#<application#<uses-permission android:name="android.permission.INTERNET"/>\n    <application#' $MANIFEST
grep -q 'usesCleartextTraffic' $MANIFEST || sed -i 's#<application#<application android:usesCleartextTraffic="true"#' $MANIFEST
flutter pub get
echo "Done. Run: flutter analyze && flutter test"
echo "Web:     flutter run -d chrome --dart-define=API_BASE_URL=http://localhost:8000/"
echo "Android: flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000/"
