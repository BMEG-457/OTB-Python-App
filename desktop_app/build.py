"""Build script for creating the OTB-EMG executable with PyInstaller."""

import subprocess
import sys


def main():
    cmd = [sys.executable, '-m', 'PyInstaller', '--clean', '--noconfirm', 'OTB-EMG.spec']
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    sys.exit(result.returncode)


if __name__ == '__main__':
    main()
