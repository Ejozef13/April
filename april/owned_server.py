"""Linux native-widget backend: terminate if its owning UI process disappears."""
import ctypes
import os
import signal
import sys


def main():
    if sys.platform.startswith('linux'):
        parent=os.getppid()
        libc=ctypes.CDLL(None,use_errno=True)
        # PR_SET_PDEATHSIG: no fork-time Python hook in the multithreaded Qt app.
        if parent==1 or libc.prctl(1,signal.SIGTERM,0,0,0)!=0:
            raise SystemExit('Cannot establish owned backend lifecycle')
        if os.getppid()!=parent:
            raise SystemExit(0)
    from .server import main as serve
    serve()


if __name__=='__main__':main()
