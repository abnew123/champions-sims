var __defProp = Object.defineProperty;
var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
var __getOwnPropNames = Object.getOwnPropertyNames;
var __hasOwnProp = Object.prototype.hasOwnProperty;
var __export = (target, all) => {
  for (var name in all)
    __defProp(target, name, { get: all[name], enumerable: true });
};
var __copyProps = (to, from, except, desc) => {
  if (from && typeof from === "object" || typeof from === "function") {
    for (let key of __getOwnPropNames(from))
      if (!__hasOwnProp.call(to, key) && key !== except)
        __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
  }
  return to;
};
var __toCommonJS = (mod) => __copyProps(__defProp({}, "__esModule", { value: true }), mod);
var data_mods_champions_abilities_exports = {};
__export(data_mods_champions_abilities_exports, {
  Abilities: () => Abilities
});
module.exports = __toCommonJS(data_mods_champions_abilities_exports);
const Abilities = {
  angershell: {
    inherit: true,
    onDamage(damage, target, source, effect) {
      this.effectState.checkedAngerShell = !(effect.effectType === "Move" && !effect.multihit);
    }
  },
  auraguard: {
    // new in Champions (Mega Lucario Z): halves the damage the Pokemon takes from contact moves
    onSourceModifyDamage(damage, source, target, move) {
      if (move.flags["contact"]) return this.chainModify(0.5);
    },
    flags: { breakable: 1 },
    name: "Aura Guard",
    rating: 3,
    num: 319
  },
  berserk: {
    inherit: true,
    onDamage(damage, target, source, effect) {
      this.effectState.checkedBerserk = !(effect.effectType === "Move" && !effect.multihit);
    }
  },
  dragonize: {
    inherit: true,
    isNonstandard: null
  },
  eelevate: {
    inherit: true,
    isNonstandard: null
  },
  emergencyexit: {
    inherit: true,
    onEmergencyExit(target) {
      if (!this.canSwitch(target.side) || target.forceSwitchFlag || target.switchFlag) return;
      target.switchFlag = true;
      this.add("-activate", target, "ability: Emergency Exit");
    }
  },
  firemane: {
    inherit: true,
    isNonstandard: null
  },
  healer: {
    inherit: true,
    onResidual(pokemon) {
      for (const allyActive of pokemon.adjacentAllies()) {
        if (allyActive.status && this.randomChance(1, 2)) {
          this.add("-activate", pokemon, "ability: Healer");
          allyActive.cureStatus();
        }
      }
    }
  },
  megasol: {
    inherit: true,
    isNonstandard: null
  },
  naturalcure: {
    inherit: true,
    onCheckShow: void 0,
    // no inherit
    onSwitchOut(pokemon) {
      if (!pokemon.status || pokemon.status === "fnt") return;
      this.add("-curestatus", pokemon, pokemon.status, "[from] ability: Natural Cure", "[silent]");
      pokemon.clearStatus();
    }
  },
  piercingdrill: {
    inherit: true,
    isNonstandard: null
  },
  regenerator: {
    inherit: true,
    onSwitchOut(pokemon) {
      if (pokemon.heal(pokemon.baseMaxhp / 3)) {
        this.add("-heal", pokemon, pokemon.getHealth, "[from] ability: Regenerator", "[silent]");
      }
    }
  },
  runaway: {
    inherit: true,
    onTrapPokemonPriority: -10,
    onTrapPokemon(pokemon) {
      pokemon.trapped = false;
    },
    onMaybeTrapPokemonPriority: -10,
    onMaybeTrapPokemon(pokemon) {
      pokemon.maybeTrapped = false;
    }
  },
  spicyspray: {
    inherit: true,
    isNonstandard: null
  },
  unseenfist: {
    inherit: true,
    onModifyMove: void 0,
    // no inherit
    onHitProtect(source, target, move) {
      if (move.flags["contact"]) {
        target.getMoveHitData(move).bypassProtect = this.effect;
        return false;
      }
    }
  },
  wimpout: {
    inherit: true,
    onEmergencyExit(target) {
      if (!this.canSwitch(target.side) || target.forceSwitchFlag || target.switchFlag) return;
      target.switchFlag = true;
      this.add("-activate", target, "ability: Wimp Out");
    }
  }
};
// Annotate the CommonJS export names for ESM import in node:
0 && (module.exports = {
  Abilities
});
