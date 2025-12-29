# Fix DKIM DNS Record for lexapp.co.ua

Your server (`mail.s0me.uk`) has DKIM configured correctly, but the DNS record needs to be updated to match.

## Step 1: Get DKIM Public Key from Server

SSH to your mail server and run:

```bash
ssh user@mail.s0me.uk

# Extract the public key
sudo cat /etc/opendkim/keys/lexapp.co.ua/mail.txt
```

You'll see output like:
```
mail._domainkey.lexapp.co.ua. IN TXT "v=DKIM1; k=rsa; p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQC..." (long key)
```

**Extract the public key**: Copy everything after `p=` and before the closing quote.

**Or use the helper script:**

```bash
# Copy the script to server
scp scripts/get_dkim_key.sh user@mail.s0me.uk:/tmp/

# SSH to server
ssh user@mail.s0me.uk

# Run the script
sudo bash /tmp/get_dkim_key.sh
```

The script will output the public key and the exact command to run.

## Step 2: Update DNS Record

From your local machine, run:

```bash
python scripts/setup_email_dns.py \
  --api-key "88cacc1b670d244fe867557673dfb4e042ffe" \
  --email "shepherdvovkes@icloud.com" \
  --dkim-selector mail \
  --dkim-key "<public_key_from_step_1>"
```

Replace `<public_key_from_step_1>` with the actual public key you copied.

## Step 3: Verify

```bash
# Check DNS record
dig TXT mail._domainkey.lexapp.co.ua

# On server, test again
ssh user@mail.s0me.uk
sudo opendkim-testkey -d lexapp.co.ua -s mail -k /etc/opendkim/keys/lexapp.co.ua/mail.private
```

Both should show success.

## Quick One-Liner (if you have SSH access)

```bash
# Get key from server and update DNS in one go
PUBLIC_KEY=$(ssh user@mail.s0me.uk "sudo grep -oP 'p=\K[^\"\s]+' /etc/opendkim/keys/lexapp.co.ua/mail.txt | tr -d '\n'") && \
python scripts/setup_email_dns.py \
  --api-key "88cacc1b670d244fe867557673dfb4e042ffe" \
  --email "shepherdvovkes@icloud.com" \
  --dkim-selector mail \
  --dkim-key "$PUBLIC_KEY"
```

## Troubleshooting

If the DNS update fails:
1. Make sure the public key doesn't have spaces or newlines
2. Verify the key format: should start with `MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQC...`
3. Check Cloudflare API permissions

After updating, wait 5-15 minutes for DNS propagation, then test again.

