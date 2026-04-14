#!/bin/bash
# ==============================================================================
# Dump Flow Tables for All Switches
# ==============================================================================
# Run this from a terminal (not inside Mininet) while Mininet is running
#
# Usage: sudo bash tests/dump_flows.sh
# ==============================================================================

echo "============================================"
echo "  Flow Table Dump - All Switches"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================"

echo ""
echo "--- Switch s1 ---"
ovs-ofctl -O OpenFlow13 dump-flows s1 2>/dev/null || echo "  Switch s1 not found"

echo ""
echo "--- Switch s2 ---"
ovs-ofctl -O OpenFlow13 dump-flows s2 2>/dev/null || echo "  Switch s2 not found"

echo ""
echo "--- Switch s3 ---"
ovs-ofctl -O OpenFlow13 dump-flows s3 2>/dev/null || echo "  Switch s3 not found"

echo ""
echo "--- Port Statistics (s1) ---"
ovs-ofctl -O OpenFlow13 dump-ports s1 2>/dev/null || echo "  Switch s1 not found"

echo ""
echo "============================================"
echo "  Flow table dump complete"
echo "============================================"
