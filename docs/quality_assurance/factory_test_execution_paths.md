# Factory Test Execution Paths

Run fast factory tests, then the full suite. Extract each generated ZIP into a clean temporary directory and invoke pytest with explicit rootdir and `--confcutdir=<app-root>`. Collect line and branch coverage, mutation outcomes, flake reruns and raw denominators. Package only after every hard gate passes.
