import argparse
import sys
from .ui.app import ZfsDashboardApp

def main():
    parser = argparse.ArgumentParser(description="ZFS Dashboard TUI")
    parser.add_argument("-i", "--interval", type=int, default=5, help="Update interval in seconds")
    parser.add_argument("-p", "--pool", type=str, help="Only show this pool")
    # Dataset regex filter not fully implemented in UI yet, but we can add the arg
    parser.add_argument("-d", "--dataset", type=str, help="Regex filter for dataset list")
    
    args = parser.parse_args()
    
    app = ZfsDashboardApp(
        interval=args.interval,
        pool_filter=args.pool,
        dataset_filter=args.dataset
    )
    app.run()

if __name__ == "__main__":
    main()
