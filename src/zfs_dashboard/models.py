from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class Snapshot:
    name: str
    used: str

@dataclass
class Dataset:
    name: str
    used: str
    avail: str
    refer: str
    mountpoint: str
    compression: str = "off"
    children: List['Dataset'] = field(default_factory=list)
    snapshots: List[Snapshot] = field(default_factory=list)

@dataclass
class Vdev:
    name: str
    state: str
    read: int = 0
    write: int = 0
    cksum: int = 0
    # IO Stats
    read_ops: int = 0
    write_ops: int = 0
    read_bytes: int = 0
    write_bytes: int = 0
    type: str = "disk" # mirror, raidz, disk, etc.
    size: str = ""
    alloc: str = ""
    free: str = ""
    frag: str = ""
    cap: str = ""

@dataclass
class Pool:
    name: str
    state: str
    size: str
    alloc: str
    free: str
    frag: str
    cap: str
    health: str
    altroot: str = "-"
    # IO Stats
    read_ops: int = 0
    write_ops: int = 0
    read_bytes: int = 0
    write_bytes: int = 0
    vdevs: List[Vdev] = field(default_factory=list)
    datasets: List[Dataset] = field(default_factory=list)
