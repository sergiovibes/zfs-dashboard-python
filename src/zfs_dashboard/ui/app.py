from textual.app import App
from textual.binding import Binding

from ..zfs import get_static_data, parse_iostat_line
from .screens import DashboardScreen
import threading
import subprocess
import time

class IostatWorker(threading.Thread):
    def __init__(self, callback):
        super().__init__(daemon=True)
        self.callback = callback
        self.running = True
        
    def run(self):
        # Run zpool iostat -H -p -y 1
        # -H: Scripted mode (no headers, tabs)
        # -p: Parsable numbers
        # -y: Omit first report (since boot) - available in newer ZFS
        # If -y not supported, we just ignore the first line if it looks huge? 
        # Actually -y is best. If not available, we might see a big spike at start.
        # Let's assume -y is available or acceptable behavior.
        # We need to run it continuously.
        
        cmd = ['zpool', 'iostat', '-v', '-H', '-p', '-y', '1']
        
        # Fallback if -y is not supported?
        # Let's try running it.
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1 # Line buffered
            )
            
            while self.running and process.poll() is None:
                line = process.stdout.readline()
                if not line:
                    break
                
                stats = parse_iostat_line(line)
                if stats:
                    self.callback(stats)
                    
        except FileNotFoundError:
            pass # zpool not found
        except Exception as e:
            print(f"Iostat worker error: {e}")
        finally:
            if process:
                process.terminate()
                process.wait()

    def stop(self):
        self.running = False


class ZfsDashboardApp(App):
    CSS = """
    .left-pane {
        width: 50%;
        height: 100%;
        border-right: solid green;
    }
    .right-pane {
        width: 50%;
        height: 100%;
    }
    PoolOverview {
        height: auto;
        border-bottom: solid blue;
        padding: 1;
    }
    VdevList {
        height: 1fr;
    }
    DatasetTreeWidget {
        height: 60%;
        border-bottom: solid blue;
    }
    DatasetDetails {
        height: 40%;
    }
    .header {
        text-align: center;
        background: $accent;
        color: $text;
        width: 100%;
    }
    """

    BINDINGS = [
        Binding("f5", "refresh_data", "Refresh"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, interval: int = 5, pool_filter: str = None, dataset_filter: str = None):
        super().__init__()
        self.interval = interval
        self.pool_filter = pool_filter
        self.dataset_filter = dataset_filter
        self.pools = []

    def on_mount(self):
        self.action_refresh_data()
        # Start background worker
        self.worker = IostatWorker(self.update_iostat)
        self.worker.start()

    def on_unmount(self):
        if hasattr(self, 'worker'):
            self.worker.stop()

    def update_iostat(self, stats):
        # stats is tuple: (name, read_ops, write_ops, read_bytes, write_bytes)
        # We need to update the UI.
        # Since this is called from a thread, we must use call_from_thread
        self.call_from_thread(self._update_iostat_ui, stats)

    def _update_iostat_ui(self, stats):
        if self.screen and isinstance(self.screen, DashboardScreen):
            self.screen.update_iostat_data(stats)

    def action_refresh_data(self):
        all_pools = get_static_data()
        
        # Apply pool filter
        if self.pool_filter:
            self.pools = [p for p in all_pools if p.name == self.pool_filter]
        else:
            self.pools = all_pools
            
        # Apply dataset filter (regex)
        # We need to filter datasets within pools.
        # Since datasets are a tree, if a child matches, we might need to keep parents.
        # Or just filter the list?
        # The requirement says "regex filter to dataset list".
        # I'll pass this filter to the UI widgets or filter here.
        # Filtering here is cleaner for the model.
        
        if self.dataset_filter:
            import re
            try:
                pattern = re.compile(self.dataset_filter)
                for pool in self.pools:
                    # Filter datasets. This is tricky with tree structure.
                    # If we filter the flat list, we might break the tree if we rebuild it.
                    # But `pool.datasets` currently contains ROOTS of the tree.
                    # If I filter roots, I might lose children.
                    # Actually `pool.datasets` in `models.py` are roots?
                    # In `zfs.py`: `pool.datasets = [ds for ds in root_datasets if ds.name == pool.name]`
                    # Yes, usually just the root dataset.
                    
                    # So I need to traverse the tree and filter.
                    # Or I can pass the filter to the widget.
                    # Passing to widget is better because it can handle "match or has matching child" logic which I already implemented for search.
                    pass 
            except re.error:
                pass
        
        # If screen is not mounted, mount it
        if not self.screen or not isinstance(self.screen, DashboardScreen):
            screen = DashboardScreen(self.pools)
            if self.dataset_filter:
                screen.dataset_filter = self.dataset_filter
            self.push_screen(screen)
        else:
            # Update existing screen
            screen = self.screen
            screen.pools = self.pools
            if self.dataset_filter:
                screen.dataset_filter = self.dataset_filter
                
            if len(self.pools) > 1:
                screen.update_all_tab()
            for pool in self.pools:
                screen.update_pool_data(pool)
