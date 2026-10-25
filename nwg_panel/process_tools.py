"""Process helpers that import no GTK: also used by the tray watcher process, which runs without it."""
import sys


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def _die_with_parent():
    # Linux: have the child receive SIGTERM when the panel dies, so a restarted panel leaves no orphan
    try:
        import ctypes, signal
        ctypes.CDLL(None, use_errno=True).prctl(1, signal.SIGTERM)  # 1 = PR_SET_PDEATHSIG
    except Exception:
        pass
