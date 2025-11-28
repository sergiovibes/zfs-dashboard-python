import subprocess
import re
from typing import List, Dict, Optional
from .models import Pool, Vdev, Dataset, Snapshot

def run_command(command: List[str]) -> str:
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error running command {' '.join(command)}: {e}")
        return ""
    except FileNotFoundError:
        # For testing/development on non-ZFS systems
        return ""

def parse_zpool_list(output: str) -> List[Pool]:
    """
    Parses `zpool list -H -o name,size,alloc,free,frag,cap,health,altroot`
    """
    pools = []
    if not output:
        return pools
        
    for line in output.strip().split('\n'):
        parts = line.split('\t')
        if len(parts) >= 8:
            pools.append(Pool(
                name=parts[0],
                size=parts[1],
                alloc=parts[2],
                free=parts[3],
                frag=parts[4],
                cap=parts[5],
                health=parts[6],
                altroot=parts[7],
                state=parts[6] # Health is often used as state in list, but status gives more detail
            ))
    return pools

def parse_zpool_status(output: str) -> Dict[str, List[Vdev]]:
    """
    Parses `zpool status` to extract vdev information.
    Returns a dictionary mapping pool names to a list of Vdevs.
    This is a complex parser as `zpool status` output is structured text.
    """
    vdevs_by_pool = {}
    current_pool = None
    in_config = False
    
    lines = output.split('\n')
    for line in lines:
        line = line.rstrip()
        stripped = line.strip()
        
        if stripped.startswith("pool:"):
            current_pool = stripped.split(":")[1].strip()
            vdevs_by_pool[current_pool] = []
            in_config = False
            continue
            
        if stripped.startswith("config:"):
            in_config = True
            continue
            
        if not in_config or not current_pool:
            continue
            
        # Skip headers and errors line
        if stripped.startswith("NAME") or stripped.startswith("errors:") or not stripped:
            continue
            
        # Basic parsing of config lines
        # Format usually: NAME  STATE  READ WRITE CKSUM
        # Indentation matters for hierarchy, but for now we just list them
        # We might need to refine this to handle mirrors/raidz properly
        
        parts = stripped.split()
        if len(parts) >= 5:
            name = parts[0]
            state = parts[1]
            try:
                read = int(parts[2])
                write = int(parts[3])
                cksum = int(parts[4])
            except ValueError:
                # Might be errors or other info
                read, write, cksum = 0, 0, 0
                
            # Determine type based on name (mirror, raidz, etc)
            vdev_type = "disk"
            if name.startswith("mirror"):
                vdev_type = "mirror"
            elif name.startswith("raidz"):
                vdev_type = "raidz"
            elif name == current_pool:
                 # This is the root vdev (pool name itself in config)
                 vdev_type = "root"
            
            # Don't add the root pool entry as a vdev if it's just the container
            if name != current_pool:
                vdevs_by_pool[current_pool].append(Vdev(
                    name=name,
                    state=state,
                    read=read,
                    write=write,
                    cksum=cksum,
                    type=vdev_type
                ))
                
    return vdevs_by_pool

def parse_zfs_list(output: str) -> List[Dataset]:
    """
    Parses `zfs list -H -p -o name,used,avail,refer,mountpoint,compression,type`
    Using -p for parsable (exact numbers) might be better, but user wants human readable?
    Let's stick to default units for now or -H without -p if we want human readable strings.
    The requirement says "size/quota", "used", "available".
    Let's use `zfs list -H -o name,used,avail,refer,mountpoint,compression,type`
    """
    datasets = []
    if not output:
        return datasets

    for line in output.strip().split('\n'):
        parts = line.split('\t')
        if len(parts) >= 7:
            # We only care about filesystems and volumes usually, but type is in parts[6]
            ds_type = parts[6]
            if ds_type in ('filesystem', 'volume'):
                datasets.append(Dataset(
                    name=parts[0],
                    used=parts[1],
                    avail=parts[2],
                    refer=parts[3],
                    mountpoint=parts[4],
                    compression=parts[5]
                ))
    return datasets

def parse_zfs_snapshots(output: str) -> Dict[str, List[Snapshot]]:
    """
    Parses `zfs list -H -t snapshot -o name,used`
    Returns dict mapping dataset name to snapshots.
    """
    snapshots_by_dataset = {}
    if not output:
        return snapshots_by_dataset
        
    for line in output.strip().split('\n'):
        parts = line.split('\t')
        if len(parts) >= 2:
            full_name = parts[0]
            used = parts[1]
            if '@' in full_name:
                dataset_name, snap_name = full_name.split('@', 1)
                if dataset_name not in snapshots_by_dataset:
                    snapshots_by_dataset[dataset_name] = []
                snapshots_by_dataset[dataset_name].append(Snapshot(name=snap_name, used=used))
                
    return snapshots_by_dataset

def build_dataset_tree(datasets: List[Dataset]) -> List[Dataset]:
    """
    Organizes a flat list of datasets into a tree structure based on names.
    Assumes datasets are sorted by name (which zfs list usually does).
    """
    # Map names to dataset objects
    ds_map = {ds.name: ds for ds in datasets}
    roots = []
    
    for ds in datasets:
        if '/' in ds.name:
            parent_name = ds.name.rsplit('/', 1)[0]
            if parent_name in ds_map:
                ds_map[parent_name].children.append(ds)
            else:
                # Parent not found (maybe not listed?), treat as root
                roots.append(ds)
        else:
            roots.append(ds)
            
    return roots

def parse_iostat_line(line: str) -> Optional[tuple[str, str, int, int, int, int]]:
    """
    Parses a single line from `zpool iostat -H -p -y 1`.
    Format: pool_name  alloc  free  read_ops  write_ops  read_bytes  write_bytes
    Or:     vdev_name  alloc  free  read_ops  write_ops  read_bytes  write_bytes
    
    Returns: (name, type_hint, read_ops, write_ops, read_bytes, write_bytes)
    type_hint is 'pool' or 'vdev' based on context (caller needs to track).
    Actually, `zpool iostat -H` prints flat lines.
    We need to know the structure.
    But usually it prints:
    pool_name ...
      vdev ...
    
    With -H, indentation is preserved?
    Let's check `zpool iostat -H` behavior.
    Usually -H removes headers and separates with tabs.
    It DOES NOT preserve indentation usually.
    Wait, if indentation is lost, we can't distinguish pool from vdev easily if names are similar.
    However, the order is always Pool -> Vdevs.
    
    Let's assume the caller handles the hierarchy or we just return the raw stats and name.
    """
    parts = line.strip().split('\t')
    if len(parts) < 7:
        return None
        
    name = parts[0]
    try:
        # parts[1] alloc, parts[2] free
        read_ops = int(parts[3])
        write_ops = int(parts[4])
        read_bytes = int(parts[5])
        write_bytes = int(parts[6])
        return (name, read_ops, write_ops, read_bytes, write_bytes)
    except (ValueError, IndexError):
        return None

def parse_zpool_iostat(output: str) -> Dict[str, Dict[str, dict]]:

    """
    Parses `zpool iostat -v -p` (using -p for exact numbers)
    Returns nested dict: pool -> vdev -> {read_ops, write_ops, read_bytes, write_bytes}
    """
    stats = {}
    if not output:
        return stats
        
    lines = output.strip().split('\n')
    # Headers usually take 1-2 lines. -v output structure:
    #              capacity     operations    bandwidth
    # pool        alloc   free   read  write   read  write
    # ----------  -----  -----  -----  -----  -----  -----
    # tank        ...
    #   mirror-0  ...
    
    # We need to find where the data starts.
    # Usually after the separator line "----------"
    
    data_started = False
    current_pool = None
    
    for line in lines:
        if "----------" in line:
            data_started = True
            continue
            
        if not data_started:
            continue
            
        parts = line.split()
        if len(parts) < 7:
            continue
            
        # With -p, numbers are raw integers.
        # Format: name alloc free read_ops write_ops read_bytes write_bytes
        # Sometimes there are more columns if latency is included, but let's assume standard iostat
        
        name = parts[0]
        try:
            read_ops = int(parts[3])
            write_ops = int(parts[4])
            read_bytes = int(parts[5])
            write_bytes = int(parts[6])
        except (ValueError, IndexError):
            continue
            
        # Identify if it's a pool or vdev
        # Indentation in `zpool iostat -v` is 2 spaces for vdevs usually
        # But `split()` removes indentation.
        # However, the order is hierarchical.
        
        # If we track known pools, we can guess.
        # But we don't have the list of pools here easily unless passed.
        # A heuristic: if it's a pool name, it's a pool.
        # But we don't know pool names here.
        
        # Actually, `zpool iostat -v` lists the pool then its vdevs.
        # We can assume top level is pool, indented is vdev.
        # But we lost indentation with `split()`.
        # Let's check indentation from original line.
        indent = len(line) - len(line.lstrip())
        
        if indent == 0:
            current_pool = name
            if current_pool not in stats:
                stats[current_pool] = {}
            # Store pool stats under "root" or similar key, or just map pool name to stats
            stats[current_pool]["__pool__"] = {
                "read_ops": read_ops, "write_ops": write_ops,
                "read_bytes": read_bytes, "write_bytes": write_bytes
            }
        elif current_pool:
            stats[current_pool][name] = {
                "read_ops": read_ops, "write_ops": write_ops,
                "read_bytes": read_bytes, "write_bytes": write_bytes
            }
            
    return stats

def get_static_data() -> List[Pool]:
    """
    Fetches static structure: Pools, Vdevs, Datasets.
    Does NOT fetch realtime IO stats.
    """
    # 1. Get Pools
    pool_list_out = run_command(['zpool', 'list', '-H', '-o', 'name,size,alloc,free,frag,cap,health,altroot'])
    pools = parse_zpool_list(pool_list_out)
    
    # 2. Get Vdevs
    status_out = run_command(['zpool', 'status'])
    vdevs_map = parse_zpool_status(status_out)
    
    # 3. Get Datasets
    zfs_list_out = run_command(['zfs', 'list', '-H', '-o', 'name,used,avail,refer,mountpoint,compression,type'])
    all_datasets = parse_zfs_list(zfs_list_out)
    
    # 4. Get Snapshots
    snap_out = run_command(['zfs', 'list', '-H', '-t', 'snapshot', '-o', 'name,used'])
    snaps_map = parse_zfs_snapshots(snap_out)
    
    # Attach snapshots to datasets
    for ds in all_datasets:
        if ds.name in snaps_map:
            ds.snapshots = snaps_map[ds.name]
            
    # Build Tree
    root_datasets = build_dataset_tree(all_datasets)
    
    # Attach Vdevs and Datasets to Pools
    for pool in pools:
        if pool.name in vdevs_map:
            pool.vdevs = vdevs_map[pool.name]
        
        # Find root dataset for this pool
        pool.datasets = [ds for ds in root_datasets if ds.name == pool.name]
        
    return pools

def get_system_status() -> List[Pool]:
    # Deprecated: Use get_static_data for structure and background thread for stats
    return get_static_data()

