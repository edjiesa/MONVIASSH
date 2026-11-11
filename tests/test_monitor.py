import unittest
import json
from app.crypto_utils import encrypt_secret, decrypt_secret
from app.ssh_collector import parse_collector_output, format_uptime

class TestSSHMonitor(unittest.TestCase):

    def test_crypto_roundtrip(self):
        secret = "SuperSecretPassword123!@#"
        encrypted = encrypt_secret(secret)
        self.assertIsNotNone(encrypted)
        self.assertNotEqual(secret, encrypted)
        decrypted = decrypt_secret(encrypted)
        self.assertEqual(secret, decrypted)

    def test_format_uptime(self):
        # 1 day, 2 hours, 30 minutes = 86400 + 7200 + 1800 = 95400
        result = format_uptime(95400)
        self.assertEqual(result, "1d 2h 30m")

        # 45 minutes = 2700
        result2 = format_uptime(2700)
        self.assertEqual(result2, "45m")

    def test_parse_ubuntu_output(self):
        sample_output = """---SECTION_OS---
PRETTY_NAME="Ubuntu 22.04.3 LTS"
NAME="Ubuntu"
VERSION_ID="22.04"
VERSION="22.04.3 LTS (Jammy Jellyfish)"
---SECTION_HOST---
ubuntu-prod-node01
---SECTION_UPTIME---
184320.50 368640.20
---SECTION_LOAD---
0.45 0.58 0.62 2/320 28419
---SECTION_CPUINFO---
4
Intel(R) Xeon(R) Platinum 8259CL CPU @ 2.50GHz
---SECTION_MEM---
MemTotal:        8048256 kB
MemFree:         1205340 kB
MemAvailable:    5120400 kB
Buffers:          340120 kB
Cached:          3804200 kB
SwapTotal:       2097148 kB
SwapFree:        2097148 kB
---SECTION_DISK---
Filesystem     1024-blocks      Used Available Capacity Mounted on
/dev/root         41151600  12582912  28568688      31% /
/dev/sda15          106858      6188    100670       6% /boot/efi
tmpfs               804828         0    804828       0% /run
---SECTION_NET---
Inter-|   Receive                                                |  Transmit
 face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed
    lo: 12345678    1000    0    0    0     0          0         0 12345678    1000    0    0    0     0       0          0
  eth0: 50000000    5000    0    0    0     0          0         0 20000000    4000    0    0    0     0       0          0
---SECTION_PROCS---
  PID USER     %CPU %MEM COMMAND
 1205 root      4.2  1.5 dockerd
 1450 ubuntu    2.8  3.2 node
  890 root      1.1  0.8 containerd
---SECTION_CPUSTAT1---
cpu  100000 2000 30000 800000 5000 100 200 0 0 0
---SECTION_CPUSTAT2---
cpu  100500 2000 30100 800400 5000 100 200 0 0 0
"""
        parsed = parse_collector_output(sample_output)
        self.assertEqual(parsed["os_name"], "Ubuntu 22.04.3 LTS")
        self.assertEqual(parsed["hostname"], "ubuntu-prod-node01")
        self.assertEqual(parsed["cpu_cores"], 4)
        self.assertEqual(parsed["cpu_model"], "Intel(R) Xeon(R) Platinum 8259CL CPU @ 2.50GHz")
        self.assertEqual(parsed["load_1m"], 0.45)
        self.assertEqual(parsed["load_5m"], 0.58)
        self.assertEqual(parsed["load_15m"], 0.62)
        self.assertAlmostEqual(parsed["ram_total_mb"], 8048256 / 1024, places=1)
        self.assertEqual(len(parsed["partitions"]), 2) # / and /boot/efi (tmpfs filtered out)
        self.assertEqual(parsed["partitions"][0]["mount"], "/")
        self.assertEqual(parsed["partitions"][0]["percent"], 31.0)
        self.assertEqual(len(parsed["processes"]), 3)
        self.assertEqual(parsed["processes"][0]["command"], "dockerd")
        self.assertGreater(parsed["cpu_percent"], 0.0)

    def test_parse_centos_output(self):
        sample_output = """---SECTION_OS---
CentOS Linux release 7.9.2009 (Core)
---SECTION_HOST---
centos7-srv01
---SECTION_UPTIME---
95400.00 190800.00
---SECTION_LOAD---
0.10 0.05 0.01 1/150 9942
---SECTION_CPUINFO---
2
AMD EPYC 7763 64-Core Processor
---SECTION_MEM---
MemTotal:        4024128 kB
MemFree:          800000 kB
Buffers:          200000 kB
Cached:          1500000 kB
SwapTotal:       1048572 kB
SwapFree:        1000000 kB
---SECTION_DISK---
Filesystem     1024-blocks      Used Available Capacity Mounted on
/dev/mapper/centos-root  52403200  10485760  41917440      20% /
/dev/sda1          1038336    200000    838336      20% /boot
---SECTION_NET---
Inter-|   Receive                                                |  Transmit
 face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed
    lo:  500000     500    0    0    0     0          0         0   500000     500    0    0    0     0       0          0
  ens3: 30000000    3000    0    0    0     0          0         0 15000000    2500    0    0    0     0       0          0
---SECTION_PROCS---
  PID USER     %CPU %MEM COMMAND
 3012 mysql     5.0  8.5 mysqld
 2140 root      1.2  0.5 nginx
---SECTION_CPUSTAT1---
cpu  50000 1000 15000 400000 2000 50 100 0 0 0
---SECTION_CPUSTAT2---
cpu  50200 1000 15050 400200 2000 50 100 0 0 0
"""
        parsed = parse_collector_output(sample_output)
        self.assertEqual(parsed["os_name"], "CentOS Linux release 7.9.2009 (Core)")
        self.assertEqual(parsed["hostname"], "centos7-srv01")
        self.assertEqual(parsed["cpu_cores"], 2)
        self.assertEqual(parsed["cpu_model"], "AMD EPYC 7763 64-Core Processor")
        self.assertEqual(parsed["load_1m"], 0.10)
        self.assertEqual(len(parsed["partitions"]), 2)
        self.assertEqual(parsed["partitions"][0]["filesystem"], "/dev/mapper/centos-root")
        self.assertEqual(len(parsed["processes"]), 2)
        self.assertEqual(parsed["processes"][0]["command"], "mysqld")

if __name__ == '__main__':
    unittest.main()
