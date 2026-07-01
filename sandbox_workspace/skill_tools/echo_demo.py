import argparse
import json
from pathlib import Path

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--payload', required=True)
    args = parser.parse_args()

    payload_path = Path(args.payload)
    payload = json.loads(payload_path.read_text(encoding='utf-8'))
    arguments = payload.get('arguments', {})
    text = str(arguments.get('text', ''))
    result = {
        'skill': payload.get('skill', 'demo_echo'),
        'received_text': text,
        'length': len(text),
        'status': 'ok',
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
