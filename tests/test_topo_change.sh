#!/bin/bash
# ==============================================================================
# Test 3: Topology Change Detection
# ==============================================================================
# Simulates link failures and verifies the controller detects them
#
# Usage: Run commands inside Mininet CLI
# ==============================================================================

echo "============================================"
echo "  Test 3: Topology Change Detection"
echo "============================================"
echo ""
echo "Run these commands in the Mininet CLI:"
echo ""
echo "Step 1: Verify initial connectivity"
echo "   mininet> pingall"
echo ""
echo "Step 2: Check initial flow tables"
echo "   mininet> sh ovs-ofctl -O OpenFlow13 dump-flows s1"
echo "   mininet> sh ovs-ofctl -O OpenFlow13 dump-flows s2"
echo "   mininet> sh ovs-ofctl -O OpenFlow13 dump-flows s3"
echo ""
echo "Step 3: Simulate link failure (s1-s2)"
echo "   mininet> link s1 s2 down"
echo "   (Watch controller terminal for LINK_DELETE event)"
echo ""
echo "Step 4: Test connectivity after failure"
echo "   mininet> h1 ping -c 3 h3"
echo "   (Should still work via alternate path s1-s3-s2)"
echo ""
echo "Step 5: Check flow tables after change"
echo "   mininet> sh ovs-ofctl -O OpenFlow13 dump-flows s1"
echo ""
echo "Step 6: Restore link"
echo "   mininet> link s1 s2 up"
echo "   (Watch controller terminal for LINK_ADD event)"
echo ""
echo "Step 7: Verify recovery"
echo "   mininet> pingall"
echo ""
echo "Step 8: Check topology events log"
echo "   mininet> sh cat logs/topology_events.log"
echo ""
echo "============================================"
