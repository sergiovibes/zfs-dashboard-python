# ZFS Dashboard (Python TUI)

A terminal-based user interface (TUI) for monitoring ZFS pools, built with Python and Textual.

[![asciicast](https://asciinema.org/a/PB6V69puintF9oqmgB34RvXWy.svg)](https://asciinema.org/a/PB6V69puintF9oqmgB34RvXWy)

## Features

- **Real-time Monitoring**: View pool status, capacity, and IOPS in real-time.
- **VDEV Details**: Detailed statistics for each Virtual Device (VDEV), including read/write operations and bytes.
- **Dataset Explorer**: Interactive tree view of datasets with search and filtering capabilities.
- **Snapshot Viewer**: Inspect snapshots for selected datasets.
- **Visualizations**: Sparklines for IOPS history and progress bars for capacity.
- **Multi-Pool Support**: Tabbed interface for managing multiple ZFS pools.

## Installation

Ensure you have Python 3.13+ installed.

1.  Clone the repository:
    ```bash
    git clone https://github.com/sergiovibes/zfs-dashboard-python.git
    cd zfs-dashboard-python
    ```

2.  Install dependencies (using `uv` or `pip`):
    ```bash
    # Using pip
    pip install textual

    # Or using uv (recommended)
    uv sync
    ```

## Usage

Run the application using the provided script or directly via Python:

```bash
# Run with default settings
python src/zfs_dashboard/main.py

# Or using uv
uv run src/zfs_dashboard/main.py
```

### Command Line Arguments

- `-i`, `--interval`: Update interval in seconds (default: 5).
- `-p`, `--pool`: Filter to show only a specific pool by name.
- `-d`, `--dataset`: Regex filter for the dataset list.

**Examples:**

```bash
# Update every 2 seconds
python src/zfs_dashboard/main.py -i 2

# Show only 'tank' pool
python src/zfs_dashboard/main.py -p tank
```

### Key Bindings

- `F5`: Refresh data manually.
- `q`: Quit the application.

## License

0BSD License. See [LICENSE](LICENSE) for details.
