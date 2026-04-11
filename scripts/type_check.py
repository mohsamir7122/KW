#!/usr/bin/env python3
from __future__ import annotations

import compileall


def main() -> int:
    ok_src = compileall.compile_dir('src', quiet=1)
    ok_scripts = compileall.compile_dir('scripts', quiet=1)
    if ok_src and ok_scripts:
        print('type_check: OK (compile-time)')
        return 0
    print('type_check: FAILED')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
