from textual.app import App
from textual.binding import Binding

from ..zfs import get_system_status
from .screens import DashboardScreen

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
        self.set_interval(self.interval, self.action_refresh_data)

    def action_refresh_data(self):
        all_pools = get_system_status()
        
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
