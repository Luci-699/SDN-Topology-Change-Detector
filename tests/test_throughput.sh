#!/bin/bash
# ==============================================================================
# Test 2: Throughput Test (iperf)
# ==============================================================================
# Tests network throughput between hosts using iperf
#
# Usage: Run commands inside Mininet CLI
# ==============================================================================

echo "============================================"
echo "  Test 2: Throughput Test (iperf)"
echo "============================================"
echo ""
echo "Run these commands in the Mininet CLI:"
echo ""
echo "1. Quick iperf test between h1 and h6:"
echo "   mininet> iperf h1 h6"
echo ""
echo "2. Detailed iperf with duration:"
echo "   mininet> h6 iperf -s &"
echo "   mininet> h1 iperf -c 10.0.0.6 -t 10 -i 1"
echo ""
echo "3. Test between different switch pairs:"
echo "   mininet> iperf h1 h4"
echo "   mininet> iperf h3 h5"
echo ""
echo "Expected: Throughput values showing network performance"
echo "============================================"
