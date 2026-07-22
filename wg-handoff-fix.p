#!/usr/bin/env python3
# Fix WiFi->cellular handoff: when wg13 is TNT after network change,
# use addWgProxy (full re-add with fresh sockets) instead of refreshWgProxy
# (lightweight refresh that doesn't rebind to the new network interface).
# Ref: GoVpnAdapter.kt "work around for now until the re-add logic is handled in go-tun"
import sys, pathlib

path = pathlib.Path(sys.argv[1])
src = path.read_text()

OLD = "val avoidReaddingProxies = true"
NEW = "val avoidReaddingProxies = false"

if NEW in src:
    print("already patched"); sys.exit(0)
if OLD not in src:
    print("ERROR: anchor not found — check GoVpnAdapter.kt manually"); sys.exit(1)

path.write_text(src.replace(OLD, NEW, 1))
print("patched:", path)
