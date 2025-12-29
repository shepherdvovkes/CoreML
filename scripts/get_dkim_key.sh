#!/bin/bash
#
# Script to extract DKIM public key from mail.txt file
# Run this on the mail server: mail.s0me.uk
# Uses base64 validation to ensure key integrity
#

DOMAIN="lexapp.co.ua"
SELECTOR="mail"
KEY_FILE="/etc/opendkim/keys/${DOMAIN}/${SELECTOR}.txt"

if [ ! -f "$KEY_FILE" ]; then
    echo "Error: DKIM key file not found: $KEY_FILE"
    exit 1
fi

echo "Extracting DKIM public key from $KEY_FILE"
echo ""

# Extract the public key parts (p= and p+)
# Remove quotes, whitespace, and combine p= and p+ parts
PUBLIC_KEY=$(awk '
    /"p=/ {
        gsub(/[" ]/, "")
        gsub(/p=/, "")
        printf "%s", $0
    }
    /"p\+/ {
        gsub(/[" ]/, "")
        gsub(/p\+/, "")
        printf "%s", $0
    }
' "$KEY_FILE" | tr -d '\n\t')

if [ -z "$PUBLIC_KEY" ]; then
    echo "Error: Could not extract public key from $KEY_FILE"
    echo ""
    echo "File contents:"
    cat "$KEY_FILE"
    exit 1
fi

# Validate base64 encoding
echo "Validating base64 key..."
if echo "$PUBLIC_KEY" | base64 -d > /dev/null 2>&1; then
    KEY_LEN=$(echo -n "$PUBLIC_KEY" | wc -c)
    echo "✓ Valid base64 key (length: $KEY_LEN characters)"
else
    echo "⚠ Warning: Key may not be valid base64"
    echo "  Proceeding anyway..."
fi

echo "DKIM Public Key (for DNS):"
echo "=========================="
echo "$PUBLIC_KEY"
echo ""
echo "Full DNS record content:"
echo "=========================="
cat "$KEY_FILE"
echo ""
echo ""
echo "To add this to DNS, run from your local machine:"
echo "python scripts/setup_email_dns.py \\"
echo "  --api-key \"88cacc1b670d244fe867557673dfb4e042ffe\" \\"
echo "  --email \"shepherdvovkes@icloud.com\" \\"
echo "  --dkim-selector mail \\"
echo "  --dkim-key \"$PUBLIC_KEY\""

