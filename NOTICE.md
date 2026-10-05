# Notices

This project's own code is under the MIT License (see `LICENSE`).

## Pokémon Showdown

Parts of this repository are derived from [Pokémon Showdown](https://github.com/smogon/pokemon-showdown), which is under the MIT License,
Copyright (c) 2011-2026 Guangcong Luo and other contributors. Its full license text is in `licenses/pokemon-showdown-LICENSE.txt`.

- `native/champ/src/` is a Rust port of Showdown's battle engine and of the handlers of its Champions mod.
- `native/*.json` (`engine_data*.json`, `champions_data.json`) and `pssim/dex_moves_types.json`, `pssim/species_stats.json` are data exported
  from Showdown's data files.
- `pssim/engine_patch/` and `pssim/live/` contain copies of Showdown data files, some with small fixes (see
  `pssim/engine_patch/champions-data.diff`).
- `mxtr/matchup.py` and `teamsearch/mx/matchup.py` reimplement Showdown's damage formula.

The JavaScript sims in `pssim/` run on the `pokemon-showdown` npm package, which is installed by `setup.sh` and is not part of this repository.

## Data

- `regionals/smogon_mc_*_moveset.txt` and the sets derived from it come from Smogon's public usage statistics (https://www.smogon.com/stats/).
- Regional team lists were read from the public standings at https://standings.limitlessvgc.com/. Only anonymised team data is kept here;
  the raw pages and player names are not.
- Regional round pairings and results (`teamsearch/archmatch.py --regionals`) were read from the public standings at
  https://www.pokedata.ovh/. Only per-archetype aggregates are kept here; the raw files with player names are not.
- Replay statistics were computed from public replays at https://replay.pokemonshowdown.com/. The replay logs themselves are not part of
  this repository; the scripts that fetch them are.

## Trademarks

Pokémon and all related names are trademarks of Nintendo, Creatures Inc. and GAME FREAK inc. This is an unofficial fan project and is not
affiliated with or endorsed by them or by The Pokémon Company.
