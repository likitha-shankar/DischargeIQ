# launchd agent for the corpus catch-up job

A backup scheduling mechanism for `scripts/corpus_catchup.sh`, to be used **if
the cron entry turns out not to fire**.

**Not installed by default.** Cron is currently the active schedule.

## Why a backup exists at all

The repository lives under `~/Desktop`, which macOS protects with TCC.
`/usr/sbin/cron` cannot read or write there without an explicit Full Disk
Access grant, and **when that grant is missing, cron fails silently**: no log,
no error, nothing to notice.

That is not hypothetical here. The cron entry was installed on 16 Aug 2026.
By 25 Aug, `logs/corpus_catchup/` contained exactly one log file, from the day
it was set up. Nine days of a nightly job produced nothing, and nothing said
so. Full Disk Access was granted to `/usr/sbin/cron` on 25 Aug, but the
schedule was disabled the same day, so **cron has still never been observed
completing a run on this machine.**

launchd is the supported mechanism on macOS. A user agent runs as the logged
in user and inherits that user's TCC grants, so a protected path behaves as it
does in a terminal. It also writes stdout and stderr to files, so a failure
before the script starts leaves evidence rather than silence. And it runs a
job missed while the machine was asleep; cron just skips the slot.

## First: find out whether you need this

Check the morning after any scheduled run:

```bash
ls -la logs/corpus_catchup/
```

- **A log file dated today exists** - cron works. You do not need this agent.
- **No log file** - cron did not run. Install the agent below.

Look at the log's contents too, not just its existence. `corpus documents
missing or stale: 0` followed by `no API calls made` is the correct output on
a finished corpus, and is different from an empty file.

## Install

**Disable the cron entry first.** Both would fire at 09:00 and contend for the
same dynamic shared quota. The script holds a lock so the loser exits
harmlessly, but relying on that is a safety net, not a plan.

```bash
crontab -e          # comment out the corpus_catchup line
```

Then:

```bash
cp scripts/launchd/com.dischargeiq.corpuscatchup.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.dischargeiq.corpuscatchup.plist
launchctl list | grep dischargeiq          # confirm it is registered
```

## Verify without waiting until tomorrow

```bash
launchctl start com.dischargeiq.corpuscatchup
```

That triggers a real run immediately, which **spends API calls** unless the
corpus is already current. Watch it:

```bash
tail -f logs/corpus_catchup/$(date +%Y%m%d).log
```

If nothing appears there, look at the agent's own streams - this is the part
cron could not give you:

```bash
cat /tmp/dischargeiq-catchup.out
cat /tmp/dischargeiq-catchup.err
```

A TCC denial, a wrong path, or a missing interpreter shows up in `.err`.

## Uninstall

```bash
launchctl unload ~/Library/LaunchAgents/com.dischargeiq.corpuscatchup.plist
rm ~/Library/LaunchAgents/com.dischargeiq.corpuscatchup.plist
```

Then re-enable the cron line if you want the schedule back.

## Notes

- **Schedule:** 09:00 daily, matching the cron entry it replaces. Worst-case
  runtime is about 70 minutes (`BATCH=8`, `MAX_PASSES=12`), so it clears well
  before an afternoon demo. A corpus job running *concurrently* with a demo
  starves it, because one analysis needs six calls in a row.
- **`RunAtLoad` is deliberately false.** True would fire a quota-consuming job
  every time the agent loads or you log in, which is not what "daily" means.
- **Full Disk Access may still be needed**, now for whatever runs the agent.
  If `/tmp/dischargeiq-catchup.err` shows permission errors on the repo path,
  grant FDA to Terminal (or your shell) in System Settings > Privacy &
  Security > Full Disk Access.
- **The real fix, if this keeps being awkward:** move the repository out of
  `~/Desktop`. TCC does not protect `~/dev`, and the whole class of problem
  disappears. It would break absolute paths in the crontab, this plist, and
  various notes, which is why it has not been done.
