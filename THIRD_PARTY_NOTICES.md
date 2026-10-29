# Third-party software

`u9cht/_vendor/titan_u9_flx_archive.py` is an unmodified copy of
`titan-ultima/src/titan/u9/flx_archive.py` from
[tgwUltima](https://github.com/theGreyWanderer-uc/tgwUltima/tree/2b6ee659cb153254ea8e3d2787d601a6fa79f3d2),
commit `2b6ee659cb153254ea8e3d2787d601a6fa79f3d2`, TITAN 0.7.8.

Copyright (c) 2025 theGreyWanderer. MIT license; the full notice is retained in
`u9cht/_vendor/LICENSE.TITAN`. Scope: FLX container reader only. This avoids
installing unrelated graphics/UI dependencies. No game fixtures are vendored.

The project adds strict validation and a layout-preserving serializer because
upstream's generic repacker regenerates unknown header bytes and changes layout.
