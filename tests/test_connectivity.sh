#!/bin/bash
# ==============================================================================
# Test 1: Connectivity Test (pingall)
# ==============================================================================
# Run this INSIDE the Mininet CLI or as a Mininet command
#
# Expected output: All hosts should reach each other (0% dropped)
#
# Usage:
#   Inside Mininet CLI, just type: pingall
#   Or from Mininet CLI: source tests/test_connectivity.sh
# ==============================================================================

echo "============================================"
echo "  Test 1: Connectivity Test"
echo "============================================"
echo ""
echo "Run these commands in the Mininet CLI:"
echo ""
echo "1. Test all-to-all connectivity:"
echo "   mininet> pingall"
echo ""
echo "2. Test specific host pairs with latency:"
echo "   mininet> h1 ping -c 5 h4"
echo "   mininet> h1 ping -c 5 h6"
echo "   mininet> h3 ping -c 5 h5"
echo ""
echo "3. View ARP tables:"
echo "   mininet> h1 arp -a"
echo ""
echo "Expected: 0% packet loss for all pairs"
echo "============================================"
