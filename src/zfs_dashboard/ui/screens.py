from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, TabbedContent, TabPane, Label
from textual.containers import Container, Horizontal, Vertical

from ..models import Pool, Dataset
from .widgets import PoolOverview, VdevList, DatasetTreeWidget, DatasetDetails

class DashboardScreen(Screen):
    def __init__(self, pools: list[Pool]):
        super().__init__()
        self.pools = pools
        self.dataset_filter = None

    def compose(self) -> ComposeResult:
        yield Header()
        
        if not self.pools:
            yield Label("No ZFS pools found.")
        else:
            initial_tab = f"tab-{self.pools[0].name}"
            if len(self.pools) > 1:
                initial_tab = "tab-all"
            
            with TabbedContent(initial=initial_tab):
                if len(self.pools) > 1:
                    with TabPane("All", id="tab-all"):
                        yield Horizontal(
                            Vertical(
                                PoolOverview(id="overview-all"),
                                VdevList(id="vdevs-all"),
                                classes="left-pane"
                            ),
                            Vertical(
                                DatasetTreeWidget(id="tree-all"),
                                DatasetDetails(id="details-all"),
                                classes="right-pane"
                            )
                        )

                for pool in self.pools:
                    with TabPane(pool.name, id=f"tab-{pool.name}"):
                        yield Horizontal(
                            Vertical(
                                PoolOverview(id=f"overview-{pool.name}"),
                                VdevList(id=f"vdevs-{pool.name}"),
                                classes="left-pane"
                            ),
                            Vertical(
                                DatasetTreeWidget(id=f"tree-{pool.name}"),
                                DatasetDetails(id=f"details-{pool.name}"),
                                classes="right-pane"
                            )
                        )
        
        yield Footer()

    def on_mount(self):
        # Populate initial data
        if len(self.pools) > 1:
            self.update_all_tab()
            
        for pool in self.pools:
            self.update_pool_data(pool)

    def update_all_tab(self):
        # Aggregate data
        total_size = 0
        total_alloc = 0
        total_free = 0
        all_vdevs = []
        all_datasets = []
        worst_health = "ONLINE"
        
        # Helper to parse size strings to bytes (simplified)
        # For now, just string concatenation or basic logic? 
        # Real aggregation requires unit parsing.
        # Let's just create a dummy pool with "Aggregated" strings for now
        # or implement a proper size parser.
        
        # For simplicity in this iteration, I'll just list all vdevs and datasets
        # and maybe skip the capacity bar or show an average?
        # Let's try to do a best effort aggregation.
        
        for pool in self.pools:
            all_vdevs.extend(pool.vdevs)
            all_datasets.extend(pool.datasets)
            if pool.health != "ONLINE":
                worst_health = pool.health
        
        # Create a dummy pool object for the overview
        agg_pool = Pool(
            name="All Pools",
            state=worst_health,
            size="N/A", # TODO: Implement size parsing
            alloc="N/A",
            free="N/A",
            frag="-",
            cap="-",
            health=worst_health,
            vdevs=all_vdevs,
            datasets=all_datasets
        )
        
        try:
            overview = self.query_one("#overview-all", PoolOverview)
            overview.pool = agg_pool
            
            vdevs = self.query_one("#vdevs-all", VdevList)
            vdevs.vdevs = all_vdevs
            
            tree = self.query_one("#tree-all", DatasetTreeWidget)
            tree.datasets = all_datasets
        except Exception:
            pass

    def update_pool_data(self, pool: Pool):
        # Update widgets for this pool
        try:
            overview = self.query_one(f"#overview-{pool.name}", PoolOverview)
            overview.pool = pool
            
            vdevs = self.query_one(f"#vdevs-{pool.name}", VdevList)
            vdevs.vdevs = pool.vdevs
            
            tree = self.query_one(f"#tree-{pool.name}", DatasetTreeWidget)
            tree.datasets = pool.datasets
            if self.dataset_filter:
                tree.dataset_filter = self.dataset_filter
        except Exception:
            pass # Widget might not exist if tab not created yet

    def on_dataset_tree_widget_selected(self, message: DatasetTreeWidget.Selected):
        # Find which pool this belongs to (hacky, but works for now)
        # Ideally the message should carry context or we search
        # But since we have unique IDs for details widget:
        # We need to find the details widget that corresponds to the active tab or the tree that sent the message
        
        # The message bubbles up from the tree.
        # We can look at message.control.id to find the pool name
        tree_id = message.control.id # e.g. tree-tank
        if tree_id and tree_id.startswith("tree-"):
            pool_name = tree_id.split("-", 1)[1]
            details = self.query_one(f"#details-{pool_name}", DatasetDetails)
            details.dataset = message.dataset
