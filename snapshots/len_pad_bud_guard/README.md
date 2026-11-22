# len_pad masters with the bud-guard riser (2026-11-22)

Regenerated from assets/len_pad with scripts/build_len_diorama_pad.py at local
worktree commit 20cc14b (lineage: bcc9d2e on output_len). The floating-pose
character crossed the 10 mm clear slab top as a 2.65 mm bud; the whole figure
hung on it. The builder's bud_guard now raises a slim 12.25 mm riser under the
bud to 19.62 mm above the slot line, so the in-window load path never pinches
below 12 mm (validation_report.json: load_path_floor_mm, bud_guard_risers).
Piece bounding boxes are unchanged to 0.005 mm, so the reviewed A3 placements
hold after a reviewed 2-row source_bounds_mm pin update.

Registered as the 06_len_pad A3 sources in configs/a3_release.json via
git_path entries pointing here.
