// ===== battle-actions.js:applyRecoilDamage
  applyRecoilDamage(damageDealt, move, pokemon) {
    let recoilDamage = null;
    if (move.struggleRecoil) recoilDamage = this.battle.clampIntRange(Math.round(pokemon.baseMaxhp / 4), 1);
    else if (move.mindBlownRecoil || move.chloroblastRecoil) recoilDamage = Math.round(pokemon.maxhp / 2);
    else if (move.recoil) {
      recoilDamage = this.battle.clampIntRange(Math.round(damageDealt * move.recoil[0] / move.recoil[1]), 1);
    } else return null;
    const hpBeforeRecoil = pokemon.hp;
    if (move.struggleRecoil) {
      this.battle.directDamage(recoilDamage, pokemon, pokemon, { id: "strugglerecoil" });
    } else {
      const effect = move.mindBlownRecoil ? this.dex.conditions.get(move.name) : "recoil";
      this.battle.damage(recoilDamage, pokemon, pokemon, effect);
    }
    if (pokemon.hp <= pokemon.maxhp / 2 && hpBeforeRecoil > pokemon.maxhp / 2) {
      this.battle.runEvent("EmergencyExit", pokemon, pokemon);
    }
    return recoilDamage;
  }
// ===== battle-actions.js:combineResults
  combineResults(left, right) {
    const NOT_FAILURE = "string";
    const NULL = "object";
    const resultsPriorities = ["undefined", NOT_FAILURE, NULL, "boolean", "number"];
    if (resultsPriorities.indexOf(typeof left) > resultsPriorities.indexOf(typeof right)) {
      return left;
    } else if (left && !right && right !== 0) {
      return left;
    } else if (typeof left === "number" && typeof right === "number") {
      return left + right;
    } else {
      return right;
    }
  }
// ===== battle-actions.js:moveHit
  moveHit(targets, pokemon, moveOrMoveName, moveData, isSecondary, isSelf) {
    if (!Array.isArray(targets)) targets = [targets];
    const retVal = this.spreadMoveHit(targets, pokemon, moveOrMoveName, moveData, isSecondary, isSelf)[0][0];
    return retVal === true ? void 0 : retVal;
  }
// ===== battle.js:getCategory
  getCategory(move) {
    return this.dex.moves.get(move).category || "Physical";
  }
// ===== pokemon.js:getActionSpeed
  getActionSpeed() {
    let speed = this.getStat("spe", false, false);
    const trickRoomCheck = this.battle.ruleTable.has("twisteddimensionmod") ? !this.battle.field.getPseudoWeather("trickroom") : this.battle.field.getPseudoWeather("trickroom");
    if (trickRoomCheck) {
      speed = 1e4 - speed;
    }
    return this.battle.trunc(speed, 13);
  }
// ===== pokemon.js:runEffectiveness
  runEffectiveness(move) {
    let totalTypeMod = 0;
    if (this.terastallized && move.type === "Stellar") {
      totalTypeMod = 1;
    } else {
      for (const type of this.getTypes()) {
        let typeMod = this.battle.dex.getEffectiveness(move, type);
        typeMod = this.battle.singleEvent("Effectiveness", move, null, this, type, move, typeMod);
        totalTypeMod += this.battle.runEvent("Effectiveness", this, type, move, typeMod);
      }
    }
    if (this.species.name === "Terapagos-Terastal" && this.hasAbility("Tera Shell") && !this.battle.suppressingAbility(this)) {
      if (move.hit === 1) delete this.abilityState.resisted;
      if (this.abilityState.resisted) return -1;
      if (move.category === "Status" || move.id === "struggle" || !this.runImmunity(move) || totalTypeMod < 0 || this.hp < this.maxhp) {
        return totalTypeMod;
      }
      this.battle.add("-activate", this, "ability: Tera Shell");
      this.abilityState.resisted = true;
      return -1;
    }
    return totalTypeMod;
  }
// ===== pokemon.js:isSemiInvulnerable
  isSemiInvulnerable() {
    return this.volatiles["fly"] || this.volatiles["bounce"] || this.volatiles["dive"] || this.volatiles["dig"] || this.volatiles["phantomforce"] || this.volatiles["shadowforce"] || this.isSkyDropped();
  }
// ===== pokemon.js:isLastActive
  isLastActive() {
    if (!this.isActive) return false;
    const allyActive = this.side.active;
    for (let i = this.position + 1; i < allyActive.length; i++) {
      if (allyActive[i] && !allyActive[i].fainted) return false;
    }
    return true;
  }
// ===== pokemon.js:getSemiLockedMove
  getSemiLockedMove(restrictData) {
    if (restrictData && this.maybeLocked) return null;
    const lockedMove = this.battle.priorityEvent("SemiLockMove", this);
    return lockedMove === true ? null : lockedMove;
  }
// ===== pokemon.js:getMoveData
  getMoveData(move) {
    move = this.battle.dex.moves.get(move);
    for (const moveSlot of this.moveSlots) {
      if (moveSlot.id === move.id) {
        return moveSlot;
      }
    }
    return null;
  }
// ===== battle.js:canSwitch
  canSwitch(side) {
    return this.possibleSwitches(side).length;
  }
// ===== battle.js:getRandomSwitchable
  getRandomSwitchable(side) {
    const canSwitchIn = this.possibleSwitches(side);
    return canSwitchIn.length ? this.sample(canSwitchIn) : null;
  }
// ===== battle.js:addMove
  addMove(...args) {
    this.lastMoveLine = this.log.length;
    this.log.push(`|${args.join("|")}`);
  }
// ===== battle.js:debug
  debug(...activity) {
    if (this.debugMode) {
      this.add("debug", ...activity);
    }
  }
// ===== battle.js:hint
  hint(hint, once, side) {
    if (this.hints.has(side ? `${side.id}|${hint}` : hint)) return;
    if (side) {
      this.addSplit(side.id, ["-hint", hint]);
    } else {
      this.add("-hint", hint);
    }
    if (once) this.hints.add(side ? `${side.id}|${hint}` : hint);
  }
