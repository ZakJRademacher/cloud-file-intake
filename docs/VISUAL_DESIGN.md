# Maintaining the presentation

Cloud File Intake / Studio uses Segoe UI and Arial system fonts. No font files are distributed. The layered panels and restrained geometry frame real working results. Source data, validation and exact-money calculations retain their existing definitions.

Edit `design-tokens.json`, then run `python tools/build_theme.py`. This updates the root palette in `web/studio.css`. Component-specific gradients and motion live in that stylesheet. Keep data units, source credits, caveats and explicit status labels visible. Test keyboard focus, a 390-pixel viewport, empty/error states and reduced motion after a change. Do not animate invented numbers.

Run the existing project tests, then `python tools/check_visual_refresh.py --url <local URL> --evidence <new evidence folder> --workdir <scratch folder>`. Install Playwright and its Edge browser support in a development environment for that browser check. Use new evidence folders to preserve historical measurements.

Start the documented local server. These presentation checks do not rerun the historical AWS deployment verification.

Practice: change one brand accent in a disposable copy, rebuild, and explain why a warning or potentially hazardous classification must keep its explicit label. Accept the change only if controls, downloads, counts and mobile layout still work.
