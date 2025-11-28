import unittest
from zfs_dashboard.zfs import parse_zpool_list, parse_zpool_status, parse_zfs_list, parse_zfs_snapshots, build_dataset_tree

class TestZFSParsers(unittest.TestCase):

    def test_parse_zpool_list(self):
        output = "tank\t10T\t5T\t5T\t10%\t50%\tONLINE\t-"
        pools = parse_zpool_list(output)
        self.assertEqual(len(pools), 1)
        self.assertEqual(pools[0].name, "tank")
        self.assertEqual(pools[0].size, "10T")
        self.assertEqual(pools[0].health, "ONLINE")

    def test_parse_zpool_status(self):
        output = """
  pool: tank
 state: ONLINE
config:

\tNAME        STATE     READ WRITE CKSUM
\ttank        ONLINE       0     0     0
\t  mirror-0  ONLINE       0     0     0
\t    sda     ONLINE       0     0     0
\t    sdb     ONLINE       0     0     0
"""
        vdevs_map = parse_zpool_status(output)
        self.assertIn("tank", vdevs_map)
        vdevs = vdevs_map["tank"]
        self.assertEqual(len(vdevs), 3) # mirror-0, sda, sdb
        self.assertEqual(vdevs[0].name, "mirror-0")
        self.assertEqual(vdevs[0].type, "mirror")
        self.assertEqual(vdevs[1].name, "sda")
        self.assertEqual(vdevs[1].type, "disk")

    def test_parse_zfs_list(self):
        output = """tank\t5T\t5T\t100G\t/tank\toff\tfilesystem
tank/data\t4T\t1T\t4T\t/tank/data\ton\tfilesystem"""
        datasets = parse_zfs_list(output)
        self.assertEqual(len(datasets), 2)
        self.assertEqual(datasets[0].name, "tank")
        self.assertEqual(datasets[1].name, "tank/data")
        self.assertEqual(datasets[1].compression, "on")

    def test_build_dataset_tree(self):
        output = """tank\t5T\t5T\t100G\t/tank\toff\tfilesystem
tank/data\t4T\t1T\t4T\t/tank/data\ton\tfilesystem"""
        datasets = parse_zfs_list(output)
        roots = build_dataset_tree(datasets)
        self.assertEqual(len(roots), 1)
        self.assertEqual(roots[0].name, "tank")
        self.assertEqual(len(roots[0].children), 1)
        self.assertEqual(roots[0].children[0].name, "tank/data")

    def test_parse_zfs_snapshots(self):
        output = "tank/data@snap1\t1G\ntank/data@snap2\t2G"
        snaps_map = parse_zfs_snapshots(output)
        self.assertIn("tank/data", snaps_map)
        self.assertEqual(len(snaps_map["tank/data"]), 2)
        self.assertEqual(snaps_map["tank/data"][0].name, "snap1")
        self.assertEqual(snaps_map["tank/data"][0].used, "1G")

if __name__ == '__main__':
    unittest.main()
