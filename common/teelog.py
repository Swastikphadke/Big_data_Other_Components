"""Mirror everything a script prints to a log file (evidence), keeping console output."""
import sys
from datetime import datetime
from pathlib import Path


class _Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, s):
        for st in self.streams:
            st.write(s)
            st.flush()

    def flush(self):
        for st in self.streams:
            st.flush()


def start(path):
    """Call once at program start: header line with timestamp + command, then tee stdout."""
    if not path:
        return
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    f = open(path, "w", encoding="utf-8")
    f.write(f"### {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')} | $ python "
            + " ".join(sys.argv) + "\n")
    sys.stdout = _Tee(sys.stdout, f)
