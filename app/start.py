"""Container bootstrap: preserve guest mode and drop root before serving HTTP."""
import os

def main():
    if os.getenv('AGENCY_WALLET_MODE'):
        from .agency_start import main as agency_main
        return agency_main()
    if os.geteuid() == 0:
        os.setgroups([])
        os.setgid(10001)
        os.setuid(10001)
    if os.geteuid() != 10001:
        raise RuntimeError('Unexpected container runtime identity')
    import uvicorn
    uvicorn.run('app.main:app', host='0.0.0.0', port=int(os.getenv('PORT','8080')), workers=1, access_log=False)

if __name__ == '__main__':
    main()
