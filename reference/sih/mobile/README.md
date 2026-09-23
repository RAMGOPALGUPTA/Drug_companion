# Field Drug Testing Mobile App

React Native + Expo Android-first field application.

The app implements the five-screen field workflow: officer login, dashboard, test capture, result review and records. It uses SQLite for local persistence, Expo Camera for capture, Expo Location for GPS, a local evidence digest, and an API outbox that retries unsynchronized records.

## Run

```bash
npm install
npx expo start
```

Use Expo Go for UI testing. A development build is recommended when testing native camera/location behavior on a physical device.

For the Android emulator the default API address is `http://10.0.2.2:8000`. A physical device must use a reachable address:

```bash
EXPO_PUBLIC_API_BASE_URL=http://192.168.x.x:8000 npx expo start
```

The development PostgreSQL database supplies `demo-operator`; map authenticated officers to provisioned API operators before production. The image stays on-device and the API receives its digest plus the test record.

The current result is intentionally `inconclusive` until a validated trained model is installed. The model is an interpretation aid for a presumptive colorimetric field test, not definitive laboratory confirmation.
