#!/usr/bin/env python3
# Inserts s.sendObsMsg(Opn, nil) at the successful-return path of StdNetBind.Open()
# in firestack's wgconn.go, so latestOpen resets on every socket (re)bind and the
# WG proxy stops getting stuck in the TNT "zombie state" after a WiFi<->cell handoff.
# Ref: celzero/rethink-app#2602
import sys, re

path = sys.argv[1]
src = open(path).read()

if "sendObsMsg(Opn, nil)" in src and "proxy-health clock" in src:
    print("already patched"); sys.exit(0)

# Anchor: the len(fns)==0 guard that sits right before the successful return in Open().
anchor = re.search(
    r'(if\s+len\(fns\)\s*==\s*0\s*\{\s*\n\s*return\s+nil,\s*0,\s*syscall\.EAFNOSUPPORT\s*\n\s*\})',
    src)
if not anchor:
    print("ERROR: could not find the len(fns)==0 anchor in Open(). "
          "This firestack commit may differ; inspect wgconn.go's Open() manually.")
    sys.exit(1)

patch = (
    '\n\n\t// reset the proxy-health clock on every (re)bind. After a WiFi<->cellular'
    '\n\t// handoff the UDP sockets rebind here, but latestOpen was never bumped, so'
    '\n\t// post-handshake packets get judged against a stale timestamp and the tunnel'
    '\n\t// is wrongly flipped to TNT (the "zombie state"; celzero/rethink-app#2602).'
    '\n\t// Close() already emits Clo the same way under s.mu; Opn mirrors it and is'
    '\n\t// handled by the tun listener, which stores now() into latestOpen.'
    '\n\ts.sendObsMsg(Opn, nil)'
)
i = anchor.end()
src = src[:i] + patch + src[i:]
open(path, "w").write(src)
print("patched:", path)
