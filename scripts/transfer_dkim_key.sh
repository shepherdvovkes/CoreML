#!/bin/bash
#
# Script to transfer DKIM key from server to local, then back to update DNS
# This ensures proper base64 encoding/decoding
#

set -e

SERVER="mail.s0me.uk"
DOMAIN="lexapp.co.ua"
SELECTOR="mail"
KEY_FILE="/etc/opendkim/keys/${DOMAIN}/${SELECTOR}.txt"
TEMP_DIR="/tmp/dkim_transfer_$$"
ZIP_FILE="/tmp/dkim_key.zip"

echo "============================================================"
echo "DKIM Key Transfer Script"
echo "============================================================"
echo ""

# Create temp directory
mkdir -p "$TEMP_DIR"
cd "$TEMP_DIR"

# Step 1: Extract key from server
echo "Step 1: Extracting DKIM key from server..."
ssh "$SERVER" "sudo cat $KEY_FILE" > server_mail.txt

# Extract using Python with proper regex
python3 << 'PYEOF' > dkim_key.txt
import sys
import re
import base64

with open('server_mail.txt', 'r') as f:
    content = f.read()

# Extract p= and p+ parts from quoted strings
p_parts = []
# Find all "p=..." or "p+..." within quotes
quoted_matches = re.findall(r'"p([+=])([^"]+)"', content)

# Sort by type: p= first, then p+
p_equals = [m[1] for m in quoted_matches if m[0] == '=']
p_plus = [m[1] for m in quoted_matches if m[0] == '+']

# Combine: first p= part, then all p+ parts
if p_equals:
    p_parts.append(p_equals[0])  # Only take first p= part
p_parts.extend(p_plus)  # Add all p+ continuation parts

# Remove duplicates while preserving order
seen = set()
unique_parts = []
for part in p_parts:
    if part not in seen:
        seen.add(part)
        unique_parts.append(part)

full_key = ''.join(unique_parts).replace(' ', '').replace('\n', '').replace('\t', '').replace('"', '')

if not full_key:
    print("Error: Could not extract key", file=sys.stderr)
    print("File content:", file=sys.stderr)
    print(content, file=sys.stderr)
    sys.exit(1)

# Validate base64
try:
    padding = 4 - len(full_key) % 4
    if padding != 4:
        test_key = full_key + '=' * padding
    else:
        test_key = full_key
    decoded = base64.b64decode(test_key)
    print(full_key)
except Exception as e:
    print(f'Warning: Base64 validation failed: {e}', file=sys.stderr)
    print(full_key)  # Still output it
PYEOF

if [ ! -s dkim_key.txt ]; then
    echo "✗ Failed to extract key from server"
    rm -rf "$TEMP_DIR"
    exit 1
fi

KEY_LENGTH=$(wc -c < dkim_key.txt | tr -d ' ')
echo "✓ Key extracted (length: $KEY_LENGTH characters)"

# Step 2: Create metadata file
echo "Step 2: Creating metadata..."
cat > metadata.txt << EOF
Domain: $DOMAIN
Selector: $SELECTOR
Key Length: $KEY_LENGTH
Extracted: $(date -u +"%Y-%m-%d %H:%M:%S UTC")
EOF

# Step 3: Zip the files
echo "Step 3: Creating zip archive..."
zip -q "$ZIP_FILE" dkim_key.txt metadata.txt
echo "✓ Created: $ZIP_FILE"

# Step 4: Transfer to server
echo "Step 4: Transferring to server..."
scp "$ZIP_FILE" "$SERVER:/tmp/dkim_key.zip"
echo "✓ Transferred to server"

# Step 5: Unzip on server
echo "Step 5: Unzipping on server..."
ssh "$SERVER" "cd /tmp && unzip -q -o dkim_key.zip && cat dkim_key.txt && rm -f dkim_key.zip dkim_key.txt metadata.txt"
echo "✓ Unzipped on server"

# Step 6: Display key for DNS update
echo ""
echo "============================================================"
echo "DKIM Public Key (for DNS update):"
echo "============================================================"
cat dkim_key.txt
echo ""
echo ""
echo "To update DNS, run:"
echo "python scripts/setup_email_dns.py \\"
echo "  --api-key \"88cacc1b670d244fe867557673dfb4e042ffe\" \\"
echo "  --email \"shepherdvovkes@icloud.com\" \\"
echo "  --dkim-selector $SELECTOR \\"
echo "  --dkim-key \"\$(cat $TEMP_DIR/dkim_key.txt)\""
echo ""

# Cleanup
read -p "Keep temporary files? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    rm -rf "$TEMP_DIR" "$ZIP_FILE"
    echo "✓ Cleaned up temporary files"
else
    echo "Files kept in: $TEMP_DIR"
    echo "Zip file: $ZIP_FILE"
fi

