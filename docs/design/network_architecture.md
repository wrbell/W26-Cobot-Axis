# Network Architecture Plan

> **Project:** W26 Cobot Axis -- ME472 Mechatronics Capstone
> **Author:** Willem (Software/EE)
> **Date:** 2026-02-12
> **Status:** Design -- not yet implemented

This document specifies the Ethernet network architecture for the W26 Cobot Axis system. It covers physical topology, IP addressing, port allocation, device configuration, firewall rules, hostname resolution, troubleshooting, and security considerations.

**Scope:** All TCP/IP-networked devices. The USB serial link between the Pi and SKR Pico, and the klippy Unix domain socket (`/tmp/klippy_uds`), are local to the Pi and are not covered here -- see `docs/design/deployment.md` for those.

---

## Table of Contents

1. [Network Topology](#1-network-topology)
2. [IP Addressing Scheme](#2-ip-addressing-scheme)
3. [Port Map](#3-port-map)
4. [UR30 Network Configuration](#4-ur30-network-configuration)
5. [Pi Network Configuration](#5-pi-network-configuration)
6. [Firewall Considerations](#6-firewall-considerations)
7. [DNS and Hostname Resolution](#7-dns-and-hostname-resolution)
8. [Troubleshooting](#8-troubleshooting)
9. [Security Notes](#9-security-notes)

---

## 1. Network Topology

### 1.1 Physical Topology

All networked devices connect to a single unmanaged gigabit Ethernet switch. An optional uplink to the university lab network provides internet access for package updates and remote monitoring.

```
                     University Lab Network
                     (DHCP, internet access)
                              |
                              | (optional uplink)
                              |
              +===============================+
              |     Gigabit Ethernet Switch    |
              |       (unmanaged, 5+ port)    |
              +==+=========+=========+========+
                 |         |         |
                 |         |         |
           +-----+    +---+---+    +---+----+
           | UR30 |    |  Pi   |    | Pi400  |
           | Ctrl |    |(headl)|    | (HMI)  |
           +------+    +---+---+    +--------+
         192.168.1.100   192.168.1.50  192.168.1.51
          (static)       (static)     (DHCP or static)
                           |
                      USB Serial
                           |
                      +---------+
                      |SKR Pico |  (not on Ethernet;
                      |(RP2040) |   local to Pi only)
                      +---------+
```

### 1.2 Logical Connections

```
Pi400 (HMI/dev)                      UR30 Controller
  |                                       |
  |--SSH (tcp/22)---->  Pi                |
  |--HTTP (tcp/80)--->  Pi (Mainsail)     |
  |--WS (tcp/7125)-->  Pi (Moonraker)    |
  |                     |                 |
  |                     |<--RTDE (tcp/30004)---|
  |                     |                 |
  |--Dashboard-------->|-------(tcp/29999)---|
  |  (optional)                           |
  |                                       |
  Pi (bridge daemon)                      |
  |--RTDE client (tcp/30004)------------>|
  |--Dashboard client (tcp/29999)------->|  (optional, for power-on automation)
  |                                       |
  Pi (Klipper)                            |
  |--USB serial-----> SKR Pico            |
  |--Unix socket----> /tmp/klippy_uds     |
```

### 1.3 Network Segment

All devices reside on a single flat Layer 2 segment: `192.168.1.0/24`. No VLANs, no routing between subnets. The switch is unmanaged and requires no configuration. Any 5-port (or larger) gigabit switch is sufficient -- there are no special requirements for QoS, IGMP, or spanning tree.

**Minimum switch port count:** 3 (UR30, Pi, Pi400). A 5-port switch is recommended to leave room for a laptop or additional diagnostic device.

---

## 2. IP Addressing Scheme

### 2.1 Address Allocation

| Device | Hostname | IP Address | Assignment | MAC (example) | Notes |
|--------|----------|-----------|------------|---------------|-------|
| UR30 Controller | ur30 | 192.168.1.100 | Static (set on teach pendant) | -- | Must not change; hardcoded in `src/bridge/config.py` |
| Pi (headless) | w26-pi | 192.168.1.50 | Static (set in OS config) | -- | Klipper host + RTDE bridge |
| Pi400 (HMI) | w26-pi400 | 192.168.1.51 | DHCP or static | -- | Optional; system works without it |
| Gateway / router | -- | 192.168.1.1 | -- | -- | Only needed if lab uplink exists |

### 2.2 Subnet Configuration

| Parameter | Value |
|-----------|-------|
| Network | 192.168.1.0/24 |
| Subnet mask | 255.255.255.0 |
| Usable host range | 192.168.1.1 -- 192.168.1.254 |
| Default gateway | 192.168.1.1 (if lab uplink present; omit if isolated) |
| DNS servers | 192.168.1.1 (lab router) or none (use `/etc/hosts` on Pi) |

### 2.3 Static vs. DHCP Decision

| Device | Recommendation | Rationale |
|--------|---------------|-----------|
| UR30 | **Static** (always) | The bridge daemon connects to this IP. Changing it requires editing `config.py` and restarting the bridge. A fixed IP eliminates a class of failure modes. |
| Pi | **Static** (production) / DHCP (development) | The Pi400 and any monitoring tools connect to the Pi by IP. A static IP simplifies SSH bookmarks and Mainsail browser bookmarks. During early development, DHCP is acceptable if mDNS is working (`w26-pi.local`). |
| Pi400 | **DHCP** (acceptable) | The Pi400 initiates all connections (SSH, HTTP); nothing connects *to* it. DHCP is fine. A static IP is preferred if SSH from the Pi back to the Pi400 is ever needed. |

### 2.4 Reserved Address Ranges

To avoid conflicts with lab equipment or DHCP pools, the W26 project uses addresses in the `.50`--`.59` and `.100` ranges:

| Range | Purpose |
|-------|---------|
| 192.168.1.1 | Lab gateway (if present) |
| 192.168.1.2 -- 192.168.1.49 | Available for lab DHCP pool |
| 192.168.1.50 -- 192.168.1.59 | W26 project devices (Pi, Pi400, future) |
| 192.168.1.100 | UR30 controller |
| 192.168.1.101 -- 192.168.1.254 | Available / lab equipment |

---

## 3. Port Map

### 3.1 TCP Ports Used

| Port | Protocol | Listener | Initiator | Purpose | Direction (from Pi perspective) |
|------|----------|----------|-----------|---------|-------------------------------|
| 30004 | TCP | UR30 | Pi (bridge daemon) | RTDE real-time data exchange, 500 Hz | Outbound |
| 29999 | TCP | UR30 | Pi or Pi400 | UR Dashboard Server (power on/off, program load) | Outbound |
| 7125 | TCP | Pi (Moonraker) | Pi400 (Mainsail JS) | Moonraker HTTP/WebSocket API | Inbound |
| 80 | TCP | Pi (nginx) | Pi400 (browser) | Mainsail web UI (static files served by nginx) | Inbound |
| 22 | TCP | Pi (sshd) | Pi400 (ssh client) | SSH remote shell access | Inbound |
| 22 | TCP | Pi400 (sshd) | Pi (optional) | SSH reverse access (rarely needed) | Outbound |

### 3.2 Local-Only Interfaces (Not on Network)

| Interface | Type | Endpoint | Purpose |
|-----------|------|----------|---------|
| `/tmp/klippy_uds` | Unix domain socket | Pi localhost | Bridge daemon to Klipper communication |
| USB serial (`/dev/serial/by-id/usb-Klipper_rp2040_*`) | USB CDC-ACM | Pi to SKR Pico | Klipper MCU protocol |

These never traverse the Ethernet network and do not require firewall rules or IP configuration.

### 3.3 UR30 Ports Reference

The UR30 controller exposes several TCP services. Only RTDE and Dashboard are used in the W26 system, but all are documented here for completeness and troubleshooting.

| Port | Service | Used by W26? | Notes |
|------|---------|-------------|-------|
| 30004 | RTDE | **Yes** (primary) | Real-time bidirectional data at 500 Hz |
| 29999 | Dashboard Server | **Optional** | Text-based robot lifecycle commands |
| 30001 | Primary Interface | No | 10 Hz state stream + URScript injection |
| 30002 | Secondary Interface | No | Same as Primary on a separate port |
| 30003 | Real-Time Interface | No | 500 Hz state stream, output-only |
| 502 | Modbus TCP | No | Industrial PLC integration |
| 50000 | XML-RPC (via URScript) | No | URScript `rpc_factory()` callbacks |

### 3.4 Moonraker / Mainsail Ports

Moonraker listens on port 7125 for both HTTP REST and WebSocket connections. Mainsail is a static single-page application served by nginx on port 80. When a browser on the Pi400 loads `http://192.168.1.50/`, nginx serves the Mainsail JavaScript, which then opens a WebSocket to `ws://192.168.1.50:7125/websocket` for live Klipper status.

**Traffic flow:**

```
Pi400 Browser
  |
  |-- GET http://192.168.1.50/ ------> Pi nginx (port 80) --> Mainsail static files
  |
  |-- WS  ws://192.168.1.50:7125/websocket --> Pi Moonraker (port 7125) --> klippy UDS
```

### 3.5 UDP Ports

| Port | Protocol | Purpose | Notes |
|------|----------|---------|-------|
| 5353 | UDP (mDNS) | Avahi/Bonjour hostname resolution | `w26-pi.local` resolves via multicast DNS |

No other UDP traffic is expected in normal operation.

---

## 4. UR30 Network Configuration

### 4.1 Setting the UR30 IP Address

The UR30's IP is configured via the teach pendant:

1. Power on the UR30 and wait for PolyScope to load.
2. Navigate to **Settings** (hamburger menu, top-right) -> **System** -> **Network**.
3. Select the Ethernet interface.
4. Set the method to **Static**.
5. Enter:
   - **IP Address:** `192.168.1.100`
   - **Subnet Mask:** `255.255.255.0`
   - **Gateway:** `192.168.1.1` (or leave blank if no internet needed)
   - **DNS:** `192.168.1.1` (or leave blank)
6. Tap **Apply**.
7. The controller may require a restart for network changes to take effect.

### 4.2 Which Ethernet Port

The UR30 controller box has a single Ethernet port (RJ45) on the rear panel. Connect this to the gigabit switch with a Cat5e or Cat6 cable.

**Cable notes:**
- Use Cat5e or Cat6 for gigabit speeds.
- Cable length up to 100 meters is fine per Ethernet specifications.
- If the switch is inside the UR30's enclosure or mounted nearby, a short (0.3m--1m) patch cable is sufficient.

### 4.3 Verifying UR30 Network

From the Pi, verify connectivity to the UR30:

```bash
# Basic connectivity
ping -c 3 192.168.1.100

# RTDE port open
nc -zv 192.168.1.100 30004

# Dashboard port open
nc -zv 192.168.1.100 29999
```

From the teach pendant, the network settings page shows the current IP, link status, and speed.

### 4.4 UR30 Network Behavior

- The UR30 controller acts as a **server** for RTDE (port 30004) and Dashboard (port 29999). The Pi connects to it; the UR30 does not initiate connections to external devices.
- RTDE allows only **one active synchronization** per TCP connection, but multiple connections can be open simultaneously.
- If the RTDE client disconnects, the UR30 continues running its program. No robot motion is interrupted by a client disconnect. The robot uses the last received input register values until a new client connects.
- The UR30 does not support DHCP by default in all firmware versions. Always use a static IP.

---

## 5. Pi Network Configuration

### 5.1 Static IP via dhcpcd (MainsailOS / older Raspberry Pi OS)

MainsailOS and older Raspberry Pi OS releases use `dhcpcd` for network management. Add the following to `/etc/dhcpcd.conf`:

```bash
# W26 Cobot Axis -- Static IP for headless Pi
interface eth0
static ip_address=192.168.1.50/24
static routers=192.168.1.1
static domain_name_servers=192.168.1.1
```

Apply the change:

```bash
sudo systemctl restart dhcpcd
```

Verify:

```bash
ip addr show eth0
# Should show: inet 192.168.1.50/24
```

### 5.2 Static IP via NetworkManager (Raspberry Pi OS Bookworm)

Raspberry Pi OS Bookworm uses NetworkManager by default. Configure a static IP with `nmcli`:

```bash
sudo nmcli con mod "Wired connection 1" \
    ipv4.method manual \
    ipv4.addresses 192.168.1.50/24 \
    ipv4.gateway 192.168.1.1 \
    ipv4.dns 192.168.1.1

sudo nmcli con up "Wired connection 1"
```

To find the connection name if it differs:

```bash
nmcli con show
```

Verify:

```bash
ip addr show eth0
```

### 5.3 Static IP via Netplan (Ubuntu-based images)

If using an Ubuntu-based image on the Pi, configure via `/etc/netplan/01-w26.yaml`:

```yaml
network:
  version: 2
  ethernets:
    eth0:
      dhcp4: false
      addresses:
        - 192.168.1.50/24
      routes:
        - to: default
          via: 192.168.1.1
      nameservers:
        addresses:
          - 192.168.1.1
```

Apply:

```bash
sudo netplan apply
```

### 5.4 DHCP with Reservation (Alternative)

If using DHCP for simplicity during development, configure a DHCP reservation on the lab router so the Pi always receives `192.168.1.50`. This requires access to the router's DHCP settings and the Pi's MAC address:

```bash
# Find the Pi's MAC address:
ip link show eth0 | grep ether
```

### 5.5 Pi400 Network Configuration

The Pi400 is optional and does not require a specific IP. It can use DHCP. If a static IP is desired, use `192.168.1.51` with the same methods described above.

---

## 6. Firewall Considerations

### 6.1 Default State

Raspberry Pi OS and MainsailOS do **not** enable a firewall by default. All ports are open to the local network. In a lab environment with a dedicated switch, this is acceptable for development.

### 6.2 If a Firewall Is Enabled

If `ufw` (Uncomplicated Firewall) or `iptables` rules are added to the Pi, the following rules are required:

**Inbound (traffic arriving at the Pi):**

| Port | Protocol | Source | Purpose | Rule |
|------|----------|--------|---------|------|
| 22 | TCP | 192.168.1.0/24 | SSH | `sudo ufw allow from 192.168.1.0/24 to any port 22` |
| 80 | TCP | 192.168.1.0/24 | Mainsail web UI | `sudo ufw allow from 192.168.1.0/24 to any port 80` |
| 7125 | TCP | 192.168.1.0/24 | Moonraker API | `sudo ufw allow from 192.168.1.0/24 to any port 7125` |
| 5353 | UDP | 224.0.0.251 (multicast) | mDNS | `sudo ufw allow 5353/udp` |

**Outbound (traffic leaving the Pi):**

| Port | Protocol | Destination | Purpose | Rule |
|------|----------|-------------|---------|------|
| 30004 | TCP | 192.168.1.100 | RTDE | Outbound is allowed by default in ufw |
| 29999 | TCP | 192.168.1.100 | Dashboard | Outbound is allowed by default in ufw |

**Example ufw setup:**

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from 192.168.1.0/24 to any port 22 proto tcp
sudo ufw allow from 192.168.1.0/24 to any port 80 proto tcp
sudo ufw allow from 192.168.1.0/24 to any port 7125 proto tcp
sudo ufw allow 5353/udp
sudo ufw enable
```

### 6.3 Lab Network Isolation

The W26 system should ideally be on its own physical switch, separate from the university's general network. If the switch has an uplink to the lab network (for internet access and remote SSH), be aware that:

- **Moonraker (port 7125) and Mainsail (port 80) have no authentication by default.** Anyone on the same network can send G-code to Klipper. This is acceptable on an isolated lab switch but is a risk if connected to a campus network.
- **SSH (port 22) uses password authentication by default.** Switch to key-based authentication if the Pi is reachable from a broader network (see Section 9).
- **The UR30 has no authentication on any of its TCP interfaces.** Anyone who can reach ports 30004, 29999, 30001, or 30002 can control the robot. The UR30 must be on a trusted network.

**Recommended topology:**

```
Campus Network (untrusted)
       |
   [Lab Router / Firewall]  <-- NAT or firewall here
       |
  [W26 Gigabit Switch]     <-- All W26 devices here, isolated
       |       |       |
     UR30     Pi    Pi400
```

If no lab router is available, use the switch without an uplink (fully isolated). Internet access on the Pi can be provided temporarily via Wi-Fi for package updates, then disabled.

---

## 7. DNS and Hostname Resolution

### 7.1 mDNS (.local Hostnames)

The Pi and Pi400 both run Avahi (mDNS/DNS-SD daemon), which is installed by default on Raspberry Pi OS and MainsailOS. This enables `.local` hostname resolution without a DNS server:

| Hostname | Resolves To | Used For |
|----------|-------------|----------|
| `w26-pi.local` | 192.168.1.50 | SSH from Pi400, Mainsail in browser |
| `w26-pi400.local` | 192.168.1.51 | SSH from Pi to Pi400 (optional) |

**Setting the hostname on the Pi:**

```bash
sudo hostnamectl set-hostname w26-pi
```

After reboot, the Pi advertises `w26-pi.local` via mDNS.

**Limitations of mDNS:**

- The UR30 **does not support mDNS**. It cannot resolve `.local` hostnames. Always use the numeric IP (`192.168.1.50`) in URScript and in `config.py`.
- mDNS requires multicast traffic. If the switch blocks multicast (some managed switches do by default), mDNS will fail. Unmanaged switches pass multicast traffic transparently.
- mDNS resolution can take 1--3 seconds on first lookup. This is fine for SSH and browser access but should not be used in the real-time data path.

### 7.2 /etc/hosts (Static Hostname Mapping)

As a belt-and-suspenders approach, add static entries to `/etc/hosts` on both the Pi and Pi400:

**On the Pi (`/etc/hosts`):**

```
127.0.0.1       localhost
::1             localhost

192.168.1.100   ur30
192.168.1.50    w26-pi
192.168.1.51    w26-pi400
```

**On the Pi400 (`/etc/hosts`):**

```
127.0.0.1       localhost
::1             localhost

192.168.1.100   ur30
192.168.1.50    w26-pi
192.168.1.51    w26-pi400
```

This allows using short names like `ssh pi@w26-pi` or `ping ur30` even if mDNS is not working.

### 7.3 Recommendation

| Context | Resolution Method |
|---------|-------------------|
| Bridge daemon connecting to UR30 | **Numeric IP** (`192.168.1.100`) in `config.py`. Never use hostnames in the real-time path. |
| SSH from Pi400 to Pi | **mDNS** (`w26-pi.local`) or numeric IP. Either works. |
| Mainsail in browser (Pi400) | **mDNS** (`http://w26-pi.local/`) or numeric IP (`http://192.168.1.50/`). Bookmark the numeric IP as a fallback. |
| URScript socket functions (if used) | **Numeric IP** only. URScript does not resolve hostnames. |

---

## 8. Troubleshooting

### 8.1 Cannot Reach UR30 from Pi

**Symptom:** `ping 192.168.1.100` fails or `nc -zv 192.168.1.100 30004` times out.

| Check | Command | Expected |
|-------|---------|----------|
| Pi has correct IP | `ip addr show eth0` | Shows `192.168.1.50/24` |
| Pi has link up | `ip link show eth0` | Shows `state UP` |
| Ethernet cable connected | `ethtool eth0` | Shows `Link detected: yes` |
| UR30 is powered on | Visual check | Teach pendant shows PolyScope |
| UR30 is on correct subnet | Teach pendant: Settings > System > Network | Shows `192.168.1.100/24` |
| Switch has link on both ports | LED indicators on switch | Solid/blinking link LEDs for both ports |
| ARP table shows UR30 | `arp -n` or `ip neigh` | Entry for `192.168.1.100` |

**Common causes:**

- **Wrong subnet:** The UR30 is on `192.168.0.x` instead of `192.168.1.x` (or vice versa). Both devices must be on the same `/24` subnet.
- **Cable issue:** Try a different Ethernet cable. Check that both ends are fully seated.
- **UR30 not fully booted:** The UR30 takes 60--90 seconds to boot. The network interface may not respond during early boot.
- **IP conflict:** Another device on the network has `192.168.1.100`. Check with `arping -D 192.168.1.100`.

### 8.2 RTDE Connection Timeout

**Symptom:** Bridge daemon logs `RTDE connection failed` or `Connection timed out` repeatedly.

| Check | Command | Expected |
|-------|---------|----------|
| Port 30004 is reachable | `nc -zv 192.168.1.100 30004` | `Connection to 192.168.1.100 30004 port [tcp/*] succeeded!` |
| UR30 program is running | Teach pendant | Program state: Running |
| RTDE is not disabled | Teach pendant: Settings > System > Remote Control | RTDE enabled |
| No other RTDE client connected | Check for other running instances | Only one bridge daemon should run |

**Common causes:**

- **UR30 program not running:** RTDE data streaming only starts when a URScript program calls `sync()` in a loop. If no program is running, the RTDE connection succeeds but no data flows.
- **RTDE disabled in UR settings:** Some UR configurations disable remote control. Check Settings > System > Remote Control on the teach pendant.
- **Firewall on the Pi blocking outbound:** Check `sudo ufw status` -- outbound should be allowed.
- **ur-rtde library version mismatch:** Ensure the `ur-rtde` Python package version is compatible with the UR30's firmware version. RTDE protocol version 2 is used by all e-Series firmware >= 5.0.

### 8.3 Moonraker / Mainsail Unreachable from Pi400

**Symptom:** `http://192.168.1.50/` does not load in the Pi400's browser.

| Check | Command (on Pi400) | Expected |
|-------|---------------------|----------|
| Pi is reachable | `ping 192.168.1.50` | Replies |
| Port 80 open on Pi | `nc -zv 192.168.1.50 80` | Succeeded |
| Port 7125 open on Pi | `nc -zv 192.168.1.50 7125` | Succeeded |
| nginx running on Pi | `ssh pi@w26-pi systemctl status nginx` | Active |
| Moonraker running on Pi | `ssh pi@w26-pi systemctl status moonraker` | Active |

**Common causes:**

- **nginx not installed or not running:** MainsailOS includes nginx. If using a manual install, ensure `sudo apt-get install nginx` was run and the Mainsail static files are deployed.
- **Moonraker authorization:** If Moonraker's `[authorization]` section does not include `192.168.1.0/24` in `trusted_clients`, the Pi400 may be blocked. See `moonraker.conf`:

  ```ini
  [authorization]
  trusted_clients:
      127.0.0.1
      192.168.1.0/24
  ```

- **Browser WebSocket issue:** Mainsail connects via WebSocket to port 7125. If port 80 works but the Mainsail UI shows "Moonraker not connected," the WebSocket connection (port 7125) is failing. Check the browser developer console for errors.

### 8.4 SSH Connection Refused

**Symptom:** `ssh pi@192.168.1.50` returns `Connection refused`.

| Check | Notes |
|-------|-------|
| SSH enabled on Pi? | SSH must be enabled during OS imaging (Raspberry Pi Imager settings) or by placing an empty file named `ssh` on the boot partition |
| sshd running? | If you have console access: `sudo systemctl enable ssh && sudo systemctl start ssh` |
| Correct username? | MainsailOS default user is `pi`. Raspberry Pi OS Bookworm requires setting a username during imaging. |

### 8.5 mDNS (.local) Not Resolving

**Symptom:** `ping w26-pi.local` fails but `ping 192.168.1.50` works.

| Check | Notes |
|-------|-------|
| Avahi running on Pi? | `systemctl status avahi-daemon` -- should be active |
| Pi400 supports mDNS? | Linux: needs `avahi-daemon` and `libnss-mdns`. macOS: built-in. Windows: needs Bonjour. |
| Multicast not blocked? | Unmanaged switches pass multicast. Some managed switches block it by default. |
| Correct hostname set? | `hostnamectl` on the Pi should show `w26-pi` |

**Workaround:** Use numeric IPs in `/etc/hosts` as described in Section 7.2.

### 8.6 Network Performance Issues

**Symptom:** RTDE data arrives late or with jitter, causing inconsistent extrusion.

| Check | Tool | Expected |
|-------|------|----------|
| Link speed is gigabit | `ethtool eth0` | `Speed: 1000Mb/s` |
| No packet loss | `ping -c 1000 -i 0.002 192.168.1.100` | 0% packet loss |
| No excessive latency | `ping -c 100 192.168.1.100` | avg < 1 ms |
| Switch not overloaded | Check switch port LEDs | No collision/error LEDs |
| No bandwidth hog on the network | `iftop` on Pi | RTDE traffic should be < 1 Mbps |

**RTDE bandwidth estimate:** At 500 Hz with a typical recipe of ~200 bytes per packet, RTDE consumes approximately `200 * 500 = 100 KB/s = 0.8 Mbps`. This is negligible on gigabit Ethernet. Network congestion is extremely unlikely to be the cause of latency issues.

---

## 9. Security Notes

### 9.1 Threat Model

This is a **university lab network**, not an internet-facing deployment. The threat model assumes:

- **Physical access is controlled.** Only team members and lab personnel can physically access the switch, Pi, and UR30.
- **The switch is not connected to the internet** (or only via a NAT router with no port forwarding). No inbound connections from the internet reach any W26 device.
- **Trust boundary:** All devices on the W26 switch are trusted. The UR30, Pi, and Pi400 all trust each other.
- **The adversary is accidental misconfiguration, not malicious attack.** The primary risks are IP conflicts, accidental G-code injection from another lab computer, or leaving services exposed if the switch is connected to a wider network.

### 9.2 No Authentication on UR30

The UR30 does not authenticate RTDE, Dashboard, or Primary/Secondary interface connections. **Anyone who can reach the UR30's IP on the network can:**

- Read all robot state data (joint positions, TCP pose, I/O states)
- Write to input registers (which URScript reads)
- Send Dashboard commands (power on/off, load/play/stop programs)
- Inject URScript commands via the Primary/Secondary interface

**Mitigation:** Keep the UR30 on an isolated switch. Do not connect the switch to a campus network without a firewall.

### 9.3 No Authentication on Moonraker (Default)

Moonraker uses `trusted_clients` (IP-based allowlisting) rather than username/password or token authentication. Any device on the allowed subnet can:

- Send G-code to Klipper (including `M112` emergency stop)
- Modify `printer.cfg`
- Restart Klipper

**Mitigation:** Limit `trusted_clients` in `moonraker.conf` to the project subnet (`192.168.1.0/24`). If the switch is connected to a broader network, restrict to specific IPs:

```ini
[authorization]
trusted_clients:
    127.0.0.1
    192.168.1.50
    192.168.1.51
```

### 9.4 SSH Hardening (Optional)

For a lab project, password-based SSH is acceptable. If the Pi will be accessible from a broader network, consider:

1. **Key-based authentication:**
   ```bash
   # On Pi400, generate a key pair:
   ssh-keygen -t ed25519 -C "w26-pi400"

   # Copy public key to Pi:
   ssh-copy-id pi@192.168.1.50

   # Then on Pi, disable password auth:
   # Edit /etc/ssh/sshd_config:
   #   PasswordAuthentication no
   sudo systemctl restart ssh
   ```

2. **Fail2ban** for brute-force protection:
   ```bash
   sudo apt-get install fail2ban
   ```

3. **Change the default password** from the Raspberry Pi OS default. (Raspberry Pi OS Bookworm and MainsailOS require setting a password during imaging, so there is no "default" password, but verify this.)

### 9.5 Trust Summary

| Connection | Authentication | Encryption | Risk | Acceptable? |
|------------|---------------|------------|------|-------------|
| RTDE (Pi -> UR30) | None | None (plaintext TCP) | Anyone on subnet can impersonate the bridge | Yes, on isolated switch |
| Dashboard (Pi/Pi400 -> UR30) | None | None | Anyone on subnet can power-cycle the robot | Yes, on isolated switch |
| SSH (Pi400 -> Pi) | Password or key | Encrypted (SSH) | Brute-force if weak password | Yes, with a reasonable password |
| Moonraker (Pi400 -> Pi) | IP allowlist | None (plaintext HTTP/WS) | Anyone on allowed subnet can send G-code | Yes, with restricted `trusted_clients` |
| Mainsail (Pi400 -> Pi) | None | None (plaintext HTTP) | Static files, no write access | Yes |

### 9.6 Recommendations

1. **Keep the W26 switch isolated from the campus network** unless internet access is specifically needed.
2. **If internet access is needed**, connect the switch uplink through a NAT router or lab firewall. Do not bridge the W26 switch directly into a campus VLAN.
3. **Do not expose ports 7125, 80, or 22 to the internet.** There is no reason for any W26 service to be internet-accessible.
4. **Change the default `pi` user password** during OS imaging.
5. **Document the UR30's IP prominently** (e.g., label on the controller box) so it is not accidentally reconfigured.

---

## Appendix A: Quick Reference Card

```
NETWORK:          192.168.1.0/24  (single flat subnet)
SWITCH:           Unmanaged gigabit, 5+ ports

UR30:             192.168.1.100   (static, set on teach pendant)
                  Ports: 30004 (RTDE), 29999 (Dashboard)

Pi (headless):    192.168.1.50    (static, set in /etc/dhcpcd.conf or nmcli)
  hostname:       w26-pi
  Ports IN:       22 (SSH), 80 (Mainsail), 7125 (Moonraker)
  Ports OUT:      30004 (RTDE to UR30), 29999 (Dashboard to UR30)
  Local only:     /tmp/klippy_uds (Unix socket), USB serial to SKR Pico

Pi400 (HMI):     192.168.1.51    (DHCP or static)
  hostname:       w26-pi400
  Ports OUT:      22 (SSH to Pi), 80 (Mainsail), 7125 (Moonraker)

VERIFY:           ping 192.168.1.100     (UR30 reachable?)
                  nc -zv 192.168.1.100 30004  (RTDE port open?)
                  nc -zv 192.168.1.50 7125    (Moonraker reachable?)
                  ssh pi@w26-pi.local         (SSH works?)
```

---

## Appendix B: Cable and Hardware Checklist

| Item | Quantity | Specification | Notes |
|------|----------|--------------|-------|
| Gigabit Ethernet switch | 1 | 5-port, unmanaged | TP-Link TL-SG105 or similar |
| Cat5e/Cat6 Ethernet cable | 3 | Appropriate length for bench layout | UR30 to switch, Pi to switch, Pi400 to switch |
| USB-C cable | 1 | Data-capable (not charge-only) | Pi to SKR Pico |

---

*This document is a design specification for the W26 Cobot Axis network architecture. Implementation should be carried out during Phase 3 (Build) in conjunction with the deployment procedures described in `docs/design/deployment.md`.*
