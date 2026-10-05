// ===== pokemon.js:getStat
  getStat(statName, unboosted, unmodified) {
    statName = (0, import_dex.toID)(statName);
    if (statName === "hp") throw new Error("Please read `maxhp` directly");
    let stat = this.storedStats[statName];
    if (unmodified && "wonderroom" in this.battle.field.pseudoWeather) {
      if (statName === "def") {
        statName = "spd";
      } else if (statName === "spd") {
        statName = "def";
      }
    }
    if (!unboosted) {
      let boosts = this.boosts;
      if (!unmodified) {
        boosts = this.battle.runEvent("ModifyBoost", this, null, null, { ...boosts });
      }
      let boost = boosts[statName];
      const boostTable = [1, 1.5, 2, 2.5, 3, 3.5, 4];
      if (boost > 6) boost = 6;
      if (boost < -6) boost = -6;
      if (boost >= 0) {
        stat = Math.floor(stat * boostTable[boost]);
      } else {
        stat = Math.floor(stat / boostTable[-boost]);
      }
    }
    if (!unmodified) {
      const statTable = { atk: "Atk", def: "Def", spa: "SpA", spd: "SpD", spe: "Spe" };
      stat = this.battle.runEvent("Modify" + statTable[statName], this, null, null, stat);
    }
    if (statName === "spe" && stat > 1e4 && !this.battle.format.battle?.trunc) stat = 1e4;
    return stat;
  }
// ===== pokemon.js:calculateStat
  calculateStat(statName, boost, modifier, statUser) {
    statName = (0, import_dex.toID)(statName);
    if (statName === "hp") throw new Error("Please read `maxhp` directly");
    let stat = this.storedStats[statName];
    if ("wonderroom" in this.battle.field.pseudoWeather) {
      if (statName === "def") {
        stat = this.storedStats["spd"];
      } else if (statName === "spd") {
        stat = this.storedStats["def"];
      }
    }
    let boosts = {};
    const boostName = statName;
    boosts[boostName] = boost;
    boosts = this.battle.runEvent("ModifyBoost", statUser || this, null, null, boosts);
    boost = boosts[boostName];
    const boostTable = [1, 1.5, 2, 2.5, 3, 3.5, 4];
    if (boost > 6) boost = 6;
    if (boost < -6) boost = -6;
    if (boost >= 0) {
      stat = Math.floor(stat * boostTable[boost]);
    } else {
      stat = Math.floor(stat / boostTable[-boost]);
    }
    return this.battle.modify(stat, modifier || 1);
  }
// ===== pokemon.js:updateSpeed
  updateSpeed() {
    this.speed = this.getActionSpeed();
  }
// ===== pokemon.js:getTypes
  getTypes(excludeAdded, preterastallized) {
    if (!preterastallized && this.terastallized && this.terastallized !== "Stellar") {
      return [this.terastallized];
    }
    const types = this.battle.runEvent("Type", this, null, null, this.types);
    if (!types.length) types.push(this.battle.gen >= 5 ? "Normal" : "???");
    if (!excludeAdded && this.addedType) return types.concat(this.addedType);
    return types;
  }
// ===== pokemon.js:hasType
  hasType(type) {
    const thisTypes = this.getTypes();
    if (typeof type === "string") {
      return thisTypes.includes(type);
    }
    for (const typeName of type) {
      if (thisTypes.includes(typeName)) return true;
    }
    return false;
  }
// ===== pokemon.js:runStatusImmunity
  runStatusImmunity(type, message) {
    if (this.fainted) return false;
    if (!type) return true;
    if (!this.battle.dex.getImmunity(type, this)) {
      this.battle.debug("natural status immunity");
      if (message) {
        this.battle.add("-immune", this);
      }
      return false;
    }
    const immunity = this.battle.runEvent("Immunity", this, null, null, type);
    if (!immunity) {
      this.battle.debug("artificial status immunity");
      if (message && immunity !== null) {
        this.battle.add("-immune", this);
      }
      return false;
    }
    return true;
  }
// ===== pokemon.js:getMoveHitData
  getMoveHitData(move) {
    if (!move.moveHitData) move.moveHitData = {};
    const slot = this.getSlot();
    return move.moveHitData[slot] || (move.moveHitData[slot] = {
      crit: false,
      typeMod: 0,
      bypassProtect: false
    });
  }
// ===== pokemon.js:foes
  foes(all) {
    return this.side.foes(all);
  }
// ===== pokemon.js:allies
  allies() {
    return this.side.allies().filter((ally) => ally !== this);
  }
// ===== pokemon.js:alliesAndSelf
  alliesAndSelf() {
    return this.side.allies();
  }
// ===== pokemon.js:adjacentAllies
  adjacentAllies() {
    return this.side.allies().filter((ally) => this.isAdjacent(ally));
  }
// ===== pokemon.js:adjacentFoes
  adjacentFoes() {
    if (this.battle.activePerHalf <= 2) return this.side.foes();
    return this.side.foes().filter((foe) => this.isAdjacent(foe));
  }
// ===== pokemon.js:isAdjacent
  isAdjacent(pokemon2) {
    if (this.fainted || pokemon2.fainted) return false;
    if (this.battle.activePerHalf <= 2) return this !== pokemon2;
    if (this.side === pokemon2.side) return Math.abs(this.position - pokemon2.position) === 1;
    return Math.abs(this.position + pokemon2.position + 1 - this.side.active.length) <= 1;
  }
// ===== pokemon.js:isAlly
  isAlly(pokemon) {
    return !!pokemon && (this.side === pokemon.side || this.side.allySide === pokemon.side);
  }
// ===== pokemon.js:getAtLoc
  getAtLoc(targetLoc) {
    let side = this.battle.sides[targetLoc < 0 ? this.side.n % 2 : (this.side.n + 1) % 2];
    targetLoc = Math.abs(targetLoc);
    if (targetLoc > side.active.length) {
      targetLoc -= side.active.length;
      side = this.battle.sides[side.n + 2];
    }
    return side.active[targetLoc - 1];
  }
// ===== pokemon.js:getLocOf
  getLocOf(target) {
    const positionOffset = Math.floor(target.side.n / 2) * target.side.active.length;
    const position = target.position + positionOffset + 1;
    const sameHalf = this.side.n % 2 === target.side.n % 2;
    return sameHalf ? -position : position;
  }
// ===== pokemon.js:removeVolatile
  removeVolatile(status) {
    if (!this.hp) return false;
    status = this.battle.dex.conditions.get(status);
    if (!this.volatiles[status.id]) return false;
    const { linkedPokemon, linkedStatus } = this.volatiles[status.id];
    this.battle.singleEvent("End", status, this.volatiles[status.id], this);
    delete this.volatiles[status.id];
    if (linkedPokemon) {
      this.removeLinkedVolatiles(linkedStatus, linkedPokemon);
    }
    return true;
  }
// ===== pokemon.js:deductPP
  deductPP(move, amount, target) {
    move = this.battle.dex.moves.get(move);
    const ppData = this.getMoveData(move);
    if (!ppData) return 0;
    ppData.used = true;
    if (!ppData.pp) return 0;
    if (!amount) amount = 1;
    ppData.pp -= amount;
    if (ppData.pp < 0) {
      amount += ppData.pp;
      ppData.pp = 0;
    }
    return amount;
  }
// ===== pokemon.js:moveUsed
  moveUsed(move, targetLoc) {
    if (this.battle.gen === 2 && ["metronome", "mimic", "mirrormove", "sketch", "sleeptalk", "transform"].includes(move.id)) {
      this.lastMove = null;
      this.lastMoveEncore = null;
    } else {
      this.lastMove = move;
      if (this.battle.gen === 2) this.lastMoveEncore = move;
    }
    this.lastMoveTargetLoc = targetLoc;
    this.moveThisTurn = move.id;
  }
// ===== pokemon.js:setItem
  setItem(item, source, effect) {
    if (!this.hp || !this.isActive) return false;
    if (typeof item === "string") item = this.battle.dex.items.get(item);
    const effectid = this.battle.effect ? this.battle.effect.id : "";
    if (RESTORATIVE_BERRIES.has("leppaberry")) {
      const inflicted = ["trick", "switcheroo"].includes(effectid);
      const external = inflicted && source && !source.isAlly(this);
      this.pendingStaleness = external ? "external" : "internal";
    } else {
      this.pendingStaleness = void 0;
    }
    const oldItem = this.getItem();
    const oldItemState = this.itemState;
    this.item = item.id;
    this.itemState = this.battle.initEffectState({ id: item.id, target: this });
    if (oldItem.exists) this.battle.singleEvent("End", oldItem, oldItemState, this);
    if (item.id) {
      this.battle.singleEvent("Start", item, this.itemState, this, source, effect);
    }
    return true;
  }
// ===== pokemon.js:takeItem
  takeItem(source) {
    if (!source) source = this;
    if (this.battle.gen <= 4 && (this.itemKnockedOff || source.itemKnockedOff)) return false;
    if (!this.item) return;
    const item = this.getItem();
    if (this.battle.runEvent("TakeItem", this, source, null, item)) {
      this.item = "";
      const oldItemState = this.itemState;
      this.battle.clearEffectState(this.itemState);
      this.pendingStaleness = void 0;
      this.battle.singleEvent("End", item, oldItemState, this);
      this.battle.runEvent("AfterTakeItem", this, null, null, item);
      return item;
    }
    return false;
  }
// ===== pokemon.js:getSlot
  getSlot() {
    const positionOffset = Math.floor(this.side.n / 2) * this.side.active.length;
    const positionLetter = "abcdef".charAt(this.position + positionOffset);
    return this.side.id + positionLetter;
  }
// ===== pokemon.js:ignoringAbility
  ignoringAbility() {
    if (this.battle.gen >= 5 && !this.isActive) return true;
    if (this.getAbility().flags["notransform"] && this.transformed) return true;
    if (this.getAbility().flags["cantsuppress"]) return false;
    if (this.volatiles["gastroacid"]) return true;
    if (this.hasItem("Ability Shield") || this.ability === "neutralizinggas") return false;
    for (const pokemon of this.battle.getAllActive()) {
      if (pokemon.ability === "neutralizinggas" && !pokemon.volatiles["gastroacid"] && !pokemon.transformed && !pokemon.abilityState.ending && !this.volatiles["commanding"]) {
        return true;
      }
    }
    return false;
  }
// ===== pokemon.js:ignoringItem
  ignoringItem(isFling = false) {
    if (this.getItem().isPrimalOrb) return false;
    if (this.battle.gen >= 5 && !this.isActive) return true;
    if (this.volatiles["embargo"] || this.battle.field.pseudoWeather["magicroom"]) return true;
    if (isFling) return this.battle.gen >= 5 && this.hasAbility("klutz");
    return !this.getItem().ignoreKlutz && this.hasAbility("klutz");
  }
// ===== pokemon.js:hasAbility
  hasAbility(ability) {
    if (Array.isArray(ability)) {
      if (!ability.map(import_dex.toID).includes(this.ability)) return false;
    } else {
      if ((0, import_dex.toID)(ability) !== this.ability) return false;
    }
    return !this.ignoringAbility();
  }
// ===== pokemon.js:hasItem
  hasItem(item) {
    if (Array.isArray(item)) {
      if (!item.map(import_dex.toID).includes(this.item)) return false;
    } else {
      if ((0, import_dex.toID)(item) !== this.item) return false;
    }
    return !this.ignoringItem();
  }
// ===== pokemon.js:getLockedMove
  getLockedMove() {
    const lockedMove = this.battle.priorityEvent("LockMove", this);
    return lockedMove === true ? null : lockedMove;
  }
// ===== pokemon.js:disableMove
  disableMove(moveid, isHidden, sourceEffect) {
    if (!sourceEffect && this.battle.event) {
      sourceEffect = this.battle.effect;
    }
    moveid = (0, import_dex.toID)(moveid);
    for (const moveSlot of this.moveSlots) {
      if (moveSlot.id === moveid && moveSlot.disabled !== true) {
        moveSlot.disabled = isHidden ? "hidden" : true;
        moveSlot.disabledSource = sourceEffect?.name || moveSlot.move;
      }
    }
  }
// ===== pokemon.js:getMoveRequestData
  getMoveRequestData() {
    let lockedMove = this.getLockedMove();
    const hardLocked = !!lockedMove;
    if (lockedMove) {
      this.trapped = true;
    } else {
      lockedMove = this.maybeLocked ? null : this.getSemiLockedMove(true);
    }
    const isLastActive = this.isLastActive();
    const canSwitchIn = this.battle.canSwitch(this.side) > 0;
    let moves = this.getMoves(lockedMove, isLastActive);
    if (this.battle.gen === 1 && !lockedMove && (["frz", "slp"].includes(this.status) || this.volatiles["partiallytrapped"] && !this.maybeLocked)) {
      moves = [{ move: "Fight", id: "fight" }];
      lockedMove = "fight";
    } else if (!moves.length) {
      moves = [{ move: "Struggle", id: "struggle", target: "randomNormal", disabled: false }];
      lockedMove = "struggle";
    }
    const data = {
      moves
    };
    if (hardLocked || !isLastActive) {
      this.maybeDisabled = false;
      this.maybeLocked = false;
      this.maybeTrapped = false;
      if (hardLocked || canSwitchIn) {
        if (this.trapped) data.trapped = true;
      }
    } else {
      this.maybeLocked = this.maybeLocked || this.maybeDisabled;
      if (this.maybeDisabled) {
        data.maybeDisabled = this.maybeDisabled;
      }
      if (this.maybeLocked) {
        data.maybeLocked = this.maybeLocked;
      }
      if (canSwitchIn) {
        if (this.trapped === true) {
          data.trapped = true;
        } else if (this.maybeTrapped) {
          data.maybeTrapped = true;
        }
      }
    }
    if (!lockedMove) {
      if (this.canMegaEvo) data.canMegaEvo = true;
      if (this.canMegaEvoX) data.canMegaEvoX = true;
      if (this.canMegaEvoY) data.canMegaEvoY = true;
      if (this.canUltraBurst) data.canUltraBurst = true;
      const canZMove = this.battle.actions.canZMove(this);
      if (canZMove) data.canZMove = canZMove;
      if (this.getDynamaxRequest()) data.canDynamax = true;
      if (data.canDynamax || this.volatiles["dynamax"]) data.maxMoves = this.getDynamaxRequest(true);
      if (this.canTerastallize) data.canTerastallize = this.canTerastallize;
    }
    return data;
  }
// ===== pokemon.js:getMoves
  getMoves(lockedMove, restrictData) {
    if (lockedMove) {
      lockedMove = (0, import_dex.toID)(lockedMove);
      if (lockedMove === "recharge") {
        return [{
          move: "Recharge",
          id: "recharge"
        }];
      }
      for (const moveSlot of this.moveSlots) {
        if (moveSlot.id !== lockedMove) continue;
        return [{
          move: moveSlot.move,
          id: moveSlot.id
        }];
      }
      return [{
        move: this.battle.dex.moves.get(lockedMove).name,
        id: lockedMove
      }];
    }
    const moves = [];
    let hasValidMove = false;
    for (const moveSlot of this.moveSlots) {
      let moveName = moveSlot.move;
      if (moveSlot.id === "hiddenpower") {
        moveName = `Hidden Power ${this.hpType}`;
        if (this.battle.gen < 6) moveName += ` ${this.hpPower}`;
      } else if (moveSlot.id === "return" || moveSlot.id === "frustration") {
        const basePowerCallback = this.battle.dex.moves.get(moveSlot.id).basePowerCallback;
        moveName += ` ${basePowerCallback(this)}`;
      }
      let target = moveSlot.target;
      switch (moveSlot.id) {
        case "curse":
          if (!this.hasType("Ghost")) {
            target = this.battle.dex.moves.get("curse").nonGhostTarget;
          }
          break;
        case "pollenpuff":
          if (this.volatiles["healblock"]) {
            target = "adjacentFoe";
          }
          break;
        case "terastarstorm":
          if (this.species.name === "Terapagos-Stellar") {
            target = "allAdjacentFoes";
          }
          break;
      }
      let disabled = moveSlot.disabled;
      if (this.volatiles["dynamax"]) {
        const canCauseStruggle = ["Encore", "Disable", "Taunt", "Assault Vest", "Belch", "Stuff Cheeks"];
        disabled = this.maxMoveDisabled(moveSlot.id) || disabled && canCauseStruggle.includes(moveSlot.disabledSource);
      } else if (moveSlot.pp <= 0) {
        disabled = true;
      }
      if (disabled === "hidden") {
        disabled = !restrictData;
      }
      if (!disabled) {
        hasValidMove = true;
      }
      moves.push({
        move: moveName,
        id: moveSlot.id,
        pp: moveSlot.pp,
        maxpp: moveSlot.maxpp,
        target,
        disabled
      });
    }
    return hasValidMove ? moves : [];
  }
// ===== pokemon.js:heal
  heal(d, source = null, effect = null) {
    if (!this.hp) return false;
    d = this.battle.trunc(d);
    if (isNaN(d)) return false;
    if (d <= 0) return false;
    if (this.hp >= this.maxhp) return false;
    this.hp += d;
    if (this.hp > this.maxhp) {
      d -= this.hp - this.maxhp;
      this.hp = this.maxhp;
    }
    return d;
  }
// ===== pokemon.js:sethp
  sethp(d) {
    if (!this.hp) return 0;
    d = this.battle.trunc(d);
    if (isNaN(d)) return;
    if (d < 1) d = 1;
    d -= this.hp;
    this.hp += d;
    if (this.hp > this.maxhp) {
      d -= this.hp - this.maxhp;
      this.hp = this.maxhp;
    }
    return d;
  }
// ===== pokemon.js:clearStatus
  clearStatus() {
    if (!this.hp || !this.status) return false;
    if (this.status === "slp" && this.removeVolatile("nightmare")) {
      this.battle.add("-end", this, "Nightmare", "[silent]");
    }
    this.setStatus("");
    return true;
  }
// ===== pokemon.js:effectiveWeather
  effectiveWeather(sourceEffect, message) {
    if (!sourceEffect && this.battle.effect) sourceEffect = this.battle.effect;
    const weather = this.battle.field.effectiveWeather();
    if (this.battle.activePokemon?.hasAbility("megasol") && sourceEffect && (sourceEffect.id === "megasol" || sourceEffect.effectType === "Move" || sourceEffect.effectType === "Weather") && sourceEffect.id !== "electroshot") {
      if (weather !== "sunnyday" && message) this.battle.add("-activate", this, "ability: Mega Sol");
      return "sunnyday";
    }
    switch (weather) {
      case "sunnyday":
      case "raindance":
      case "desolateland":
      case "primordialsea":
        if (this.hasItem("utilityumbrella")) return "";
    }
    return weather;
  }
// ===== pokemon.js:getCappedBoost
  getCappedBoost(boosts) {
    const cappedBoost = {};
    let boostName;
    for (boostName in boosts) {
      const boost = boosts[boostName];
      if (!boost) continue;
      cappedBoost[boostName] = this.battle.clampIntRange(this.boosts[boostName] + boost, -6, 6) - this.boosts[boostName];
    }
    return cappedBoost;
  }
// ===== pokemon.js:setSpecies
  setSpecies(rawSpecies, source = this.battle.effect, isTransform = false) {
    const species = this.battle.runEvent("ModifySpecies", this, null, source, rawSpecies);
    if (!species) return null;
    this.species = species;
    this.setType(species.types, true);
    this.apparentType = rawSpecies.types.join("/");
    this.addedType = species.addedType || "";
    this.knownType = true;
    this.weighthg = species.weighthg;
    const stats = this.battle.spreadModify(this.species.baseStats, this.set);
    if (this.species.maxHP) stats.hp = this.species.maxHP;
    if (!this.maxhp) {
      this.baseMaxhp = stats.hp;
      this.maxhp = stats.hp;
      this.hp = stats.hp;
    }
    if (!isTransform) this.baseStoredStats = stats;
    let statName;
    for (statName in this.storedStats) {
      this.storedStats[statName] = stats[statName];
      if (this.modifiedStats) this.modifiedStats[statName] = stats[statName];
    }
    if (this.battle.gen <= 1) {
      if (this.status === "par") this.modifyStat("spe", 0.25);
      if (this.status === "brn") this.modifyStat("atk", 0.5);
    }
    this.speed = this.storedStats.spe;
    return species;
  }
// ===== pokemon.js:getWeight
  getWeight() {
    const weighthg = this.battle.runEvent("ModifyWeight", this, null, null, this.weighthg);
    return Math.max(1, weighthg);
  }
// ===== pokemon.js:getStatus
  getStatus() {
    return this.battle.dex.conditions.getByID(this.status);
  }
// ===== pokemon.js:getVolatile
  getVolatile(status) {
    status = this.battle.dex.conditions.get(status);
    if (!this.volatiles[status.id]) return null;
    return status;
  }
// ===== pokemon.js:getItem
  getItem() {
    return this.battle.dex.items.getByID(this.item);
  }
// ===== pokemon.js:getAbility
  getAbility() {
    return this.battle.dex.abilities.getByID(this.ability);
  }
// ===== pokemon.js:setAbility
  setAbility(ability, source, sourceEffect, isFromFormeChange = false, isTransform = false) {
    if (!this.hp) return false;
    if (typeof ability === "string") ability = this.battle.dex.abilities.get(ability);
    if (!sourceEffect && this.battle.effect) sourceEffect = this.battle.effect;
    const oldAbility = this.battle.dex.abilities.get(this.ability);
    if (!isFromFormeChange) {
      if (ability.flags["cantsuppress"] || this.getAbility().flags["cantsuppress"]) return false;
    }
    if (!isFromFormeChange && !isTransform) {
      const setAbilityEvent = this.battle.runEvent("SetAbility", this, source, sourceEffect, ability);
      if (!setAbilityEvent) return setAbilityEvent;
    }
    this.battle.singleEvent("End", oldAbility, this.abilityState, this, source);
    this.ability = ability.id;
    this.abilityState = this.battle.initEffectState({ id: ability.id, target: this });
    if (sourceEffect && !isFromFormeChange && !isTransform) {
      switch (sourceEffect.id) {
        case "mummy":
        case "lingeringaroma":
          this.battle.add("-activate", source, sourceEffect.fullname, this, "[ability] " + oldAbility.name);
          break;
        default:
          if (source) {
            this.battle.add("-ability", this, ability.name, oldAbility.name, `[from] ${sourceEffect.fullname}`, `[of] ${source}`);
          } else {
            this.battle.add("-ability", this, ability.name, oldAbility.name, `[from] ${sourceEffect.fullname}`);
          }
          break;
      }
    }
    if (ability.id && this.battle.gen > 3 && (!isTransform || oldAbility.id !== ability.id || this.battle.gen <= 4)) {
      this.battle.singleEvent("Start", ability, this.abilityState, this, source);
    }
    return oldAbility.id;
  }
// ===== pokemon.js:hasMove
  hasMove(moveid) {
    moveid = (0, import_dex.toID)(moveid);
    if (moveid.substr(0, 11) === "hiddenpower") moveid = "hiddenpower";
    for (const moveSlot of this.moveSlots) {
      if (moveid === moveSlot.id) {
        return moveid;
      }
    }
    return false;
  }
// ===== pokemon.js:getUndynamaxedHP
  getUndynamaxedHP(amount) {
    const hp = amount || this.hp;
    if (this.volatiles["dynamax"]) {
      return Math.ceil(hp * this.baseMaxhp / this.maxhp);
    }
    return hp;
  }
// NOT FOUND pokemon.js:runSwitchIn
// ===== pokemon.js:addType
  addType(newType) {
    if (this.terastallized) return false;
    this.addedType = newType;
    return true;
  }
// ===== pokemon.js:setType
  setType(newType, enforce = false) {
    if (!enforce) {
      if (typeof newType === "string" ? newType === "Stellar" : newType.includes("Stellar")) return false;
      if (this.battle.gen >= 5 && (this.species.num === 493 || this.species.num === 773) || this.battle.gen === 4 && this.hasAbility("multitype")) {
        return false;
      }
      if (this.terastallized) return false;
    }
    if (!newType) throw new Error("Must pass type to setType");
    this.types = typeof newType === "string" ? [newType] : newType;
    this.addedType = "";
    this.knownType = true;
    this.apparentType = this.types.join("/");
    return true;
  }
// NOT FOUND pokemon.js:getHealth
// ===== pokemon.js:transformInto
  transformInto(pokemon, effect) {
    const species = pokemon.species;
    if (pokemon.fainted || this.illusion || pokemon.illusion || pokemon.volatiles["substitute"] && this.battle.gen >= 5 || pokemon.transformed && this.battle.gen >= 2 || this.transformed && this.battle.gen >= 5 || species.name === "Eternatus-Eternamax" || ["Ogerpon", "Terapagos"].includes(species.baseSpecies) && (this.terastallized || pokemon.terastallized) || this.terastallized === "Stellar") {
      return false;
    }
    if (this.battle.dex.currentMod === "gen1stadium" && (species.name === "Ditto" || this.species.name === "Ditto" && pokemon.moves.includes("transform"))) {
      return false;
    }
    if (!this.setSpecies(species, effect, true)) return false;
    this.transformed = true;
    this.weighthg = pokemon.weighthg;
    const types = pokemon.getTypes(true, true);
    this.setType(pokemon.volatiles["roost"] ? pokemon.volatiles["roost"].typeWas : types, true);
    this.addedType = pokemon.addedType;
    this.knownType = this.isAlly(pokemon) && pokemon.knownType;
    this.apparentType = pokemon.apparentType;
    let statName;
    for (statName in this.storedStats) {
      this.storedStats[statName] = pokemon.storedStats[statName];
      if (this.modifiedStats) this.modifiedStats[statName] = pokemon.modifiedStats[statName];
    }
    this.moveSlots = [];
    this.hpType = this.battle.gen >= 5 ? this.hpType : pokemon.hpType;
    this.hpPower = this.battle.gen >= 5 ? this.hpPower : pokemon.hpPower;
    this.timesAttacked = pokemon.timesAttacked;
    for (const [i, moveSlot] of pokemon.moveSlots.entries()) {
      let moveName = moveSlot.move;
      if (moveSlot.id === "hiddenpower") {
        moveName = "Hidden Power " + this.hpType;
      }
      const move = this.battle.dex.moves.get(moveSlot.id);
      const pp = Math.min(5, move.pp);
      this.moveSlots.push({
        move: moveName,
        id: moveSlot.id,
        pp,
        maxpp: this.battle.gen >= 5 ? pp : this.battle.calculatePP(move, this.ppUps[i] || 0),
        target: moveSlot.target,
        disabled: false,
        used: false,
        virtual: true
      });
    }
    let boostName;
    for (boostName in pokemon.boosts) {
      this.boosts[boostName] = pokemon.boosts[boostName];
    }
    if (this.battle.gen >= 6) {
      const volatilesToCopy = ["dragoncheer", "focusenergy", "gmaxchistrike", "laserfocus"];
      for (const volatile of volatilesToCopy) this.removeVolatile(volatile);
      for (const volatile of volatilesToCopy) {
        if (pokemon.volatiles[volatile]) {
          this.addVolatile(volatile);
          if (volatile === "gmaxchistrike") this.volatiles[volatile].layers = pokemon.volatiles[volatile].layers;
          if (volatile === "dragoncheer") this.volatiles[volatile].hasDragonType = pokemon.volatiles[volatile].hasDragonType;
        }
      }
    }
    if (effect) {
      this.battle.add("-transform", this, pokemon, "[from] " + effect.fullname);
    } else {
      this.battle.add("-transform", this, pokemon);
    }
    if (this.terastallized) {
      this.knownType = true;
      this.apparentType = this.terastallized;
    }
    if (this.battle.gen > 2) this.setAbility(pokemon.ability, this, null, true, true);
    if (this.battle.gen === 4) {
      if (this.species.num === 487) {
        if (this.species.name === "Giratina" && this.item === "griseousorb") {
          this.formeChange("Giratina-Origin");
        } else if (this.species.name === "Giratina-Origin" && this.item !== "griseousorb") {
          this.formeChange("Giratina");
        }
      }
      if (this.species.num === 493) {
        const item = this.getItem();
        const targetForme = item?.onPlate ? "Arceus-" + item.onPlate : "Arceus";
        if (this.species.name !== targetForme) {
          this.formeChange(targetForme);
        }
      }
    }
    if (["Ogerpon", "Terapagos"].includes(this.species.baseSpecies) && this.canTerastallize) this.canTerastallize = false;
    return true;
  }
// ===== pokemon.js:isGrounded
  isGrounded(negateImmunity = false) {
    if ("gravity" in this.battle.field.pseudoWeather) return true;
    if ("ingrain" in this.volatiles && this.battle.gen >= 4) return true;
    if ("smackdown" in this.volatiles) return true;
    const item = this.ignoringItem() ? "" : this.item;
    if (item === "ironball") return true;
    if (!negateImmunity && this.hasType("Flying") && !(this.hasType("???") && "roost" in this.volatiles)) return false;
    if (this.hasAbility(["levitate", "eelevate"]) && !this.battle.suppressingAbility(this)) return null;
    if ("magnetrise" in this.volatiles) return false;
    if ("telekinesis" in this.volatiles) return false;
    return item !== "airballoon";
  }
// ===== pokemon.js:clearVolatile
  clearVolatile(includeSwitchFlags = true) {
    this.boosts = {
      atk: 0,
      def: 0,
      spa: 0,
      spd: 0,
      spe: 0,
      accuracy: 0,
      evasion: 0
    };
    this.moveSlots = this.baseMoveSlots.slice();
    this.transformed = false;
    this.ability = this.baseAbility;
    this.hpType = this.baseHpType;
    this.hpPower = this.baseHpPower;
    if (this.canTerastallize === false) this.canTerastallize = this.teraType;
    for (const i in this.volatiles) {
      if (this.volatiles[i].linkedStatus) {
        this.removeLinkedVolatiles(this.volatiles[i].linkedStatus, this.volatiles[i].linkedPokemon);
      }
    }
    if (this.species.name === "Eternatus-Eternamax" && this.volatiles["dynamax"]) {
      this.volatiles = { dynamax: this.volatiles["dynamax"] };
    } else {
      this.volatiles = {};
    }
    if (includeSwitchFlags) {
      this.switchFlag = false;
      this.forceSwitchFlag = false;
    }
    this.lastMove = null;
    this.lastMoveEncore = null;
    this.lastMoveUsed = null;
    this.moveThisTurn = "";
    this.moveLastTurnResult = void 0;
    this.moveThisTurnResult = void 0;
    this.lastDamage = 0;
    this.attackedBy = [];
    this.hurtThisTurn = null;
    this.newlySwitched = true;
    this.beingCalledBack = false;
    this.volatileStaleness = void 0;
    delete this.abilityState.started;
    delete this.itemState.started;
    this.setSpecies(this.baseSpecies);
  }
// ===== pokemon.js:updateMaxHp
  updateMaxHp() {
    const newBaseMaxHp = this.battle.statModify(this.species.baseStats, this.set, "hp");
    if (newBaseMaxHp === this.baseMaxhp) return;
    this.baseMaxhp = newBaseMaxHp;
    const newMaxHP = this.volatiles["dynamax"] ? 2 * this.baseMaxhp : this.baseMaxhp;
    this.hp = this.hp <= 0 ? 0 : Math.max(1, newMaxHP - (this.maxhp - this.hp));
    this.maxhp = newMaxHP;
    if (this.hp) this.battle.add("-heal", this, this.getHealth, "[silent]");
  }
// ===== pokemon.js:getSmartTargets
  getSmartTargets(target, move) {
    const target2 = target.adjacentAllies()[0];
    if (!target2 || target2 === this || !target2.hp) {
      move.smartTarget = false;
      return [target];
    }
    if (!target.hp) {
      move.smartTarget = false;
      return [target2];
    }
    return [target, target2];
  }
// ===== pokemon.js:getLastAttackedBy
  getLastAttackedBy() {
    if (this.attackedBy.length === 0) return void 0;
    return this.attackedBy[this.attackedBy.length - 1];
  }
// ===== pokemon.js:gotAttacked
  gotAttacked(move, damage, source) {
    const damageNumber = typeof damage === "number" ? damage : 0;
    move = this.battle.dex.moves.get(move);
    this.attackedBy.push({
      source,
      damage: damageNumber,
      move: move.id,
      thisTurn: true,
      slot: source.getSlot(),
      damageValue: damage
    });
  }
// ===== pokemon.js:getNature
  getNature() {
    return this.battle.dex.natures.get(this.set.nature);
  }
// ===== side.js:foePokemonLeft
  foePokemonLeft() {
    if (this.battle.gameType === "freeforall") {
      return this.battle.sides.filter((side) => side !== this).map((side) => side.pokemonLeft).reduce((a, b) => a + b);
    }
    if (this.foe.allySide) return this.foe.pokemonLeft + this.foe.allySide.pokemonLeft;
    return this.foe.pokemonLeft;
  }
// ===== side.js:randomFoe
  randomFoe() {
    const actives = this.foes();
    if (!actives.length) return null;
    return this.battle.sample(actives);
  }
// ===== side.js:foes
  foes(all) {
    if (this.battle.gameType === "freeforall") {
      return this.battle.sides.map((side) => side.active[0]).filter((pokemon) => pokemon && pokemon.side !== this && (all || !!pokemon.hp));
    }
    return this.foe.allies(all);
  }
// ===== side.js:allies
  allies(all) {
    let allies = this.activeTeam().filter((ally) => ally);
    if (!all) allies = allies.filter((ally) => !!ally.hp);
    return allies;
  }
// ===== side.js:addSideCondition
  addSideCondition(status, source = null, sourceEffect = null) {
    if (!source && this.battle.event?.target) source = this.battle.event.target;
    if (source === "debug") source = this.active[0];
    if (!source) throw new Error(`setting sidecond without a source`);
    if (!source.getSlot) source = source.active[0];
    status = this.battle.dex.conditions.get(status);
    if (this.sideConditions[status.id]) {
      if (!status.onSideRestart) return false;
      return this.battle.singleEvent("SideRestart", status, this.sideConditions[status.id], this, source, sourceEffect);
    }
    this.sideConditions[status.id] = this.battle.initEffectState({
      id: status.id,
      target: this,
      source,
      sourceSlot: source.getSlot(),
      duration: status.duration
    });
    if (status.durationCallback) {
      this.sideConditions[status.id].duration = status.durationCallback.call(this.battle, this.active[0], source, sourceEffect);
    }
    if (!this.battle.singleEvent("SideStart", status, this.sideConditions[status.id], this, source, sourceEffect)) {
      delete this.sideConditions[status.id];
      return false;
    }
    this.battle.runEvent("SideConditionStart", this, source, status);
    return true;
  }
// ===== side.js:removeSideCondition
  removeSideCondition(status) {
    status = this.battle.dex.conditions.get(status);
    if (!this.sideConditions[status.id]) return false;
    this.battle.singleEvent("SideEnd", status, this.sideConditions[status.id], this);
    delete this.sideConditions[status.id];
    return true;
  }
// ===== side.js:getSideCondition
  getSideCondition(status) {
    status = this.battle.dex.conditions.get(status);
    if (!this.sideConditions[status.id]) return null;
    return status;
  }
// ===== side.js:addSlotCondition
  addSlotCondition(target, status, source = null, sourceEffect = null) {
    source ??= this.battle.event?.target || null;
    if (source === "debug") source = this.active[0];
    if (target instanceof import_pokemon.Pokemon) target = target.position;
    if (!source) throw new Error(`setting sidecond without a source`);
    status = this.battle.dex.conditions.get(status);
    if (this.slotConditions[target][status.id]) {
      if (!status.onRestart) return false;
      return this.battle.singleEvent("Restart", status, this.slotConditions[target][status.id], this, source, sourceEffect);
    }
    const conditionState = this.slotConditions[target][status.id] = this.battle.initEffectState({
      id: status.id,
      target: this,
      source,
      sourceSlot: source.getSlot(),
      isSlotCondition: true,
      duration: status.duration
    });
    if (status.durationCallback) {
      conditionState.duration = status.durationCallback.call(this.battle, this.active[0], source, sourceEffect);
    }
    if (!this.battle.singleEvent("Start", status, conditionState, this.active[target], source, sourceEffect)) {
      delete this.slotConditions[target][status.id];
      return false;
    }
    return true;
  }
// ===== side.js:removeSlotCondition
  removeSlotCondition(target, status) {
    if (target instanceof import_pokemon.Pokemon) target = target.position;
    status = this.battle.dex.conditions.get(status);
    if (!this.slotConditions[target][status.id]) return false;
    this.battle.singleEvent("End", status, this.slotConditions[target][status.id], this.active[target]);
    delete this.slotConditions[target][status.id];
    return true;
  }
// ===== field.js:setWeather
  setWeather(status, source = null, sourceEffect = null) {
    status = this.battle.dex.conditions.get(status);
    if (!sourceEffect && this.battle.effect) sourceEffect = this.battle.effect;
    if (!source && this.battle.event?.target) source = this.battle.event.target;
    if (source === "debug") source = this.battle.sides[0].active[0];
    if (this.weather === status.id) {
      if (sourceEffect && sourceEffect.effectType === "Ability") {
        if (this.battle.gen > 5 || this.weatherState.duration === 0) {
          return false;
        }
      } else if (this.battle.gen > 2 || status.id === "sandstorm") {
        return false;
      }
    }
    if (source) {
      const result = this.battle.runEvent("SetWeather", source, source, status);
      if (!result) {
        if (result === false) {
          if (sourceEffect?.weather) {
            this.battle.add("-fail", source, sourceEffect, "[from] " + this.weather);
          } else if (sourceEffect && sourceEffect.effectType === "Ability") {
            this.battle.add("-ability", source, sourceEffect, "[from] " + this.weather, "[fail]");
          }
        }
        return null;
      }
    }
    const prevWeather = this.weather;
    const prevWeatherState = this.weatherState;
    this.weather = status.id;
    this.weatherState = this.battle.initEffectState({ id: status.id });
    if (source) {
      this.weatherState.source = source;
      this.weatherState.sourceSlot = source.getSlot();
    }
    if (status.duration) {
      this.weatherState.duration = status.duration;
    }
    if (status.durationCallback) {
      if (!source) throw new Error(`setting weather without a source`);
      this.weatherState.duration = status.durationCallback.call(this.battle, source, source, sourceEffect);
    }
    if (!this.battle.singleEvent("FieldStart", status, this.weatherState, this, source, sourceEffect)) {
      this.weather = prevWeather;
      this.weatherState = prevWeatherState;
      return false;
    }
    this.battle.eachEvent("WeatherChange", sourceEffect);
    return true;
  }
// ===== field.js:clearWeather
  clearWeather() {
    if (!this.weather) return false;
    const prevWeather = this.getWeather();
    this.battle.singleEvent("FieldEnd", prevWeather, this.weatherState, this);
    this.weather = "";
    this.battle.clearEffectState(this.weatherState);
    this.battle.eachEvent("WeatherChange");
    return true;
  }
// ===== field.js:effectiveWeather
  effectiveWeather() {
    if (this.suppressingWeather()) return "";
    return this.weather;
  }
// ===== field.js:suppressingWeather
  suppressingWeather() {
    for (const side of this.battle.sides) {
      for (const pokemon of side.active) {
        if (pokemon && !pokemon.fainted && !pokemon.ignoringAbility() && pokemon.getAbility().suppressWeather && !pokemon.abilityState.ending) {
          return true;
        }
      }
    }
    return false;
  }
// ===== field.js:isWeather
  isWeather(weather) {
    const ourWeather = this.effectiveWeather();
    if (!Array.isArray(weather)) {
      return ourWeather === (0, import_dex.toID)(weather);
    }
    return weather.map(import_dex.toID).includes(ourWeather);
  }
// ===== field.js:getWeather
  getWeather() {
    return this.battle.dex.conditions.getByID(this.weather);
  }
// ===== field.js:setTerrain
  setTerrain(status, source = null, sourceEffect = null) {
    status = this.battle.dex.conditions.get(status);
    if (!sourceEffect && this.battle.effect) sourceEffect = this.battle.effect;
    if (!source && this.battle.event?.target) source = this.battle.event.target;
    if (source === "debug") source = this.battle.sides[0].active[0];
    if (!source) throw new Error(`setting terrain without a source`);
    if (this.terrain === status.id) return false;
    const prevTerrain = this.terrain;
    const prevTerrainState = this.terrainState;
    this.terrain = status.id;
    this.terrainState = this.battle.initEffectState({
      id: status.id,
      source,
      sourceSlot: source.getSlot(),
      duration: status.duration
    });
    if (status.durationCallback) {
      this.terrainState.duration = status.durationCallback.call(this.battle, source, source, sourceEffect);
    }
    if (!this.battle.singleEvent("FieldStart", status, this.terrainState, this, source, sourceEffect)) {
      this.terrain = prevTerrain;
      this.terrainState = prevTerrainState;
      return false;
    }
    this.battle.eachEvent("TerrainChange", sourceEffect);
    return true;
  }
// ===== field.js:clearTerrain
  clearTerrain() {
    if (!this.terrain) return false;
    const prevTerrain = this.getTerrain();
    this.battle.singleEvent("FieldEnd", prevTerrain, this.terrainState, this);
    this.terrain = "";
    this.battle.clearEffectState(this.terrainState);
    this.battle.eachEvent("TerrainChange");
    return true;
  }
// ===== field.js:effectiveTerrain
  effectiveTerrain(target) {
    if (this.battle.event && !target) target = this.battle.event.target;
    return this.battle.runEvent("TryTerrain", target) ? this.terrain : "";
  }
// ===== field.js:isTerrain
  isTerrain(terrain, target) {
    const ourTerrain = this.effectiveTerrain(target);
    if (!Array.isArray(terrain)) {
      return ourTerrain === (0, import_dex.toID)(terrain);
    }
    return terrain.map(import_dex.toID).includes(ourTerrain);
  }
// ===== field.js:addPseudoWeather
  addPseudoWeather(status, source = null, sourceEffect = null) {
    if (!source && this.battle.event?.target) source = this.battle.event.target;
    if (source === "debug") source = this.battle.sides[0].active[0];
    status = this.battle.dex.conditions.get(status);
    let state = this.pseudoWeather[status.id];
    if (state) {
      if (!status.onFieldRestart) return false;
      return this.battle.singleEvent("FieldRestart", status, state, this, source, sourceEffect);
    }
    state = this.pseudoWeather[status.id] = this.battle.initEffectState({
      id: status.id,
      source,
      sourceSlot: source?.getSlot(),
      duration: status.duration
    });
    if (status.durationCallback) {
      if (!source) throw new Error(`setting fieldcond without a source`);
      state.duration = status.durationCallback.call(this.battle, source, source, sourceEffect);
    }
    if (!this.battle.singleEvent("FieldStart", status, state, this, source, sourceEffect)) {
      delete this.pseudoWeather[status.id];
      return false;
    }
    this.battle.runEvent("PseudoWeatherChange", source, source, status);
    return true;
  }
// ===== field.js:removePseudoWeather
  removePseudoWeather(status) {
    status = this.battle.dex.conditions.get(status);
    const state = this.pseudoWeather[status.id];
    if (!state) return false;
    this.battle.singleEvent("FieldEnd", status, state, this);
    delete this.pseudoWeather[status.id];
    return true;
  }
// ===== field.js:getPseudoWeather
  getPseudoWeather(status) {
    status = this.battle.dex.conditions.get(status);
    return this.pseudoWeather[status.id] ? status : null;
  }
// ===== battle.js:initEffectState
  initEffectState(obj, effectOrder) {
    if (!obj.id) obj.id = "";
    if (effectOrder !== void 0) {
      obj.effectOrder = effectOrder;
    } else if (obj.id && obj.target && (!(obj.target instanceof import_pokemon.Pokemon) || obj.target.isActive)) {
      obj.effectOrder = this.effectOrder++;
    } else {
      obj.effectOrder = 0;
    }
    return obj;
  }
// ===== battle.js:clearEffectState
  clearEffectState(state) {
    state.id = "";
    for (const k in state) {
      if (k === "id" || k === "target") {
        continue;
      } else if (k === "effectOrder") {
        state.effectOrder = 0;
      } else {
        delete state[k];
      }
    }
  }
// ===== battle.js:getAllPokemon
  getAllPokemon() {
    const pokemonList = [];
    for (const side of this.sides) {
      pokemonList.push(...side.pokemon);
    }
    return pokemonList;
  }
// ===== battle.js:retargetLastMove
  retargetLastMove(newTarget) {
    if (this.lastMoveLine < 0) return;
    const parts = this.log[this.lastMoveLine].split("|");
    parts[4] = newTarget.toString();
    this.log[this.lastMoveLine] = parts.join("|");
  }
// ===== battle.js:attrLastMove
  attrLastMove(...args) {
    if (this.lastMoveLine < 0) return;
    if (this.log[this.lastMoveLine].startsWith("|-anim|")) {
      if (args.includes("[still]")) {
        this.log.splice(this.lastMoveLine, 1);
        this.lastMoveLine = -1;
        return;
      }
    } else if (args.includes("[still]")) {
      const parts = this.log[this.lastMoveLine].split("|");
      parts[4] = "";
      this.log[this.lastMoveLine] = parts.join("|");
    }
    this.log[this.lastMoveLine] += `|${args.join("|")}`;
  }
// ===== battle.js:add
  add(...parts) {
    if (!parts.some((part) => typeof part === "function")) {
      this.log.push(`|${parts.join("|")}`);
      return;
    }
    let side = null;
    const secret = [];
    const shared = [];
    for (const part of parts) {
      if (typeof part === "function") {
        const split = part();
        if (side && side !== split.side) throw new Error("Multiple sides passed to add");
        side = split.side;
        secret.push(split.secret);
        shared.push(split.shared);
      } else {
        secret.push(part);
        shared.push(part);
      }
    }
    this.addSplit(side, secret, shared);
  }
// ===== battle.js:checkMoveMakesContact
  checkMoveMakesContact(move, attacker, defender, announcePads = false) {
    if (move.flags["contact"] && attacker.hasItem("protectivepads")) {
      if (announcePads) {
        this.add("-activate", defender, this.effect.fullname);
        this.add("-activate", attacker, "item: Protective Pads");
      }
      return false;
    }
    return !!move.flags["contact"];
  }
// ===== battle.js:getOverflowedTurnCount
  getOverflowedTurnCount() {
    return this.gen >= 8 ? this.trunc(this.turn - 1, 8) : this.turn - 1;
  }
// ===== battle.js:win
  win(side) {
    if (this.ended) return false;
    if (side && typeof side === "string") {
      side = this.getSide(side);
    } else if (!side || !this.sides.includes(side)) {
      side = null;
    }
    this.winner = side ? side.name : "";
    this.add("");
    if (side?.allySide) {
      this.add("win", side.name + " & " + side.allySide.name);
    } else if (side) {
      this.add("win", side.name);
    } else {
      this.add("tie");
    }
    this.ended = true;
    this.requestState = "";
    for (const s of this.sides) {
      if (s) s.activeRequest = null;
    }
    return true;
  }
// ===== battle.js:faint
  faint(pokemon, source, effect) {
    pokemon.faint(source, effect);
  }
// ===== battle.js:swapPosition
  swapPosition(pokemon, newPosition, attributes) {
    if (newPosition >= pokemon.side.active.length) {
      throw new Error("Invalid swap position");
    }
    const target = pokemon.side.active[newPosition];
    if (newPosition !== 1 && (!target || target.fainted)) return false;
    this.add("swap", pokemon, newPosition, attributes || "");
    const side = pokemon.side;
    side.pokemon[pokemon.position] = target;
    side.pokemon[newPosition] = pokemon;
    side.active[pokemon.position] = side.pokemon[pokemon.position];
    side.active[newPosition] = side.pokemon[newPosition];
    if (target) target.position = pokemon.position;
    pokemon.position = newPosition;
    this.runEvent("Swap", target, pokemon);
    this.runEvent("Swap", pokemon, target);
    return true;
  }
// ===== battle.js:validTarget
  validTarget(target, source, targetType) {
    return this.validTargetLoc(source.getLocOf(target), source, targetType);
  }
// ===== battle.js:chain
  chain(previousMod, nextMod) {
    if (Array.isArray(previousMod)) {
      previousMod = this.trunc(previousMod[0] * 4096 / previousMod[1]);
    } else {
      previousMod = this.trunc(previousMod * 4096);
    }
    if (Array.isArray(nextMod)) {
      nextMod = this.trunc(nextMod[0] * 4096 / nextMod[1]);
    } else {
      nextMod = this.trunc(nextMod * 4096);
    }
    return (previousMod * nextMod + 2048 >> 12) / 4096;
  }
// ===== battle.js:chainModify
  chainModify(numerator, denominator = 1) {
    const previousMod = this.trunc(this.event.modifier * 4096);
    if (Array.isArray(numerator)) {
      denominator = numerator[1];
      numerator = numerator[0];
    }
    const nextMod = this.trunc(numerator * 4096 / denominator);
    this.event.modifier = (previousMod * nextMod + 2048 >> 12) / 4096;
  }
// ===== battle.js:finalModify
  finalModify(relayVar) {
    relayVar = this.modify(relayVar, this.event.modifier);
    this.event.modifier = 1;
    return relayVar;
  }
// ===== battle.js:getActionSpeed
  getActionSpeed(action) {
    if (action.choice === "move") {
      let move = action.move;
      if (action.zmove) {
        const zMoveName = this.actions.getZMove(action.move, action.pokemon, true);
        if (zMoveName) {
          const zMove = this.dex.getActiveMove(zMoveName);
          if (zMove.exists && zMove.isZ) {
            move = zMove;
          }
        }
      }
      if (action.maxMove) {
        const maxMoveName = this.actions.getMaxMove(action.maxMove, action.pokemon);
        if (maxMoveName) {
          const maxMove = this.actions.getActiveMaxMove(action.move, action.pokemon);
          if (maxMove.exists && maxMove.isMax) {
            move = maxMove;
          }
        }
      }
      let priority = this.dex.moves.get(move.id).priority;
      const target = this.getTarget(action.pokemon, action.move, action.targetLoc);
      priority = this.singleEvent("ModifyPriority", move, null, action.pokemon, target, null, priority);
      priority = this.runEvent("ModifyPriority", action.pokemon, target, move, priority);
      action.priority = priority + action.fractionalPriority;
      if (this.gen > 5) action.move.priority = priority;
    }
    if (!action.pokemon) {
      action.speed = 1;
    } else {
      if (this.gen <= 4 && action.choice === "move" && action.fractionalPriority < 0) {
        action.speed = -action.pokemon.getStat("spe", false, false);
      } else {
        action.speed = action.pokemon.getActionSpeed();
      }
    }
  }
// ===== battle-actions.js:runMove
  runMove(moveOrMoveName, pokemon, targetLoc, options) {
    pokemon.activeMoveActions++;
    const zMove = options?.zMove;
    const maxMove = options?.maxMove;
    const externalMove = options?.externalMove;
    const originalTarget = options?.originalTarget;
    let sourceEffect = options?.sourceEffect;
    let target = this.battle.getTarget(pokemon, maxMove || zMove || moveOrMoveName, targetLoc, originalTarget);
    let baseMove = this.dex.getActiveMove(moveOrMoveName);
    const priority = baseMove.priority;
    const pranksterBoosted = baseMove.pranksterBoosted;
    if (baseMove.id !== "struggle" && !zMove && !maxMove && !externalMove) {
      const changedMove = this.battle.runEvent("OverrideAction", pokemon, target, baseMove);
      if (changedMove && changedMove !== true) {
        baseMove = this.dex.getActiveMove(changedMove);
        baseMove.priority = priority;
        if (pranksterBoosted) baseMove.pranksterBoosted = pranksterBoosted;
        target = this.battle.getRandomTarget(pokemon, baseMove);
      }
    }
    let move = baseMove;
    if (zMove) {
      move = this.getActiveZMove(baseMove, pokemon);
    } else if (maxMove) {
      move = this.getActiveMaxMove(baseMove, pokemon);
    }
    move.isExternal = externalMove;
    this.battle.setActiveMove(move, pokemon, target);
    const willTryMove = this.battle.runEvent("BeforeMove", pokemon, target, move);
    if (!willTryMove) {
      this.battle.runEvent("MoveAborted", pokemon, target, move);
      this.battle.clearActiveMove(true);
      pokemon.moveThisTurnResult = willTryMove;
      return;
    }
    if (move.flags["cantusetwice"] && pokemon.lastMove?.id === move.id) {
      pokemon.addVolatile(move.id);
    }
    if (move.beforeMoveCallback) {
      if (move.beforeMoveCallback.call(this.battle, pokemon, target, move)) {
        this.battle.clearActiveMove(true);
        pokemon.moveThisTurnResult = false;
        return;
      }
    }
    pokemon.lastDamage = 0;
    if (!externalMove) {
      const lockedMove = pokemon.getLockedMove();
      if (!lockedMove) {
        if (!pokemon.deductPP(baseMove, null, target) && move.id !== "struggle") {
          this.battle.add("cant", pokemon, "nopp", move);
          this.battle.clearActiveMove(true);
          pokemon.moveThisTurnResult = false;
          return;
        }
      } else {
        sourceEffect = this.dex.conditions.get("lockedmove");
      }
      pokemon.moveUsed(move, targetLoc);
    }
    const noLock = externalMove && !pokemon.volatiles["lockedmove"];
    if (zMove) {
      if (pokemon.illusion) {
        this.battle.singleEvent("End", this.dex.abilities.get("Illusion"), pokemon.abilityState, pokemon);
      }
      this.battle.add("-zpower", pokemon);
      pokemon.side.zMoveUsed = true;
    }
    const oldActiveMove = move;
    const moveDidSomething = this.useMove(baseMove, pokemon, { target, sourceEffect, zMove, maxMove });
    this.battle.lastSuccessfulMoveThisTurn = moveDidSomething ? this.battle.activeMove && this.battle.activeMove.id : null;
    if (this.battle.activeMove) move = this.battle.activeMove;
    this.battle.singleEvent("AfterMove", move, null, pokemon, target, move);
    this.battle.runEvent("AfterMove", pokemon, target, move);
    if (move.flags["cantusetwice"] && pokemon.removeVolatile(move.id)) {
      this.battle.add("-hint", `Some effects can force a Pokemon to use ${move.name} again in a row.`);
    }
    if (move.flags["dance"] && moveDidSomething && !move.isExternal) {
      const dancers = [];
      for (const currentPoke of this.battle.getAllActive()) {
        if (pokemon === currentPoke) continue;
        if (currentPoke.hasAbility("dancer") && !currentPoke.isSemiInvulnerable()) {
          dancers.push(currentPoke);
        }
      }
      dancers.sort(
        (a, b) => -(b.storedStats["spe"] - a.storedStats["spe"]) || b.abilityState.effectOrder - a.abilityState.effectOrder
      );
      const targetOf1stDance = this.battle.activeTarget;
      for (const dancer of dancers) {
        if (this.battle.faintMessages()) break;
        if (dancer.fainted) continue;
        this.battle.add("-activate", dancer, "ability: Dancer");
        const dancersTarget = !targetOf1stDance.isAlly(dancer) && pokemon.isAlly(dancer) ? targetOf1stDance : pokemon;
        const dancersTargetLoc = dancer.getLocOf(dancersTarget);
        this.runMove(move.id, dancer, dancersTargetLoc, { sourceEffect: this.dex.abilities.get("dancer"), externalMove: true });
      }
    }
    if (noLock && pokemon.volatiles["lockedmove"]) delete pokemon.volatiles["lockedmove"];
    this.battle.faintMessages();
    this.battle.checkWin();
    if (this.battle.gen <= 4) {
      this.battle.activeMove = oldActiveMove;
    }
  }
// ===== battle-actions.js:useMove
  useMove(move, pokemon, options) {
    pokemon.moveThisTurnResult = void 0;
    const oldMoveResult = pokemon.moveThisTurnResult;
    const moveResult = this.useMoveInner(move, pokemon, options);
    if (oldMoveResult === pokemon.moveThisTurnResult) pokemon.moveThisTurnResult = moveResult;
    return moveResult;
  }
// ===== battle-actions.js:useMoveInner
  useMoveInner(moveOrMoveName, pokemon, options) {
    let target = options?.target;
    let sourceEffect = options?.sourceEffect;
    const zMove = options?.zMove;
    const maxMove = options?.maxMove;
    if (!sourceEffect && this.battle.effect.id) sourceEffect = this.battle.effect;
    if (sourceEffect && ["instruct", "custapberry"].includes(sourceEffect.id)) sourceEffect = null;
    let move = this.dex.getActiveMove(moveOrMoveName);
    pokemon.lastMoveUsed = move;
    if (move.id === "weatherball" && zMove) {
      this.battle.singleEvent("ModifyType", move, null, pokemon, target, move, move);
      if (move.type !== "Normal") sourceEffect = move;
    }
    if (zMove || move.category !== "Status" && sourceEffect && sourceEffect.isZ) {
      move = this.getActiveZMove(move, pokemon);
    }
    if (maxMove && move.category !== "Status") {
      this.battle.singleEvent("ModifyType", move, null, pokemon, target, move, move);
      this.battle.runEvent("ModifyType", pokemon, target, move, move);
    }
    if (maxMove || move.category !== "Status" && sourceEffect && sourceEffect.isMax) {
      move = this.getActiveMaxMove(move, pokemon);
    }
    if (this.battle.activeMove) {
      move.priority = this.battle.activeMove.priority;
      if (!move.hasBounced) move.pranksterBoosted = this.battle.activeMove.pranksterBoosted;
    }
    const baseTarget = move.target;
    let targetRelayVar = { target };
    targetRelayVar = this.battle.runEvent("ModifyTarget", pokemon, target, move, targetRelayVar, true);
    if (targetRelayVar.target !== void 0) target = targetRelayVar.target;
    if (target === void 0) target = this.battle.getRandomTarget(pokemon, move);
    if (move.target === "self" || move.target === "allies") {
      target = pokemon;
    }
    if (sourceEffect) {
      move.sourceEffect = sourceEffect.id;
      move.ignoreAbility = sourceEffect.ignoreAbility;
    }
    let moveResult = false;
    this.battle.setActiveMove(move, pokemon, target);
    this.battle.singleEvent("ModifyType", move, null, pokemon, target, move, move);
    this.battle.singleEvent("ModifyMove", move, null, pokemon, target, move, move);
    if (baseTarget !== move.target) {
      target = this.battle.getRandomTarget(pokemon, move);
    }
    move = this.battle.runEvent("ModifyType", pokemon, target, move, move);
    move = this.battle.runEvent("ModifyMove", pokemon, target, move, move);
    if (baseTarget !== move.target) {
      target = this.battle.getRandomTarget(pokemon, move);
    }
    if (!move || pokemon.fainted) {
      return false;
    }
    let attrs = "";
    let movename = move.name;
    if (move.id === "hiddenpower") movename = "Hidden Power";
    if (sourceEffect) attrs += `|[from] ${sourceEffect.fullname}`;
    if (zMove && move.isZ === true) {
      attrs = `|[anim]${movename}${attrs}`;
      movename = `Z-${movename}`;
    }
    this.battle.addMove("move", pokemon, movename, `${target}${attrs}`);
    if (zMove) this.runZPower(move, pokemon);
    if (!target) {
      this.battle.attrLastMove("[notarget]");
      this.battle.add(this.battle.gen >= 5 ? "-fail" : "-notarget", pokemon);
      return false;
    }
    const { targets, pressureTargets } = pokemon.getMoveTargets(move, target);
    if (targets.length) {
      target = targets[targets.length - 1];
    }
    const callerMoveForPressure = sourceEffect && sourceEffect.pp ? sourceEffect : null;
    if (!sourceEffect || callerMoveForPressure) {
      let extraPP = 0;
      for (const source of pressureTargets) {
        const ppDrop = this.battle.runEvent("DeductPP", source, pokemon, move);
        if (ppDrop !== true) {
          extraPP += ppDrop || 0;
        }
      }
      if (extraPP > 0) {
        pokemon.deductPP(callerMoveForPressure || moveOrMoveName, extraPP);
      }
    }
    let tryMoveResult = this.battle.singleEvent("TryMove", move, null, pokemon, target, move);
    if (tryMoveResult) {
      tryMoveResult = this.battle.runEvent("TryMove", pokemon, target, move);
    }
    if (!tryMoveResult) {
      return tryMoveResult;
    }
    this.battle.singleEvent("UseMoveMessage", move, null, pokemon, target, move);
    if (move.ignoreImmunity === void 0) {
      move.ignoreImmunity = move.category === "Status";
    }
    if (this.battle.gen !== 4 && move.selfdestruct === "always") {
      this.battle.faint(pokemon, pokemon, move);
    }
    let damage = false;
    if (move.target === "all" || move.target === "foeSide" || move.target === "allySide" || move.target === "allyTeam") {
      damage = this.tryMoveHit(targets, pokemon, move);
      if (damage === this.battle.NOT_FAIL) pokemon.moveThisTurnResult = null;
      if (damage || damage === 0 || damage === void 0) moveResult = true;
    } else {
      if (!targets.length) {
        this.battle.attrLastMove("[notarget]");
        this.battle.add(this.battle.gen >= 5 ? "-fail" : "-notarget", pokemon);
        return false;
      }
      if (this.battle.gen === 4 && move.selfdestruct === "always") {
        this.battle.faint(pokemon, pokemon, move);
      }
      moveResult = this.trySpreadMoveHit(targets, pokemon, move);
    }
    if (move.selfBoost && moveResult) this.moveHit(pokemon, pokemon, move, move.selfBoost, false, true);
    if (!pokemon.hp) {
      this.battle.faint(pokemon, pokemon, move);
    }
    if (!moveResult) {
      const originalHp = pokemon.hp;
      this.battle.singleEvent("MoveFail", move, null, target, pokemon, move);
      if (pokemon && pokemon !== target && move.category !== "Status") {
        if (pokemon.hp <= pokemon.maxhp / 2 && originalHp > pokemon.maxhp / 2) {
          this.battle.runEvent("EmergencyExit", pokemon, pokemon);
        }
      }
      return false;
    }
    if (!(move.hasSheerForce && pokemon.hasAbility("sheerforce")) && !move.flags["futuremove"]) {
      const originalHp = pokemon.hp;
      this.battle.singleEvent("AfterMoveSecondarySelf", move, null, pokemon, target, move);
      this.battle.runEvent("AfterMoveSecondarySelf", pokemon, target, move);
      if (pokemon && pokemon !== target && move.category !== "Status") {
        if (pokemon.hp <= pokemon.maxhp / 2 && originalHp > pokemon.maxhp / 2) {
          this.battle.runEvent("EmergencyExit", pokemon, pokemon);
        }
      }
    }
    return true;
  }
// ===== battle-actions.js:trySpreadMoveHit
  trySpreadMoveHit(targets, pokemon, move, notActive) {
    if (targets.length > 1 && !move.smartTarget) move.spreadHit = true;
    const moveSteps = [
      // 0. check for semi invulnerability
      this.hitStepInvulnerabilityEvent,
      // 1. run the 'TryHit' event (Protect, Magic Bounce, Volt Absorb, etc.) (this is step 2 in gens 5 & 6, and step 4 in gen 4)
      this.hitStepTryHitEvent,
      // 2. check for type immunity (this is step 1 in gens 4-6)
      this.hitStepTypeImmunity,
      // 3. check for various move-specific immunities
      this.hitStepTryImmunity,
      // 4. check accuracy
      this.hitStepAccuracy,
      // 5. break protection effects
      this.hitStepBreakProtect,
      // 6. steal positive boosts (Spectral Thief)
      this.hitStepStealBoosts,
      // 7. loop that processes each hit of the move (has its own steps per iteration)
      this.hitStepMoveHitLoop
    ];
    if (this.battle.gen <= 6) {
      [moveSteps[1], moveSteps[2]] = [moveSteps[2], moveSteps[1]];
    }
    if (this.battle.gen === 4) {
      [moveSteps[2], moveSteps[4]] = [moveSteps[4], moveSteps[2]];
    }
    if (notActive) this.battle.setActiveMove(move, pokemon, targets[0]);
    const hitResult = this.battle.singleEvent("Try", move, null, pokemon, targets[0], move) && this.battle.singleEvent("PrepareHit", move, {}, targets[0], pokemon, move) && this.battle.runEvent("PrepareHit", pokemon, targets[0], move);
    if (!hitResult) {
      if (hitResult === false) {
        this.battle.add("-fail", pokemon);
        this.battle.attrLastMove("[still]");
      }
      return hitResult === this.battle.NOT_FAIL;
    }
    let atLeastOneFailure = false;
    for (const step of moveSteps) {
      const hitResults = step.call(this, targets, pokemon, move);
      if (!hitResults) continue;
      targets = targets.filter((val, i) => hitResults[i] || hitResults[i] === 0);
      atLeastOneFailure = atLeastOneFailure || hitResults.some((val) => val === false);
      if (move.smartTarget && atLeastOneFailure) move.smartTarget = false;
      if (!targets.length) {
        break;
      }
    }
    move.hitTargets = targets;
    const moveResult = !!targets.length;
    if (!moveResult && !atLeastOneFailure) pokemon.moveThisTurnResult = null;
    const hitSlot = targets.map((p) => p.getSlot());
    if (move.spreadHit) this.battle.attrLastMove("[spread] " + hitSlot.join(","));
    return moveResult;
  }
// ===== battle-actions.js:hitStepMoveHitLoop
  hitStepMoveHitLoop(targets, pokemon, move) {
    let damage = [];
    for (const i of targets.keys()) {
      damage[i] = 0;
    }
    move.totalDamage = 0;
    pokemon.lastDamage = 0;
    let targetHits = move.multihit || 1;
    if (Array.isArray(targetHits)) {
      if (targetHits[0] === 2 && targetHits[1] === 5) {
        if (this.battle.gen >= 5) {
          targetHits = this.battle.sample([2, 2, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 3, 4, 4, 4, 5, 5, 5]);
          if (targetHits < 4 && pokemon.hasItem("loadeddice")) {
            targetHits = 5 - this.battle.random(2);
          }
        } else {
          targetHits = this.battle.sample([2, 2, 2, 3, 3, 3, 4, 5]);
        }
      } else {
        targetHits = this.battle.random(targetHits[0], targetHits[1] + 1);
      }
    }
    if (targetHits === 10 && pokemon.hasItem("loadeddice")) targetHits -= this.battle.random(7);
    targetHits = Math.floor(targetHits);
    let nullDamage = true;
    let moveDamage = [];
    const isSleepUsable = move.sleepUsable || this.dex.moves.get(move.sourceEffect).sleepUsable;
    let targetsCopy = targets.slice(0);
    let hit;
    for (hit = 1; hit <= targetHits; hit++) {
      if (damage.includes(false)) break;
      if (hit > 1 && pokemon.status === "slp" && (!isSleepUsable || this.battle.gen === 4)) break;
      if (targets.every((target2) => !target2?.hp)) break;
      move.hit = hit;
      move.lastHit = move.hit === targetHits;
      if (move.smartTarget && targets.length > 1) {
        targetsCopy = [targets[hit - 1]];
        damage = [damage[hit - 1]];
      } else {
        targetsCopy = targets.slice(0);
      }
      const target = targetsCopy[0];
      if (target && typeof move.smartTarget === "boolean") {
        if (hit > 1) {
          this.battle.addMove("-anim", pokemon, move.name, target);
        } else {
          this.battle.retargetLastMove(target);
        }
      }
      if (target && move.multiaccuracy && hit > 1) {
        let accuracy = move.accuracy;
        const boostTable = [1, 4 / 3, 5 / 3, 2, 7 / 3, 8 / 3, 3];
        if (accuracy !== true) {
          if (!move.ignoreAccuracy) {
            const boosts = this.battle.runEvent("ModifyBoost", pokemon, null, null, { ...pokemon.boosts });
            const boost = this.battle.clampIntRange(boosts["accuracy"], -6, 6);
            if (boost > 0) {
              accuracy *= boostTable[boost];
            } else {
              accuracy /= boostTable[-boost];
            }
          }
          if (!move.ignoreEvasion) {
            const boosts = this.battle.runEvent("ModifyBoost", target, null, null, { ...target.boosts });
            const boost = this.battle.clampIntRange(boosts["evasion"], -6, 6);
            if (boost > 0) {
              accuracy /= boostTable[boost];
            } else if (boost < 0) {
              accuracy *= boostTable[-boost];
            }
          }
        }
        accuracy = this.battle.runEvent("ModifyAccuracy", target, pokemon, move, accuracy);
        if (!move.alwaysHit) {
          accuracy = this.battle.runEvent("Accuracy", target, pokemon, move, accuracy);
          if (accuracy !== true && !this.battle.randomChance(accuracy, 100)) break;
        }
      }
      const moveData = move;
      if (!moveData.flags) moveData.flags = {};
      let moveDamageThisHit;
      [moveDamageThisHit, targetsCopy] = this.spreadMoveHit(targetsCopy, pokemon, move, moveData);
      if (move.smartTarget) {
        moveDamage.push(...moveDamageThisHit);
      } else {
        moveDamage = moveDamageThisHit;
      }
      if (!moveDamage.some((val) => val !== false)) break;
      nullDamage = false;
      for (const [i, md] of moveDamage.entries()) {
        if (move.smartTarget && i !== hit - 1) continue;
        damage[i] = md === true || !md ? 0 : md;
        move.totalDamage += damage[i];
      }
      this.battle.eachEvent("Update");
      if (!pokemon.hp && targets.length === 1) {
        hit++;
        break;
      }
    }
    if (hit === 1) return damage.fill(false);
    if (nullDamage) damage.fill(false);
    this.battle.faintMessages(false, false, !pokemon.hp);
    if (move.multihit && typeof move.smartTarget !== "boolean") {
      this.battle.add("-hitcount", targets[0], hit - 1);
    }
    if (move.totalDamage) {
      this.applyRecoilDamage(move.totalDamage, move, pokemon);
    }
    if (move.smartTarget) {
      targetsCopy = targets.slice(0);
    }
    for (const [i, target] of targetsCopy.entries()) {
      if (target && pokemon !== target) {
        target.gotAttacked(move, moveDamage[i], pokemon);
        if (typeof moveDamage[i] === "number") {
          target.timesAttacked += move.smartTarget ? 1 : hit - 1;
        }
      }
    }
    if (move.ohko && !targets[0].hp) this.battle.add("-ohko");
    if (!damage.some((val) => !!val || val === 0)) return damage;
    this.battle.eachEvent("Update");
    this.afterMoveSecondaryEvent(targetsCopy.filter((val) => !!val), pokemon, move);
    if (!(move.hasSheerForce && pokemon.hasAbility("sheerforce"))) {
      for (const [i, d] of damage.entries()) {
        const curDamage = targets.length === 1 ? move.totalDamage : d;
        if (typeof curDamage === "number" && targets[i].hp) {
          const targetHPBeforeDamage = (targets[i].hurtThisTurn || 0) + curDamage;
          if (targets[i].hp <= targets[i].maxhp / 2 && targetHPBeforeDamage > targets[i].maxhp / 2) {
            this.battle.runEvent("EmergencyExit", targets[i], pokemon);
          }
        }
      }
    }
    return damage;
  }
// ===== battle-actions.js:runMoveEffects
  runMoveEffects(damage, targets, source, move, moveData, isSecondary, isSelf) {
    let didAnything = damage.reduce(this.combineResults);
    for (const [i, target] of targets.entries()) {
      if (target === false) continue;
      let hitResult;
      let didSomething = void 0;
      if (target) {
        if (moveData.boosts && !target.fainted) {
          hitResult = this.battle.boost(moveData.boosts, target, source, move, isSecondary, isSelf);
          didSomething = this.combineResults(didSomething, hitResult);
        }
        if (moveData.heal && !target.fainted) {
          if (target.hp >= target.maxhp) {
            this.battle.add("-fail", target, "heal");
            this.battle.attrLastMove("[still]");
            damage[i] = this.combineResults(damage[i], false);
            didAnything = this.combineResults(didAnything, null);
            continue;
          }
          const amount = target.baseMaxhp * moveData.heal[0] / moveData.heal[1];
          const d = this.battle.heal((this.battle.gen < 5 ? Math.floor : Math.round)(amount), target, source, move);
          if (!d && d !== 0) {
            if (d !== null) {
              this.battle.add("-fail", source);
              this.battle.attrLastMove("[still]");
            }
            this.battle.debug("heal interrupted");
            damage[i] = this.combineResults(damage[i], false);
            didAnything = this.combineResults(didAnything, null);
            continue;
          }
          didSomething = true;
        }
        if (moveData.status) {
          hitResult = target.trySetStatus(moveData.status, source, moveData.ability ? moveData.ability : move);
          if (!hitResult && move.status) {
            damage[i] = this.combineResults(damage[i], false);
            didAnything = this.combineResults(didAnything, null);
            continue;
          }
          didSomething = this.combineResults(didSomething, hitResult);
        }
        if (moveData.forceStatus) {
          hitResult = target.setStatus(moveData.forceStatus, source, move);
          didSomething = this.combineResults(didSomething, hitResult);
        }
        if (moveData.volatileStatus) {
          hitResult = target.addVolatile(moveData.volatileStatus, source, move);
          didSomething = this.combineResults(didSomething, hitResult);
        }
        if (moveData.sideCondition) {
          hitResult = target.side.addSideCondition(moveData.sideCondition, source, move);
          didSomething = this.combineResults(didSomething, hitResult);
        }
        if (moveData.slotCondition) {
          hitResult = target.side.addSlotCondition(target, moveData.slotCondition, source, move);
          didSomething = this.combineResults(didSomething, hitResult);
        }
        if (moveData.weather) {
          hitResult = this.battle.field.setWeather(moveData.weather, source, move);
          didSomething = this.combineResults(didSomething, hitResult);
        }
        if (moveData.terrain) {
          hitResult = this.battle.field.setTerrain(moveData.terrain, source, move);
          didSomething = this.combineResults(didSomething, hitResult);
        }
        if (moveData.pseudoWeather) {
          hitResult = this.battle.field.addPseudoWeather(moveData.pseudoWeather, source, move);
          didSomething = this.combineResults(didSomething, hitResult);
        }
        if (moveData.forceSwitch) {
          hitResult = !!this.battle.canSwitch(target.side);
          didSomething = this.combineResults(didSomething, hitResult);
        }
        if (move.target === "all" && !isSelf) {
          if (moveData.onHitField) {
            hitResult = this.battle.singleEvent("HitField", moveData, {}, target, source, move);
            didSomething = this.combineResults(didSomething, hitResult);
          }
        } else if ((move.target === "foeSide" || move.target === "allySide") && !isSelf) {
          if (moveData.onHitSide) {
            hitResult = this.battle.singleEvent("HitSide", moveData, {}, target.side, source, move);
            didSomething = this.combineResults(didSomething, hitResult);
          }
        } else {
          if (moveData.onHit) {
            hitResult = this.battle.singleEvent("Hit", moveData, {}, target, source, move);
            didSomething = this.combineResults(didSomething, hitResult);
          }
          if (!isSelf && !isSecondary) {
            this.battle.runEvent("Hit", target, source, move);
          }
        }
      }
      if (moveData.selfdestruct === "ifHit" && damage[i] !== false) {
        this.battle.faint(source, source, move);
      }
      if (moveData.selfSwitch) {
        if (this.battle.canSwitch(source.side) && !source.volatiles["commanded"]) {
          didSomething = true;
        } else {
          didSomething = this.combineResults(didSomething, false);
        }
      }
      if (didSomething === void 0) didSomething = true;
      damage[i] = this.combineResults(damage[i], didSomething === null ? false : didSomething);
      didAnything = this.combineResults(didAnything, didSomething);
    }
    if (!didAnything && didAnything !== 0 && !moveData.self && !moveData.selfdestruct) {
      if (!isSelf && !isSecondary) {
        if (didAnything === false) {
          this.battle.add("-fail", source);
          this.battle.attrLastMove("[still]");
        }
      }
      this.battle.debug("move failed because it did nothing");
    } else if (move.selfSwitch && source.hp && !source.volatiles["commanded"]) {
      source.switchFlag = move.id;
    }
    return damage;
  }
// ===== battle-actions.js:selfDrops
  selfDrops(targets, source, move, moveData, isSecondary) {
    for (const target of targets) {
      if (target === false) continue;
      if (moveData.self && !move.selfDropped) {
        if (!isSecondary && moveData.self.boosts) {
          const secondaryRoll = this.battle.random(100);
          if (typeof moveData.self.chance === "undefined" || secondaryRoll < moveData.self.chance) {
            this.moveHit(source, source, move, moveData.self, isSecondary, true);
          }
          if (!move.multihit) move.selfDropped = true;
        } else {
          this.moveHit(source, source, move, moveData.self, isSecondary, true);
        }
      }
    }
  }
// ===== battle-actions.js:secondaries
  secondaries(targets, source, move, moveData, isSelf) {
    if (!moveData.secondaries) return;
    for (const target of targets) {
      if (target === false) continue;
      const secondaries = this.battle.runEvent("ModifySecondaries", target, source, moveData, moveData.secondaries.slice());
      for (const secondary of secondaries) {
        const secondaryRoll = this.battle.random(100);
        const secondaryOverflow = (secondary.boosts || secondary.self) && this.battle.gen <= 8;
        if (typeof secondary.chance === "undefined" || secondaryRoll < (secondaryOverflow ? secondary.chance % 256 : secondary.chance)) {
          this.moveHit(target, source, move, secondary, true, isSelf);
        }
      }
    }
  }
// ===== battle-actions.js:getSpreadDamage
  getSpreadDamage(damage, targets, source, move, moveData, isSecondary, isSelf) {
    for (const [i, target] of targets.entries()) {
      if (!target) continue;
      this.battle.activeTarget = target;
      damage[i] = void 0;
      const curDamage = this.getDamage(source, target, moveData);
      if (curDamage === false || curDamage === null) {
        if (damage[i] === false && !isSecondary && !isSelf) {
          this.battle.add("-fail", source);
          this.battle.attrLastMove("[still]");
        }
        this.battle.debug("damage calculation interrupted");
        damage[i] = false;
        continue;
      }
      damage[i] = curDamage;
    }
    return damage;
  }
// ===== battle-actions.js:tryPrimaryHitEvent
  tryPrimaryHitEvent(damage, targets, pokemon, move, moveData, isSecondary) {
    for (const [i, target] of targets.entries()) {
      if (!target) continue;
      damage[i] = this.battle.runEvent("TryPrimaryHit", target, pokemon, moveData);
    }
    return damage;
  }
// NOT FOUND battle-actions.js:calcRecoilDamage
// ===== battle-actions.js:afterMoveSecondaryEvent
  afterMoveSecondaryEvent(targets, pokemon, move) {
    if (!(move.hasSheerForce && pokemon.hasAbility("sheerforce"))) {
      this.battle.singleEvent("AfterMoveSecondary", move, null, targets[0], pokemon, move);
      this.battle.runEvent("AfterMoveSecondary", targets, pokemon, move);
    }
    return void 0;
  }
// ===== battle-actions.js:dragIn
  dragIn(side, pos) {
    const pokemon = this.battle.getRandomSwitchable(side);
    if (!pokemon || pokemon.isActive) return false;
    const oldActive = side.active[pos];
    if (!oldActive) throw new Error(`nothing to drag out`);
    if (!oldActive.hp) return false;
    if (!this.battle.runEvent("DragOut", oldActive)) {
      return false;
    }
    if (!this.switchIn(pokemon, pos, null, true)) return false;
    return true;
  }
// ===== battle-actions.js:runMegaEvo
  runMegaEvo(pokemon) {
    const speciesid = pokemon.canMegaEvo || pokemon.canUltraBurst;
    if (!speciesid) return false;
    pokemon.formeChange(speciesid, pokemon.getItem(), true);
    const wasMega = pokemon.canMegaEvo;
    for (const ally of pokemon.side.pokemon) {
      if (wasMega) {
        ally.canMegaEvo = false;
      } else {
        ally.canUltraBurst = null;
      }
    }
    this.battle.runEvent("AfterMega", pokemon);
    return true;
  }
// ===== battle-queue.js:willMove
  willMove(pokemon) {
    if (pokemon.fainted) return null;
    for (const action of this.list) {
      if (action.choice === "move" && action.pokemon === pokemon) {
        return action;
      }
    }
    return null;
  }
// ===== battle-queue.js:cancelMove
  cancelMove(pokemon) {
    for (const [i, action] of this.list.entries()) {
      if (action.choice === "move" && action.pokemon === pokemon) {
        this.list.splice(i, 1);
        return true;
      }
    }
    return false;
  }
// ===== battle-queue.js:cancelAction
  cancelAction(pokemon) {
    const oldLength = this.list.length;
    for (let i = 0; i < this.list.length; i++) {
      if (this.list[i].pokemon === pokemon) {
        this.list.splice(i, 1);
        i--;
      }
    }
    return this.list.length !== oldLength;
  }
// ===== battle-queue.js:changeAction
  changeAction(pokemon, action) {
    this.cancelAction(pokemon);
    if (!action.pokemon) action.pokemon = pokemon;
    this.insertChoice(action);
  }
// ===== battle-queue.js:prioritizeAction
  prioritizeAction(action, sourceEffect) {
    for (const [i, curAction] of this.list.entries()) {
      if (curAction === action) {
        this.list.splice(i, 1);
        break;
      }
    }
    action.sourceEffect = sourceEffect;
    action.order = 3;
    this.list.unshift(action);
  }
// ===== battle-queue.js:willAct
  willAct() {
    for (const action of this.list) {
      if (["move", "switch", "instaswitch", "shift"].includes(action.choice)) {
        return action;
      }
    }
    return null;
  }
