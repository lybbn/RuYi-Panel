#!/bin/bash
set -euo pipefail

KERNEL_VERSION=$(uname -r)
KERNEL_MAJOR=$(echo "$KERNEL_VERSION" | cut -d. -f1)
KERNEL_MINOR=$(echo "$KERNEL_VERSION" | cut -d. -f2)

echo "=== Linux Kernel Vulnerability Check ==="
echo "Kernel: $KERNEL_VERSION"
echo ""

echo "--- Module Loading Status ---"
VULN_MODULES="algif_aead esp4 esp6 espintcp rxrpc"
LOADED_MODULES=""
for mod in $VULN_MODULES; do
    if grep -qE "^${mod} " /proc/modules 2>/dev/null; then
        echo "[LOADED]   $mod"
        LOADED_MODULES="$LOADED_MODULES $mod"
    else
        echo "[NOT LOADED] $mod"
    fi
done
echo ""

echo "--- Mitigation Status ---"
MITIGATION_FILES=$(ls /etc/modprobe.d/*.conf 2>/dev/null || true)
if [ -n "$MITIGATION_FILES" ]; then
    for mod in algif_aead esp4 esp6 rxrpc; do
        if echo "$MITIGATION_FILES" | xargs grep -h "install ${mod}" 2>/dev/null | grep -q "/bin/false\|/bin/true"; then
            echo "[MITIGATED] $mod - blocked in modprobe.d"
        else
            echo "[UNMITIGATED] $mod - no block rule found"
        fi
    done
else
    echo "[UNMITIGATED] No modprobe.d configuration files found"
fi
echo ""

echo "--- Kernel Update Check ---"
if command -v apt &>/dev/null; then
    UPDATES=$(apt list --upgradable 2>/dev/null | grep -i linux-image || true)
    if [ -n "$UPDATES" ]; then
        echo "[UPDATES AVAILABLE]"
        echo "$UPDATES"
    else
        echo "[NO KERNEL UPDATES] All kernel packages are up to date (or check failed)"
    fi
elif command -v dnf &>/dev/null; then
    UPDATES=$(dnf check-update kernel 2>/dev/null || true)
    if [ -n "$UPDATES" ]; then
        echo "[UPDATES AVAILABLE]"
        echo "$UPDATES"
    else
        echo "[NO KERNEL UPDATES]"
    fi
elif command -v yum &>/dev/null; then
    UPDATES=$(yum check-update kernel 2>/dev/null || true)
    if [ -n "$UPDATES" ]; then
        echo "[UPDATES AVAILABLE]"
        echo "$UPDATES"
    else
        echo "[NO KERNEL UPDATES]"
    fi
else
    echo "[UNKNOWN] Package manager not recognized"
fi
echo ""

echo "--- User Namespace Restrictions ---"
UNPRIV_USERNS=$(cat /proc/sys/kernel/unprivileged_userns_clone 2>/dev/null || echo "N/A")
MAX_USERNS=$(cat /proc/sys/user/max_user_namespaces 2>/dev/null || echo "N/A")
echo "unprivileged_userns_clone: $UNPRIV_USERNS"
echo "max_user_namespaces: $MAX_USERNS"
if [ "$UNPRIV_USERNS" = "0" ] || [ "$MAX_USERNS" = "0" ]; then
    echo "[PARTIAL PROTECTION] User namespaces are restricted"
else
    echo "[NO PROTECTION] User namespaces are not restricted"
fi
echo ""

echo "=== Vulnerability Summary ==="
echo "Kernel: $KERNEL_VERSION"

COPY_FAIL="UNKNOWN"
DIRTY_FRAG="UNKNOWN"
FRAGNESIA="UNKNOWN"

ALGIF_MITIGATED=false
ESP_MITIGATED=false
RXRPC_MITIGATED=false

if [ -n "$MITIGATION_FILES" ]; then
    if echo "$MITIGATION_FILES" | xargs grep -h "install algif_aead" 2>/dev/null | grep -q "/bin/false\|/bin/true"; then
        ALGIF_MITIGATED=true
    fi
    if echo "$MITIGATION_FILES" | xargs grep -h "install esp4" 2>/dev/null | grep -q "/bin/false\|/bin/true"; then
        ESP_MITIGATED=true
    fi
    if echo "$MITIGATION_FILES" | xargs grep -h "install rxrpc" 2>/dev/null | grep -q "/bin/false\|/bin/true"; then
        RXRPC_MITIGATED=true
    fi
fi

ALGIF_LOADED=false
ESP_LOADED=false
RXRPC_LOADED=false
if echo "$LOADED_MODULES" | grep -q "algif_aead"; then ALGIF_LOADED=true; fi
if echo "$LOADED_MODULES" | grep -qE "esp4|esp6"; then ESP_LOADED=true; fi
if echo "$LOADED_MODULES" | grep -q "rxrpc"; then RXRPC_LOADED=true; fi

if $ALGIF_MITIGATED && ! $ALGIF_LOADED; then
    COPY_FAIL="MITIGATED"
elif $ALGIF_LOADED; then
    COPY_FAIL="VULNERABLE"
else
    COPY_FAIL="MITIGATED (module not loaded)"
fi

if ($ESP_MITIGATED && ! $ESP_LOADED) && ($RXRPC_MITIGATED && ! $RXRPC_LOADED); then
    DIRTY_FRAG="MITIGATED"
elif $ESP_LOADED || $RXRPC_LOADED; then
    DIRTY_FRAG="VULNERABLE"
else
    DIRTY_FRAG="MITIGATED (modules not loaded)"
fi

if $ESP_MITIGATED && ! $ESP_LOADED; then
    FRAGNESIA="MITIGATED"
elif $ESP_LOADED; then
    FRAGNESIA="VULNERABLE"
else
    FRAGNESIA="MITIGATED (modules not loaded)"
fi

echo "| Vulnerability | CVE | Status |"
echo "|---------------|-----|--------|"
echo "| Copy Fail | CVE-2026-31431 | $COPY_FAIL |"
echo "| Dirty Frag | QVD-2026-24699 | $DIRTY_FRAG |"
echo "| Fragnesia | CVE-2026-46300 | $FRAGNESIA |"
