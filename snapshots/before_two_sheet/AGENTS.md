# Production artwork rules

- Follow `docs/laser-cut-quality.md` for every cutting-file change.
- Use `scripts/laser_paths.py` for generated laser contours. Never serialize a
  raster-traced polygon directly as thousands of cutting lines.
- Preserve artwork scale/placement, hole diameters, slot/tab dimensions and the
  user's protected external 30-piece contours. Inspect protected originals and
  report any findings separately; do not silently edit them.
- Run `python -m unittest discover -s tests` and `python scripts/verify_release.py`
  before publishing. The latter includes every current SVG, AI, PDF and native
  VectorCraft laser plate plus matching ZIP contents. Any owned-path error blocks
  publication. Inspect rendered layouts and enlarged cut paths too.
- Update `output/LASER_PATH_AUDIT.json`, report exact coverage and limitations,
  and mark superseded files as retired. Do not call a file physically tested
  based only on software checks.
- Push source/configuration to main and production output to output_len.
- Do not use image generation for this project unless the user explicitly lifts
  their existing prohibition.
- Do not generate or include fit-test coupons, sample bases, or test keys in
  production layouts or packages. The user explicitly rejected all test pieces.

- Keep current production artifacts registered in configs/a3_release.json. Restore archived inputs only under tmp/source_cache, never under output.
- Before cleanup, verify all candidates against the pushed raw archive before any deletion. Preserve new remote contributions; do not overwrite concurrent branch updates.
