"""Single-instance Railway sandbox entrypoint; prepare volume then drop root."""
import os
from pathlib import Path

def main():
    if os.getenv('AGENCY_WALLET_MODE') != 'sandbox':
        raise RuntimeError('This image is for the agency sandbox only')
    database = Path(os.environ['UNO_AGENCY_DB_PATH'])
    if database.parent != Path('/data'):
        raise RuntimeError('Agency image requires /data persistent volume')
    if os.geteuid() == 0:
        # Only the dedicated mount directory; never recursively chown arbitrary paths.
        Path('/data').mkdir(exist_ok=True)
        os.chown('/data', 10001, 10001)
        os.setgroups([])
        os.setgid(10001)
        os.setuid(10001)
    if os.geteuid() != 10001:
        raise RuntimeError('Unexpected agency runtime identity')
    import uvicorn
    uvicorn.run('app.main:app', host='0.0.0.0', port=int(os.getenv('PORT','8000')), workers=1, access_log=False)

if __name__ == '__main__':
    main()
