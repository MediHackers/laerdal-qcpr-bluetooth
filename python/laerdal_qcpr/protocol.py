"""BLE protocol constants for Laerdal QCPR devices."""

# All custom Laerdal characteristics share this UUID base
LAERDAL_UUID_BASE = "d746-4092-84e7-dad34863fe4a"

# Control characteristics
QCPR_CMD_UUID = f"000001b1-{LAERDAL_UUID_BASE}"
QCPR_CONFIG_UUID = f"00000127-{LAERDAL_UUID_BASE}"
QCPR_STATUS_UUID = f"000001b2-{LAERDAL_UUID_BASE}"
QCPR_MODE_SWITCH_UUID = f"000001e2-{LAERDAL_UUID_BASE}"

# Data characteristics
QCPR_DATA_UUID = f"00000027-{LAERDAL_UUID_BASE}"
QCPR_EVENT_UUID = f"00000028-{LAERDAL_UUID_BASE}"
QCPR_COUNT_UUID = f"00000030-{LAERDAL_UUID_BASE}"
QCPR_STATS_UUID = f"0000012a-{LAERDAL_UUID_BASE}"
QCPR_SESSION_UUID = f"000001a1-{LAERDAL_UUID_BASE}"

# Authentication token (captured from official Laerdal QCPR app, firmware 1.4.2.165)
AUTH_TOKEN = bytes.fromhex("5c0eb9be03d260096d3e1f0c8026c81073cd2ea2")

# Stream control commands written to CONFIG characteristic
CMD_START_STREAM = bytes.fromhex("03ff00")
CMD_STOP_STREAM = bytes.fromhex("000000")

# BLS quality guidelines
BLS_DEPTH_MIN_MM = 50
BLS_DEPTH_MAX_MM = 60
BLS_RATE_MIN = 100   # compressions per minute
BLS_RATE_MAX = 120
