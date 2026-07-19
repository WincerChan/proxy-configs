# Handoff

## Current task and status

- **Goal (this session):** Explain / integrate blackmatrix7 Surge `Apple_All_No_Resolve` rules; later aimed at iOS Telegram notification / APNs routing; then split “Apple push vs other Apple”.
- **User close-out:** User said the problem report was a **false alarm** (wrong message), they **withdrew the changes**, and sent `对话结束`.
- **Repo fact check (verified at handoff time):** Working tree is **clean** on `master` at `9e27d74`. Apple-push-related commits are **still present** in git (not fully reverted in this workspace). User may have reverted only on the client, or intends to revert later.
- **Stopping point:** Session ended by user. No further code work requested.
- **Recommended next step (if a new session continues):**
  1. Confirm with user whether git should fully roll back Apple-related commits, or keep them.
  2. If full revert: reset/revert to pre-Apple baseline `436cc61` (or selectively undo files below), then `python3 scripts/build-release.py stable` and tests.
  3. If keep: note QX remote `ApplePush` can auto-disable when URL refresh fails; prefer local-only APNs or a reliably hosted list.

## Changes made (this thread; still in git HEAD)

### Commits on master

- `69c0594` feat(apple): split APNs push from general Apple policy  
- `9e27d74` fix(quanx): remove duplicated filter_local section  

### Material deltas vs pre-Apple baseline `436cc61`

| Area | Before (`436cc61`) | After (HEAD `9e27d74`) |
|------|--------------------|------------------------|
| Clash Apple provider | MetaCubeX `geosite/apple.mrs` as `apple_domain` | blackmatrix7 `Clash/Apple/Apple_All.yaml` classical `apple` |
| Clash groups | only `🍎 Apple` (DIRECT first) | `🍎 Apple推送` (proxy first) + `🍎 Apple` (DIRECT first) |
| Clash rules | `RULE-SET,apple_domain,🍎 Apple` | APNs domains → `🍎 Apple推送`; `RULE-SET,apple,🍎 Apple,no-resolve` |
| QX policy | only `🍎 Apple` direct-first | + `🍎 Apple推送` proxy-first |
| QX remote | only blackmatrix7 `Apple.list` → `🍎 Apple` | + `rules/apple-push.list` URL → `🍎 Apple推送` **before** Apple.list |
| QX local | no APNs lines | 7 APNs host rules → `🍎 Apple推送` |
| New files | — | `rules/apple-push.list`; CI once touched for publishing list (check current CI) |

### Key paths

- `src/clash/20-proxy-groups.yaml`, `30-rule-providers.yaml`, `40-rules.yaml`
- `src/quanx/20-policy.conf`, `50-filter-remote.conf`, `70-filter-local.conf`
- `rules/apple-push.list`
- `dist/clash/clash-naixi-stable.yaml`, `dist/quanx/quantumultx-naixi-stable.conf`
- Build: `python3 scripts/build-release.py stable`

### Validation already run (during session)

- `python3 scripts/build-release.py stable` — pass (when changes were built)
- `python3 -m unittest discover -s tests -v` — 10 pass
- `python3 scripts/validate-clash.py dist/clash/clash-naixi-stable.yaml` — pass

## Uncertainties

1. **User “撤回改动” vs git state:** User said they reverted; workspace HEAD still has Apple-push commits. Confirm actual desired tree.
2. **Whether Telegram/APNs was ever broken here:** User later said message was sent by mistake and there was no problem.
3. **QX remote `ApplePush` reliability:** Resource at  
   `https://raw.githubusercontent.com/WincerChan/proxy-configs/master/rules/apple-push.list`  
   may 404 / fail refresh (private repo, not pushed, or raw.githubusercontent issues) → QX **auto-disables** resource after refresh. This matched user report “开启后刷新又关闭”.
4. **filter_local vs remote Apple.list order:** If remote Apple matches first with `force-policy=🍎 Apple` (direct), local APNs rules may never win unless resource order / local priority puts APNs first.
5. **Environment:** Could not reliably HTTP-verify GitHub raw from the agent environment (TLS errors).

## Pitfalls and failed approaches

1. **Treating Surge `IP-CIDR,...,no-resolve` as equivalent to QX `IP-CIDR,...,Apple`:** Same CIDRs; third field is option vs policy — not interchangeable.
2. **Only swapping/adding Apple domain lists without fixing policy:** Telegram iOS push uses **APNs** (`push.apple.com` / Apple IPs), not Telegram domain rules. List alone does not fix push if policy is DIRECT.
3. **Two `[filter_local]` sections** (priority APNs section + main local): QX import error `duplicated section ... [filter_local]`. Only one `[filter_local]` allowed.
4. **Remote-only ApplePush list in QX:** On update failure, QX turns the resource off again after user enables it — bad UX; local-only or always-reachable URL required.
5. **Putting full Apple on proxy:** Fixes some APNs cases but slows App Store/iCloud; user preferred push-only proxy, then abandoned the effort as unnecessary.
6. **Do not re-add dual `[filter_local]` or a flaky remote ApplePush without a public stable URL.**

## Project context (stable)

- Personal Clash/Mihomo + Quantumult X configs; edit `src/`, build `dist/`.
- Stable artifacts: `dist/clash/clash-naixi-stable.yaml`, `dist/quanx/quantumultx-naixi-stable.conf`
- Pre-Apple-work baseline commit for clean rollback reference: `436cc61`
