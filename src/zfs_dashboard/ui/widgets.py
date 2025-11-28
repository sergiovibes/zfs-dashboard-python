from textual.app import ComposeResult
from textual.widgets import Static, Tree, ProgressBar, DataTable, Label, Sparkline, Input
from textual.containers import Vertical, Horizontal, Grid
from textual.reactive import reactive
from textual.message import Message

from ..models import Pool, Vdev, Dataset
from ..utils import humanize_bytes

class PoolOverview(Static):
    pool = reactive(None)

    def compose(self) -> ComposeResult:
        yield Label("Pool Status", id="pool-status-label")
        yield Label("", id="pool-state")
        yield Label("Capacity", id="pool-cap-label")
        yield ProgressBar(total=100, show_eta=False, id="pool-capacity-bar")
        yield Label("", id="pool-capacity-text")
        
        yield Label("Read IOPS", classes="header-small")
        yield Sparkline(data=[], summary_function=max, id="read-ops-spark")
        yield Label("Write IOPS", classes="header-small")
        yield Sparkline(data=[], summary_function=max, id="write-ops-spark")

    def update_stats(self):
        """Force update of stats from self.pool"""
        if self.pool:
            self.watch_pool(self.pool)

    def watch_pool(self, pool: Pool):
        if pool:
            self.query_one("#pool-state", Label).update(f"State: {pool.state} | Health: {pool.health}")
            
            # Parse capacity percentage
            try:
                cap_val = int(pool.cap.strip('%'))
            except ValueError:
                cap_val = 0
            
            bar = self.query_one("#pool-capacity-bar", ProgressBar)
            bar.progress = cap_val
            
            self.query_one("#pool-capacity-text", Label).update(f"{pool.alloc} / {pool.size} ({pool.cap})")
            
            # Update Sparklines
            # We need to maintain history. Since this widget persists, we can store it in self.
            if not hasattr(self, "read_history"):
                self.read_history = []
                self.write_history = []
            
            self.read_history.append(pool.read_ops)
            self.write_history.append(pool.write_ops)
            if len(self.read_history) > 60:
                self.read_history.pop(0)
                self.write_history.pop(0)
                
            self.query_one("#read-ops-spark", Sparkline).data = self.read_history
            self.query_one("#write-ops-spark", Sparkline).data = self.write_history

class VdevList(Static):
    vdevs = reactive([])

    def compose(self) -> ComposeResult:
        yield Label("VDEVs", classes="header")
        yield DataTable(id="vdev-table")

    def on_mount(self):
        table = self.query_one(DataTable)
        table.add_columns("Name", "State", "Read", "Write", "Cksum", "Type", "R IOPS", "W IOPS", "R Bytes", "W Bytes")

    def update_vdevs(self):
        """Force update of vdev table"""
        self.watch_vdevs(self.vdevs)

    def watch_vdevs(self, vdevs: list[Vdev]):
        table = self.query_one(DataTable)
        table.clear()
        for vdev in vdevs:
            table.add_row(
                vdev.name,
                vdev.state,
                str(vdev.read),
                str(vdev.write),
                str(vdev.cksum),
                vdev.type,
                str(vdev.read_ops),
                str(vdev.write_ops),
                humanize_bytes(vdev.read_bytes),
                humanize_bytes(vdev.write_bytes)
            )

class DatasetTreeWidget(Static):
    datasets = reactive([])
    search_query = reactive("")
    dataset_filter = reactive("")

    class Selected(Message):
        def __init__(self, dataset: Dataset, tree_id: str):
            self.dataset = dataset
            self.tree_id = tree_id
            super().__init__()

    def compose(self) -> ComposeResult:
        yield Input(placeholder="Search datasets...", id="search-input")
        yield Tree("Datasets", id="dataset-tree")

    def on_input_changed(self, event: Input.Changed):
        self.search_query = event.value
        self.rebuild_tree()

    def watch_datasets(self, datasets: list[Dataset]):
        self.rebuild_tree()

    def watch_dataset_filter(self, filter_str: str):
        self.rebuild_tree()

    def rebuild_tree(self):
        tree = self.query_one(Tree)
        tree.clear()
        tree.root.expand()
        
        for root in self.datasets:
            self._add_node(tree.root, root)

    def _add_node(self, parent_node, dataset: Dataset):
        # Check if this node or any of its children match the query
        if self.matches(dataset) or self.has_matching_child(dataset):
            # Format label with columns
            # Name | Used | Avail | Compress | Mount
            # We use fixed width for simplicity, or just append info
            # Name is the tree node, so indentation is handled by Tree.
            # We just append the other columns.
            # Note: Tree indentation eats into width.
            
            # Simple formatting:
            label = f"{dataset.name} [dim]{dataset.used} {dataset.avail} {dataset.compression} {dataset.mountpoint}[/]"
            
            node = parent_node.add(label, data=dataset)
            
            # Expand if searching
            if self.search_query:
                node.expand()
            elif len(dataset.children) > 10:
                node.collapse()
            else:
                node.expand()
                
            for child in dataset.children:
                self._add_node(node, child)

    def matches(self, dataset: Dataset) -> bool:
        # Check CLI filter
        if self.dataset_filter:
            import re
            try:
                if not re.search(self.dataset_filter, dataset.name):
                    return False
            except re.error:
                pass
        
        if not self.search_query:
            return True
        return self.search_query.lower() in dataset.name.lower()

    def has_matching_child(self, dataset: Dataset) -> bool:
        if not self.search_query:
            return True # If no query, children "match" (are visible)
        for child in dataset.children:
            if self.matches(child) or self.has_matching_child(child):
                return True
        return False

    def on_tree_node_selected(self, event: Tree.NodeSelected):
        if event.node.data:
            self.post_message(self.Selected(event.node.data, self.id))

class DatasetDetails(Static):
    dataset = reactive(None)

    def compose(self) -> ComposeResult:
        yield Label("Dataset Details", classes="header")
        yield DataTable(id="dataset-details-table")
        yield Label("Snapshots", classes="header")
        yield DataTable(id="snapshot-table")

    def on_mount(self):
        dt = self.query_one("#dataset-details-table", DataTable)
        dt.add_columns("Property", "Value")
        
        st = self.query_one("#snapshot-table", DataTable)
        st.add_columns("Name", "Used")

    def watch_dataset(self, dataset: Dataset):
        dt = self.query_one("#dataset-details-table", DataTable)
        dt.clear()
        st = self.query_one("#snapshot-table", DataTable)
        st.clear()

        if dataset:
            dt.add_rows([
                ("Name", dataset.name),
                ("Mountpoint", dataset.mountpoint),
                ("Used", dataset.used),
                ("Available", dataset.avail),
                ("Referenced", dataset.refer),
                ("Compression", dataset.compression),
            ])
            
            for snap in dataset.snapshots:
                st.add_row(snap.name, snap.used)
