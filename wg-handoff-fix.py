#!/usr/bin/env python3
# Fix: when useActive is true, bindAny returns early without binding the WG
# UDP socket to any network. After WiFi->cell handoff the socket has no route.
# Fix: bind to cm.activeNetwork instead of skipping.
import sys, pathlib, re

path = pathlib.Path(sys.argv[1])
src = path.read_text()

OLD = """            if (curnet?.useActive == true) {
                logd("bind: use active network is true, who: $who, addr: $addrPort, fd: $fid")
                Logger.vv(LOG_TAG_VPN, "bindAny: execution time: ${elapsedRealtime() - startTime} ms (active nw path)")
                return
            }"""

NEW = """            if (curnet?.useActive == true) {
                logd("bind: use active network is true, who: $who, addr: $addrPort, fd: $fid")
                // Fix: bind to the active network instead of skipping - without this,
                // WireGuard UDP sockets float unbound and lose their route after WiFi->cell handoff.
                val activeNw = cm.activeNetwork
                if (activeNw != null && pfd != null) {
                    val ok = bindToNw(activeNw, pfd, fid)
                    Logger.i(LOG_TAG_VPN, "bind: active nw fallback, who: $who, fd: $fid, ok: $ok")
                }
                Logger.vv(LOG_TAG_VPN, "bindAny: execution time: ${elapsedRealtime() - startTime} ms (active nw path)")
                return
            }"""

if NEW.strip() in src:
    print("already patched"); sys.exit(0)
if OLD not in src:
    print("ERROR: anchor not found in BraveVPNService.kt"); sys.exit(1)

path.write_text(src.replace(OLD, NEW, 1))
print("patched:", path)
