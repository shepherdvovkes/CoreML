#!/usr/bin/env python3
"""
Script to configure SPF and DKIM DNS records for lexapp.co.ua via Cloudflare API
"""
import os
import sys
import json
import argparse
import base64
from typing import Optional, Dict, Any
import httpx


class CloudflareDNSManager:
    """Manages DNS records via Cloudflare API"""
    
    BASE_URL = "https://api.cloudflare.com/client/v4"
    
    def __init__(self, api_token: Optional[str] = None, api_key: Optional[str] = None, email: Optional[str] = None):
        """Initialize with either API token (preferred) or Global API Key + Email"""
        if api_token:
            # Use API Token (Bearer authentication)
            self.headers = {
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json"
            }
        elif api_key and email:
            # Use Global API Key (X-Auth-Key and X-Auth-Email)
            self.headers = {
                "X-Auth-Key": api_key,
                "X-Auth-Email": email,
                "Content-Type": "application/json"
            }
        else:
            raise ValueError("Either api_token or (api_key + email) must be provided")
    
    def get_zone_id(self, domain: str) -> Optional[str]:
        """Get zone ID for a domain"""
        url = f"{self.BASE_URL}/zones"
        params = {"name": domain}
        
        try:
            response = httpx.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if data.get("success") and data.get("result"):
                zone_id = data["result"][0]["id"]
                print(f"✓ Found zone ID for {domain}: {zone_id}")
                return zone_id
            else:
                print(f"✗ Domain {domain} not found in Cloudflare")
                return None
        except httpx.HTTPError as e:
            print(f"✗ Error getting zone ID: {e}")
            return None
    
    def list_dns_records(self, zone_id: str, record_type: str = "TXT") -> list:
        """List DNS records of a specific type"""
        url = f"{self.BASE_URL}/zones/{zone_id}/dns_records"
        params = {"type": record_type}
        
        try:
            response = httpx.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if data.get("success"):
                return data.get("result", [])
            return []
        except httpx.HTTPError as e:
            print(f"✗ Error listing DNS records: {e}")
            return []
    
    def find_spf_record(self, zone_id: str) -> Optional[Dict[str, Any]]:
        """Find existing SPF record"""
        records = self.list_dns_records(zone_id, "TXT")
        for record in records:
            content = record.get("content", "")
            if content.startswith("v=spf1"):
                return record
        return None
    
    def create_or_update_spf_record(
        self, 
        zone_id: str, 
        domain: str, 
        spf_content: str,
        server_ip: str
    ) -> bool:
        """Create or update SPF record"""
        existing_record = self.find_spf_record(zone_id)
        
        # Build SPF content
        spf_record = f"v=spf1 mx a ip4:{server_ip} ~all"
        
        if existing_record:
            # Update existing record
            record_id = existing_record["id"]
            url = f"{self.BASE_URL}/zones/{zone_id}/dns_records/{record_id}"
            
            data = {
                "type": "TXT",
                "name": domain,
                "content": spf_record,
                "ttl": 3600
            }
            
            try:
                response = httpx.patch(url, headers=self.headers, json=data, timeout=30)
                response.raise_for_status()
                result = response.json()
                
                if result.get("success"):
                    print(f"✓ Updated SPF record for {domain}")
                    print(f"  Content: {spf_record}")
                    return True
                else:
                    print(f"✗ Failed to update SPF record: {result.get('errors')}")
                    return False
            except httpx.HTTPError as e:
                print(f"✗ Error updating SPF record: {e}")
                return False
        else:
            # Create new record
            url = f"{self.BASE_URL}/zones/{zone_id}/dns_records"
            
            data = {
                "type": "TXT",
                "name": domain,
                "content": spf_record,
                "ttl": 3600
            }
            
            try:
                response = httpx.post(url, headers=self.headers, json=data, timeout=30)
                response.raise_for_status()
                result = response.json()
                
                if result.get("success"):
                    print(f"✓ Created SPF record for {domain}")
                    print(f"  Content: {spf_record}")
                    return True
                else:
                    print(f"✗ Failed to create SPF record: {result.get('errors')}")
                    return False
            except httpx.HTTPError as e:
                print(f"✗ Error creating SPF record: {e}")
                return False
    
    def find_dmarc_record(self, zone_id: str) -> Optional[Dict[str, Any]]:
        """Find existing DMARC record"""
        records = self.list_dns_records(zone_id, "TXT")
        for record in records:
            name = record.get("name", "")
            content = record.get("content", "")
            if "_dmarc" in name.lower() or content.startswith("v=DMARC1"):
                return record
        return None
    
    def find_dkim_record(self, zone_id: str, selector: str, domain: str) -> Optional[Dict[str, Any]]:
        """Find existing DKIM record"""
        dkim_name = f"{selector}._domainkey.{domain}"
        records = self.list_dns_records(zone_id, "TXT")
        for record in records:
            name = record.get("name", "")
            if name == dkim_name or name.endswith(f".{dkim_name}"):
                return record
        return None
    
    def create_dkim_record(
        self,
        zone_id: str,
        domain: str,
        selector: str,
        public_key: str,
        include_optional: bool = True
    ) -> bool:
        """Create or update DKIM TXT record
        
        Args:
            zone_id: Cloudflare zone ID
            domain: Domain name
            selector: DKIM selector
            public_key: DKIM public key (base64) - can be raw or with whitespace
            include_optional: Include optional parameters (h=sha256, t=y)
        """
        # Clean and validate the base64 key
        # Remove whitespace, newlines, and any p= prefix
        cleaned_key = public_key.strip()
        cleaned_key = cleaned_key.replace(' ', '').replace('\n', '').replace('\t', '')
        if cleaned_key.startswith('p='):
            cleaned_key = cleaned_key[2:]
        if cleaned_key.startswith('p+'):
            cleaned_key = cleaned_key[2:]
        
        # Validate it's valid base64 by trying to decode it
        try:
            # Remove any base64 padding if present for validation
            test_key = cleaned_key.rstrip('=')
            # Try to decode to validate it's proper base64
            base64.b64decode(cleaned_key + '=' * (4 - len(cleaned_key) % 4))
            print(f"✓ Validated base64 key (length: {len(cleaned_key)} characters)")
        except Exception as e:
            print(f"⚠ Warning: Key may not be valid base64: {e}")
            print("  Proceeding anyway, but key validation may fail")
        
        dkim_name = f"{selector}._domainkey.{domain}"
        if include_optional:
            dkim_content = f"v=DKIM1; h=sha256; k=rsa; t=y; p={cleaned_key}"
        else:
            dkim_content = f"v=DKIM1; k=rsa; p={cleaned_key}"
        
        # Check if record already exists
        existing_record = self.find_dkim_record(zone_id, selector, domain)
        
        if existing_record:
            # Update existing record
            record_id = existing_record["id"]
            url = f"{self.BASE_URL}/zones/{zone_id}/dns_records/{record_id}"
            
            data = {
                "type": "TXT",
                "name": dkim_name,
                "content": dkim_content,
                "ttl": 3600
            }
            
            try:
                response = httpx.patch(url, headers=self.headers, json=data, timeout=30)
                response.raise_for_status()
                result = response.json()
                
                if result.get("success"):
                    print(f"✓ Updated DKIM record: {dkim_name}")
                    print(f"  Content: {dkim_content[:50]}...")
                    return True
                else:
                    print(f"✗ Failed to update DKIM record: {result.get('errors')}")
                    return False
            except httpx.HTTPError as e:
                print(f"✗ Error updating DKIM record: {e}")
                return False
        else:
            # Create new record
            url = f"{self.BASE_URL}/zones/{zone_id}/dns_records"
            
            data = {
                "type": "TXT",
                "name": dkim_name,
                "content": dkim_content,
                "ttl": 3600
            }
            
            try:
                response = httpx.post(url, headers=self.headers, json=data, timeout=30)
                response.raise_for_status()
                result = response.json()
                
                if result.get("success"):
                    print(f"✓ Created DKIM record: {dkim_name}")
                    print(f"  Content: {dkim_content[:50]}...")
                    return True
                else:
                    print(f"✗ Failed to create DKIM record: {result.get('errors')}")
                    return False
            except httpx.HTTPError as e:
                print(f"✗ Error creating DKIM record: {e}")
                return False
    
    def create_or_update_dmarc_record(
        self,
        zone_id: str,
        domain: str,
        policy: str = "quarantine",
        pct: int = 100,
        rua: Optional[str] = None,
        ruf: Optional[str] = None
    ) -> bool:
        """Create or update DMARC TXT record
        
        Args:
            zone_id: Cloudflare zone ID
            domain: Domain name
            policy: DMARC policy (none, quarantine, reject)
            pct: Percentage of emails to apply policy (0-100)
            rua: Aggregate report email address (optional)
            ruf: Forensic report email address (optional)
        """
        dmarc_name = f"_dmarc.{domain}"
        
        # Build DMARC record content
        dmarc_parts = [f"v=DMARC1", f"p={policy}", f"pct={pct}"]
        
        if rua:
            dmarc_parts.append(f"rua=mailto:{rua}")
        if ruf:
            dmarc_parts.append(f"ruf=mailto:{ruf}")
        
        dmarc_content = "; ".join(dmarc_parts)
        
        existing_record = self.find_dmarc_record(zone_id)
        
        if existing_record:
            # Update existing record
            record_id = existing_record["id"]
            url = f"{self.BASE_URL}/zones/{zone_id}/dns_records/{record_id}"
            
            data = {
                "type": "TXT",
                "name": dmarc_name,
                "content": dmarc_content,
                "ttl": 3600
            }
            
            try:
                response = httpx.patch(url, headers=self.headers, json=data, timeout=30)
                response.raise_for_status()
                result = response.json()
                
                if result.get("success"):
                    print(f"✓ Updated DMARC record: {dmarc_name}")
                    print(f"  Content: {dmarc_content}")
                    return True
                else:
                    print(f"✗ Failed to update DMARC record: {result.get('errors')}")
                    return False
            except httpx.HTTPError as e:
                print(f"✗ Error updating DMARC record: {e}")
                return False
        else:
            # Create new record
            url = f"{self.BASE_URL}/zones/{zone_id}/dns_records"
            
            data = {
                "type": "TXT",
                "name": dmarc_name,
                "content": dmarc_content,
                "ttl": 3600
            }
            
            try:
                response = httpx.post(url, headers=self.headers, json=data, timeout=30)
                response.raise_for_status()
                result = response.json()
                
                if result.get("success"):
                    print(f"✓ Created DMARC record: {dmarc_name}")
                    print(f"  Content: {dmarc_content}")
                    return True
                else:
                    print(f"✗ Failed to create DMARC record: {result.get('errors')}")
                    return False
            except httpx.HTTPError as e:
                print(f"✗ Error creating DMARC record: {e}")
                return False


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Setup SPF and DKIM DNS records via Cloudflare API")
    parser.add_argument(
        "--token",
        help="Cloudflare API token (or set CLOUDFLARE_API_TOKEN env var)",
        default=None
    )
    parser.add_argument(
        "--api-key",
        help="Cloudflare Global API Key (or set CLOUDFLARE_API_KEY env var)",
        default=None
    )
    parser.add_argument(
        "--email",
        help="Cloudflare account email (required with --api-key, or set CLOUDFLARE_EMAIL env var)",
        default=None
    )
    parser.add_argument(
        "--dkim-selector",
        help="DKIM selector (e.g., 'mail')",
        default=None
    )
    parser.add_argument(
        "--dkim-key",
        help="DKIM public key (from opendkim mail.txt file)",
        default=None
    )
    parser.add_argument(
        "--dmarc-policy",
        help="DMARC policy: none, quarantine, or reject (default: quarantine)",
        choices=["none", "quarantine", "reject"],
        default="quarantine"
    )
    parser.add_argument(
        "--dmarc-pct",
        help="DMARC percentage (0-100, default: 100)",
        type=int,
        default=100
    )
    parser.add_argument(
        "--dmarc-rua",
        help="DMARC aggregate report email (e.g., dmarc@lexapp.co.ua)",
        default=None
    )
    parser.add_argument(
        "--dmarc-ruf",
        help="DMARC forensic report email (e.g., dmarc@lexapp.co.ua)",
        default=None
    )
    parser.add_argument(
        "--setup-dmarc",
        help="Set up DMARC record",
        action="store_true"
    )
    
    args = parser.parse_args()
    
    # Get Cloudflare authentication credentials
    api_token = args.token or os.getenv("CLOUDFLARE_API_TOKEN")
    api_key = args.api_key or os.getenv("CLOUDFLARE_API_KEY")
    email = args.email or os.getenv("CLOUDFLARE_EMAIL")
    
    if not api_token and not (api_key and email):
        try:
            auth_method = input("Use API Token (t) or Global API Key (k)? [t/k]: ").strip().lower()
            if auth_method == 'k':
                api_key = input("Enter your Cloudflare Global API Key: ").strip()
                email = input("Enter your Cloudflare account email: ").strip()
            else:
                api_token = input("Enter your Cloudflare API token: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n✗ Cloudflare authentication is required")
            print("   Options:")
            print("   1. Set CLOUDFLARE_API_TOKEN environment variable")
            print("   2. Use --token argument")
            print("   3. Set CLOUDFLARE_API_KEY and CLOUDFLARE_EMAIL environment variables")
            print("   4. Use --api-key and --email arguments")
            sys.exit(1)
        
        if not api_token and not (api_key and email):
            print("✗ Cloudflare authentication is required")
            sys.exit(1)
    
    # Configuration
    domain = "lexapp.co.ua"
    server_ip = "178.162.234.145"
    
    print(f"\n{'='*60}")
    print(f"Setting up email DNS records for {domain}")
    print(f"{'='*60}\n")
    
    # Initialize manager
    try:
        if api_token:
            manager = CloudflareDNSManager(api_token=api_token)
        else:
            manager = CloudflareDNSManager(api_key=api_key, email=email)
    except ValueError as e:
        print(f"✗ {e}")
        sys.exit(1)
    
    # Get zone ID
    zone_id = manager.get_zone_id(domain)
    if not zone_id:
        print("✗ Could not find zone ID. Exiting.")
        sys.exit(1)
    
    print()
    
    # Setup SPF record
    print("Setting up SPF record...")
    spf_success = manager.create_or_update_spf_record(
        zone_id=zone_id,
        domain=domain,
        spf_content="v=spf1",
        server_ip=server_ip
    )
    
    if not spf_success:
        print("✗ Failed to setup SPF record")
        sys.exit(1)
    
    print()
    
    # DKIM setup instructions
    print(f"{'='*60}")
    print("DKIM Setup Instructions")
    print(f"{'='*60}")
    print("""
DKIM requires server-side configuration. To set up DKIM:

1. Install OpenDKIM on your mail server:
   sudo apt-get install opendkim opendkim-tools

2. Generate DKIM key pair:
   sudo opendkim-genkey -t -s mail -d lexapp.co.ua
   
   This creates:
   - mail.private (private key)
   - mail.txt (public key DNS record)

3. Configure Postfix to use DKIM:
   Add to /etc/postfix/main.cf:
   milter_protocol = 2
   milter_default_action = accept
   smtpd_milters = inet:localhost:8891
   non_smtpd_milters = inet:localhost:8891

4. Configure OpenDKIM:
   Edit /etc/opendkim.conf:
   Domain                  lexapp.co.ua
   KeyFile                 /etc/opendkim/keys/lexapp.co.ua/mail.private
   Selector                mail
   Socket                  inet:8891@localhost

5. After generating the key, run this script again with:
   python scripts/setup_email_dns.py --dkim-selector mail --dkim-key <public_key_from_mail.txt>

   Or manually add the DKIM TXT record in Cloudflare:
   Name: mail._domainkey.lexapp.co.ua
   Type: TXT
   Content: (from mail.txt file)
""")
    
    # Check if DKIM key is provided
    if args.dkim_selector and args.dkim_key:
        print(f"\nSetting up DKIM record with selector '{args.dkim_selector}'...")
        dkim_success = manager.create_dkim_record(
            zone_id=zone_id,
            domain=domain,
            selector=args.dkim_selector,
            public_key=args.dkim_key
        )
        
        if dkim_success:
            print("\n✓ DKIM record created successfully!")
    elif args.dkim_selector or args.dkim_key:
        print("\n✗ Both --dkim-selector and --dkim-key are required for DKIM setup")
    
    # Setup DMARC if requested
    if args.setup_dmarc:
        print(f"\nSetting up DMARC record...")
        dmarc_success = manager.create_or_update_dmarc_record(
            zone_id=zone_id,
            domain=domain,
            policy=args.dmarc_policy,
            pct=args.dmarc_pct,
            rua=args.dmarc_rua,
            ruf=args.dmarc_ruf
        )
        
        if dmarc_success:
            print("\n✓ DMARC record created successfully!")
    
    print(f"\n{'='*60}")
    print("Setup complete!")
    print(f"{'='*60}")
    print("\nNote: DNS changes may take a few minutes to propagate.")
    print("\nVerify DNS records with:")
    print(f"  dig TXT {domain}                    # SPF")
    print(f"  dig TXT mail._domainkey.{domain}    # DKIM (when configured)")
    print(f"  dig TXT _dmarc.{domain}            # DMARC (when configured)")


if __name__ == "__main__":
    main()

