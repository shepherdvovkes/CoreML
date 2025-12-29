#!/bin/bash
#
# Script to set up DKIM signing for Postfix on Ubuntu/Debian
# Run this script on your mail server (178.162.234.145)
#

set -e

DOMAIN="lexapp.co.ua"
SELECTOR="mail"
OPENDKIM_DIR="/etc/opendkim"
KEYS_DIR="${OPENDKIM_DIR}/keys/${DOMAIN}"

echo "============================================================"
echo "Setting up DKIM for Postfix on ${DOMAIN}"
echo "============================================================"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "✗ Please run as root (use sudo)"
    exit 1
fi

# Install OpenDKIM
echo "Step 1: Installing OpenDKIM..."
if ! command -v opendkim-genkey &> /dev/null; then
    apt-get update
    apt-get install -y opendkim opendkim-tools
else
    echo "✓ OpenDKIM is already installed"
fi

# Create keys directory
echo ""
echo "Step 2: Creating keys directory..."
mkdir -p "${KEYS_DIR}"
chown opendkim:opendkim "${KEYS_DIR}"
chmod 700 "${KEYS_DIR}"

# Generate DKIM key pair
echo ""
echo "Step 3: Generating DKIM key pair..."
if [ ! -f "${KEYS_DIR}/${SELECTOR}.private" ]; then
    opendkim-genkey -t -s "${SELECTOR}" -d "${DOMAIN}" -D "${KEYS_DIR}/"
    chown opendkim:opendkim "${KEYS_DIR}"/*
    chmod 600 "${KEYS_DIR}/${SELECTOR}.private"
    chmod 644 "${KEYS_DIR}/${SELECTOR}.txt"
    echo "✓ DKIM keys generated"
else
    echo "✓ DKIM keys already exist"
fi

# Configure OpenDKIM
echo ""
echo "Step 4: Configuring OpenDKIM..."
OPENDKIM_CONF="/etc/opendkim.conf"

# Backup original config
if [ ! -f "${OPENDKIM_CONF}.backup" ]; then
    cp "${OPENDKIM_CONF}" "${OPENDKIM_CONF}.backup"
fi

# Create new config
cat > "${OPENDKIM_CONF}" <<EOF
# OpenDKIM configuration for ${DOMAIN}

# Basic settings
Syslog                  yes
SyslogSuccess           yes
LogWhy                  yes

# Signing settings
Canonicalization        relaxed/simple
Mode                    sv
SubDomains              no

# Domain and key settings
Domain                  ${DOMAIN}
KeyFile                 ${KEYS_DIR}/${SELECTOR}.private
Selector                ${SELECTOR}

# Socket settings
Socket                  inet:8891@localhost
PidFile                 /var/run/opendkim/opendkim.pid
UMask                   022
UserID                  opendkim:opendkim

# Trusted hosts (add your server IP if needed)
InternalHosts           refile:/etc/opendkim/TrustedHosts

# External hosts
ExternalIgnoreList      refile:/etc/opendkim/TrustedHosts
EOF

# Create TrustedHosts file
echo ""
echo "Step 5: Setting up trusted hosts..."
TRUSTED_HOSTS="/etc/opendkim/TrustedHosts"
cat > "${TRUSTED_HOSTS}" <<EOF
127.0.0.1
localhost
${DOMAIN}
*.${DOMAIN}
EOF

# Configure Postfix
echo ""
echo "Step 6: Configuring Postfix..."
POSTFIX_MAIN="/etc/postfix/main.cf"

# Backup original config
if [ ! -f "${POSTFIX_MAIN}.backup" ]; then
    cp "${POSTFIX_MAIN}" "${POSTFIX_MAIN}.backup"
fi

# Check if milter is already configured
if ! grep -q "milter_protocol" "${POSTFIX_MAIN}"; then
    cat >> "${POSTFIX_MAIN}" <<EOF

# OpenDKIM milter configuration
milter_protocol = 2
milter_default_action = accept
smtpd_milters = inet:localhost:8891
non_smtpd_milters = inet:localhost:8891
EOF
    echo "✓ Postfix milter configuration added"
else
    echo "✓ Postfix milter already configured"
fi

# Restart services
echo ""
echo "Step 7: Restarting services..."
systemctl restart opendkim
systemctl enable opendkim
systemctl restart postfix

echo ""
echo "============================================================"
echo "DKIM Setup Complete!"
echo "============================================================"
echo ""
echo "DKIM Public Key (add this to DNS):"
echo "-----------------------------------"
cat "${KEYS_DIR}/${SELECTOR}.txt"
echo ""
echo "Next steps:"
echo "1. Copy the public key above"
echo "2. Run the DNS setup script:"
echo "   python scripts/setup_email_dns.py --api-key <key> --email <email> \\"
echo "     --dkim-selector ${SELECTOR} --dkim-key <public_key_from_above>"
echo ""
echo "Or manually add to Cloudflare DNS:"
echo "  Name: ${SELECTOR}._domainkey.${DOMAIN}"
echo "  Type: TXT"
echo "  Content: (from the output above)"
echo ""
echo "3. Verify DKIM with:"
echo "   dig TXT ${SELECTOR}._domainkey.${DOMAIN}"
echo ""

