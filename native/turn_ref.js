// ===== battle-queue.js:resolveAction
  resolveAction(action, midTurn = false) {
    if (!action) throw new Error(`Action not passed to resolveAction`);
    if (action.choice === "pass") return [];
    const actions = [action];
    if (!action.side && action.pokemon) action.side = action.pokemon.side;
    if (!action.move && action.moveid) action.move = this.battle.dex.getActiveMove(action.moveid);
    if (!action.order) {
      const orders = {
        team: 1,
        start: 2,
        instaswitch: 3,
        beforeTurn: 4,
        beforeTurnMove: 5,
        revivalblessing: 6,
        runSwitch: 101,
        switch: 103,
        megaEvo: 104,
        megaEvoX: 104,
        megaEvoY: 104,
        runDynamax: 105,
        terastallize: 106,
        priorityChargeMove: 107,
        shift: 200,
        // default is 200 (for moves)
        residual: 300
      };
      if (action.choice in orders) {
        action.order = orders[action.choice];
      } else {
        action.order = 200;
        if (!["move", "event"].includes(action.choice)) {
          throw new Error(`Unexpected orderless action ${action.choice}`);
        }
      }
    }
    if (!midTurn) {
      if (action.choice === "move") {
        if (!action.maxMove && !action.zmove && action.move.beforeTurnCallback) {
          actions.unshift(...this.resolveAction({
            choice: "beforeTurnMove",
            pokemon: action.pokemon,
            move: action.move,
            targetLoc: action.targetLoc
          }));
        }
        if (action.mega && !action.pokemon.isSkyDropped()) {
          actions.unshift(...this.resolveAction({
            choice: "megaEvo",
            pokemon: action.pokemon
          }));
        }
        if (action.megax && !action.pokemon.isSkyDropped()) {
          actions.unshift(...this.resolveAction({
            choice: "megaEvoX",
            pokemon: action.pokemon
          }));
        }
        if (action.megay && !action.pokemon.isSkyDropped()) {
          actions.unshift(...this.resolveAction({
            choice: "megaEvoY",
            pokemon: action.pokemon
          }));
        }
        if (action.terastallize && !action.pokemon.terastallized) {
          actions.unshift(...this.resolveAction({
            choice: "terastallize",
            pokemon: action.pokemon
          }));
        }
        if (action.maxMove && !action.pokemon.volatiles["dynamax"]) {
          actions.unshift(...this.resolveAction({
            choice: "runDynamax",
            pokemon: action.pokemon
          }));
        }
        if (!action.maxMove && !action.zmove && action.move.priorityChargeCallback) {
          actions.unshift(...this.resolveAction({
            choice: "priorityChargeMove",
            pokemon: action.pokemon,
            move: action.move
          }));
        }
        action.fractionalPriority = this.battle.runEvent("FractionalPriority", action.pokemon, null, action.move, 0);
      } else if (["switch", "instaswitch"].includes(action.choice)) {
        if (typeof action.pokemon.switchFlag === "string") {
          action.sourceEffect = this.battle.dex.moves.get(action.pokemon.switchFlag);
        }
        action.pokemon.switchFlag = false;
      }
    }
    const deferPriority = this.battle.gen === 7 && action.mega && action.mega !== "done";
    if (action.move) {
      let target = null;
      action.move = this.battle.dex.getActiveMove(action.move);
      if (!action.targetLoc) {
        target = this.battle.getRandomTarget(action.pokemon, action.move);
        if (target) action.targetLoc = action.pokemon.getLocOf(target);
      }
      action.originalTarget = action.pokemon.getAtLoc(action.targetLoc);
    }
    if (!deferPriority) this.battle.getActionSpeed(action);
    return actions;
  }
// ===== battle-queue.js:insertChoice
  insertChoice(choices, midTurn = false) {
    if (Array.isArray(choices)) {
      for (const choice2 of choices) {
        this.insertChoice(choice2);
      }
      return;
    }
    const choice = choices;
    if (choice.pokemon) {
      choice.pokemon.updateSpeed();
    }
    const actions = this.resolveAction(choice, midTurn);
    let firstIndex = null;
    let lastIndex = null;
    for (const [i, curAction] of this.list.entries()) {
      const compared = this.battle.comparePriority(actions[0], curAction);
      if (compared <= 0 && firstIndex === null) {
        firstIndex = i;
      }
      if (compared < 0) {
        lastIndex = i;
        break;
      }
    }
    if (firstIndex === null) {
      this.list.push(...actions);
    } else {
      if (lastIndex === null) lastIndex = this.list.length;
      const index = firstIndex === lastIndex ? firstIndex : this.battle.random(firstIndex, lastIndex + 1);
      this.list.splice(index, 0, ...actions);
    }
  }
// ===== battle.js:comparePriority
  comparePriority(a, b) {
    return -((b.order || 4294967296) - (a.order || 4294967296)) || (b.priority || 0) - (a.priority || 0) || (b.speed || 0) - (a.speed || 0) || -((b.subOrder || 0) - (a.subOrder || 0)) || -((b.effectOrder || 0) - (a.effectOrder || 0)) || 0;
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
// ===== battle.js:runAction
  runAction(action) {
    const pokemonOriginalHP = action.pokemon?.hp;
    let residualPokemon = [];
    switch (action.choice) {
      case "start": {
        for (const side of this.sides) {
          if (side.pokemonLeft) side.pokemonLeft = side.pokemon.length;
          this.add("teamsize", side.id, side.pokemon.length);
        }
        this.add("start");
        for (const pokemon of this.getAllPokemon()) {
          this.singleEvent("BattleStart", this.dex.conditions.getByID(pokemon.species.id), pokemon.speciesState, pokemon);
        }
        this.format.onBattleStart?.call(this);
        for (const rule of this.ruleTable.keys()) {
          if ("+*-!".includes(rule.charAt(0))) continue;
          const subFormat = this.dex.formats.get(rule);
          subFormat.onBattleStart?.call(this);
        }
        for (const side of this.sides) {
          for (let i = 0; i < side.active.length; i++) {
            if (!side.pokemonLeft) {
              side.active[i] = side.pokemon[i];
              side.active[i].fainted = true;
              side.active[i].hp = 0;
            } else {
              this.actions.switchIn(side.pokemon[i], i);
            }
          }
        }
        this.midTurn = true;
        break;
      }
      case "move":
        if (!action.pokemon.isActive) return false;
        if (action.pokemon.fainted) return false;
        this.actions.runMove(action.move, action.pokemon, action.targetLoc, {
          sourceEffect: action.sourceEffect,
          zMove: action.zmove,
          maxMove: action.maxMove,
          originalTarget: action.originalTarget
        });
        break;
      case "megaEvo":
        this.actions.runMegaEvo(action.pokemon);
        break;
      case "megaEvoX":
        this.actions.runMegaEvoX?.(action.pokemon);
        break;
      case "megaEvoY":
        this.actions.runMegaEvoY?.(action.pokemon);
        break;
      case "runDynamax":
        action.pokemon.addVolatile("dynamax");
        action.pokemon.side.dynamaxUsed = true;
        if (action.pokemon.side.allySide) action.pokemon.side.allySide.dynamaxUsed = true;
        break;
      case "terastallize":
        this.actions.terastallize(action.pokemon);
        break;
      case "beforeTurnMove":
        if (!action.pokemon.isActive) return false;
        if (action.pokemon.fainted) return false;
        this.debug("before turn callback: " + action.move.id);
        const target = this.getTarget(action.pokemon, action.move, action.targetLoc);
        if (!target) return false;
        if (!action.move.beforeTurnCallback) throw new Error(`beforeTurnMove has no beforeTurnCallback`);
        action.move.beforeTurnCallback.call(this, action.pokemon, target);
        break;
      case "priorityChargeMove":
        if (!action.pokemon.isActive) return false;
        if (action.pokemon.fainted) return false;
        this.debug("priority charge callback: " + action.move.id);
        if (!action.move.priorityChargeCallback) throw new Error(`priorityChargeMove has no priorityChargeCallback`);
        action.move.priorityChargeCallback.call(this, action.pokemon);
        break;
      case "event":
        this.runEvent(action.event, action.pokemon);
        break;
      case "team":
        if (action.index === 0) {
          action.pokemon.side.pokemon = [];
        }
        action.pokemon.side.pokemon.push(action.pokemon);
        action.pokemon.position = action.index;
        return;
      case "pass":
        return;
      case "instaswitch":
      case "switch":
        if (action.choice === "switch" && action.pokemon.status) {
          this.singleEvent("CheckShow", this.dex.abilities.getByID("naturalcure"), null, action.pokemon);
        }
        if (this.actions.switchIn(action.target, action.pokemon.position, action.sourceEffect) === "pursuitfaint") {
          if (this.gen <= 4) {
            this.hint("Previously chosen switches continue in Gen 2-4 after a Pursuit target faints.");
            action.priority = -101;
            this.queue.unshift(action);
            break;
          } else {
            this.hint("A Pokemon can't switch between when it runs out of HP and when it faints");
            break;
          }
        }
        break;
      case "revivalblessing":
        action.pokemon.side.pokemonLeft++;
        if (action.target.position < action.pokemon.side.active.length) {
          this.queue.addChoice({
            choice: "instaswitch",
            pokemon: action.target,
            target: action.target
          });
        }
        action.target.fainted = false;
        action.target.faintQueued = false;
        action.target.subFainted = false;
        action.target.status = "";
        action.target.hp = 1;
        action.target.sethp(action.target.maxhp / 2);
        this.add("-heal", action.target, action.target.getHealth, "[from] move: Revival Blessing");
        action.pokemon.side.removeSlotCondition(action.pokemon, "revivalblessing");
        break;
      case "runSwitch":
        this.actions.runSwitch(action.pokemon);
        break;
      case "shift":
        if (!action.pokemon.isActive) return false;
        if (action.pokemon.fainted) return false;
        this.swapPosition(action.pokemon, 1);
        break;
      case "beforeTurn":
        this.eachEvent("BeforeTurn");
        break;
      case "residual":
        this.add("");
        this.clearActiveMove(true);
        this.updateSpeed();
        residualPokemon = this.getAllActive().map((pokemon) => [pokemon, pokemon.getUndynamaxedHP()]);
        this.fieldEvent("Residual");
        if (!this.ended) this.add("upkeep");
        break;
    }
    for (const side of this.sides) {
      for (const pokemon of side.active) {
        if (pokemon.forceSwitchFlag) {
          if (pokemon.hp) this.actions.dragIn(pokemon.side, pokemon.position);
          pokemon.forceSwitchFlag = false;
        }
      }
    }
    this.clearActiveMove();
    this.faintMessages();
    if (this.ended) return true;
    if (!this.queue.peek() || this.gen <= 3 && ["move", "residual"].includes(this.queue.peek().choice)) {
      this.checkFainted();
    } else if (["megaEvo", "megaEvoX", "megaEvoY"].includes(action.choice) && this.gen === 7) {
      this.eachEvent("Update");
      for (const [i, queuedAction] of this.queue.list.entries()) {
        if (queuedAction.pokemon === action.pokemon && queuedAction.choice === "move") {
          this.queue.list.splice(i, 1);
          queuedAction.mega = "done";
          this.queue.insertChoice(queuedAction, true);
          break;
        }
      }
      return false;
    } else if (this.queue.peek()?.choice === "instaswitch") {
      return false;
    }
    if (this.gen >= 5 && action.choice !== "start") {
      this.eachEvent("Update");
      for (const [pokemon, originalHP] of residualPokemon) {
        const maxhp = pokemon.getUndynamaxedHP(pokemon.maxhp);
        if (pokemon.hp && pokemon.getUndynamaxedHP() <= maxhp / 2 && originalHP > maxhp / 2) {
          this.runEvent("EmergencyExit", pokemon);
        }
      }
    }
    if (action.choice === "runSwitch") {
      const pokemon = action.pokemon;
      if (pokemon.hp && pokemon.hp <= pokemon.maxhp / 2 && pokemonOriginalHP > pokemon.maxhp / 2) {
        this.runEvent("EmergencyExit", pokemon);
      }
    }
    const switches = this.sides.map(
      (side) => side.active.some((pokemon) => pokemon && !!pokemon.switchFlag)
    );
    for (let i = 0; i < this.sides.length; i++) {
      let reviveSwitch = false;
      if (switches[i] && !this.canSwitch(this.sides[i])) {
        for (const pokemon of this.sides[i].active) {
          if (this.sides[i].slotConditions[pokemon.position]["revivalblessing"]) {
            reviveSwitch = true;
            continue;
          }
          pokemon.switchFlag = false;
        }
        if (!reviveSwitch) switches[i] = false;
      } else if (switches[i]) {
        for (const pokemon of this.sides[i].active) {
          if (pokemon.hp && pokemon.switchFlag && pokemon.switchFlag !== "revivalblessing" && !pokemon.skipBeforeSwitchOutEventFlag) {
            this.runEvent("BeforeSwitchOut", pokemon);
            pokemon.skipBeforeSwitchOutEventFlag = true;
            this.faintMessages();
            if (this.ended) return true;
            if (pokemon.fainted) {
              switches[i] = this.sides[i].active.some((sidePokemon) => sidePokemon && !!sidePokemon.switchFlag);
            }
          }
        }
      }
    }
    for (const playerSwitch of switches) {
      if (playerSwitch) {
        this.makeRequest("switch");
        return true;
      }
    }
    if (this.gen < 5) this.eachEvent("Update");
    if (this.gen >= 8 && (this.queue.peek()?.choice === "move" || this.queue.peek()?.choice === "runDynamax")) {
      this.updateSpeed();
      for (const queueAction of this.queue.list) {
        if (queueAction.pokemon) this.getActionSpeed(queueAction);
      }
      this.queue.sort();
    }
    return false;
  }
// ===== battle.js:faintMessages
  faintMessages(lastFirst = false, forceCheck = false, checkWin = true) {
    if (this.ended) return;
    const length = this.faintQueue.length;
    if (!length) {
      if (forceCheck && this.checkWin()) return true;
      return false;
    }
    if (lastFirst) {
      this.faintQueue.unshift(this.faintQueue[this.faintQueue.length - 1]);
      this.faintQueue.pop();
    }
    let faintQueueLeft, faintData;
    while (this.faintQueue.length) {
      faintQueueLeft = this.faintQueue.length;
      faintData = this.faintQueue.shift();
      const pokemon = faintData.target;
      if (!pokemon.fainted && this.runEvent("BeforeFaint", pokemon, faintData.source, faintData.effect)) {
        this.add("faint", pokemon);
        if (pokemon.side.pokemonLeft) pokemon.side.pokemonLeft--;
        if (pokemon.side.totalFainted < 100) pokemon.side.totalFainted++;
        this.runEvent("Faint", pokemon, faintData.source, faintData.effect);
        this.singleEvent("End", pokemon.getAbility(), pokemon.abilityState, pokemon);
        this.singleEvent("End", pokemon.getItem(), pokemon.itemState, pokemon);
        if (pokemon.formeRegression && !pokemon.transformed) {
          pokemon.baseSpecies = this.dex.species.get(pokemon.set.species || pokemon.set.name);
          pokemon.baseAbility = (0, import_dex.toID)(pokemon.set.ability);
        }
        pokemon.clearVolatile(false);
        pokemon.fainted = true;
        pokemon.illusion = null;
        pokemon.isActive = false;
        pokemon.isStarted = false;
        delete pokemon.terastallized;
        if (pokemon.formeRegression) {
          pokemon.details = pokemon.getUpdatedDetails();
          this.add("detailschange", pokemon, pokemon.details, "[silent]");
          pokemon.updateMaxHp();
          pokemon.formeRegression = false;
        }
        pokemon.side.faintedThisTurn = pokemon;
        if (this.faintQueue.length >= faintQueueLeft) checkWin = true;
      }
    }
    if (this.gen <= 1) {
      this.queue.clear();
    } else if (this.gen <= 3 && this.gameType === "singles") {
      for (const pokemon of this.getAllActive()) {
        if (this.gen <= 2) {
          this.queue.cancelMove(pokemon);
        } else {
          this.queue.cancelAction(pokemon);
        }
      }
    }
    if (checkWin && this.checkWin(faintData)) return true;
    if (faintData && length) {
      this.runEvent("AfterFaint", faintData.target, faintData.source, faintData.effect, length);
    }
    return false;
  }
// NOT FOUND battle.js:nextTurn
// ===== battle.js:endTurn
  endTurn() {
    this.turn++;
    this.lastSuccessfulMoveThisTurn = null;
    const dynamaxEnding = [];
    for (const pokemon of this.getAllActive()) {
      if (pokemon.volatiles["dynamax"]?.turns === 3) {
        dynamaxEnding.push(pokemon);
      }
    }
    if (dynamaxEnding.length > 1) {
      this.updateSpeed();
      this.speedSort(dynamaxEnding);
    }
    for (const pokemon of dynamaxEnding) {
      pokemon.removeVolatile("dynamax");
    }
    if (this.gen === 1) {
      for (const pokemon of this.getAllActive()) {
        if (pokemon.volatiles["partialtrappinglock"]) {
          const target = pokemon.volatiles["partialtrappinglock"].locked;
          if (target.hp <= 0 || !target.volatiles["partiallytrapped"]) {
            delete pokemon.volatiles["partialtrappinglock"];
          }
        }
        if (pokemon.volatiles["partiallytrapped"]) {
          const source = pokemon.volatiles["partiallytrapped"].source;
          if (source.hp <= 0 || !source.volatiles["partialtrappinglock"]) {
            delete pokemon.volatiles["partiallytrapped"];
          }
        }
        if (pokemon.volatiles["fakepartiallytrapped"]) {
          const counterpart = pokemon.volatiles["fakepartiallytrapped"].counterpart;
          if (counterpart.hp <= 0 || !counterpart.volatiles["fakepartiallytrapped"]) {
            delete pokemon.volatiles["fakepartiallytrapped"];
          }
        }
      }
    }
    const trappedBySide = [];
    const stalenessBySide = [];
    for (const side of this.sides) {
      let sideTrapped = true;
      let sideStaleness;
      for (const pokemon of side.active) {
        if (!pokemon) continue;
        pokemon.moveThisTurn = "";
        pokemon.newlySwitched = false;
        pokemon.moveLastTurnResult = pokemon.moveThisTurnResult;
        pokemon.moveThisTurnResult = void 0;
        if (this.turn !== 1) {
          pokemon.usedItemThisTurn = false;
          pokemon.statsRaisedThisTurn = false;
          pokemon.statsLoweredThisTurn = false;
          pokemon.hurtThisTurn = null;
        }
        pokemon.maybeDisabled = false;
        pokemon.maybeLocked = false;
        for (const moveSlot of pokemon.moveSlots) {
          moveSlot.disabled = false;
          moveSlot.disabledSource = "";
        }
        this.runEvent("DisableMove", pokemon);
        for (const moveSlot of pokemon.moveSlots) {
          const activeMove = this.dex.getActiveMove(moveSlot.id);
          this.singleEvent("DisableMove", activeMove, null, pokemon);
          if (activeMove.flags["cantusetwice"] && pokemon.lastMove?.id === moveSlot.id) {
            pokemon.disableMove(pokemon.lastMove.id);
          }
        }
        if (pokemon.getLastAttackedBy() && this.gen >= 7) pokemon.knownType = true;
        for (let i = pokemon.attackedBy.length - 1; i >= 0; i--) {
          const attack = pokemon.attackedBy[i];
          if (attack.source.isActive) {
            attack.thisTurn = false;
          } else {
            pokemon.attackedBy.splice(pokemon.attackedBy.indexOf(attack), 1);
          }
        }
        if (this.gen >= 7 && !pokemon.terastallized) {
          const seenPokemon = pokemon.illusion || pokemon;
          const realTypeString = seenPokemon.getTypes(true).join("/");
          if (realTypeString !== seenPokemon.apparentType) {
            this.add("-start", pokemon, "typechange", realTypeString, "[silent]");
            seenPokemon.apparentType = realTypeString;
            if (pokemon.addedType) {
              this.add("-start", pokemon, "typeadd", pokemon.addedType, "[silent]");
            }
          }
        }
        pokemon.trapped = pokemon.maybeTrapped = false;
        this.runEvent("TrapPokemon", pokemon);
        if (!pokemon.knownType || this.dex.getImmunity("trapped", pokemon)) {
          this.runEvent("MaybeTrapPokemon", pokemon);
        }
        if (this.gen > 2) {
          for (const source of pokemon.foes()) {
            const species = (source.illusion || source).species;
            if (!species.abilities) continue;
            for (const abilitySlot in species.abilities) {
              const abilityName = species.abilities[abilitySlot];
              if (abilityName === source.ability) {
                continue;
              }
              const ruleTable = this.ruleTable;
              if ((ruleTable.has("+hackmons") || !ruleTable.has("obtainableabilities")) && !this.format.team) {
                continue;
              } else if (abilitySlot === "H" && species.unreleasedHidden) {
                continue;
              }
              const ability = this.dex.abilities.get(abilityName);
              if (ruleTable.has("-ability:" + ability.id)) continue;
              if (pokemon.knownType && !this.dex.getImmunity("trapped", pokemon)) continue;
              this.singleEvent("FoeMaybeTrapPokemon", ability, {}, pokemon, source);
            }
          }
        }
        if (pokemon.fainted) continue;
        sideTrapped = sideTrapped && pokemon.trapped;
        const staleness = pokemon.volatileStaleness || pokemon.staleness;
        if (staleness) sideStaleness = sideStaleness === "external" ? sideStaleness : staleness;
        pokemon.activeTurns++;
      }
      trappedBySide.push(sideTrapped);
      stalenessBySide.push(sideStaleness);
      side.faintedLastTurn = side.faintedThisTurn;
      side.faintedThisTurn = null;
    }
    if (this.maybeTriggerEndlessBattleClause(trappedBySide, stalenessBySide)) return;
    if (this.gameType === "triples" && this.sides.every((side) => side.pokemonLeft === 1)) {
      const actives = this.getAllActive();
      if (actives.length > 1 && !actives[0].isAdjacent(actives[1])) {
        this.swapPosition(actives[0], 1, "[silent]");
        this.swapPosition(actives[1], 1, "[silent]");
        this.add("-center");
      }
    }
    this.add("turn", this.turn);
    if (this.gameType === "multi") {
      for (const side of this.sides) {
        if (side.canDynamaxNow()) {
          if (this.turn === 1) {
            this.addSplit(side.id, ["-candynamax", side.id]);
          } else {
            this.add("-candynamax", side.id);
          }
        }
      }
    }
    if (this.gen === 2) this.quickClawRoll = this.randomChance(60, 256);
    if (this.gen === 3) this.quickClawRoll = this.randomChance(1, 5);
    this.makeRequest("move");
  }
// NOT FOUND battle.js:residualEvent
// ===== battle.js:getAllActive
  getAllActive(includeFainted) {
    const pokemonList = [];
    for (const side of this.sides) {
      for (const pokemon of side.active) {
        if (pokemon && (includeFainted || !pokemon.fainted)) {
          pokemonList.push(pokemon);
        }
      }
    }
    return pokemonList;
  }
// ===== battle.js:checkFainted
  checkFainted() {
    for (const side of this.sides) {
      for (const pokemon of side.active) {
        if (pokemon.fainted) {
          pokemon.status = "fnt";
          pokemon.switchFlag = true;
        }
      }
    }
  }
// ===== battle-actions.js:switchIn
  switchIn(pokemon, pos, sourceEffect = null, isDrag) {
    if (!pokemon || pokemon.isActive) {
      this.battle.hint("A switch failed because the Pok\xE9mon trying to switch in is already in.");
      return false;
    }
    const side = pokemon.side;
    if (pos >= side.active.length) {
      throw new Error(`Invalid switch position ${pos} / ${side.active.length}`);
    }
    const oldActive = side.active[pos];
    const unfaintedActive = oldActive?.hp ? oldActive : null;
    if (unfaintedActive) {
      oldActive.beingCalledBack = true;
      let switchCopyFlag = false;
      if (sourceEffect && typeof sourceEffect.selfSwitch === "string") {
        switchCopyFlag = sourceEffect.selfSwitch;
      }
      if (!oldActive.skipBeforeSwitchOutEventFlag && !isDrag) {
        this.battle.runEvent("BeforeSwitchOut", oldActive);
        if (this.battle.gen >= 5) {
          this.battle.eachEvent("Update");
        }
      }
      oldActive.skipBeforeSwitchOutEventFlag = false;
      if (!this.battle.runEvent("SwitchOut", oldActive)) {
        return false;
      }
      if (!oldActive.hp) {
        return "pursuitfaint";
      }
      this.battle.singleEvent("End", oldActive.getAbility(), oldActive.abilityState, oldActive);
      this.battle.singleEvent("End", oldActive.getItem(), oldActive.itemState, oldActive);
      this.battle.queue.cancelAction(oldActive);
      let newMove = null;
      if (this.battle.gen === 4 && sourceEffect) {
        newMove = oldActive.lastMove;
      }
      if (switchCopyFlag) {
        pokemon.copyVolatileFrom(oldActive, switchCopyFlag);
      }
      if (newMove) pokemon.lastMove = newMove;
      oldActive.clearVolatile();
    }
    if (oldActive) {
      oldActive.isActive = false;
      oldActive.isStarted = false;
      oldActive.usedItemThisTurn = false;
      oldActive.statsRaisedThisTurn = false;
      oldActive.statsLoweredThisTurn = false;
      oldActive.position = pokemon.position;
      if (oldActive.fainted) oldActive.status = "";
      if (this.battle.gen <= 4) {
        pokemon.lastItem = oldActive.lastItem;
        oldActive.lastItem = "";
      }
      pokemon.position = pos;
      side.pokemon[pokemon.position] = pokemon;
      side.pokemon[oldActive.position] = oldActive;
    }
    pokemon.isActive = true;
    side.active[pos] = pokemon;
    pokemon.activeTurns = 0;
    pokemon.activeMoveActions = 0;
    for (const moveSlot of pokemon.moveSlots) {
      moveSlot.used = false;
    }
    pokemon.abilityState = this.battle.initEffectState({ id: pokemon.ability, target: pokemon });
    pokemon.itemState = this.battle.initEffectState({ id: pokemon.item, target: pokemon });
    this.battle.runEvent("BeforeSwitchIn", pokemon);
    if (sourceEffect) {
      this.battle.add(isDrag ? "drag" : "switch", pokemon, pokemon.getFullDetails, `[from] ${sourceEffect}`);
    } else {
      this.battle.add(isDrag ? "drag" : "switch", pokemon, pokemon.getFullDetails);
    }
    if (isDrag && this.battle.gen === 2) pokemon.draggedIn = this.battle.turn;
    pokemon.previouslySwitchedIn++;
    if (isDrag && this.battle.gen >= 5) {
      this.runSwitch(pokemon);
    } else {
      this.battle.queue.insertChoice({ choice: "runSwitch", pokemon });
    }
    return true;
  }
// ===== battle-actions.js:runSwitch
  runSwitch(pokemon) {
    const switchersIn = [pokemon];
    while (this.battle.queue.peek()?.choice === "runSwitch") {
      const nextSwitch = this.battle.queue.shift();
      switchersIn.push(nextSwitch.pokemon);
    }
    const allActive = this.battle.getAllActive(true);
    this.battle.speedSort(allActive);
    this.battle.speedOrder = allActive.map((a) => a.getFieldPositionValue());
    this.battle.fieldEvent("SwitchIn", switchersIn);
    for (const poke of switchersIn) {
      if (!poke.hp) continue;
      poke.isStarted = true;
      poke.draggedIn = null;
    }
    return true;
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
// ===== battle-actions.js:hitStepInvulnerabilityEvent
  hitStepInvulnerabilityEvent(targets, pokemon, move) {
    if (move.id === "helpinghand") return new Array(targets.length).fill(true);
    const hitResults = [];
    for (const [i, target] of targets.entries()) {
      if (target.volatiles["commanding"]) {
        hitResults[i] = false;
      } else if (this.battle.gen >= 8 && move.id === "toxic" && pokemon.hasType("Poison")) {
        hitResults[i] = true;
      } else {
        hitResults[i] = this.battle.runEvent("Invulnerability", target, pokemon, move);
      }
      if (hitResults[i] === false) {
        if (move.smartTarget) {
          move.smartTarget = false;
        } else {
          if (!move.spreadHit) this.battle.attrLastMove("[miss]");
          this.battle.add("-miss", pokemon, target);
        }
      }
    }
    return hitResults;
  }
// ===== battle-actions.js:hitStepTryHitEvent
  hitStepTryHitEvent(targets, pokemon, move) {
    const hitResults = this.battle.runEvent("TryHit", targets, pokemon, move);
    if (!hitResults.includes(true) && hitResults.includes(false)) {
      this.battle.add("-fail", pokemon);
      this.battle.attrLastMove("[still]");
    }
    for (const i of targets.keys()) {
      if (hitResults[i] !== this.battle.NOT_FAIL) hitResults[i] = hitResults[i] || false;
    }
    return hitResults;
  }
// ===== battle-actions.js:hitStepTypeImmunity
  hitStepTypeImmunity(targets, pokemon, move) {
    if (move.ignoreImmunity === void 0) {
      move.ignoreImmunity = move.category === "Status";
    }
    const hitResults = [];
    for (const i of targets.keys()) {
      hitResults[i] = targets[i].runImmunity(move, !move.smartTarget);
    }
    return hitResults;
  }
// ===== battle-actions.js:hitStepTryImmunity
  hitStepTryImmunity(targets, pokemon, move) {
    const hitResults = [];
    for (const [i, target] of targets.entries()) {
      if (this.battle.gen >= 6 && move.flags["powder"] && target !== pokemon && !this.dex.getImmunity("powder", target)) {
        this.battle.debug("natural powder immunity");
        this.battle.add("-immune", target);
        hitResults[i] = false;
      } else if (!this.battle.singleEvent("TryImmunity", move, {}, target, pokemon, move)) {
        this.battle.add("-immune", target);
        hitResults[i] = false;
      } else if (this.battle.gen >= 7 && move.pranksterBoosted && pokemon.hasAbility("prankster") && !targets[i].isAlly(pokemon) && !this.dex.getImmunity("prankster", target)) {
        this.battle.debug("natural prankster immunity");
        if (target.illusion || !(move.status && !this.dex.getImmunity(move.status, target))) {
          this.battle.hint("Since gen 7, Dark is immune to Prankster moves.");
        }
        this.battle.add("-immune", target);
        hitResults[i] = false;
      } else {
        hitResults[i] = true;
      }
    }
    return hitResults;
  }
// ===== battle-actions.js:hitStepAccuracy
  hitStepAccuracy(targets, pokemon, move) {
    const hitResults = [];
    for (const [i, target] of targets.entries()) {
      this.battle.activeTarget = target;
      let accuracy = move.accuracy;
      if (move.ohko) {
        if (!target.isSemiInvulnerable()) {
          accuracy = 30;
          if (move.ohko === "Ice" && this.battle.gen >= 7 && !pokemon.hasType("Ice")) {
            accuracy = 20;
          }
          if (!target.volatiles["dynamax"] && pokemon.level >= target.level && (move.ohko === true || !target.hasType(move.ohko))) {
            accuracy += pokemon.level - target.level;
          } else {
            this.battle.add("-immune", target, "[ohko]");
            hitResults[i] = false;
            continue;
          }
        }
      } else {
        accuracy = this.battle.runEvent("ModifyAccuracy", target, pokemon, move, accuracy);
        if (accuracy !== true) {
          let boost = 0;
          if (!move.ignoreAccuracy) {
            const boosts = this.battle.runEvent("ModifyBoost", pokemon, null, null, { ...pokemon.boosts });
            boost = this.battle.clampIntRange(boosts["accuracy"], -6, 6);
          }
          if (!move.ignoreEvasion) {
            const boosts = this.battle.runEvent("ModifyBoost", target, null, null, { ...target.boosts });
            boost = this.battle.clampIntRange(boost - boosts["evasion"], -6, 6);
          }
          if (boost > 0) {
            accuracy = this.battle.trunc(accuracy * (3 + boost) / 3);
          } else if (boost < 0) {
            accuracy = this.battle.trunc(accuracy * 3 / (3 - boost));
          }
        }
      }
      if (move.alwaysHit || move.id === "toxic" && this.battle.gen >= 8 && pokemon.hasType("Poison") || move.target === "self" && move.category === "Status" && !target.isSemiInvulnerable()) {
        accuracy = true;
      } else {
        accuracy = this.battle.runEvent("Accuracy", target, pokemon, move, accuracy);
      }
      if (accuracy !== true && !this.battle.randomChance(accuracy, 100)) {
        if (move.smartTarget) {
          move.smartTarget = false;
        } else {
          if (!move.spreadHit) this.battle.attrLastMove("[miss]");
          this.battle.add("-miss", pokemon, target);
        }
        if (!move.ohko && pokemon.hasItem("blunderpolicy") && pokemon.useItem()) {
          this.battle.boost({ spe: 2 }, pokemon);
        }
        hitResults[i] = false;
        continue;
      }
      hitResults[i] = true;
    }
    return hitResults;
  }
// ===== battle-actions.js:hitStepBreakProtect
  hitStepBreakProtect(targets, pokemon, move) {
    if (move.breaksProtect) {
      for (const target of targets) {
        let broke = false;
        for (const effectid of [
          "banefulbunker",
          "burningbulwark",
          "kingsshield",
          "obstruct",
          "protect",
          "silktrap",
          "spikyshield"
        ]) {
          if (target.removeVolatile(effectid)) broke = true;
        }
        if (this.battle.gen >= 6 || !target.isAlly(pokemon)) {
          for (const effectid of ["craftyshield", "matblock", "quickguard", "wideguard"]) {
            if (target.side.removeSideCondition(effectid)) broke = true;
          }
        }
        if (broke) {
          if (move.id === "feint") {
            this.battle.add("-activate", target, "move: Feint");
          } else {
            this.battle.add("-activate", target, `move: ${move.name}`, "[broken]");
          }
          if (this.battle.gen >= 6) delete target.volatiles["stall"];
        }
      }
    }
    return void 0;
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
// ===== battle-actions.js:spreadMoveHit
  spreadMoveHit(targets, pokemon, moveOrMoveName, hitEffect, isSecondary, isSelf) {
    const target = targets[0];
    let damage = [];
    for (const i of targets.keys()) {
      damage[i] = true;
    }
    const move = this.dex.getActiveMove(moveOrMoveName);
    let hitResult = true;
    let moveData = hitEffect;
    if (!moveData) moveData = move;
    if (!moveData.flags) moveData.flags = {};
    if (move.target === "all" && !isSelf) {
      hitResult = this.battle.singleEvent("TryHitField", moveData, {}, target || null, pokemon, move);
    } else if ((move.target === "foeSide" || move.target === "allySide" || move.target === "allyTeam") && !isSelf) {
      hitResult = this.battle.singleEvent("TryHitSide", moveData, {}, target || null, pokemon, move);
    } else if (target) {
      hitResult = this.battle.singleEvent("TryHit", moveData, {}, target, pokemon, move);
    }
    if (!hitResult) {
      if (hitResult === false) {
        this.battle.add("-fail", pokemon);
        this.battle.attrLastMove("[still]");
      }
      return [[false], targets];
    }
    if (!isSecondary && !isSelf) {
      if (move.target !== "all" && move.target !== "allyTeam" && move.target !== "allySide" && move.target !== "foeSide") {
        damage = this.tryPrimaryHitEvent(damage, targets, pokemon, move, moveData, isSecondary);
      }
    }
    for (const i of targets.keys()) {
      if (damage[i] === this.battle.HIT_SUBSTITUTE) {
        damage[i] = true;
        targets[i] = null;
      }
      if (targets[i] && isSecondary && !moveData.self) {
        damage[i] = true;
      }
      if (!damage[i]) targets[i] = false;
    }
    damage = this.getSpreadDamage(damage, targets, pokemon, move, moveData, isSecondary, isSelf);
    for (const i of targets.keys()) {
      if (damage[i] === false) targets[i] = false;
    }
    damage = this.battle.spreadDamage(damage, targets, pokemon, move);
    for (const i of targets.keys()) {
      if (damage[i] === false) targets[i] = false;
    }
    damage = this.runMoveEffects(damage, targets, pokemon, move, moveData, isSecondary, isSelf);
    for (const i of targets.keys()) {
      if (!damage[i] && damage[i] !== 0) targets[i] = false;
    }
    const activeTarget = this.battle.activeTarget;
    if (moveData.self && !move.selfDropped) this.selfDrops(targets, pokemon, move, moveData, isSecondary);
    if (moveData.secondaries) this.secondaries(targets, pokemon, move, moveData, isSelf);
    this.battle.activeTarget = activeTarget;
    if (moveData.forceSwitch) damage = this.forceSwitch(damage, targets, pokemon, move);
    for (const i of targets.keys()) {
      if (!damage[i] && damage[i] !== 0) targets[i] = false;
    }
    const damagedTargets = [];
    const damagedDamage = [];
    for (const [i, t] of targets.entries()) {
      if (typeof damage[i] === "number" && t) {
        damagedTargets.push(t);
        damagedDamage.push(damage[i]);
      }
    }
    const pokemonOriginalHP = pokemon.hp;
    if (damagedDamage.length && !isSecondary && !isSelf) {
      if (this.battle.gen >= 5) {
        this.battle.runEvent("DamagingHit", damagedTargets, pokemon, move, damagedDamage);
      }
      if (moveData.onAfterHit && pokemon.hp) {
        for (const t of damagedTargets) {
          this.battle.singleEvent("AfterHit", moveData, {}, t, pokemon, move);
        }
      }
      if (this.battle.gen < 5) {
        this.battle.runEvent("DamagingHit", damagedTargets, pokemon, move, damagedDamage);
      }
      if (pokemon.hp && pokemon.hp <= pokemon.maxhp / 2 && pokemonOriginalHP > pokemon.maxhp / 2) {
        this.battle.runEvent("EmergencyExit", pokemon);
      }
    }
    return [damage, targets];
  }
// ===== battle-actions.js:tryPrimaryHitEvent
  tryPrimaryHitEvent(damage, targets, pokemon, move, moveData, isSecondary) {
    for (const [i, target] of targets.entries()) {
      if (!target) continue;
      damage[i] = this.battle.runEvent("TryPrimaryHit", target, pokemon, moveData);
    }
    return damage;
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
// ===== battle-actions.js:forceSwitch
  forceSwitch(damage, targets, source, move) {
    for (const [i, target] of targets.entries()) {
      if (target && target.hp > 0 && source.hp > 0 && this.battle.canSwitch(target.side)) {
        const hitResult = this.battle.runEvent("DragOut", target, source, move);
        if (hitResult) {
          target.forceSwitchFlag = true;
        } else if (hitResult === false && move.category === "Status") {
          this.battle.add("-fail", source);
          this.battle.attrLastMove("[still]");
          damage[i] = false;
        }
      }
    }
    return damage;
  }
// ===== battle-actions.js:moveHit
  moveHit(targets, pokemon, moveOrMoveName, moveData, isSecondary, isSelf) {
    if (!Array.isArray(targets)) targets = [targets];
    const retVal = this.spreadMoveHit(targets, pokemon, moveOrMoveName, moveData, isSecondary, isSelf)[0][0];
    return retVal === true ? void 0 : retVal;
  }
// ===== battle-actions.js:afterMoveSecondaryEvent
  afterMoveSecondaryEvent(targets, pokemon, move) {
    if (!(move.hasSheerForce && pokemon.hasAbility("sheerforce"))) {
      this.battle.singleEvent("AfterMoveSecondary", move, null, targets[0], pokemon, move);
      this.battle.runEvent("AfterMoveSecondary", targets, pokemon, move);
    }
    return void 0;
  }
// ===== battle-actions.js:tryMoveHit
  tryMoveHit(targetOrTargets, pokemon, move) {
    const target = Array.isArray(targetOrTargets) ? targetOrTargets[0] : targetOrTargets;
    const targets = Array.isArray(targetOrTargets) ? targetOrTargets : [target];
    this.battle.setActiveMove(move, pokemon, targets[0]);
    let hitResult = this.battle.singleEvent("Try", move, null, pokemon, target, move) && this.battle.singleEvent("PrepareHit", move, {}, target, pokemon, move) && this.battle.runEvent("PrepareHit", pokemon, target, move);
    if (!hitResult) {
      if (hitResult === false) {
        this.battle.add("-fail", pokemon);
        this.battle.attrLastMove("[still]");
      }
      return false;
    }
    const isFFAHazard = move.target === "foeSide" && this.battle.gameType === "freeforall";
    if (move.target === "all") {
      hitResult = this.battle.runEvent("TryHitField", target, pokemon, move);
    } else if (isFFAHazard) {
      const hitResults = this.battle.runEvent("TryHitSide", targets, pokemon, move);
      if (hitResults.some((result) => !result)) return false;
      hitResult = true;
    } else {
      hitResult = this.battle.runEvent("TryHitSide", target, pokemon, move);
    }
    if (!hitResult) {
      if (hitResult === false) {
        this.battle.add("-fail", pokemon);
        this.battle.attrLastMove("[still]");
      }
      return false;
    }
    return this.moveHit(isFFAHazard ? targets : target, pokemon, move);
  }
// ===== battle-actions.js:getZMove
  getZMove(move, pokemon, skipChecks) {
    const item = pokemon.getItem();
    if (!skipChecks) {
      if (pokemon.side.zMoveUsed) return;
      if (!item.zMove) return;
      if (item.itemUser && !item.itemUser.includes(pokemon.species.name)) return;
      const moveData = pokemon.getMoveData(move);
      if (!moveData?.pp) return;
    }
    if (item.zMoveFrom) {
      if (move.name === item.zMoveFrom) return item.zMove;
    } else if (item.zMove === true) {
      if (move.type === item.zMoveType) {
        if (move.category === "Status") {
          return move.name;
        } else if (move.zMove?.basePower) {
          return this.Z_MOVES[move.type];
        }
      }
    }
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
// ===== battle-actions.js:canMegaEvo
  canMegaEvo(pokemon) {
    const species = pokemon.baseSpecies;
    const altForme = species.otherFormes && this.dex.species.get(species.otherFormes[0]);
    const item = pokemon.getItem();
    if ((this.battle.gen <= 7 || this.battle.ruleTable.has("+tag:past") || this.battle.ruleTable.has("+tag:future")) && altForme?.isMega && altForme?.requiredMove && pokemon.baseMoves.includes((0, import_dex.toID)(altForme.requiredMove)) && !item.zMove) {
      return altForme.name;
    }
    if (!item.megaStone) return null;
    let megaEvolution = item.megaStone[species.name];
    if (megaEvolution && this.dex.species.get(megaEvolution).gen >= 9) return megaEvolution;
    megaEvolution = item.megaStone[species.baseSpecies];
    return megaEvolution && megaEvolution !== species.name ? megaEvolution : null;
  }
// ===== battle-actions.js:targetTypeChoices
  targetTypeChoices(targetType) {
    return CHOOSABLE_TARGETS.has(targetType);
  }
// NOT FOUND battle-actions.js:getTarget
// NOT FOUND battle-actions.js:getRandomTarget
// ===== pokemon.js:getActionSpeed
  getActionSpeed() {
    let speed = this.getStat("spe", false, false);
    const trickRoomCheck = this.battle.ruleTable.has("twisteddimensionmod") ? !this.battle.field.getPseudoWeather("trickroom") : this.battle.field.getPseudoWeather("trickroom");
    if (trickRoomCheck) {
      speed = 1e4 - speed;
    }
    return this.battle.trunc(speed, 13);
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
// ===== pokemon.js:getWeight
  getWeight() {
    const weighthg = this.battle.runEvent("ModifyWeight", this, null, null, this.weighthg);
    return Math.max(1, weighthg);
  }
// ===== pokemon.js:damage
  damage(d, source = null, effect = null) {
    if (!this.hp || isNaN(d) || d <= 0) return 0;
    if (d < 1 && d > 0) d = 1;
    d = this.battle.trunc(d);
    this.hp -= d;
    if (this.hp <= 0) {
      d += this.hp;
      this.faint(source, effect);
    }
    return d;
  }
// ===== pokemon.js:faint
  faint(source = null, effect = null) {
    if (this.fainted || this.faintQueued) return 0;
    const d = this.hp;
    this.hp = 0;
    this.switchFlag = false;
    this.faintQueued = true;
    this.battle.faintQueue.push({
      target: this,
      source,
      effect
    });
    return d;
  }
// ===== pokemon.js:trySetStatus
  trySetStatus(status, source = null, sourceEffect = null) {
    return this.setStatus(this.status || status, source, sourceEffect);
  }
// ===== pokemon.js:setStatus
  setStatus(status, source = null, sourceEffect = null, ignoreImmunities = false) {
    if (!this.hp) return false;
    status = this.battle.dex.conditions.get(status);
    if (this.battle.event) {
      if (!source) source = this.battle.event.source;
      if (!sourceEffect) sourceEffect = this.battle.effect;
    }
    if (!source) source = this;
    if (this.status === status.id) {
      if (sourceEffect?.status === this.status) {
        this.battle.add("-fail", this, this.status);
      } else if (sourceEffect?.status) {
        this.battle.add("-fail", source);
        this.battle.attrLastMove("[still]");
      }
      return false;
    }
    if (!ignoreImmunities && status.id && !(source?.hasAbility("corrosion") && ["tox", "psn"].includes(status.id))) {
      if (!this.runStatusImmunity(status.id === "tox" ? "psn" : status.id)) {
        this.battle.debug("immune to status");
        if (sourceEffect?.status) {
          this.battle.add("-immune", this);
        }
        return false;
      }
    }
    const prevStatus = this.status;
    const prevStatusState = this.statusState;
    if (status.id) {
      const result = this.battle.runEvent("SetStatus", this, source, sourceEffect, status);
      if (!result) {
        this.battle.debug("set status [" + status.id + "] interrupted");
        return result;
      }
    }
    this.status = status.id;
    this.statusState = this.battle.initEffectState({ id: status.id, target: this });
    if (source) this.statusState.source = source;
    if (status.duration) this.statusState.duration = status.duration;
    if (status.durationCallback) {
      this.statusState.duration = status.durationCallback.call(this.battle, this, source, sourceEffect);
    }
    if (status.id && !this.battle.singleEvent("Start", status, this.statusState, this, source, sourceEffect)) {
      this.battle.debug("status start [" + status.id + "] interrupted");
      this.status = prevStatus;
      this.statusState = prevStatusState;
      return false;
    }
    if (status.id && !this.battle.runEvent("AfterSetStatus", this, source, sourceEffect, status)) {
      return false;
    }
    return true;
  }
// ===== pokemon.js:boostBy
  boostBy(boosts) {
    boosts = this.getCappedBoost(boosts);
    let delta = 0;
    let boostName;
    for (boostName in boosts) {
      delta = boosts[boostName];
      this.boosts[boostName] += delta;
    }
    return delta;
  }
// ===== pokemon.js:eatItem
  eatItem(force, source, sourceEffect) {
    if (!this.item) return false;
    if (!this.hp && this.item !== "jabocaberry" && this.item !== "rowapberry" || !this.isActive) return false;
    if (!sourceEffect && this.battle.effect) sourceEffect = this.battle.effect;
    if (!source && this.battle.event?.target) source = this.battle.event.target;
    const item = this.getItem();
    if (sourceEffect?.effectType === "Item" && this.item !== sourceEffect.id && source === this) {
      return false;
    }
    if (this.battle.runEvent("UseItem", this, null, null, item) && (force || this.battle.runEvent("TryEatItem", this, null, null, item))) {
      this.battle.add("-enditem", this, item, "[eat]");
      this.battle.singleEvent("Eat", item, this.itemState, this, source, sourceEffect);
      this.battle.runEvent("EatItem", this, source, sourceEffect, item);
      if (RESTORATIVE_BERRIES.has(item.id)) {
        switch (this.pendingStaleness) {
          case "internal":
            if (this.staleness !== "external") this.staleness = "internal";
            break;
          case "external":
            this.staleness = "external";
            break;
        }
        this.pendingStaleness = void 0;
      }
      this.lastItem = this.item;
      this.item = "";
      this.battle.clearEffectState(this.itemState);
      this.usedItemThisTurn = true;
      this.ateBerry = true;
      this.battle.runEvent("AfterUseItem", this, null, null, item);
      return true;
    }
    return false;
  }
// ===== pokemon.js:useItem
  useItem(source, sourceEffect) {
    if (!this.hp && !this.getItem().isGem || !this.isActive) return false;
    if (!this.item) return false;
    if (!sourceEffect && this.battle.effect) sourceEffect = this.battle.effect;
    if (!source && this.battle.event?.target) source = this.battle.event.target;
    const item = this.getItem();
    if (sourceEffect?.effectType === "Item" && this.item !== sourceEffect.id && source === this) {
      return false;
    }
    if (this.battle.runEvent("UseItem", this, null, null, item)) {
      switch (item.id) {
        case "redcard":
          this.battle.add("-enditem", this, item, `[of] ${source}`);
          break;
        default:
          if (item.isGem) {
            this.battle.add("-enditem", this, item, "[from] gem");
          } else {
            this.battle.add("-enditem", this, item);
          }
          break;
      }
      if (item.boosts) {
        this.battle.boost(item.boosts, this, source, item);
      }
      this.battle.singleEvent("Use", item, this.itemState, this, source, sourceEffect);
      this.lastItem = this.item;
      this.item = "";
      this.battle.clearEffectState(this.itemState);
      this.usedItemThisTurn = true;
      this.battle.runEvent("AfterUseItem", this, null, null, item);
      return true;
    }
    return false;
  }
// ===== pokemon.js:getMoveTargets
  getMoveTargets(move, target) {
    let targets = [];
    switch (move.target) {
      case "all":
      case "foeSide":
      case "allySide":
      case "allyTeam":
        if (!move.target.startsWith("foe")) {
          targets.push(...this.alliesAndSelf());
        }
        if (!move.target.startsWith("ally")) {
          targets.push(...this.foes(true));
        }
        if (targets.length && !targets.includes(target)) {
          this.battle.retargetLastMove(targets[targets.length - 1]);
        }
        break;
      case "allAdjacent":
        targets.push(...this.adjacentAllies());
      // falls through
      case "allAdjacentFoes":
        targets.push(...this.adjacentFoes());
        if (targets.length && !targets.includes(target)) {
          this.battle.retargetLastMove(targets[targets.length - 1]);
        }
        break;
      case "allies":
        targets = this.alliesAndSelf();
        break;
      default:
        const selectedTarget = target;
        if (!target || target.fainted && !target.isAlly(this) && this.battle.gameType !== "freeforall") {
          const possibleTarget = this.battle.getRandomTarget(this, move);
          if (!possibleTarget) return { targets: [], pressureTargets: [] };
          target = possibleTarget;
        }
        if (this.battle.activePerHalf > 1 && !move.tracksTarget) {
          const isCharging = move.flags["charge"] && !this.volatiles["twoturnmove"] && !(move.id.startsWith("solarb") && ["sunnyday", "desolateland"].includes(this.effectiveWeather(move))) && !(move.id === "electroshot" && ["raindance", "primordialsea"].includes(this.effectiveWeather(move))) && !(this.hasItem("powerherb") && move.id !== "skydrop");
          if (!isCharging) {
            target = this.battle.priorityEvent("RedirectTarget", this, this, move, target);
          }
        }
        if (move.smartTarget) {
          targets = this.getSmartTargets(target, move);
          target = targets[0];
        } else {
          targets.push(target);
        }
        if (target.fainted && !move.flags["futuremove"]) {
          return { targets: [], pressureTargets: [] };
        }
        if (selectedTarget !== target) {
          this.battle.retargetLastMove(target);
        }
    }
    let pressureTargets = targets;
    if (move.target === "foeSide") {
      pressureTargets = [];
    }
    if (move.flags["mustpressure"]) {
      pressureTargets = this.foes();
    }
    return { targets, pressureTargets };
  }
// ===== pokemon.js:runImmunity
  runImmunity(source, message) {
    if (!source) return true;
    const type = typeof source !== "string" ? source.type : source;
    if (typeof source !== "string") {
      if (source.ignoreImmunity && (source.ignoreImmunity === true || source.ignoreImmunity[type])) {
        return true;
      }
    }
    if (!type || type === "???") return true;
    if (!this.battle.dex.types.isName(type)) {
      throw new Error("Use runStatusImmunity for " + type);
    }
    const negateImmunity = !this.battle.runEvent("NegateImmunity", this, type);
    const notImmune = type === "Ground" ? this.isGrounded(negateImmunity) : negateImmunity || this.battle.dex.getImmunity(type, this);
    if (notImmune) return true;
    if (!message) return false;
    if (notImmune === null) {
      if (this.hasAbility("levitate")) {
        this.battle.add("-immune", this, "[from] ability: Levitate");
      } else if (this.hasAbility("eelevate")) {
        this.battle.add("-immune", this, "[from] ability: Eelevate");
      } else {
        this.battle.add("-immune", this);
      }
    } else {
      this.battle.add("-immune", this);
    }
    return false;
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
// ===== pokemon.js:addVolatile
  addVolatile(status, source = null, sourceEffect = null, linkedStatus = null) {
    let result;
    status = this.battle.dex.conditions.get(status);
    if (!this.hp && !status.affectsFainted) return false;
    if (linkedStatus && source && !source.hp) return false;
    if (this.battle.event) {
      if (!source) source = this.battle.event.source;
      if (!sourceEffect) sourceEffect = this.battle.effect;
    }
    if (!source) source = this;
    if (this.volatiles[status.id]) {
      if (!status.onRestart) return false;
      return this.battle.singleEvent("Restart", status, this.volatiles[status.id], this, source, sourceEffect);
    }
    if (!this.runStatusImmunity(status.id)) {
      this.battle.debug("immune to volatile status");
      if (sourceEffect?.status) {
        this.battle.add("-immune", this);
      }
      return false;
    }
    result = this.battle.runEvent("TryAddVolatile", this, source, sourceEffect, status);
    if (!result) {
      this.battle.debug("add volatile [" + status.id + "] interrupted");
      return result;
    }
    this.volatiles[status.id] = this.battle.initEffectState({ id: status.id, name: status.name, target: this });
    if (source) {
      this.volatiles[status.id].source = source;
      this.volatiles[status.id].sourceSlot = source.getSlot();
    }
    if (sourceEffect) this.volatiles[status.id].sourceEffect = sourceEffect;
    if (status.duration) this.volatiles[status.id].duration = status.duration;
    if (status.durationCallback) {
      this.volatiles[status.id].duration = status.durationCallback.call(this.battle, this, source, sourceEffect);
    }
    result = this.battle.singleEvent("Start", status, this.volatiles[status.id], this, source, sourceEffect);
    if (!result) {
      delete this.volatiles[status.id];
      return result;
    }
    if (linkedStatus && source) {
      if (!source.volatiles[linkedStatus.toString()]) {
        source.addVolatile(linkedStatus, this, sourceEffect);
        source.volatiles[linkedStatus.toString()].linkedPokemon = [this];
        source.volatiles[linkedStatus.toString()].linkedStatus = status;
      } else {
        source.volatiles[linkedStatus.toString()].linkedPokemon.push(this);
      }
      this.volatiles[status.toString()].linkedPokemon = [source];
      this.volatiles[status.toString()].linkedStatus = linkedStatus;
    }
    return true;
  }
// ===== pokemon.js:cureStatus
  cureStatus(silent = false) {
    if (!this.hp || !this.status) return false;
    this.battle.add("-curestatus", this, this.status, silent ? "[silent]" : "[msg]");
    if (this.status === "slp" && this.removeVolatile("nightmare")) {
      this.battle.add("-end", this, "Nightmare", "[silent]");
    }
    this.setStatus("");
    return true;
  }
// ===== pokemon.js:setBoost
  setBoost(boosts) {
    let boostName;
    for (boostName in boosts) {
      this.boosts[boostName] = boosts[boostName];
    }
  }
// ===== battle.js:boost
  boost(boost, target = null, source = null, effect = null, isSecondary = false, isSelf = false) {
    if (this.event) {
      target ||= this.event.target;
      source ||= this.event.source;
      effect ||= this.effect;
    }
    if (!target?.hp) return 0;
    if (!target.isActive) return false;
    if (this.gen > 5 && !target.side.foePokemonLeft()) return false;
    boost = this.runEvent("ChangeBoost", target, source, effect, { ...boost });
    boost = target.getCappedBoost(boost);
    boost = this.runEvent("TryBoost", target, source, effect, { ...boost });
    let success = null;
    let boosted = isSecondary;
    let boostName;
    for (boostName in boost) {
      const currentBoost = {
        [boostName]: boost[boostName]
      };
      let boostBy = target.boostBy(currentBoost);
      let msg = "-boost";
      if (boost[boostName] < 0 || target.boosts[boostName] === -6) {
        msg = "-unboost";
        boostBy = -boostBy;
      }
      if (boostBy) {
        success = true;
        switch (effect?.id) {
          case "bellydrum":
          case "angerpoint":
            this.add("-setboost", target, "atk", target.boosts["atk"], "[from] " + effect.fullname);
            break;
          case "bellydrum2":
            this.add(msg, target, boostName, boostBy, "[silent]");
            this.hint("In Gen 2, Belly Drum boosts by 2 when it fails.");
            break;
          case "zpower":
            this.add(msg, target, boostName, boostBy, "[zeffect]");
            break;
          default:
            if (!effect) break;
            if (effect.effectType === "Move") {
              this.add(msg, target, boostName, boostBy);
            } else if (effect.effectType === "Item") {
              this.add(msg, target, boostName, boostBy, "[from] item: " + effect.name);
            } else {
              if (effect.effectType === "Ability" && !boosted) {
                this.add("-ability", target, effect.name, "boost");
                boosted = true;
              }
              this.add(msg, target, boostName, boostBy);
            }
            break;
        }
        this.runEvent("AfterEachBoost", target, source, effect, currentBoost);
      } else if (effect?.effectType === "Ability") {
        if (isSecondary || isSelf) this.add(msg, target, boostName, boostBy);
      } else if (!isSecondary && !isSelf) {
        this.add(msg, target, boostName, boostBy);
      }
    }
    this.runEvent("AfterBoost", target, source, effect, boost);
    if (success) {
      if (Object.values(boost).some((x) => x > 0)) target.statsRaisedThisTurn = true;
      if (Object.values(boost).some((x) => x < 0)) target.statsLoweredThisTurn = true;
    }
    return success;
  }
// ===== battle.js:damage
  damage(damage, target = null, source = null, effect = null, instafaint = false) {
    if (this.event) {
      target ||= this.event.target;
      source ||= this.event.source;
      effect ||= this.effect;
    }
    return this.spreadDamage([damage], [target], source, effect, instafaint)[0];
  }
// ===== battle.js:spreadDamage
  spreadDamage(damage, targetArray = null, source = null, effect = null, instafaint = false) {
    if (!targetArray) return [0];
    const retVals = [];
    if (typeof effect === "string" || !effect) effect = this.dex.conditions.getByID(effect || "");
    for (const [i, curDamage] of damage.entries()) {
      const target = targetArray[i];
      let targetDamage = curDamage;
      if (!(targetDamage || targetDamage === 0)) {
        retVals[i] = targetDamage;
        continue;
      }
      if (!target || !target.hp) {
        retVals[i] = 0;
        continue;
      }
      if (!target.isActive) {
        retVals[i] = false;
        continue;
      }
      if (targetDamage !== 0) targetDamage = this.clampIntRange(targetDamage, 1);
      if (effect.id !== "strugglerecoil") {
        if (effect.effectType === "Weather" && !target.runStatusImmunity(effect.id)) {
          this.debug("weather immunity");
          retVals[i] = 0;
          continue;
        }
        targetDamage = this.runEvent("Damage", target, source, effect, targetDamage, true);
        if (!(targetDamage || targetDamage === 0)) {
          this.debug("damage event failed");
          retVals[i] = curDamage === true ? void 0 : targetDamage;
          continue;
        }
      }
      if (targetDamage !== 0) targetDamage = this.clampIntRange(targetDamage, 1);
      if (this.gen <= 1) {
        if (this.dex.currentMod === "gen1stadium" || !["recoil", "drain", "leechseed"].includes(effect.id) && effect.effectType !== "Status") {
          this.lastDamage = targetDamage;
        }
      }
      retVals[i] = targetDamage = target.damage(targetDamage, source, effect);
      if (targetDamage !== 0) target.hurtThisTurn = target.hp;
      if (source && effect.effectType === "Move") source.lastDamage = targetDamage;
      const name = effect.fullname === "tox" ? "psn" : effect.fullname;
      switch (effect.id) {
        case "partiallytrapped":
          this.add("-damage", target, target.getHealth, "[from] " + target.volatiles["partiallytrapped"].sourceEffect.fullname, "[partiallytrapped]");
          break;
        case "powder":
          this.add("-damage", target, target.getHealth, "[silent]");
          break;
        case "confused":
          this.add("-damage", target, target.getHealth, "[from] confusion");
          break;
        default:
          if (effect.effectType === "Move" || !name) {
            this.add("-damage", target, target.getHealth);
          } else if (source && (source !== target || effect.effectType === "Ability")) {
            this.add("-damage", target, target.getHealth, `[from] ${name}`, `[of] ${source}`);
          } else {
            this.add("-damage", target, target.getHealth, `[from] ${name}`);
          }
          break;
      }
      if (targetDamage && effect.effectType === "Move") {
        if (this.gen <= 4 && effect.drain && source) {
          const amount = this.clampIntRange(Math.floor(targetDamage * effect.drain[0] / effect.drain[1]), 1);
          if (this.gen <= 1) this.lastDamage = amount;
          this.heal(amount, source, target, "drain");
        }
        if (this.gen > 4 && effect.drain && source) {
          const amount = Math.round(targetDamage * effect.drain[0] / effect.drain[1]);
          this.heal(amount, source, target, "drain");
        }
      }
    }
    if (instafaint) {
      for (const [i, target] of targetArray.entries()) {
        if (!retVals[i] || !target) continue;
        if (target.hp <= 0) {
          this.debug(`instafaint: ${this.faintQueue.map((entry) => entry.target.name)}`);
          this.faintMessages(true);
          if (this.gen <= 2) {
            target.faint();
            if (this.gen <= 1) this.queue.clear();
          }
        }
      }
    }
    return retVals;
  }
// ===== battle.js:heal
  heal(damage, target, source = null, effect = null) {
    if (this.event) {
      target ||= this.event.target;
      source ||= this.event.source;
      effect ||= this.effect;
    }
    if (effect === "drain") effect = this.dex.conditions.getByID(effect);
    if (damage && damage <= 1) damage = 1;
    damage = this.trunc(damage);
    damage = this.runEvent("TryHeal", target, source, effect, damage);
    if (!damage) return damage;
    if (!target?.hp) return false;
    if (!target.isActive) return false;
    if (target.hp >= target.maxhp) return false;
    const finalDamage = target.heal(damage, source, effect);
    switch (effect?.id) {
      case "leechseed":
      case "rest":
        this.add("-heal", target, target.getHealth, "[silent]");
        break;
      case "drain":
        this.add("-heal", target, target.getHealth, "[from] drain", `[of] ${source}`);
        break;
      case "wish":
        break;
      case "zpower":
        this.add("-heal", target, target.getHealth, "[zeffect]");
        break;
      default:
        if (!effect) break;
        if (effect.effectType === "Move") {
          this.add("-heal", target, target.getHealth);
        } else if (source && source !== target) {
          this.add("-heal", target, target.getHealth, `[from] ${effect.fullname}`, `[of] ${source}`);
        } else {
          this.add("-heal", target, target.getHealth, `[from] ${effect.fullname}`);
        }
        break;
    }
    this.runEvent("Heal", target, source, effect, finalDamage);
    return finalDamage;
  }
// ===== battle.js:directDamage
  directDamage(damage, target, source = null, effect = null) {
    if (this.event) {
      target ||= this.event.target;
      source ||= this.event.source;
      effect ||= this.effect;
    }
    if (!target?.hp) return 0;
    if (!damage) return 0;
    damage = this.clampIntRange(damage, 1);
    if (typeof effect === "string" || !effect) effect = this.dex.conditions.getByID(effect || "");
    if (this.gen <= 1 && this.dex.currentMod !== "gen1stadium" && ["confusion", "jumpkick", "highjumpkick"].includes(effect.id)) {
      this.lastDamage = damage;
      if (target.volatiles["substitute"]) {
        const hint = "In Gen 1, if a Pokemon with a Substitute hurts itself due to confusion or Jump Kick/Hi Jump Kick recoil and the target";
        const foe = target.side.foe.active[0];
        if (foe?.volatiles["substitute"]) {
          foe.volatiles["substitute"].hp -= damage;
          if (foe.volatiles["substitute"].hp <= 0) {
            foe.removeVolatile("substitute");
            foe.subFainted = true;
          } else {
            this.add("-activate", foe, "Substitute", "[damage]");
          }
          this.hint(hint + " has a Substitute, the target's Substitute takes the damage.");
          return damage;
        } else {
          this.hint(hint + " does not have a Substitute there is no damage dealt.");
          return 0;
        }
      }
    }
    damage = target.damage(damage, source, effect);
    switch (effect.id) {
      case "strugglerecoil":
        this.add("-damage", target, target.getHealth, "[from] recoil");
        break;
      case "confusion":
        this.add("-damage", target, target.getHealth, "[from] confusion");
        break;
      default:
        this.add("-damage", target, target.getHealth);
        break;
    }
    if (target.fainted) this.faint(target);
    return damage;
  }
// ===== battle.js:getTarget
  getTarget(pokemon, move, targetLoc, originalTarget) {
    move = this.dex.moves.get(move);
    let tracksTarget = move.tracksTarget;
    if (pokemon.hasAbility(["stalwart", "propellertail"])) tracksTarget = true;
    if (tracksTarget && originalTarget?.isActive) {
      return originalTarget;
    }
    if (move.smartTarget) {
      const curTarget = pokemon.getAtLoc(targetLoc);
      return curTarget && !curTarget.fainted ? curTarget : this.getRandomTarget(pokemon, move);
    }
    const selfLoc = pokemon.getLocOf(pokemon);
    if (["adjacentAlly", "any", "normal"].includes(move.target) && targetLoc === selfLoc && !pokemon.volatiles["twoturnmove"] && !pokemon.volatiles["iceball"] && !pokemon.volatiles["rollout"]) {
      return move.flags["futuremove"] ? pokemon : null;
    }
    if (move.target !== "randomNormal" && this.validTargetLoc(targetLoc, pokemon, move.target)) {
      const target = pokemon.getAtLoc(targetLoc);
      if (target?.fainted) {
        if (this.gameType === "freeforall") {
          return target;
        }
        if (target.isAlly(pokemon)) {
          if (move.target === "adjacentAllyOrSelf" && this.gen !== 5) {
            return pokemon;
          }
          return target;
        }
      }
      if (target && !target.fainted) {
        return target;
      }
    }
    return this.getRandomTarget(pokemon, move);
  }
// ===== battle.js:validTargetLoc
  validTargetLoc(targetLoc, source, targetType) {
    if (targetLoc === 0) return true;
    const numSlots = this.activePerHalf;
    const sourceLoc = source.getLocOf(source);
    if (Math.abs(targetLoc) > numSlots) return false;
    const isSelf = sourceLoc === targetLoc;
    const isFoe = this.gameType === "freeforall" ? !isSelf : targetLoc > 0;
    const acrossFromTargetLoc = -(numSlots + 1 - targetLoc);
    const isAdjacent = targetLoc > 0 ? Math.abs(acrossFromTargetLoc - sourceLoc) <= 1 : Math.abs(targetLoc - sourceLoc) === 1;
    if (this.gameType === "freeforall" && targetType === "adjacentAlly") {
      return isAdjacent;
    }
    switch (targetType) {
      case "randomNormal":
      case "scripted":
      case "normal":
        return isAdjacent;
      case "adjacentAlly":
        return isAdjacent && !isFoe;
      case "adjacentAllyOrSelf":
        return isAdjacent && !isFoe || isSelf;
      case "adjacentFoe":
        return isAdjacent && isFoe;
      case "any":
        return !isSelf;
    }
    return false;
  }
// ===== battle.js:getRandomTarget
  getRandomTarget(pokemon, move) {
    move = this.dex.moves.get(move);
    if (["self", "all", "allySide", "allyTeam", "adjacentAllyOrSelf"].includes(move.target)) {
      return pokemon;
    } else if (move.target === "adjacentAlly") {
      if (this.gameType === "singles") return null;
      const adjacentAllies = pokemon.adjacentAllies();
      return adjacentAllies.length ? this.sample(adjacentAllies) : null;
    }
    if (this.gameType === "singles") return pokemon.side.foe.active[0];
    if (this.activePerHalf > 2) {
      if (move.target === "adjacentFoe" || move.target === "normal" || move.target === "randomNormal") {
        const adjacentFoes = pokemon.adjacentFoes();
        if (adjacentFoes.length) return this.sample(adjacentFoes);
        return pokemon.side.foe.active[pokemon.side.foe.active.length - 1 - pokemon.position];
      }
    }
    return pokemon.side.randomFoe() || pokemon.side.foe.active[0];
  }
