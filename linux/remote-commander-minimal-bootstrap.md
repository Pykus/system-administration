# Remote Commander — minimal Linux bootstrap

A short bootstrap for Debian/Ubuntu when the goal is to pair Remote Commander first and finish the persistent setup remotely.

## 1. Verify Node.js 22

```bash
node -v
```

If Node.js 22 is not installed:

```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs
```

Verify:

```bash
node -v
npm -v
```

## 2. Create the Remote Commander account

```bash
sudo useradd -m -s /bin/bash remote-commander 2>/dev/null || true
```

If this host is intentionally delegated for full remote administration, create the local sudoers drop-in according to your organization's policy and validate it before continuing.

## 3. Start the first pairing from the correct working directory

Do **not** start `npx` while the current directory is another user's private home, such as `/home/admin`. The child shell may fail with:

```text
spawn sh EACCES
```

Start it from the service account's own home:

```bash
sudo -u remote-commander -H bash -lc 'cd /home/remote-commander && npx -y @wonderwhy-er/desktop-commander@latest remote'
```

Warnings about deprecated transitive npm packages are not the same as a startup failure. Diagnose the final `npm error` / exit status.

After pairing, perform the persistent install, supervisor/autostart and privilege verification remotely.

## Verification

Typical checks after takeover:

```bash
whoami
node -v
npm -v
```

For an intentionally delegated administrative account, also verify the configured sudo policy non-interactively.

## Why this bootstrap stays short

The operator only needs to establish a working, correctly-versioned Remote Commander session. Repetitive persistent setup belongs on the remote side, where it can be scripted, tested and documented consistently.
