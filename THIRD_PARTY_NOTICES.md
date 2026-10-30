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

P4 research additionally used an already-installed Capstone disassembler under
its BSD-style license (installed LICENSE.TXT). Distribution metadata reports
5.0.9; the imported module reports 5.0.7. No Capstone source/binary is vendored,
and it is an optional local dependency of the experimental trace script, not of
the normal text tools or unit suite. No package was installed during this batch.

P5-0 adds an optional, isolated `tools/OctodiffProbe` project using **Octodiff
1.3.23** (assembly 1.3.23.0), Apache License 2.0. This exact historical version
matches UltimaPatcher's dependency and retains its original target-hash check.
It is a private executable-reconstruction research dependency, not a dependency
of the Python FLX tools or ordinary unit tests. No Octodiff binary is vendored.
NuGet package SHA-256:
`ecd44c02fdfe1730fca5ea091e4b7a409380adf994f03923fb11718076f86bf3`.
The package includes `LICENSE.txt`; source reference tag 1.3.23 resolves to
`bc821c41cb3a497e16229c1e81b7a51146abab7e` in
[OctopusDeploy/Octodiff](https://github.com/OctopusDeploy/Octodiff/tree/bc821c41cb3a497e16229c1e81b7a51146abab7e).
The package is deprecated upstream; using its pinned applier here reproduces
the patcher's behavior rather than upgrading an experimental protocol client.
The small Python metadata inspectors are project-written and are not appliers.
