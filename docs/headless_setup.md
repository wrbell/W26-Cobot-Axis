# Headless Pi Setup from a Laptop (No Switch, Direct Ethernet)

Bring up the Raspberry Pi and SKR Pico for the W26 Cobot Axis using a Mac or Windows laptop, with no ethernet switch, no router in the middle, and no Pi400. The laptop connects directly to the Pi over a single ethernet cable, then the rest of the install (Klipper firmware, bridge daemon, Klipper config) runs over SSH.

This guide covers only the "how do I SSH in" gap. After Step 4 finishes, you hand off to [SETUP.md](../SETUP.md) starting at **§4 Step 3: Clone the Repository** and follow the rest of that guide unchanged.

---

## Table of Contents

1. [When to use this guide](#1-when-to-use-this-guide)
2. [Prerequisites](#2-prerequisites)
3. [Step 1: Image the SD card](#3-step-1-image-the-sd-card)
4. [Step 2: Connect the Pi over direct ethernet and SSH in](#4-step-2-connect-the-pi-over-direct-ethernet-and-ssh-in)
5. [Step 3: First-login sanity checks](#5-step-3-first-login-sanity-checks)
6. [Step 4: Give the Pi internet access via the laptop](#6-step-4-give-the-pi-internet-access-via-the-laptop)
7. [Step 5: Hand off to SETUP.md](#7-step-5-hand-off-to-setupmd)
8. [Step 6: Driving the config with Claude Code over SSH](#8-step-6-driving-the-config-with-claude-code-over-ssh)
9. [Step 7: Flashing the Pico from the Pi over SSH](#9-step-7-flashing-the-pico-from-the-pi-over-ssh)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. When to use this guide

Use this guide when **all** of the following apply:

- You're setting up the Pi from a personal Mac or Windows laptop.
- You don't have an ethernet switch, managed switch, or router you can plug the Pi into.
- You don't have a Pi400 on the network.
- You want to reach the Pi over ethernet, not WiFi.

If you have a switch or router, follow [SETUP.md](../SETUP.md) directly — it assumes a shared subnet and is simpler.

### What this guide does not cover

- WiFi-based headless setup. Configuring WiFi in Pi Imager works, but that's out of scope here.
- USB gadget mode (SSH over USB-C). The Pi 4 can be coerced into `g_ether` gadget mode, but it's fiddly, varies by Pi model, and direct ethernet is strictly simpler. Skip it.
- UR30 network integration. Once the Pi is reachable you'll still need a proper switch (or at minimum a second ethernet port on the host) to put the UR30 on the same subnet as the Pi. That's a different problem — see [SETUP.md §3 Step 2](../SETUP.md#3-step-2-network-configuration).

---

## 2. Prerequisites

### Hardware

| Item | Notes |
|------|-------|
| Raspberry Pi (4B recommended) | With 5.1V/3A USB-C power supply |
| MicroSD card | 16 GB minimum, 32 GB recommended |
| BigTreeTech SKR Pico V1.0 | With USB-C data cable to the Pi (needed later, not for SSH) |
| Ethernet cable (Cat 5e or Cat 6) | Standard straight-through; modern NICs do auto-MDIX so no crossover cable needed |
| Laptop | Mac (macOS 12+) or Windows (10/11) with a free ethernet port (built-in or USB adapter) |
| MicroSD card reader | Built-in or USB |

### Software on the laptop

- **Raspberry Pi Imager** — https://www.raspberrypi.com/software/
- **SSH client:**
  - macOS: built-in (`ssh` in Terminal or iTerm2)
  - Windows: built-in OpenSSH (`ssh` in PowerShell or Windows Terminal), or PuTTY
- **Windows only — mDNS/Bonjour** for resolving `.local` hostnames:
  - Install [Bonjour Print Services for Windows](https://support.apple.com/kb/DL999) (free, from Apple)
  - Or install iTunes, which bundles Bonjour
  - Or skip Bonjour and use the link-local IP directly (see Step 2)

---

## 3. Step 1: Image the SD card

Flash **MainsailOS** — it ships with Klipper, Moonraker, and Mainsail pre-installed, matching what the deploy script expects.

1. Download the latest image from the [MainsailOS releases page](https://github.com/mainsail-crew/MainsailOS/releases). The `.img.xz` file is a few hundred MB.
2. Open **Raspberry Pi Imager** on the laptop.
3. **Choose OS** → **Use custom** → select the downloaded `.img.xz`.
4. **Choose Storage** → select the SD card.
5. Click the gear icon (or `Ctrl+Shift+X` / `Cmd+Shift+X`) to open advanced settings and set:

   | Setting | Value |
   |---------|-------|
   | Hostname | `w26-pi` |
   | Enable SSH | Yes, with password authentication |
   | Username | `pi` |
   | Password | Choose a secure password (you'll use it repeatedly) |
   | Configure WiFi | **Skip** — we're using direct ethernet |
   | Locale | Your timezone and keyboard layout |

6. Click **Write** and wait for the flash + verify to finish (~5 min).
7. Eject the card, insert it into the Pi, connect the Pi's 5.1V/3A power supply, and power on.
8. Wait 2–3 minutes for first boot to finish (it resizes the filesystem and generates SSH host keys).

---

## 4. Step 2: Connect the Pi over direct ethernet and SSH in

This is the part that's not in SETUP.md. You plug the ethernet cable straight from the laptop to the Pi — no switch, no router. Both ends assign themselves **link-local** IPv4 addresses in the `169.254.x.x` range (RFC 3927 / Zeroconf). mDNS then resolves `w26-pi.local` to that address.

### 4.1 Wire it up

1. Plug one end of the ethernet cable into the Pi's ethernet port.
2. Plug the other end into the laptop's ethernet port (built-in or USB-to-ethernet adapter).
3. Confirm the Pi's power LED is solid and the ethernet port's link LED is blinking.

### 4.2 macOS — SSH via Bonjour

Bonjour is built in; no install needed.

```bash
ssh pi@w26-pi.local
```

First connection prompts for the host key — type `yes`, then enter the password you set in Pi Imager.

If the hostname doesn't resolve (`ssh: Could not resolve hostname w26-pi.local`), wait 30 seconds and try again — mDNS takes a moment to propagate after first boot. If it still fails, check that the laptop has a link-local address on ethernet:

```bash
ifconfig | grep -A3 "en[0-9]:" | grep "inet 169.254"
```

You should see something like `inet 169.254.103.47`. If you don't, the interface isn't up — check the cable and that the ethernet service is enabled (System Settings → Network → Ethernet → `Configure IPv4: Using DHCP with manual address` or `Using DHCP`; leave it at DHCP, the OS falls back to link-local when no DHCP reply arrives).

You can also browse advertised SSH services to confirm the Pi is reachable:

```bash
dns-sd -B _ssh._tcp local.
```

You should see `w26-pi` appear within a few seconds. `Ctrl+C` to stop.

### 4.3 Windows — SSH via Bonjour

If you installed Bonjour (or iTunes):

```powershell
ssh pi@w26-pi.local
```

Same flow as macOS: accept the host key, enter the password.

### 4.4 Windows — SSH without Bonjour

If you can't install Bonjour, fall back to the link-local IP.

1. Ping the Pi's hostname repeatedly so the ARP table populates. Even if the ping fails to resolve, the broadcast ARP traffic will reveal the Pi:

   ```powershell
   ping w26-pi
   ```

2. List ARP entries on the ethernet adapter:

   ```powershell
   arp -a
   ```

   Look for a `169.254.x.x` entry with a `dynamic` type on your ethernet adapter. That's the Pi.

3. SSH to that IP:

   ```powershell
   ssh pi@169.254.x.x
   ```

If `arp -a` shows nothing on 169.254, check `ipconfig` for your ethernet adapter — it should have an "Autoconfiguration IPv4 Address" in the `169.254.x.x` range. If it doesn't, the adapter is still waiting for DHCP; disable and re-enable it (`Disable`/`Enable` from Network Connections), or wait 60 seconds.

### 4.5 Sanity check

You should now be logged into the Pi with a shell prompt like `pi@w26-pi:~ $`. The connection is over link-local ethernet; the Pi has no internet yet (that's Step 4).

---

## 5. Step 3: First-login sanity checks

Run these on the Pi (through your SSH session) to confirm the environment is healthy before moving on.

```bash
hostname                       # should print: w26-pi
ip addr show eth0 | grep inet  # should show a 169.254.x.x/16 address
uname -a                       # confirm kernel/arch
df -h /                        # confirm the rootfs resized correctly (~29 GB free on a 32 GB card)
```

Skip the `ping 8.8.8.8` check — the Pi has **no default route** yet, so outbound traffic will fail. We fix that in Step 4.

---

## 6. Step 4: Give the Pi internet access via the laptop

Klipper, Moonraker, and the bridge daemon all need to install packages from the internet (`apt install`, `pip install`, `git clone`). Since the Pi is only connected to the laptop, the laptop has to share its internet connection out to the ethernet port.

### 6.1 macOS — Internet Sharing

1. Open **System Settings** (or **System Preferences** on older macOS) → **General** → **Sharing**.
2. Click the **(i)** next to **Internet Sharing**.
3. **Share your connection from:** `Wi-Fi` (or whichever interface has internet).
4. **To computers using:** check `Ethernet` (or your USB ethernet adapter).
5. Close the panel, then toggle **Internet Sharing** on. macOS confirms — click **Start**.

macOS starts handing out DHCP on the ethernet side, typically on the `192.168.2.0/24` subnet with the laptop at `192.168.2.1`. The Pi will pick up a new address on its next DHCP renew.

On the Pi, renew its lease (or just reboot):

```bash
sudo dhclient -r eth0 && sudo dhclient eth0
# or on Bookworm / NetworkManager:
sudo nmcli device reapply eth0
# or simplest:
sudo reboot
```

After the Pi comes back, reconnect from the laptop — mDNS still works, so the same command resolves to the new IP:

```bash
ssh pi@w26-pi.local
```

If your SSH session complains about a mismatched host key, that's expected; the host key hasn't changed, but the IP has. Don't delete the known_hosts entry — `w26-pi.local` resolves differently now and SSH stores entries by hostname, not IP.

Verify internet from the Pi:

```bash
ping -c 2 8.8.8.8            # should succeed
ping -c 2 deb.debian.org     # DNS + outbound both working
```

### 6.2 Windows — Internet Connection Sharing (ICS)

1. Open **Settings** → **Network & internet** → **Advanced network settings** → **More network adapter options** (this opens the classic **Network Connections** control panel). On Windows 10, go straight to **Control Panel** → **Network and Sharing Center** → **Change adapter settings**.
2. Right-click your **WiFi** adapter (the one with internet) → **Properties**.
3. Select the **Sharing** tab.
4. Check **"Allow other network users to connect through this computer's Internet connection."**
5. Under **"Home networking connection"**, select your **ethernet** adapter.
6. Click **OK**.

Windows typically assigns `192.168.137.1` to the ethernet adapter and hands out DHCP from `192.168.137.2` upward.

On the Pi, renew the lease or reboot, then reconnect:

```powershell
ssh pi@w26-pi.local
```

Verify internet from the Pi:

```bash
ping -c 2 8.8.8.8
```

### 6.3 Notes

- **Internet Sharing is a per-reboot setting** on macOS and Windows. If you reboot the laptop, re-enable sharing before you expect the Pi to reach the internet.
- **Corporate/managed laptops** sometimes block Internet Sharing via MDM policy. If that's your situation, you'll need to bring in a cheap unmanaged switch — the rest of this guide assumes sharing works.
- **VPNs on the laptop** can interact badly with ICS/Internet Sharing. If you have a VPN connected, the Pi may end up with no DNS or a blackholed default route. Disconnect the VPN for the Pi's install steps, then reconnect afterward.

---

## 7. Step 5: Hand off to SETUP.md

Once you can `ssh pi@w26-pi.local` and the Pi can reach the internet, the rest of the install is identical to the switch-based setup.

Pick up at **[SETUP.md §4 Step 3: Clone the Repository](../SETUP.md#4-step-3-clone-the-repository)** and follow every step through **§9 Step 8: End-to-End Verification**.

You can **skip** [SETUP.md §3 Step 2: Network Configuration](../SETUP.md#3-step-2-network-configuration) — that section is about putting the Pi on the lab subnet with the UR30. For bench bring-up on a laptop you don't need a static IP; the Internet-Sharing DHCP lease is fine.

When you eventually move to the lab (or add a switch and the UR30), come back to SETUP.md §3 and configure a static IP at that point.

---

## 8. Step 6: Driving the config with Claude Code over SSH

The rest of SETUP.md is a long sequence of commands run on the Pi over SSH. Claude Code (running on your laptop, not on the Pi) is well-suited to drive this:

- It already has the repo indexed — it can read `deploy.sh`, `printer.cfg`, and the bridge source before touching the Pi.
- [`deploy.sh`](../deploy.sh) and [`scripts/dev-sync.sh`](../scripts/dev-sync.sh) are designed to run from a laptop and SSH into the Pi; both take the Pi as an argument.
- Tailing logs, restarting services, and re-deploying after edits all collapse into short prompts.

### 8.1 One-time laptop setup

**Set up SSH key auth** so Claude doesn't hit a password prompt every time it shells into the Pi:

```bash
# On the laptop (from any terminal):
ssh-keygen -t ed25519 -C "w26-pi" -f ~/.ssh/w26_pi   # accept the default (no passphrase) or add one
ssh-copy-id -i ~/.ssh/w26_pi.pub pi@w26-pi.local
```

Add a convenience entry to `~/.ssh/config` so `ssh w26-pi` just works:

```ssh-config
Host w26-pi
  HostName w26-pi.local
  User pi
  IdentityFile ~/.ssh/w26_pi
  ServerAliveInterval 30
```

**Reduce Claude Code permission prompts.** After your first Claude-driven session against the Pi, run the `/fewer-permission-prompts` skill:

```text
/fewer-permission-prompts
```

It reviews the session transcript, identifies the `ssh`, `rsync`, `scp`, and deploy commands you've already approved, and proposes an allowlist to add to `.claude/settings.local.json` (git-ignored; per-clone, not shared with the team). Accept the proposal and future sessions stop prompting for those commands.

If you'd rather write the allowlist by hand, the typical entries are:

```json
{
  "permissions": {
    "allow": [
      "Bash(ssh w26-pi:*)",
      "Bash(ssh pi@w26-pi.local:*)",
      "Bash(rsync:*)",
      "Bash(scp:*)",
      "Bash(bash scripts/dev-sync.sh:*)",
      "Bash(bash deploy.sh:*)"
    ]
  }
}
```

### 8.2 Common prompts that "just work"

Once the allowlist is set, these prompts run end-to-end without interactive approval:

| What you want | What to ask Claude |
|--------------|---------------------|
| First-time deploy to the Pi | *"Deploy the current repo state to w26-pi. Skip flashing since I did that in Step 4."* → runs `bash deploy.sh --skip-flash` on the Pi via SSH |
| Sync code changes and restart the bridge | *"Sync my latest src/ changes to the Pi and restart the bridge."* → runs `bash scripts/dev-sync.sh pi@w26-pi.local` |
| Tail Klipper log | *"Tail the Klipper log on the Pi."* → `ssh w26-pi "tail -f /tmp/klippy.log"` |
| Inspect bridge logs | *"Show me the last 50 lines of the bridge daemon log."* → `ssh w26-pi journalctl -u w26-bridge -n 50` |
| Restart everything | *"Restart klipper and the bridge on the Pi."* → `ssh w26-pi "sudo systemctl restart klipper w26-bridge"` |
| Find the MCU serial | *"What's the Klipper MCU serial path on the Pi?"* → `ssh w26-pi "ls /dev/serial/by-id/usb-Klipper_rp2040_*"` |
| Pull up the printer.cfg | *"Show me the printer.cfg that's actually loaded on the Pi."* → `ssh w26-pi "cat ~/printer_data/config/printer.cfg"` |

### 8.3 Working on code locally, iterating on the Pi

The fastest dev loop is:

1. Edit code in `src/bridge/` on the laptop (Claude Code makes the edits directly).
2. Run `bash scripts/dev-sync.sh pi@w26-pi.local` — rsyncs `src/` in ~1 second and restarts the bridge.
3. `ssh w26-pi journalctl -u w26-bridge -f` to watch the bridge come back up.

`deploy.sh` is the heavier tool for first-time setup or when systemd units, Python deps, or Klipper config paths change. `dev-sync.sh` is the right tool for code iteration.

### 8.4 What **not** to do

- **Don't install Claude Code on the Pi.** The Pi 4B has the RAM to run it, but Klipper's real-time loop is sensitive to CPU contention and the Pi's disk I/O is slow. Keep Claude on the laptop where the repo already lives.
- **Don't edit files on the Pi directly via `ssh w26-pi vi ...`.** Edits will be overwritten by the next `dev-sync.sh` or `deploy.sh`, and you lose git history. Edit on the laptop, sync to the Pi.

---

## 9. Step 7: Flashing the Pico from the Pi over SSH

SETUP.md §5 covers the Pico flash. The flow is unchanged when working over SSH — Claude can run each command remotely — but note two practical points:

- **The BOOTSEL button is physical.** You have to be near the SKR Pico to hold BOOTSEL while pressing RESET (or replug USB). Claude can't do that. Once the board is in BOOTSEL mode, the rest (`lsblk`, `cp ... /media/.../RPI-RP2/`) runs over SSH.
- **A pre-built `klipper.uf2` is published on GitHub Releases.** See the shortcut note in [SETUP.md §5](../SETUP.md#5-step-4-flash-klipper-firmware-to-skr-pico). Download it locally, `scp` it to the Pi, and skip the `make menuconfig` + `make` steps. Much faster.

Example flow (run these from Claude on the laptop):

```bash
# 1. Download the latest release asset locally
curl -L -o klipper.uf2 https://github.com/wrbell/W26-Cobot-Axis/releases/latest/download/klipper.uf2

# 2. Copy to the Pi
scp klipper.uf2 w26-pi:~/

# 3. Put the board in BOOTSEL mode (physical — hold BOOTSEL, press RESET)

# 4. Flash from the Pi
ssh w26-pi "lsblk -f | grep RPI-RP2"                 # confirm mass-storage mount
ssh w26-pi "cp ~/klipper.uf2 /media/pi/RPI-RP2/ && sync"
```

The board reboots into Klipper firmware automatically.

---

## 10. Troubleshooting

### `w26-pi.local` doesn't resolve

- **macOS:** flush the DNS cache:

  ```bash
  sudo dscacheutil -flushcache
  sudo killall -HUP mDNSResponder
  ```

- **Windows without Bonjour:** `.local` won't resolve. Install Bonjour, or use `arp -a` to find the link-local IP and SSH to the IP directly.
- **After Internet Sharing is enabled:** the Pi's IP changes from `169.254.x.x` to `192.168.2.x` (macOS) or `192.168.137.x` (Windows). mDNS follows automatically, but a cached DNS entry may keep pointing at the old address — flush the cache as above.

### SSH hangs on connect

- Check link-local assignment on the laptop:
  - macOS: `ifconfig en0` (or `en7`, `en8` for USB adapters) — look for `inet 169.254.x.x`
  - Windows: `ipconfig` — look for "Autoconfiguration IPv4 Address" in the `169.254.x.x` range
- No 169.254 address? The interface is still waiting for DHCP. Modern OSes fall back to link-local after ~30 seconds. If it never falls back, the interface is down — check the cable and LEDs.
- Check the Pi itself came up — power LED solid, green activity LED blinking during boot. First boot takes 2–3 minutes.

### Pi has no internet after Internet Sharing / ICS

- Confirm sharing is actually enabled (macOS: the Sharing panel shows **On**; Windows: the WiFi adapter's Properties → Sharing tab still has the checkbox set).
- Confirm the right adapter pair: share **from** the interface with internet (WiFi) **to** the ethernet adapter connected to the Pi.
- On the Pi: `ip route` should show a default route (`default via 192.168.2.1` on macOS, `default via 192.168.137.1` on Windows). If there's no default route, the Pi didn't pick up DHCP — reboot the Pi or force a renew.
- Check DNS: `ssh w26-pi "cat /etc/resolv.conf"` should show at least one nameserver. If it's empty, set one temporarily with `sudo echo 'nameserver 8.8.8.8' | sudo tee /etc/resolv.conf`.
- VPN interference — disconnect any active VPN on the laptop.

### `ssh: Host key verification failed` after sharing is enabled

The Pi's IP changed, but the host key didn't. SSH stores known_hosts by hostname (`w26-pi.local`), so you shouldn't see this for the hostname — but if you SSH'd by IP earlier (e.g. `ssh pi@169.254.103.47`), that entry is now stale. Remove just the old IP entry:

```bash
ssh-keygen -R 169.254.103.47        # replace with the old IP you used
```

Don't blanket-delete `~/.ssh/known_hosts` — that loses every other system you've connected to.

### `deploy.sh` or `dev-sync.sh` fails with "permission denied (publickey)"

SSH key auth isn't set up yet. Either run through Step 8.1 again (`ssh-copy-id`), or run the script with password auth by first confirming you can log in interactively: `ssh pi@w26-pi.local`. If that works, key auth is the only gap — fix it once and both scripts stop prompting.

### Claude Code keeps asking permission for every SSH command

Run the `/fewer-permission-prompts` skill after your first session. If the skill isn't available in your Claude install, hand-edit `.claude/settings.local.json` with the allowlist from §8.1.

### mDNS fully blocked (corporate firewall on the laptop, weird network stack)

Fall back to link-local IP addressing:

```bash
# Pre-Internet-Sharing:
ssh pi@169.254.x.x

# Post-Internet-Sharing (macOS):
ssh pi@192.168.2.x

# Post-Internet-Sharing (Windows):
ssh pi@192.168.137.x
```

Find the exact IP with `arp -a` on the laptop after pinging `w26-pi`. Add an entry to `~/.ssh/config` if you end up using the IP repeatedly.

---

## Related Guides

| Guide | Purpose |
|-------|---------|
| [SETUP.md](../SETUP.md) | Full switch-based Pi setup — pick up at §4 once SSH works |
| [DEVELOPMENT.md](../DEVELOPMENT.md) | Local dev/test environment (no hardware needed) |
| [docs/dev_bench_guide.md](dev_bench_guide.md) | Dev bench bring-up with URSim on Windows |
| [scripts/dev-sync.sh](../scripts/dev-sync.sh) | Fast rsync from laptop to Pi + service restart |
| [deploy.sh](../deploy.sh) | Full idempotent deploy script |
