# Starting a new game after loading does not reset the world

2026-11-12. Runtime 0.2.43-p11. Front page sessions on the private copies of both the GOG and Steam releases.

## Observation (human)

Sequence:
1. Main menu → load a saved game.
2. In game, open the menu → Start New Game.

Result: the new game starts with the world of the loaded save.
- The Avatar is back in the starting house.
- Items already taken are missing: belt, clothes, keys.
- The front door is already open.

The human saw it on both releases.

## Status: CONFIRMED native game behaviour

On 2026-11-12 the same sequence was run on the private Steam copy with an unmodified English `u9.exe`. Nothing was injected: no front page, no launcher, no runtime. The items were still missing.

Supporting evidence:
- The starting-state files in `<game>/runtime` (165 `nonfixed.*` files and `NPC.FLX`) are not damaged. They hash identically in three places:
  - the private Steam copy;
  - the original Steam install;
  - the private GOG copy.
- The session did not write any of them; their modification times are unchanged. The leftover state is therefore held in memory, not on disk.
- The runtime touches only text, fonts and input. It never touches world objects or doors.

Workaround for players: to start a new game, quit and restart the game first.

## Related, still UNKNOWN: "cannot move" after loading

The human once saw the Avatar unable to move after the same load → new game sequence.
- It did not happen again in the next two sessions, one of them the unmodified English run.
- A HYPOTHESIS was considered: the hover-name feature (a synthetic held X) was active in the menus while the game was loading. It was not confirmed, because the problem did not reproduce.
- Most likely it is part of the same leftover state, but this is not shown.
- If it comes back, first press and release X once. If movement returns, the hover feature is involved.
