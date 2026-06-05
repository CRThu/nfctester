import argparse
import sys
from nfctester.crypto import AES128Crypto

def main():
    parser = argparse.ArgumentParser(description="AES-128 CLI Tool")
    parser.add_argument("-m", "--mode", choices=["encrypt", "decrypt"], required=True)
    parser.add_argument("-i", "--input", required=True, help="Input hex string (16 bytes)")
    parser.add_argument("-k", "--key", required=True, help="Key hex string (16 bytes)")
    
    args = parser.parse_args()
    
    try:
        data = bytes.fromhex(args.input)
        key = bytes.fromhex(args.key)
        crypto = AES128Crypto()
        
        if args.mode == "encrypt":
            result = crypto.encrypt(data, key)
        else:
            result = crypto.decrypt(data, key)
            
        print(result.hex().upper())
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
