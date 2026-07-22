#!/usr/bin/env python3
# Fix WiFi->cellular handoff for WireGuard in RethinkDNS.
#
# Root cause: bindAny() in BraveVPNService returns early without binding the
# WG UDP socket to any network in two cases:
#   1. nws.isEmpty() - cellular not yet in ipv4Net during the transition window
#   2. curnet?.useActive == true - the app tells itself "use active network" but
#      then immediately returns without actually binding to it
#
# Both cases leave the socket floating on 0.0.0.0 with no network binding.
# When WiFi dies, there is no route and sendto fails with "network is unreachable".
#
# Fix: in both early-return cases, attempt to bind to cm.activeNetwork before
# returning. If cm.activeNetwork is null or the bind fails, we fall through to
# the original behavior. No behavior change when cellular is not available.
import sys, pathlib

path = pathlib.Path(sys.argv[1])
src = path.read_text()

# Patch 1: nws.isEmpty() - add activeNetwork fallback before returning
OLD1 = '''        if (nws.isEmpty()) {
            Logger.w(LOG_TAG_VPN, "no network to bind, who: $who, fd: $fid, addr: $addrPort")
            Logger.vv(LOG_TAG_VPN, "bindAny: execution time: ${elapsedRealtime() - startTime} ms (nws empty)")
            return
        }'''

NEW1 = '''        if (nws.isEmpty()) {
            Logger.w(LOG_TAG_VPN, "no network to bind, who: $who, fd: $fid, addr: $addrPort")
            // Fix: nws may be empty during WiFi->cell transition window.
            // Try cm.activeNetwork directly before giving up.
            val activeNw = cm.activeNetwork
            if (activeNw != null) {
                try {
                    val tmpPfd = ParcelFileDescriptor.adoptFd(fid.toInt())
                    val ok = bindToNw(activeNw, tmpPfd, fid)
                    tmpPfd.detachFd()
                    Logger.i(LOG_TAG_VPN, "bind: nws-empty activeNw fallback, who: $who, fd: $fid, ok: $ok")
                    if (ok) {
                        Logger.vv(LOG_TAG_VPN, "bindAny: execution time: ${elapsedRealtime() - startTime} ms (nws-empty activeNw ok)")
                        return
                    }
                } catch (e: Exception) {
                    Logger.e(LOG_TAG_VPN, "bind: nws-empty activeNw fallback err: who: $who, fd: $fid, ${e.message}")
                }
            }
            Logger.vv(LOG_TAG_VPN, "bindAny: execution time: ${elapsedRealtime() - startTime} ms (nws empty)")
            return
        }'''

# Patch 2: useActive early return - bind to activeNetwork instead of bailing
OLD2 = '''            // who is not used, but kept for future use
            // binding to the underlying network is not working.
            // no need to bind if use active network is true
            if (curnet?.useActive == true) {
                logd("bind: use active network is true, who: $who, addr: $addrPort, fd: $fid")
                Logger.vv(LOG_TAG_VPN, "bindAny: execution time: ${elapsedRealtime() - startTime} ms (active nw path)")
                return
            }'''

NEW2 = '''            // who is not used, but kept for future use
            // Fix: bind to cm.activeNetwork instead of returning unbound.
            // The original comment said "binding to the underlying network is not working"
            // but an unbound socket loses its route on WiFi->cell handoff (network is unreachable).
            if (curnet?.useActive == true) {
                logd("bind: use active network is true, who: $who, addr: $addrPort, fd: $fid")
                val activeNw = cm.activeNetwork
                if (activeNw != null && pfd != null) {
                    val ok = bindToNw(activeNw, pfd, fid)
                    Logger.i(LOG_TAG_VPN, "bind: useActive activeNw fallback, who: $who, fd: $fid, ok: $ok")
                }
                Logger.vv(LOG_TAG_VPN, "bindAny: execution time: ${elapsedRealtime() - startTime} ms (active nw path)")
                return
            }'''

changed = False

if "nws-empty activeNw fallback" in src and "useActive activeNw fallback" in src:
    print("already patched"); sys.exit(0)

if OLD1 not in src:
    print("ERROR: patch 1 anchor (nws.isEmpty block) not found in BraveVPNService.kt")
    sys.exit(1)

if OLD2 not in src:
    print("ERROR: patch 2 anchor (useActive block) not found in BraveVPNService.kt")
    sys.exit(1)

src = src.replace(OLD1, NEW1, 1)
src = src.replace(OLD2, NEW2, 1)
path.write_text(src)
print("patched both nws.isEmpty and useActive blocks in:", path)
