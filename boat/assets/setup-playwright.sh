#!/usr/bin/env bash
# Install Playwright browsers on a Boat sandbox (boat.dev, formerly ascii.dev
# Box), so they survive a snapshot.
#
#   boat new --setup-file ~/.claude/skills/boat/assets/setup-playwright.sh
#   boat scp setup-playwright.sh <id>:/home/user/ && boat ssh <id> 'bash ~/setup-playwright.sh'
#
# Idempotent. A second run with the same version and browser set exits early.
#
# Arg 1: Playwright version. Default: the version a Derive checkout on the box
#        pins, else PIN below. A browser build that does not match
#        @playwright/test is refused at launch, not at install.
# Arg 2+: browsers. Default: chromium webkit. `pnpm test:e2e` is chromium-only
#        by design; webkit is what PLAYWRIGHT_IOS=1 (`pnpm test:e2e:ios`) needs.
#
# ~/.cache IS EXCLUDED FROM EVERY SNAPSHOT. Measured 2026-09-11: browsers
# installed to the default ~/.cache/ms-playwright were gone from a box created
# with `box new --from`, which then failed with "Executable doesn't exist".
# So browsers go in ~/.playwright, and three mechanisms point Playwright there:
#
#   1. /etc/environment sets PLAYWRIGHT_BROWSERS_PATH. pam_env reads it for
#      every PAM session, so `boat ssh` gets the variable. profile.d does not
#      reach `boat ssh`, which runs no login shell.
#   2. /etc/profile.d/playwright.sh exports the same variable for login shells.
#      `boat exec` already arrives with it set this way.
#   3. playwright-browsers.service re-links ~/.cache/ms-playwright at boot, so
#      the default path works even with no variable at all.
#
# All three live outside ~/.cache, so all three survive the snapshot.
# fleet-seed solves the same problem a fourth way, browsers under ~/repo/.playwright.
set -euo pipefail

PIN=1.60.0

# --setup-file may run as root. The box user owns the browsers, so drop to it;
# `user` holds passwordless sudo, which is all --with-deps needs.
if [ "$(id -u)" = 0 ] && id user >/dev/null 2>&1; then
  exec runuser -u user -- bash "$0" "$@"
fi

VERSION="${1:-}"
shift || true
BROWSERS=("$@")
[ "${#BROWSERS[@]}" -gt 0 ] || BROWSERS=(chromium webkit)

if [ -z "$VERSION" ]; then
  for pkg in "$HOME"/repo/derive-web/node_modules/@playwright/test/package.json \
             "$HOME"/Derive/derive-web/node_modules/@playwright/test/package.json; do
    if [ -f "$pkg" ]; then
      VERSION=$(node -p "require('$pkg').version" 2>/dev/null || true)
      [ -n "$VERSION" ] && break
    fi
  done
fi
[ -n "$VERSION" ] || VERSION="$PIN"

BROWSERS_DIR="$HOME/.playwright"
MARKER="$HOME/.playwright-ready"
WANT="$VERSION ${BROWSERS[*]} $BROWSERS_DIR"

install_pointers() {
  # All three are rewritten even on an early exit, because a restored box has
  # the marker already and the pointers are cheap to reassert.
  sudo sed -i '/^PLAYWRIGHT_BROWSERS_PATH=/d' /etc/environment
  echo "PLAYWRIGHT_BROWSERS_PATH=$BROWSERS_DIR" | sudo tee -a /etc/environment >/dev/null
  sudo tee /etc/profile.d/playwright.sh >/dev/null <<EOF
export PLAYWRIGHT_BROWSERS_PATH=$BROWSERS_DIR
EOF
  sudo tee /etc/systemd/system/playwright-browsers.service >/dev/null <<EOF
[Unit]
Description=Point the default Playwright browser path at $BROWSERS_DIR
After=local-fs.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/sh -c 'mkdir -p $HOME/.cache && rm -rf $HOME/.cache/ms-playwright && ln -sfn $BROWSERS_DIR $HOME/.cache/ms-playwright'

[Install]
WantedBy=multi-user.target
EOF
  sudo systemctl daemon-reload
  sudo systemctl enable --now playwright-browsers.service >/dev/null
}

if [ -f "$MARKER" ] && [ "$(cat "$MARKER")" = "$WANT" ] && [ -d "$BROWSERS_DIR" ]; then
  install_pointers
  echo "SETUP_PLAYWRIGHT: already installed ($WANT)"
  exit 0
fi

echo "SETUP_PLAYWRIGHT: installing playwright@$VERSION ${BROWSERS[*]} -> $BROWSERS_DIR"
PLAYWRIGHT_BROWSERS_PATH="$BROWSERS_DIR" \
  npx --yes "playwright@$VERSION" install --with-deps "${BROWSERS[@]}"
install_pointers

# Prove each browser launches before claiming the box is ready, and do it with
# no env var set, so the smoke test exercises the symlink a restored box relies
# on rather than a variable only this script has.
SMOKE=$(mktemp /tmp/pw-smoke.XXXXXX.mjs)
cat > "$SMOKE" <<'EOF'
const mod = await import(process.argv[2]);
for (const name of process.argv.slice(3)) {
  const b = await mod[name].launch();
  const p = await b.newPage();
  await p.setContent('<h1>ok</h1>');
  const txt = await p.locator('h1').textContent();
  if (txt !== 'ok') throw new Error(`${name}: read back ${txt}`);
  console.log(`SETUP_PLAYWRIGHT: ${name} ${b.version()} launches`);
  await b.close();
}
EOF
ENTRY=$(find "$HOME/.npm/_npx" -path "*/node_modules/playwright/index.mjs" 2>/dev/null | head -1 || true)
if [ -z "$ENTRY" ]; then
  ENTRY=$(find "$HOME" -maxdepth 6 -path "*/node_modules/@playwright/test/index.mjs" 2>/dev/null | head -1 || true)
fi
if [ -z "$ENTRY" ]; then
  echo "SETUP_PLAYWRIGHT: no playwright entry point found to smoke-test" >&2
  exit 1
fi
env -u PLAYWRIGHT_BROWSERS_PATH node "$SMOKE" "$ENTRY" "${BROWSERS[@]}"
rm -f "$SMOKE"

echo "$WANT" > "$MARKER"
echo "SETUP_PLAYWRIGHT: done ($WANT)"
