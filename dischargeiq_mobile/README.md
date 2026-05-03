# `dischargeiq_mobile/` — Flutter mobile client (on hold)

Cross-platform mobile frontend for DischargeIQ. **Currently on hold** for
the shared repo — this directory is listed in `.gitignore` and stays
local-only until the team decides to revive it.

## Status

| Item                     | Detail                                                       |
|--------------------------|--------------------------------------------------------------|
| Framework                | Flutter (Dart)                                               |
| Target platforms         | iOS, Android, Web                                            |
| Backend connection       | Calls `POST /analyze` and `POST /chat` on the FastAPI server |
| API base URL             | Hardcoded in `lib/config.dart` — update before running      |
| Git status               | Gitignored — **not committed to the shared repo**            |
| Demo path                | Use Streamlit (`./start.sh`) instead                         |

## Running locally (if you have a local copy)

```bash
cd dischargeiq_mobile
flutter pub get
flutter run -d chrome --web-port 55497
```

Ensure the FastAPI backend is running on port 8000 first (`./start.sh`
from the repo root). Update `lib/config.dart` with the correct server
address if running on a LAN or device other than localhost.

## Flutter resources

- [Learn Flutter](https://docs.flutter.dev/get-started/learn-flutter)
- [Write your first Flutter app](https://docs.flutter.dev/get-started/codelab)
- [Flutter online documentation](https://docs.flutter.dev/)
