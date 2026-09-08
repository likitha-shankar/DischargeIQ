# Task 4.5 - Production Builds with Locked Dependencies ◑

**Deliverable:** production builds, dependencies locked.

## Done

**Python locked:** `requirements.lock.txt`, with `DEPENDENCIES.md` as the
licence manifest. Audited clean - no GPL, AGPL, or network-copyleft anywhere,
which is a Gate requirement and was separately confirmed as Liebovitz item
3.1.

**Release APK builds:** `scripts/build_beta_kit.sh` produces a universal,
direct-install APK plus the tester kit.

**In-app attribution:** open-source licences visible in Settings, backend
dependencies included (`d756744`, LOF action item 36:04). All 18 backend
entries were verified against `requirements.lock.txt` - the first version
listed two packages that were not installed and ten wrong versions.

## Not done, and out of scope

**Store-signed builds.** The release APK signs with the debug key on purpose
for the direct-install beta path. A Play upload needs a real keystore and a
paid account; an App Store or TestFlight build needs a paid Apple account.
Neither account exists, and both were deferred to a first LOF payout.

This is a scope boundary, not a gap - say so rather than reporting the task
as partially failed.

## Fixed 8 Sep 2026

The kit was packaging an APK built without the API key, which returns 401 on
every analysis against the hosted backend. The build now compiles the key in
and refuses to assemble without it (`a15c9f6`). See [task-2.6](task-2.6.md).
