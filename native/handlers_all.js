// move:protect.onPrepareHit
onPrepareHit(pokemon) {
      return !!this.queue.willAct() && this.runEvent("StallMove", pokemon);
    }

// move:protect.onHit
onHit(pokemon) {
      pokemon.addVolatile("stall");
    }

// move:fakeout.onTry
onTry(source) {
      if (source.activeMoveActions > 1) {
        this.hint("Fake Out only works on your first turn out.");
        return false;
      }
    }

// move:fakeout.onDisableMove
onDisableMove(pokemon) {
      if (pokemon.activeMoveActions) {
        pokemon.disableMove("fakeout");
      }
    }

// move:grassyglide.onModifyPriority
onModifyPriority(priority, source, target, move) {
      if (this.field.isTerrain("grassyterrain") && source.isGrounded()) {
        return priority + 1;
      }
    }

// move:partingshot.onHit
onHit(target, source, move) {
      const success = this.boost({ atk: -1, spa: -1 }, target, source);
      if (!success && !target.hasAbility("mirrorarmor")) {
        delete move.selfSwitch;
      }
    }

// move:direclaw.secondaries.0.onHit
onHit(target, source) {
        const status = this.sample(["psn", "par", "slp"]);
        target.trySetStatus(status, source);
      }

// move:weatherball.onModifyType
onModifyType(move, pokemon) {
      switch (pokemon.effectiveWeather()) {
        case "sunnyday":
        case "desolateland":
          move.type = "Fire";
          break;
        case "raindance":
        case "primordialsea":
          move.type = "Water";
          break;
        case "sandstorm":
          move.type = "Rock";
          break;
        case "hail":
        case "snowscape":
          move.type = "Ice";
          break;
      }
    }

// move:weatherball.onModifyMove
onModifyMove(move, pokemon) {
      switch (pokemon.effectiveWeather()) {
        case "sunnyday":
        case "desolateland":
          move.basePower *= 2;
          break;
        case "raindance":
        case "primordialsea":
          move.basePower *= 2;
          break;
        case "sandstorm":
          move.basePower *= 2;
          break;
        case "hail":
        case "snowscape":
          move.basePower *= 2;
          break;
      }
      this.debug(`BP: ${move.basePower}`);
    }

// move:helpinghand.onTryHit
onTryHit(target) {
      if (!target.newlySwitched && !this.queue.willMove(target)) return false;
    }

// move:suckerpunch.onTry
onTry(source, target) {
      const action = this.queue.willMove(target);
      const move = action?.choice === "move" ? action.move : null;
      if (!move || move.category === "Status" && move.id !== "mefirst" || target.volatiles["mustrecharge"]) {
        return false;
      }
    }

// move:expandingforce.onBasePower
onBasePower(basePower, source) {
      if (this.field.isTerrain("psychicterrain") && source.isGrounded()) {
        this.debug("terrain buff");
        return this.chainModify(1.5);
      }
    }

// move:expandingforce.onModifyMove
onModifyMove(move, source, target) {
      if (this.field.isTerrain("psychicterrain") && source.isGrounded()) {
        move.target = "allAdjacentFoes";
      }
    }

// move:followme.onTry
onTry(source) {
      return this.activePerHalf > 1;
    }

// move:throatchop.secondaries.0.onHit
onHit(target) {
        target.addVolatile("throatchop");
      }

// move:lowkick.basePowerCallback
basePowerCallback(pokemon, target) {
      const targetWeight = target.getWeight();
      let bp;
      if (targetWeight >= 2e3) {
        bp = 120;
      } else if (targetWeight >= 1e3) {
        bp = 100;
      } else if (targetWeight >= 500) {
        bp = 80;
      } else if (targetWeight >= 250) {
        bp = 60;
      } else if (targetWeight >= 100) {
        bp = 40;
      } else {
        bp = 20;
      }
      this.debug(`BP: ${bp}`);
      return bp;
    }

// move:lowkick.onTryHit
onTryHit(target, pokemon, move) {
      if (target.volatiles["dynamax"]) {
        this.add("-fail", pokemon, "Dynamax");
        this.attrLastMove("[still]");
        return null;
      }
    }

// move:lastrespects.basePowerCallback
basePowerCallback(pokemon, target, move) {
      return 50 + 50 * pokemon.side.totalFainted;
    }

// move:hurricane.onModifyMove
onModifyMove(move, pokemon, target) {
      switch (target?.effectiveWeather()) {
        case "raindance":
        case "primordialsea":
          move.accuracy = true;
          break;
        case "sunnyday":
        case "desolateland":
          move.accuracy = 50;
          break;
      }
    }

// move:ragepowder.onTry
onTry(source) {
      return this.activePerHalf > 1;
    }

// move:wideguard.onTry
onTry() {
      return !!this.queue.willAct();
    }

// move:wideguard.onHitSide
onHitSide(side, source) {
      source.addVolatile("stall");
    }

// move:electroshot.onTryMove
onTryMove(attacker, defender, move) {
      if (attacker.removeVolatile(move.id)) {
        return;
      }
      this.add("-prepare", attacker, move.name);
      this.boost({ spa: 1 }, attacker, attacker, move);
      if (["raindance", "primordialsea"].includes(attacker.effectiveWeather())) {
        this.attrLastMove("[still]");
        this.addMove("-anim", attacker, move.name, defender);
        return;
      }
      if (!this.runEvent("ChargeMove", attacker, defender, move)) {
        return;
      }
      attacker.addVolatile("twoturnmove", defender);
      return null;
    }

// move:detect.onPrepareHit
onPrepareHit(pokemon) {
      return !!this.queue.willAct() && this.runEvent("StallMove", pokemon);
    }

// move:detect.onHit
onHit(pokemon) {
      pokemon.addVolatile("stall");
    }

// move:knockoff.onBasePower
onBasePower(basePower, source, target, move) {
      const item = target.getItem();
      if (!this.singleEvent("TakeItem", item, target.itemState, target, target, move, item)) return;
      if (item.id) {
        return this.chainModify(1.5);
      }
    }

// move:knockoff.onAfterHit
onAfterHit(target, source) {
      const item = target.takeItem();
      if (item) {
        this.add("-enditem", target, item.name, "[from] move: Knock Off", `[of] ${source}`);
      }
    }

// move:stompingtantrum.basePowerCallback
basePowerCallback(pokemon, target, move) {
      if (pokemon.moveLastTurnResult === false) {
        this.debug("doubling Stomping Tantrum BP due to previous move failure");
        return move.basePower * 2;
      }
      return move.basePower;
    }

// move:blizzard.onModifyMove
onModifyMove(move) {
      if (this.field.isWeather(["hail", "snowscape"])) move.accuracy = true;
    }

// move:perishsong.onHitField
onHitField(target, source, move) {
      let result = false;
      let message = false;
      for (const pokemon of this.getAllActive()) {
        if (this.runEvent("Invulnerability", pokemon, source, move) === false) {
          this.add("-miss", source, pokemon);
          result = true;
        } else if (this.runEvent("TryHit", pokemon, source, move) === null) {
          result = true;
        } else if (!pokemon.volatiles["perishsong"]) {
          pokemon.addVolatile("perishsong");
          this.add("-start", pokemon, "perish3", "[silent]");
          result = true;
          message = true;
        }
      }
      if (!result) return false;
      if (message) this.add("-fieldactivate", "move: Perish Song");
    }

// move:auroraveil.onTry
onTry() {
      return this.field.isWeather(["hail", "snowscape"]);
    }

// move:solarbeam.onTryMove
onTryMove(attacker, defender, move) {
      if (attacker.removeVolatile(move.id)) {
        return;
      }
      this.add("-prepare", attacker, move.name);
      if (["sunnyday", "desolateland"].includes(attacker.effectiveWeather(void 0, true))) {
        this.attrLastMove("[still]");
        this.addMove("-anim", attacker, move.name, defender);
        return;
      }
      if (!this.runEvent("ChargeMove", attacker, defender, move)) {
        return;
      }
      attacker.addVolatile("twoturnmove", defender);
      return null;
    }

// move:solarbeam.onBasePower
onBasePower(basePower, pokemon, target) {
      const weakWeathers = ["raindance", "primordialsea", "sandstorm", "hail", "snowscape"];
      if (weakWeathers.includes(pokemon.effectiveWeather())) {
        this.debug("weakened by weather");
        return this.chainModify(0.5);
      }
    }

// move:eruption.basePowerCallback
basePowerCallback(pokemon, target, move) {
      const bp = move.basePower * pokemon.hp / pokemon.maxhp;
      this.debug(`BP: ${bp}`);
      return bp;
    }

// move:psychicfangs.onTryHit
onTryHit(pokemon) {
      pokemon.side.removeSideCondition("reflect");
      pokemon.side.removeSideCondition("lightscreen");
      pokemon.side.removeSideCondition("auroraveil");
    }

// move:trick.onTryImmunity
onTryImmunity(target) {
      return !target.hasAbility("stickyhold");
    }

// move:trick.onHit
onHit(target, source, move) {
      const yourItem = target.takeItem(source);
      const myItem = source.takeItem();
      if (yourItem === false || myItem === false || !yourItem && !myItem) {
        if (yourItem) target.item = yourItem.id;
        if (myItem) source.item = myItem.id;
        return false;
      }
      if (myItem && !this.singleEvent("TakeItem", myItem, source.itemState, target, source, move, myItem) || yourItem && !this.singleEvent("TakeItem", yourItem, target.itemState, source, target, move, yourItem)) {
        if (yourItem) target.item = yourItem.id;
        if (myItem) source.item = myItem.id;
        return false;
      }
      this.add("-activate", source, "move: Trick", `[of] ${target}`);
      if (myItem) {
        target.setItem(myItem);
        this.add("-item", target, myItem, "[from] move: Trick");
      } else {
        this.add("-enditem", target, yourItem, "[silent]", "[from] move: Trick");
      }
      if (yourItem) {
        source.setItem(yourItem);
        this.add("-item", source, yourItem, "[from] move: Trick");
      } else {
        this.add("-enditem", source, myItem, "[silent]", "[from] move: Trick");
      }
    }

// move:spikyshield.onPrepareHit
onPrepareHit(pokemon) {
      return !!this.queue.willAct() && this.runEvent("StallMove", pokemon);
    }

// move:spikyshield.onHit
onHit(pokemon) {
      pokemon.addVolatile("stall");
    }

// move:terrainpulse.onModifyType
onModifyType(move, pokemon) {
      if (!pokemon.isGrounded()) return;
      switch (this.field.terrain) {
        case "electricterrain":
          move.type = "Electric";
          break;
        case "grassyterrain":
          move.type = "Grass";
          break;
        case "mistyterrain":
          move.type = "Fairy";
          break;
        case "psychicterrain":
          move.type = "Psychic";
          break;
      }
    }

// move:terrainpulse.onModifyMove
onModifyMove(move, pokemon) {
      if (this.field.terrain && pokemon.isGrounded()) {
        move.basePower *= 2;
        this.debug("BP doubled in Terrain");
      }
    }

// move:yawn.onTryHit
onTryHit(target) {
      if (target.status || !target.runStatusImmunity("slp")) {
        return false;
      }
    }

// move:clangoroussoul.onTry
onTry(source) {
      if (source.hp <= source.maxhp * 33 / 100 || source.maxhp === 1) return false;
    }

// move:clangoroussoul.onTryHit
onTryHit(pokemon, target, move) {
      if (!this.boost(move.boosts)) return null;
      delete move.boosts;
    }

// move:clangoroussoul.onHit
onHit(pokemon) {
      this.directDamage(pokemon.maxhp * 33 / 100);
    }

// move:doubleshock.onTryMove
onTryMove(pokemon, target, move) {
      if (pokemon.hasType("Electric")) return;
      this.add("-fail", pokemon, "move: Double Shock");
      this.attrLastMove("[still]");
      return null;
    }

// move:doubleshock.self.onHit
onHit(pokemon) {
        pokemon.setType(pokemon.getTypes(true).map((type) => type === "Electric" ? "???" : type));
        this.add("-start", pokemon, "typechange", pokemon.getTypes().join("/"), "[from] move: Double Shock");
      }

// move:waterspout.basePowerCallback
basePowerCallback(pokemon, target, move) {
      const bp = move.basePower * pokemon.hp / pokemon.maxhp;
      this.debug(`BP: ${bp}`);
      return bp;
    }

// move:steelroller.onTry
onTry() {
      return !this.field.isTerrain("");
    }

// move:steelroller.onHit
onHit() {
      this.field.clearTerrain();
    }

// move:steelroller.onAfterSubDamage
onAfterSubDamage() {
      this.field.clearTerrain();
    }

// move:freezedry.onEffectiveness
onEffectiveness(typeMod, target, type) {
      if (type === "Water") return 1;
    }

// move:revivalblessing.onTryHit
onTryHit(source) {
      if (!source.side.pokemon.filter((ally) => ally.fainted).length) {
        return false;
      }
    }

// move:powertrip.basePowerCallback
basePowerCallback(pokemon, target, move) {
      const bp = move.basePower + 20 * pokemon.positiveBoosts();
      this.debug(`BP: ${bp}`);
      return bp;
    }

// move:firstimpression.onTry
onTry(source) {
      if (source.activeMoveActions > 1) {
        this.hint("First Impression only works on your first turn out.");
        return false;
      }
    }

// move:firstimpression.onDisableMove
onDisableMove(pokemon) {
      if (pokemon.activeMoveActions) {
        pokemon.disableMove("firstimpression");
      }
    }

// move:tripleaxel.basePowerCallback
basePowerCallback(pokemon, target, move) {
      return 20 * move.hit;
    }

// move:superfang.damageCallback
damageCallback(pokemon, target) {
      return this.clampIntRange(target.getUndynamaxedHP() / 2, 1);
    }

// move:poltergeist.onTry
onTry(source, target) {
      return !!target.item;
    }

// move:poltergeist.onTryHit
onTryHit(target, source, move) {
      this.add("-activate", target, "move: Poltergeist", this.dex.items.get(target.item).name);
    }

// move:banefulbunker.onPrepareHit
onPrepareHit(pokemon) {
      return !!this.queue.willAct() && this.runEvent("StallMove", pokemon);
    }

// move:banefulbunker.onHit
onHit(pokemon) {
      pokemon.addVolatile("stall");
    }

// move:kingsshield.onPrepareHit
onPrepareHit(pokemon) {
      return !!this.queue.willAct() && this.runEvent("StallMove", pokemon);
    }

// move:kingsshield.onHit
onHit(pokemon) {
      pokemon.addVolatile("stall");
    }

// move:phantomforce.onTryMove
onTryMove(attacker, defender, move) {
      if (attacker.removeVolatile(move.id)) {
        return;
      }
      this.add("-prepare", attacker, move.name);
      if (!this.runEvent("ChargeMove", attacker, defender, move)) {
        return;
      }
      attacker.addVolatile("twoturnmove", defender);
      return null;
    }

// move:ragefist.basePowerCallback
basePowerCallback(pokemon) {
      return Math.min(350, 50 + 50 * pokemon.timesAttacked);
    }

// move:disable.onTryHit
onTryHit(target) {
      if (!target.lastMove || target.lastMove.isZOrMaxPowered || target.lastMove.isMax || target.lastMove.id === "struggle") {
        return false;
      }
    }

// move:grassknot.basePowerCallback
basePowerCallback(pokemon, target) {
      const targetWeight = target.getWeight();
      let bp;
      if (targetWeight >= 2e3) {
        bp = 120;
      } else if (targetWeight >= 1e3) {
        bp = 100;
      } else if (targetWeight >= 500) {
        bp = 80;
      } else if (targetWeight >= 250) {
        bp = 60;
      } else if (targetWeight >= 100) {
        bp = 40;
      } else {
        bp = 20;
      }
      this.debug(`BP: ${bp}`);
      return bp;
    }

// move:grassknot.onTryHit
onTryHit(target, source, move) {
      if (target.volatiles["dynamax"]) {
        this.add("-fail", source, "move: Grass Knot", "[from] Dynamax");
        this.attrLastMove("[still]");
        return null;
      }
    }

// move:healpulse.onHit
onHit(target, source) {
      let success = false;
      if (source.hasAbility("megalauncher")) {
        success = !!this.heal(this.modify(target.baseMaxhp, 0.75));
      } else {
        success = !!this.heal(Math.ceil(target.baseMaxhp * 0.5));
      }
      if (success && !target.isAlly(source)) {
        target.staleness = "external";
      }
      if (!success) {
        this.add("-fail", target, "heal");
        return this.NOT_FAIL;
      }
      return success;
    }

// move:risingvoltage.basePowerCallback
basePowerCallback(source, target, move) {
      if (this.field.isTerrain("electricterrain") && target.isGrounded()) {
        if (!source.isAlly(target)) this.hint(`${move.name}'s BP doubled on grounded target.`);
        return move.basePower * 2;
      }
      return move.basePower;
    }

// move:substitute.onTryHit
onTryHit(source) {
      if (source.volatiles["substitute"]) {
        this.add("-fail", source, "move: Substitute");
        return this.NOT_FAIL;
      }
      if (source.hp <= source.maxhp / 4 || source.maxhp === 1) {
        this.add("-fail", source, "move: Substitute", "[weak]");
        return this.NOT_FAIL;
      }
    }

// move:substitute.onHit
onHit(target) {
      this.directDamage(target.maxhp / 4);
    }

// move:heavyslam.basePowerCallback
basePowerCallback(pokemon, target) {
      const targetWeight = target.getWeight();
      const pokemonWeight = pokemon.getWeight();
      let bp;
      if (pokemonWeight >= targetWeight * 5) {
        bp = 120;
      } else if (pokemonWeight >= targetWeight * 4) {
        bp = 100;
      } else if (pokemonWeight >= targetWeight * 3) {
        bp = 80;
      } else if (pokemonWeight >= targetWeight * 2) {
        bp = 60;
      } else {
        bp = 40;
      }
      this.debug(`BP: ${bp}`);
      return bp;
    }

// move:heavyslam.onTryHit
onTryHit(target, pokemon, move) {
      if (target.volatiles["dynamax"]) {
        this.add("-fail", pokemon, "Dynamax");
        this.attrLastMove("[still]");
        return null;
      }
    }

// move:batonpass.onHit
onHit(target) {
      if (!this.canSwitch(target.side) || target.volatiles["commanded"]) {
        this.attrLastMove("[still]");
        this.add("-fail", target);
        return this.NOT_FAIL;
      }
    }

// move:batonpass.self.onHit
onHit(source) {
        source.skipBeforeSwitchOutEventFlag = true;
      }

// move:icespinner.onAfterHit
onAfterHit(target, source) {
      this.field.clearTerrain();
    }

// move:icespinner.onAfterSubDamage
onAfterSubDamage(damage, target, source) {
      if (source.hp) {
        this.field.clearTerrain();
      }
    }

// move:leechseed.onTryImmunity
onTryImmunity(target) {
      return !target.hasType("Grass");
    }

// move:stoneaxe.onAfterHit
onAfterHit(target, source, move) {
      if (!move.hasSheerForce && source.hp) {
        for (const side of source.side.foeSidesWithConditions()) {
          side.addSideCondition("stealthrock");
        }
      }
    }

// move:stoneaxe.onAfterSubDamage
onAfterSubDamage(damage, target, source, move) {
      if (!move.hasSheerForce && source.hp) {
        for (const side of source.side.foeSidesWithConditions()) {
          side.addSideCondition("stealthrock");
        }
      }
    }

// move:acrobatics.basePowerCallback
basePowerCallback(pokemon, target, move) {
      if (!pokemon.item) {
        this.debug("BP doubled for no item");
        return move.basePower * 2;
      }
      return move.basePower;
    }

// move:quickguard.onTry
onTry() {
      return !!this.queue.willAct();
    }

// move:quickguard.onHitSide
onHitSide(side, source) {
      source.addVolatile("stall");
    }

// move:healingwish.onTryHit
onTryHit(source) {
      if (!this.canSwitch(source.side)) {
        this.attrLastMove("[still]");
        this.add("-fail", source);
        return this.NOT_FAIL;
      }
    }

// move:psychup.onHit
onHit(target, source) {
      let i;
      for (i in target.boosts) {
        source.boosts[i] = target.boosts[i];
      }
      const volatilesToCopy = ["dragoncheer", "focusenergy", "gmaxchistrike", "laserfocus"];
      for (const volatile of volatilesToCopy) source.removeVolatile(volatile);
      for (const volatile of volatilesToCopy) {
        if (target.volatiles[volatile]) {
          source.addVolatile(volatile);
          if (volatile === "gmaxchistrike") source.volatiles[volatile].layers = target.volatiles[volatile].layers;
          if (volatile === "dragoncheer") source.volatiles[volatile].hasDragonType = target.volatiles[volatile].hasDragonType;
        }
      }
      this.add("-copyboost", source, target, "[from] move: Psych Up");
    }

// move:allyswitch.onPrepareHit
onPrepareHit(pokemon) {
      return pokemon.addVolatile("allyswitch");
    }

// move:allyswitch.onHit
onHit(pokemon) {
      let success = true;
      if (this.format.gameType !== "doubles" && this.format.gameType !== "triples") success = false;
      if (pokemon.side.active.length === 3 && pokemon.position === 1) success = false;
      const newPosition = pokemon.position === 0 ? pokemon.side.active.length - 1 : 0;
      if (!pokemon.side.active[newPosition]) success = false;
      if (pokemon.side.active[newPosition].fainted) success = false;
      if (!success) {
        this.add("-fail", pokemon, "move: Ally Switch");
        this.attrLastMove("[still]");
        return this.NOT_FAIL;
      }
      this.swapPosition(pokemon, newPosition, "[from] move: Ally Switch");
    }

// move:bellydrum.onHit
onHit(target) {
      if (target.hp <= target.maxhp / 2 || target.boosts.atk >= 6 || target.maxhp === 1) {
        return false;
      }
      this.directDamage(target.maxhp / 2);
      this.boost({ atk: 12 }, target);
    }

// move:lastresort.onTry
onTry(source) {
      if (source.moveSlots.length < 2) return false;
      let hasLastResort = false;
      for (const moveSlot of source.moveSlots) {
        if (moveSlot.id === "lastresort") {
          hasLastResort = true;
          continue;
        }
        if (!moveSlot.used) return false;
      }
      return hasLastResort;
    }

// move:soak.onHit
onHit(target) {
      if (target.getTypes().join() === "Water" || !target.setType("Water")) {
        this.add("-fail", target);
        return null;
      }
      this.add("-start", target, "typechange", "Water");
    }

// move:finalgambit.damageCallback
damageCallback(pokemon) {
      const damage = pokemon.hp;
      pokemon.faint();
      return damage;
    }

// move:thunder.onModifyMove
onModifyMove(move, pokemon, target) {
      switch (target?.effectiveWeather()) {
        case "raindance":
        case "primordialsea":
          move.accuracy = true;
          break;
        case "sunnyday":
        case "desolateland":
          move.accuracy = 50;
          break;
      }
    }

// move:skillswap.onHit
onHit(target, source, move) {
      return this.skillSwap(source, target);
    }

// move:assurance.basePowerCallback
basePowerCallback(pokemon, target, move) {
      if (target.hurtThisTurn) {
        this.debug("BP doubled on damaged target");
        return move.basePower * 2;
      }
      return move.basePower;
    }

// move:curse.onModifyMove
onModifyMove(move, source, target) {
      if (!source.hasType("Ghost")) {
        move.target = "self";
      } else if (source !== target && source.isAlly(target)) {
        move.target = "randomNormal";
      }
    }

// move:curse.onTryHit
onTryHit(target, source, move) {
      if (source.hasType("Ghost") && target.volatiles["curse"]) {
        return false;
      }
    }

// move:curse.onHit
onHit(target, source) {
      if (!source.hasType("Ghost")) {
        return !!this.boost({ spe: -1, atk: 1, def: 1 }, source, source);
      }
      this.directDamage(source.maxhp / 2, source, source);
      if (source.isAlly(target)) {
        const random = this.getRandomTarget(source, "Curse");
        if (!random) return false;
        target = random;
      }
      delete target.volatiles["curse"];
      target.addVolatile("curse");
    }

// move:beatup.basePowerCallback
basePowerCallback(pokemon, target, move) {
      const setSpecies = this.dex.species.get(move.allies.shift().set.species);
      const bp = 5 + Math.floor(setSpecies.baseStats.atk / 10);
      this.debug(`BP for ${setSpecies.name} hit: ${bp}`);
      return bp;
    }

// move:beatup.onModifyMove
onModifyMove(move, pokemon) {
      move.allies = pokemon.side.pokemon.filter((ally) => ally === pokemon || !ally.fainted && !ally.status);
      move.multihit = move.allies.length;
    }

// move:haze.onHitField
onHitField() {
      this.add("-clearallboost");
      for (const pokemon of this.getAllActive()) {
        pokemon.clearBoosts();
      }
    }

// move:barbbarrage.onBasePower
onBasePower(basePower, pokemon, target) {
      if (target.status === "psn" || target.status === "tox") {
        return this.chainModify(2);
      }
    }

// move:brickbreak.onTryHit
onTryHit(pokemon) {
      pokemon.side.removeSideCondition("reflect");
      pokemon.side.removeSideCondition("lightscreen");
      pokemon.side.removeSideCondition("auroraveil");
    }

// move:round.basePowerCallback
basePowerCallback(target, source, move) {
      if (move.sourceEffect === "round") {
        this.debug("BP doubled");
        return move.basePower * 2;
      }
      return move.basePower;
    }

// move:round.onTry
onTry(source, target, move) {
      for (const action of this.queue.list) {
        if (!action.pokemon || !action.move || action.maxMove || action.zmove) continue;
        if (action.move.id === "round") {
          this.queue.prioritizeAction(action, move);
          return;
        }
      }
    }

// move:upperhand.onTry
onTry(source, target) {
      const action = this.queue.willMove(target);
      const move = action?.choice === "move" ? action.move : null;
      if (!move || move.priority <= 0.1 || move.category === "Status") {
        return false;
      }
    }

// move:ficklebeam.onBasePower
onBasePower(basePower, pokemon) {
      if (this.randomChance(3, 10)) {
        this.attrLastMove("[anim] Fickle Beam All Out");
        this.add("-activate", pokemon, "move: Fickle Beam");
        return this.chainModify(2);
      }
    }

// move:clearsmog.onHit
onHit(target) {
      target.clearBoosts();
      this.add("-clearboost", target);
    }

// move:destinybond.onPrepareHit
onPrepareHit(pokemon) {
      return !pokemon.removeVolatile("destinybond");
    }

// move:afteryou.onHit
onHit(target) {
      if (this.activePerHalf === 1) return false;
      const action = this.queue.willMove(target);
      if (action) {
        this.queue.prioritizeAction(action);
        this.add("-activate", target, "move: After You");
      } else {
        return false;
      }
    }

// move:ragingbull.onTryHit
onTryHit(pokemon) {
      pokemon.side.removeSideCondition("reflect");
      pokemon.side.removeSideCondition("lightscreen");
      pokemon.side.removeSideCondition("auroraveil");
    }

// move:ragingbull.onModifyType
onModifyType(move, pokemon) {
      switch (pokemon.species.name) {
        case "Tauros-Paldea-Combat":
          move.type = "Fighting";
          break;
        case "Tauros-Paldea-Blaze":
          move.type = "Fire";
          break;
        case "Tauros-Paldea-Aqua":
          move.type = "Water";
          break;
      }
    }

// move:facade.onBasePower
onBasePower(basePower, pokemon) {
      if (pokemon.status && pokemon.status !== "slp") {
        return this.chainModify(2);
      }
    }

// move:futuresight.onTry
onTry(source, target) {
      if (!target.side.addSlotCondition(target, "futuremove")) return false;
      Object.assign(target.side.slotConditions[target.position]["futuremove"], {
        move: "futuresight",
        source,
        moveData: {
          id: "futuresight",
          name: "Future Sight",
          accuracy: 100,
          basePower: 120,
          category: "Special",
          priority: 0,
          flags: { allyanim: 1, metronome: 1, futuremove: 1 },
          ignoreImmunity: false,
          effectType: "Move",
          type: "Psychic"
        }
      });
      this.add("-start", source, "move: Future Sight");
      return this.NOT_FAIL;
    }

// move:payback.basePowerCallback
basePowerCallback(pokemon, target, move) {
      if (target.newlySwitched || this.queue.willMove(target)) {
        this.debug("Payback NOT boosted");
        return move.basePower;
      }
      this.debug("Payback damage boost");
      return move.basePower * 2;
    }

// move:pollenpuff.onTryHit
onTryHit(target, source, move) {
      if (source.isAlly(target)) {
        move.basePower = 0;
        move.infiltrates = true;
      }
    }

// move:pollenpuff.onTryMove
onTryMove(source, target, move) {
      if (source.isAlly(target) && source.volatiles["healblock"]) {
        this.attrLastMove("[still]");
        this.add("cant", source, "move: Heal Block", move);
        return false;
      }
    }

// move:pollenpuff.onHit
onHit(target, source, move) {
      if (source.isAlly(target)) {
        if (!this.heal(Math.floor(target.baseMaxhp * 0.5))) {
          return this.NOT_FAIL;
        }
      }
    }

// move:entrainment.onTryHit
onTryHit(target, source) {
      if (target === source || target.volatiles["dynamax"]) return false;
      if (target.ability === source.ability || target.getAbility().flags["cantsuppress"] || target.ability === "truant" || source.getAbility().flags["noentrain"]) {
        return false;
      }
    }

// move:entrainment.onHit
onHit(target, source) {
      const oldAbility = target.setAbility(source.ability, source);
      if (!oldAbility) return oldAbility;
      if (!target.isAlly(source)) target.volatileStaleness = "external";
    }

// move:transform.onHit
onHit(target, pokemon) {
      return pokemon.transformInto(target);
    }

// move:steelbeam.onMoveFail
onMoveFail(target, source, move) {
      if (move.multihit) return;
      this.damage(Math.round(source.maxhp / 2), source, source, this.dex.conditions.get("Steel Beam"));
    }

// move:powerswap.onHit
onHit(target, source) {
      const targetBoosts = {};
      const sourceBoosts = {};
      const atkSpa = ["atk", "spa"];
      for (const stat of atkSpa) {
        targetBoosts[stat] = target.boosts[stat];
        sourceBoosts[stat] = source.boosts[stat];
      }
      source.setBoost(targetBoosts);
      target.setBoost(sourceBoosts);
      this.add("-swapboost", source, target, "atk, spa", "[from] move: Power Swap");
    }

// move:switcheroo.onTryImmunity
onTryImmunity(target) {
      return !target.hasAbility("stickyhold");
    }

// move:switcheroo.onHit
onHit(target, source, move) {
      const yourItem = target.takeItem(source);
      const myItem = source.takeItem();
      if (yourItem === false || myItem === false || !yourItem && !myItem) {
        if (yourItem) target.item = yourItem.id;
        if (myItem) source.item = myItem.id;
        return false;
      }
      if (myItem && !this.singleEvent("TakeItem", myItem, source.itemState, target, source, move, myItem) || yourItem && !this.singleEvent("TakeItem", yourItem, target.itemState, source, target, move, yourItem)) {
        if (yourItem) target.item = yourItem.id;
        if (myItem) source.item = myItem.id;
        return false;
      }
      this.add("-activate", source, "move: Trick", `[of] ${target}`);
      if (myItem) {
        target.setItem(myItem);
        this.add("-item", target, myItem, "[from] move: Switcheroo");
      } else {
        this.add("-enditem", target, yourItem, "[silent]", "[from] move: Switcheroo");
      }
      if (yourItem) {
        source.setItem(yourItem);
        this.add("-item", source, yourItem, "[from] move: Switcheroo");
      } else {
        this.add("-enditem", source, myItem, "[silent]", "[from] move: Switcheroo");
      }
    }

// move:hardpress.basePowerCallback
basePowerCallback(pokemon, target) {
      const hp = target.hp;
      const maxHP = target.maxhp;
      const bp = Math.floor(Math.floor((100 * (100 * Math.floor(hp * 4096 / maxHP)) + 2048 - 1) / 4096) / 100) || 1;
      this.debug(`BP for ${hp}/${maxHP} HP: ${bp}`);
      return bp;
    }

// move:struggle.onModifyMove
onModifyMove(move, pokemon, target) {
      move.type = "???";
      this.add("-activate", pokemon, "move: Struggle");
    }

// item:focussash.onDamage
onDamage(damage, target, source, effect) {
      if (target.hp === target.maxhp && damage >= target.hp && effect && effect.effectType === "Move") {
        if (target.useItem()) {
          return target.hp - 1;
        }
      }
    }

// item:sitrusberry.onUpdate
onUpdate(pokemon) {
      if (pokemon.hp <= pokemon.maxhp / 2) {
        pokemon.eatItem();
      }
    }

// item:sitrusberry.onTryEatItem
onTryEatItem(item, pokemon) {
      if (!this.runEvent("TryHeal", pokemon, null, this.effect, pokemon.baseMaxhp / 4)) return false;
    }

// item:sitrusberry.onEat
onEat(pokemon) {
      this.heal(pokemon.baseMaxhp / 4);
    }

// item:lifeorb.onModifyDamage
onModifyDamage(damage, source, target, move) {
      return this.chainModify([5324, 4096]);
    }

// item:lifeorb.onAfterMoveSecondarySelf
onAfterMoveSecondarySelf(source, target, move) {
      if (source && source !== target && move && move.category !== "Status" && !source.forceSwitchFlag) {
        this.damage(source.baseMaxhp / 10, source, source, this.dex.items.get("lifeorb"));
      }
    }

// item:miracleseed.onBasePower
onBasePower(basePower, user, target, move) {
      if (move.type === "Grass") {
        return this.chainModify([4915, 4096]);
      }
    }

// item:leftovers.onResidual
onResidual(pokemon) {
      this.heal(pokemon.baseMaxhp / 16);
    }

// item:salamencite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:choicescarf.onStart
onStart(pokemon) {
      if (pokemon.volatiles["choicelock"]) {
        this.debug("removing choicelock");
      }
      pokemon.removeVolatile("choicelock");
    }

// item:choicescarf.onModifyMove
onModifyMove(move, pokemon) {
      pokemon.addVolatile("choicelock");
    }

// item:choicescarf.onModifySpe
onModifySpe(spe, pokemon) {
      if (pokemon.volatiles["dynamax"]) return;
      return this.chainModify(1.5);
    }

// item:grassyseed.onStart
onStart(pokemon) {
      if (!pokemon.ignoringItem() && this.field.isTerrain("grassyterrain")) {
        pokemon.useItem();
      }
    }

// item:grassyseed.onTerrainChange
onTerrainChange(pokemon) {
      if (this.field.isTerrain("grassyterrain")) {
        pokemon.useItem();
      }
    }

// item:raichunitey.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:psychicseed.onStart
onStart(pokemon) {
      if (!pokemon.ignoringItem() && this.field.isTerrain("psychicterrain")) {
        pokemon.useItem();
      }
    }

// item:psychicseed.onTerrainChange
onTerrainChange(pokemon) {
      if (this.field.isTerrain("psychicterrain")) {
        pokemon.useItem();
      }
    }

// item:whiteherb.onStart
onStart(pokemon) {
      this.effectState.boosts = {};
      let ready = false;
      let i;
      for (i in pokemon.boosts) {
        if (pokemon.boosts[i] < 0) {
          ready = true;
          this.effectState.boosts[i] = 0;
        }
      }
      if (ready) this.effectState.target.useItem();
      delete this.effectState.boosts;
    }

// item:whiteherb.onAnySwitchIn
onAnySwitchIn() {
      this.effect.onStart.call(this, this.effectState.target);
    }

// item:whiteherb.onAnyAfterMega
onAnyAfterMega() {
      this.effect.onStart.call(this, this.effectState.target);
    }

// item:whiteherb.onAnyAfterMove
onAnyAfterMove() {
      this.effect.onStart.call(this, this.effectState.target);
    }

// item:whiteherb.onResidual
onResidual(pokemon) {
      this.effect.onStart.call(this, pokemon);
    }

// item:whiteherb.onUse
onUse(pokemon) {
      pokemon.setBoost(this.effectState.boosts);
      this.add("-clearnegativeboost", pokemon, "[silent]");
    }

// item:chopleberry.onSourceModifyDamage
onSourceModifyDamage(damage, source, target, move) {
      if (move.type === "Fighting" && target.getMoveHitData(move).typeMod > 0) {
        const hitSub = target.volatiles["substitute"] && !move.flags["bypasssub"] && !(move.infiltrates && this.gen >= 6);
        if (hitSub) return;
        if (target.eatItem()) {
          this.debug("-50% reduction");
          this.add("-enditem", target, this.effect, "[weaken]");
          return this.chainModify(0.5);
        }
      }
    }

// item:chopleberry.onEat
onEat() {
    }

// item:rockyhelmet.onDamagingHit
onDamagingHit(damage, target, source, move) {
      if (this.checkMoveMakesContact(move, source, target)) {
        this.damage(source.baseMaxhp / 6, source, target);
      }
    }

// item:floettite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone || !item.megaStone[source.baseSpecies.name] && !Object.values(item.megaStone).includes(source.baseSpecies.name);
    }

// item:golisopite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:charizarditey.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:fairyfeather.onBasePower
onBasePower(basePower, user, target, move) {
      if (move && move.type === "Fairy") {
        return this.chainModify([4915, 4096]);
      }
    }

// item:colburberry.onSourceModifyDamage
onSourceModifyDamage(damage, source, target, move) {
      if (move.type === "Dark" && target.getMoveHitData(move).typeMod > 0) {
        const hitSub = target.volatiles["substitute"] && !move.flags["bypasssub"] && !(move.infiltrates && this.gen >= 6);
        if (hitSub) return;
        if (target.eatItem()) {
          this.debug("-50% reduction");
          this.add("-enditem", target, this.effect, "[weaken]");
          return this.chainModify(0.5);
        }
      }
    }

// item:colburberry.onEat
onEat() {
    }

// item:garchompitez.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:staraptite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:gardevoirite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:tyranitarite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:gengarite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:froslassite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:metagrossite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:mysticwater.onBasePower
onBasePower(basePower, user, target, move) {
      if (move.type === "Water") {
        return this.chainModify([4915, 4096]);
      }
    }

// item:blackglasses.onBasePower
onBasePower(basePower, user, target, move) {
      if (move && move.type === "Dark") {
        return this.chainModify([4915, 4096]);
      }
    }

// item:delphoxite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:occaberry.onSourceModifyDamage
onSourceModifyDamage(damage, source, target, move) {
      if (move.type === "Fire" && target.getMoveHitData(move).typeMod > 0) {
        const hitSub = target.volatiles["substitute"] && !move.flags["bypasssub"] && !(move.infiltrates && this.gen >= 6);
        if (hitSub) return;
        if (target.eatItem()) {
          this.debug("-50% reduction");
          this.add("-enditem", target, this.effect, "[weaken]");
          return this.chainModify(0.5);
        }
      }
    }

// item:occaberry.onEat
onEat() {
    }

// item:charcoal.onBasePower
onBasePower(basePower, user, target, move) {
      if (move && move.type === "Fire") {
        return this.chainModify([4915, 4096]);
      }
    }

// item:lucarionitez.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:passhoberry.onSourceModifyDamage
onSourceModifyDamage(damage, source, target, move) {
      if (move.type === "Water" && target.getMoveHitData(move).typeMod > 0) {
        const hitSub = target.volatiles["substitute"] && !move.flags["bypasssub"] && !(move.infiltrates && this.gen >= 6);
        if (hitSub) return;
        if (target.eatItem()) {
          this.debug("-50% reduction");
          this.add("-enditem", target, this.effect, "[weaken]");
          return this.chainModify(0.5);
        }
      }
    }

// item:passhoberry.onEat
onEat() {
    }

// item:swampertite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:dragoninite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:ejectbutton.onAfterMoveSecondary
onAfterMoveSecondary(target, source, move) {
      if (source && source !== target && target.hp && move && move.category !== "Status" && !move.flags["futuremove"]) {
        if (!this.canSwitch(target.side) || target.forceSwitchFlag || target.beingCalledBack || target.isSkyDropped()) return;
        if (target.volatiles["commanding"] || target.volatiles["commanded"]) return;
        for (const pokemon of this.getAllActive()) {
          if (pokemon.switchFlag === true) return;
        }
        target.switchFlag = true;
        if (!target.useItem()) {
          target.switchFlag = false;
        }
      }
    }

// item:baxcalibrite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:glimmoranite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:aerodactylite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:cameruptite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:blastoisinite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:absolitez.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:blazikenite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:widelens.onSourceModifyAccuracy
onSourceModifyAccuracy(accuracy) {
      if (typeof accuracy === "number") {
        return this.chainModify([4505, 4096]);
      }
    }

// item:mawilite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:cobaberry.onSourceModifyDamage
onSourceModifyDamage(damage, source, target, move) {
      if (move.type === "Flying" && target.getMoveHitData(move).typeMod > 0) {
        const hitSub = target.volatiles["substitute"] && !move.flags["bypasssub"] && !(move.infiltrates && this.gen >= 6);
        if (hitSub) return;
        if (target.eatItem()) {
          this.debug("-50% reduction");
          this.add("-enditem", target, this.effect, "[weaken]");
          return this.chainModify(0.5);
        }
      }
    }

// item:cobaberry.onEat
onEat() {
    }

// item:scovillainite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:kasibberry.onSourceModifyDamage
onSourceModifyDamage(damage, source, target, move) {
      if (move.type === "Ghost" && target.getMoveHitData(move).typeMod > 0) {
        const hitSub = target.volatiles["substitute"] && !move.flags["bypasssub"] && !(move.infiltrates && this.gen >= 6);
        if (hitSub) return;
        if (target.eatItem()) {
          this.debug("-50% reduction");
          this.add("-enditem", target, this.effect, "[weaken]");
          return this.chainModify(0.5);
        }
      }
    }

// item:kasibberry.onEat
onEat() {
    }

// item:sharpbeak.onBasePower
onBasePower(basePower, user, target, move) {
      if (move && move.type === "Flying") {
        return this.chainModify([4915, 4096]);
      }
    }

// item:raichunitex.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:lopunnite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:pyroarite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:twistedspoon.onBasePower
onBasePower(basePower, user, target, move) {
      if (move.type === "Psychic") {
        return this.chainModify([4915, 4096]);
      }
    }

// item:expertbelt.onModifyDamage
onModifyDamage(damage, source, target, move) {
      if (move && target.getMoveHitData(move).typeMod > 0) {
        return this.chainModify([4915, 4096]);
      }
    }

// item:alakazite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:nevermeltice.onBasePower
onBasePower(basePower, user, target, move) {
      if (move.type === "Ice") {
        return this.chainModify([4915, 4096]);
      }
    }

// item:meganiumite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:meowsticite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone || !item.megaStone[source.baseSpecies.name] && !Object.values(item.megaStone).includes(source.baseSpecies.name);
    }

// item:roseliberry.onSourceModifyDamage
onSourceModifyDamage(damage, source, target, move) {
      if (move.type === "Fairy" && target.getMoveHitData(move).typeMod > 0) {
        const hitSub = target.volatiles["substitute"] && !move.flags["bypasssub"] && !(move.infiltrates && this.gen >= 6);
        if (hitSub) return;
        if (target.eatItem()) {
          this.debug("-50% reduction");
          this.add("-enditem", target, this.effect, "[weaken]");
          return this.chainModify(0.5);
        }
      }
    }

// item:roseliberry.onEat
onEat() {
    }

// item:garchompite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:venusaurite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:habanberry.onSourceModifyDamage
onSourceModifyDamage(damage, source, target, move) {
      if (move.type === "Dragon" && target.getMoveHitData(move).typeMod > 0) {
        const hitSub = target.volatiles["substitute"] && !move.flags["bypasssub"] && !(move.infiltrates && this.gen >= 6);
        if (hitSub) return;
        if (target.eatItem()) {
          this.debug("-50% reduction");
          this.add("-enditem", target, this.effect, "[weaken]");
          return this.chainModify(0.5);
        }
      }
    }

// item:habanberry.onEat
onEat() {
    }

// item:leek.onModifyCritRatio
onModifyCritRatio(critRatio, user) {
      if (["farfetchd", "sirfetchd"].includes(this.toID(user.baseSpecies.baseSpecies))) {
        return critRatio + 2;
      }
    }

// item:scraftinite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:mentalherb.onUpdate
onUpdate(pokemon) {
      const conditions = ["attract", "taunt", "encore", "torment", "disable", "healblock"];
      for (const firstCondition of conditions) {
        if (pokemon.volatiles[firstCondition]) {
          if (!pokemon.useItem()) return;
          for (const secondCondition of conditions) {
            pokemon.removeVolatile(secondCondition);
            if (firstCondition === "attract" && secondCondition === "attract") {
              this.add("-end", pokemon, "move: Attract", "[from] item: Mental Herb");
            }
          }
          return;
        }
      }
    }

// item:kangaskhanite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:charizarditex.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:crabominite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:starminite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:scopelens.onModifyCritRatio
onModifyCritRatio(critRatio) {
      return critRatio + 1;
    }

// item:gyaradosite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:sceptilite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:magnet.onBasePower
onBasePower(basePower, user, target, move) {
      if (move.type === "Electric") {
        return this.chainModify([4915, 4096]);
      }
    }

// item:blackbelt.onBasePower
onBasePower(basePower, user, target, move) {
      if (move && move.type === "Fighting") {
        return this.chainModify([4915, 4096]);
      }
    }

// item:lucarionite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:electricseed.onStart
onStart(pokemon) {
      if (!pokemon.ignoringItem() && this.field.isTerrain("electricterrain")) {
        pokemon.useItem();
      }
    }

// item:electricseed.onTerrainChange
onTerrainChange(pokemon) {
      if (this.field.isTerrain("electricterrain")) {
        pokemon.useItem();
      }
    }

// item:manectite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:aggronite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:dragalgite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:scizorite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:steelixite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:kebiaberry.onSourceModifyDamage
onSourceModifyDamage(damage, source, target, move) {
      if (move.type === "Poison" && target.getMoveHitData(move).typeMod > 0) {
        const hitSub = target.volatiles["substitute"] && !move.flags["bypasssub"] && !(move.infiltrates && this.gen >= 6);
        if (hitSub) return;
        if (target.eatItem()) {
          this.debug("-50% reduction");
          this.add("-enditem", target, this.effect, "[weaken]");
          return this.chainModify(0.5);
        }
      }
    }

// item:kebiaberry.onEat
onEat() {
    }

// item:lumberry.onAfterSetStatus
onAfterSetStatus(status, pokemon) {
      pokemon.eatItem();
    }

// item:lumberry.onUpdate
onUpdate(pokemon) {
      if (pokemon.status || pokemon.volatiles["confusion"]) {
        pokemon.eatItem();
      }
    }

// item:lumberry.onEat
onEat(pokemon) {
      pokemon.cureStatus();
      pokemon.removeVolatile("confusion");
    }

// item:dragonfang.onBasePower
onBasePower(basePower, user, target, move) {
      if (move && move.type === "Dragon") {
        return this.chainModify([4915, 4096]);
      }
    }

// item:brightpowder.onModifyAccuracy
onModifyAccuracy(accuracy) {
      if (typeof accuracy !== "number") return;
      this.debug("brightpowder - decreasing accuracy");
      return this.chainModify([3686, 4096]);
    }

// item:pidgeotite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:spelltag.onBasePower
onBasePower(basePower, user, target, move) {
      if (move.type === "Ghost") {
        return this.chainModify([4915, 4096]);
      }
    }

// item:silkscarf.onBasePower
onBasePower(basePower, user, target, move) {
      if (move.type === "Normal") {
        return this.chainModify([4915, 4096]);
      }
    }

// item:tangaberry.onSourceModifyDamage
onSourceModifyDamage(damage, source, target, move) {
      if (move.type === "Bug" && target.getMoveHitData(move).typeMod > 0) {
        const hitSub = target.volatiles["substitute"] && !move.flags["bypasssub"] && !(move.infiltrates && this.gen >= 6);
        if (hitSub) return;
        if (target.eatItem()) {
          this.debug("-50% reduction");
          this.add("-enditem", target, this.effect, "[weaken]");
          return this.chainModify(0.5);
        }
      }
    }

// item:tangaberry.onEat
onEat() {
    }

// item:kingsrock.onModifyMove
onModifyMove(move) {
      if (move.category !== "Status") {
        if (!move.secondaries) move.secondaries = [];
        for (const secondary of move.secondaries) {
          if (secondary.volatileStatus === "flinch") return;
        }
        move.secondaries.push({
          chance: 10,
          volatileStatus: "flinch"
        });
      }
    }

// item:babiriberry.onSourceModifyDamage
onSourceModifyDamage(damage, source, target, move) {
      if (move.type === "Steel" && target.getMoveHitData(move).typeMod > 0) {
        const hitSub = target.volatiles["substitute"] && !move.flags["bypasssub"] && !(move.infiltrates && this.gen >= 6);
        if (hitSub) return;
        if (target.eatItem()) {
          this.debug("-50% reduction");
          this.add("-enditem", target, this.effect, "[weaken]");
          return this.chainModify(0.5);
        }
      }
    }

// item:babiriberry.onEat
onEat() {
    }

// item:normalgem.onSourceTryPrimaryHit
onSourceTryPrimaryHit(target, source, move) {
      if (target === source || move.category === "Status" || move.flags["pledgecombo"]) return;
      if (move.type === "Normal" && source.useItem()) {
        source.addVolatile("gem");
      }
    }

// item:houndoominite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:chartiberry.onSourceModifyDamage
onSourceModifyDamage(damage, source, target, move) {
      if (move.type === "Rock" && target.getMoveHitData(move).typeMod > 0) {
        const hitSub = target.volatiles["substitute"] && !move.flags["bypasssub"] && !(move.infiltrates && this.gen >= 6);
        if (hitSub) return;
        if (target.eatItem()) {
          this.debug("-50% reduction");
          this.add("-enditem", target, this.effect, "[weaken]");
          return this.chainModify(0.5);
        }
      }
    }

// item:chartiberry.onEat
onEat() {
    }

// item:softsand.onBasePower
onBasePower(basePower, user, target, move) {
      if (move.type === "Ground") {
        return this.chainModify([4915, 4096]);
      }
    }

// item:altarianite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:excadrite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:absolite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:sablenite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:galladite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:clefablite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:drampanite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:chandelurite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:greninjite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:malamarite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:hawluchanite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:chesnaughtite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:slowbronite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:feraligite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:abomasite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:golurkite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:banettite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:skarmorite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:ampharosite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// item:heracronite.onTakeItem
onTakeItem(item, source) {
      return !item.megaStone?.[source.baseSpecies.baseSpecies];
    }

// ability:grassysurge.onStart
onStart(source) {
      this.field.setTerrain("grassyterrain");
    }

// ability:intimidate.onStart
onStart(pokemon) {
      let activated = false;
      for (const target of pokemon.adjacentFoes()) {
        if (!activated) {
          this.add("-ability", pokemon, "Intimidate", "boost");
          activated = true;
        }
        if (target.volatiles["substitute"]) {
          this.add("-immune", target);
        } else {
          this.boost({ atk: -1 }, target, pokemon, null, true);
        }
      }
    }

// ability:unburden.onAfterUseItem
onAfterUseItem(item, pokemon) {
      if (pokemon !== this.effectState.target) return;
      pokemon.addVolatile("unburden");
    }

// ability:unburden.onTakeItem
onTakeItem(item, pokemon) {
      pokemon.addVolatile("unburden");
    }

// ability:unburden.onEnd
onEnd(pokemon) {
      pokemon.removeVolatile("unburden");
    }

// ability:defiant.onAfterEachBoost
onAfterEachBoost(boost, target, source, effect) {
      if (!source || target.isAlly(source)) {
        return;
      }
      let statsLowered = false;
      let i;
      for (i in boost) {
        if (boost[i] < 0) {
          statsLowered = true;
        }
      }
      if (statsLowered) {
        this.boost({ atk: 2 }, target, target, null, false, true);
      }
    }

// ability:aerilate.onModifyType
onModifyType(move, pokemon) {
      const noModifyType = [
        "judgment",
        "multiattack",
        "naturalgift",
        "revelationdance",
        "technoblast",
        "terrainpulse",
        "weatherball"
      ];
      if (move.type === "Normal" && (!noModifyType.includes(move.id) || this.activeMove?.isMax) && !(move.isZ && move.category !== "Status") && !(move.name === "Tera Blast" && pokemon.terastallized)) {
        move.type = "Flying";
        move.typeChangerBoosted = this.effect;
      }
    }

// ability:aerilate.onBasePower
onBasePower(basePower, pokemon, target, move) {
      if (move.typeChangerBoosted === this.effect) return this.chainModify([4915, 4096]);
    }

// ability:psychicsurge.onStart
onStart(source) {
      this.field.setTerrain("psychicterrain");
    }

// ability:goodasgold.onTryHit
onTryHit(target, source, move) {
      if (move.category === "Status" && target !== source) {
        this.add("-immune", target, "[from] ability: Good as Gold");
        return null;
      }
    }

// ability:toughclaws.onBasePower
onBasePower(basePower, attacker, defender, move) {
      if (move.flags["contact"]) {
        return this.chainModify([5325, 4096]);
      }
    }

// ability:adaptability.onModifySTAB
onModifySTAB(stab, source, target, move) {
      if (move.forceSTAB || source.hasType(move.type)) {
        if (stab === 2) {
          return 2.25;
        }
        return 2;
      }
    }

// ability:pixilate.onModifyType
onModifyType(move, pokemon) {
      const noModifyType = [
        "judgment",
        "multiattack",
        "naturalgift",
        "revelationdance",
        "technoblast",
        "terrainpulse",
        "weatherball"
      ];
      if (move.type === "Normal" && (!noModifyType.includes(move.id) || this.activeMove?.isMax) && !(move.isZ && move.category !== "Status") && !(move.name === "Tera Blast" && pokemon.terastallized)) {
        move.type = "Fairy";
        move.typeChangerBoosted = this.effect;
      }
    }

// ability:pixilate.onBasePower
onBasePower(basePower, pokemon, target, move) {
      if (move.typeChangerBoosted === this.effect) return this.chainModify([4915, 4096]);
    }

// ability:noguard.onAnyInvulnerability
onAnyInvulnerability(target, source, move) {
      if (move && (source === this.effectState.target || target === this.effectState.target)) return 0;
    }

// ability:noguard.onAnyAccuracy
onAnyAccuracy(accuracy, target, source, move) {
      if (move && (source === this.effectState.target || target === this.effectState.target)) {
        return true;
      }
      return accuracy;
    }

// ability:drizzle.onStart
onStart(source) {
      if (source.species.id === "kyogre" && source.item === "blueorb") return;
      this.field.setWeather("raindance");
    }

// ability:drought.onStart
onStart(source) {
      if (source.species.id === "groudon" && source.item === "redorb") return;
      this.field.setWeather("sunnyday");
    }

// ability:armortail.onFoeTryMove
onFoeTryMove(target, source, move) {
      const targetAllExceptions = ["perishsong", "flowershield", "rototiller"];
      if (move.target === "foeSide" || move.target === "all" && !targetAllExceptions.includes(move.id)) {
        return;
      }
      const armorTailHolder = this.effectState.target;
      if ((source.isAlly(armorTailHolder) || move.target === "all") && move.priority > 0.1) {
        this.attrLastMove("[still]");
        this.add("cant", armorTailHolder, "ability: Armor Tail", move, `[of] ${target}`);
        return false;
      }
    }

// ability:prankster.onModifyPriority
onModifyPriority(priority, pokemon, target, move) {
      if (move?.category === "Status") {
        move.pranksterBoosted = true;
        return priority + 1;
      }
    }

// ability:rockhead.onDamage
onDamage(damage, target, source, effect) {
      if (effect.id === "recoil") {
        if (!this.activeMove) throw new Error("Battle.activeMove is null");
        if (this.activeMove.id !== "struggle") return null;
      }
    }

// ability:fairyaura.onStart
onStart(pokemon) {
      if (this.suppressingAbility(pokemon)) return;
      this.add("-ability", pokemon, "Fairy Aura");
    }

// ability:fairyaura.onAnyBasePower
onAnyBasePower(basePower, source, target, move) {
      if (target === source || move.category === "Status" || move.type !== "Fairy") return;
      if (!move.auraBooster?.hasAbility("Fairy Aura")) move.auraBooster = this.effectState.target;
      if (move.auraBooster !== this.effectState.target) return;
      return this.chainModify([move.hasAuraBreak ? 3072 : 5448, 4096]);
    }

// ability:competitive.onAfterEachBoost
onAfterEachBoost(boost, target, source, effect) {
      if (!source || target.isAlly(source)) {
        return;
      }
      let statsLowered = false;
      let i;
      for (i in boost) {
        if (boost[i] < 0) {
          statsLowered = true;
        }
      }
      if (statsLowered) {
        this.boost({ spa: 2 }, target, target, null, false, true);
      }
    }

// ability:stamina.onDamagingHit
onDamagingHit(damage, target, source, effect) {
      this.boost({ def: 1 });
    }

// ability:flamebody.onDamagingHit
onDamagingHit(damage, target, source, move) {
      if (this.checkMoveMakesContact(move, source, target)) {
        if (this.randomChance(3, 10)) {
          source.trySetStatus("brn", target);
        }
      }
    }

// ability:snowwarning.onStart
onStart(source) {
      this.field.setWeather("snowscape");
    }

// ability:contrary.onChangeBoost
onChangeBoost(boost, target, source, effect) {
      if (effect && effect.id === "zpower") return;
      let i;
      for (i in boost) {
        boost[i] *= -1;
      }
    }

// ability:roughskin.onDamagingHit
onDamagingHit(damage, target, source, move) {
      if (this.checkMoveMakesContact(move, source, target, true)) {
        this.damage(source.baseMaxhp / 8, source, target);
      }
    }

// ability:sandstream.onStart
onStart(source) {
      this.field.setWeather("sandstorm");
    }

// ability:hospitality.onStart
onStart(pokemon) {
      for (const ally of pokemon.adjacentAllies()) {
        this.heal(ally.baseMaxhp / 4, ally, pokemon);
      }
    }

// ability:flashfire.onTryHit
onTryHit(target, source, move) {
      if (target !== source && move.type === "Fire") {
        move.accuracy = true;
        if (!target.addVolatile("flashfire")) {
          this.add("-immune", target, "[from] ability: Flash Fire");
        }
        return null;
      }
    }

// ability:flashfire.onEnd
onEnd(pokemon) {
      pokemon.removeVolatile("flashfire");
    }

// ability:shadowtag.onFoeTrapPokemon
onFoeTrapPokemon(pokemon) {
      if (!pokemon.hasAbility("shadowtag") && pokemon.isAdjacent(this.effectState.target)) {
        pokemon.tryTrap(true);
      }
    }

// ability:shadowtag.onFoeMaybeTrapPokemon
onFoeMaybeTrapPokemon(pokemon, source) {
      if (!source) source = this.effectState.target;
      if (!source || !pokemon.isAdjacent(source)) return;
      if (!pokemon.hasAbility("shadowtag")) {
        pokemon.maybeTrapped = true;
      }
    }

// ability:sandrush.onModifySpe
onModifySpe(spe, pokemon) {
      if (this.field.isWeather("sandstorm")) {
        return this.chainModify(2);
      }
    }

// ability:sandrush.onImmunity
onImmunity(type, pokemon) {
      if (type === "sandstorm") return false;
    }

// ability:swiftswim.onModifySpe
onModifySpe(spe, pokemon) {
      if (["raindance", "primordialsea"].includes(pokemon.effectiveWeather())) {
        return this.chainModify(2);
      }
    }

// ability:poisontouch.onSourceDamagingHit
onSourceDamagingHit(damage, target, source, move) {
      if (target.hasAbility("shielddust") || target.hasItem("covertcloak")) return;
      if (this.checkMoveMakesContact(move, target, source)) {
        if (this.randomChance(3, 10)) {
          target.trySetStatus("psn", source);
        }
      }
    }

// ability:soundproof.onTryHit
onTryHit(target, source, move) {
      if (target !== source && move.flags["sound"]) {
        this.add("-immune", target, "[from] ability: Soundproof");
        return null;
      }
    }

// ability:soundproof.onAllyTryHitSide
onAllyTryHitSide(target, source, move) {
      if (move.flags["sound"]) {
        this.add("-immune", this.effectState.target, "[from] ability: Soundproof");
      }
    }

// ability:multiscale.onSourceModifyDamage
onSourceModifyDamage(damage, source, target, move) {
      if (target.hp >= target.maxhp) {
        this.debug("Multiscale weaken");
        return this.chainModify(0.5);
      }
    }

// ability:thermalexchange.onDamagingHit
onDamagingHit(damage, target, source, move) {
      if (move.type === "Fire") {
        this.boost({ atk: 1 });
      }
    }

// ability:thermalexchange.onUpdate
onUpdate(pokemon) {
      if (pokemon.status === "brn") {
        this.add("-activate", pokemon, "ability: Thermal Exchange");
        pokemon.cureStatus();
      }
    }

// ability:thermalexchange.onSetStatus
onSetStatus(status, target, source, effect) {
      if (status.id !== "brn") return;
      if (effect?.status) {
        this.add("-immune", target, "[from] ability: Thermal Exchange");
      }
      return false;
    }

// ability:liquidvoice.onModifyType
onModifyType(move, pokemon) {
      if (move.flags["sound"] && !pokemon.volatiles["dynamax"]) {
        move.type = "Water";
      }
    }

// ability:chlorophyll.onModifySpe
onModifySpe(spe, pokemon) {
      if (["sunnyday", "desolateland"].includes(pokemon.effectiveWeather())) {
        return this.chainModify(2);
      }
    }

// ability:sharpness.onBasePower
onBasePower(basePower, attacker, defender, move) {
      if (move.flags["slicing"]) {
        this.debug("Sharpness boost");
        return this.chainModify(1.5);
      }
    }

// ability:magicbounce.onTryHit
onTryHit(target, source, move) {
      if (target === source || move.hasBounced || !move.flags["reflectable"] || target.isSemiInvulnerable()) {
        return;
      }
      const newMove = this.dex.getActiveMove(move.id);
      newMove.hasBounced = true;
      newMove.pranksterBoosted = false;
      this.actions.useMove(newMove, target, { target: source });
      return null;
    }

// ability:magicbounce.onAllyTryHitSide
onAllyTryHitSide(target, source, move) {
      if (target.isAlly(source) || move.hasBounced || !move.flags["reflectable"] || target.isSemiInvulnerable()) {
        return;
      }
      const newMove = this.dex.getActiveMove(move.id);
      newMove.hasBounced = true;
      newMove.pranksterBoosted = false;
      this.actions.useMove(newMove, this.effectState.target, { target: source });
      move.hasBounced = true;
      return null;
    }

// ability:mirrorarmor.onTryBoost
onTryBoost(boost, target, source, effect) {
      if (!source || target === source || !boost || effect.name === "Mirror Armor") return;
      let b;
      for (b in boost) {
        if (boost[b] < 0) {
          if (target.boosts[b] === -6) continue;
          const negativeBoost = {};
          negativeBoost[b] = boost[b];
          delete boost[b];
          if (source.hp) {
            this.add("-ability", target, "Mirror Armor");
            this.boost(negativeBoost, source, target, null, true);
          }
        }
      }
    }

// ability:ironfist.onBasePower
onBasePower(basePower, attacker, defender, move) {
      if (move.flags["punch"]) {
        this.debug("Iron Fist boost");
        return this.chainModify([4915, 4096]);
      }
    }

// ability:speedboost.onResidual
onResidual(pokemon) {
      if (pokemon.activeTurns) {
        this.boost({ spe: 1 });
      }
    }

// ability:sheerforce.onModifyMove
onModifyMove(move, pokemon) {
      if (move.secondaries && !move.hasSheerForceBoost) {
        delete move.secondaries;
        delete move.self;
        if (move.id === "clangoroussoulblaze") delete move.selfBoost;
        move.hasSheerForce = true;
      }
    }

// ability:sheerforce.onBasePower
onBasePower(basePower, pokemon, target, move) {
      if (move.hasSheerForce || move.hasSheerForceBoost) return this.chainModify([5325, 4096]);
    }

// ability:megalauncher.onBasePower
onBasePower(basePower, attacker, defender, move) {
      if (move.flags["pulse"]) {
        return this.chainModify(1.5);
      }
    }

// ability:friendguard.onAnyModifyDamage
onAnyModifyDamage(damage, source, target, move) {
      if (target !== this.effectState.target && target.isAlly(this.effectState.target)) {
        this.debug("Friend Guard weaken");
        return this.chainModify(0.75);
      }
    }

// ability:galewings.onModifyPriority
onModifyPriority(priority, pokemon, target, move) {
      if (move?.type === "Flying" && pokemon.hp === pokemon.maxhp) return priority + 1;
    }

// ability:regenerator.onSwitchOut
onSwitchOut(pokemon) {
      if (pokemon.heal(pokemon.baseMaxhp / 3)) {
        this.add("-heal", pokemon, pokemon.getHealth, "[from] ability: Regenerator", "[silent]");
      }
    }

// ability:scrappy.onModifyMove
onModifyMove(move) {
      if (!move.ignoreImmunity) move.ignoreImmunity = {};
      if (move.ignoreImmunity !== true) {
        move.ignoreImmunity["Fighting"] = true;
        move.ignoreImmunity["Normal"] = true;
      }
    }

// ability:scrappy.onTryBoost
onTryBoost(boost, target, source, effect) {
      if (effect.name === "Intimidate" && boost.atk) {
        delete boost.atk;
        this.add("-fail", target, "unboost", "Attack", "[from] ability: Scrappy", `[of] ${target}`);
      }
    }

// ability:hugepower.onModifyAtk
onModifyAtk(atk) {
      return this.chainModify(2);
    }

// ability:infiltrator.onModifyMove
onModifyMove(move) {
      move.infiltrates = true;
    }

// ability:technician.onBasePower
onBasePower(basePower, attacker, defender, move) {
      const basePowerAfterMultiplier = this.modify(basePower, this.event.modifier);
      this.debug(`Base Power: ${basePowerAfterMultiplier}`);
      if (basePowerAfterMultiplier <= 60) {
        this.debug("Technician boost");
        return this.chainModify(1.5);
      }
    }

// ability:innerfocus.onTryAddVolatile
onTryAddVolatile(status, pokemon) {
      if (status.id === "flinch") return null;
    }

// ability:innerfocus.onTryBoost
onTryBoost(boost, target, source, effect) {
      if (effect.name === "Intimidate" && boost.atk) {
        delete boost.atk;
        this.add("-fail", target, "unboost", "Attack", "[from] ability: Inner Focus", `[of] ${target}`);
      }
    }

// ability:toxicdebris.onDamagingHit
onDamagingHit(damage, target, source, move) {
      const side = source.isAlly(target) ? source.side.foe : source.side;
      const toxicSpikes = side.sideConditions["toxicspikes"];
      if (move.category === "Physical" && (!toxicSpikes || toxicSpikes.layers < 2)) {
        this.add("-activate", target, "ability: Toxic Debris");
        side.addSideCondition("toxicspikes", target);
      }
    }

// ability:stancechange.onModifyMove
onModifyMove(move, attacker, defender) {
      if (attacker.species.baseSpecies !== "Aegislash" || attacker.transformed) return;
      if (move.category === "Status" && move.id !== "kingsshield") return;
      const targetForme = move.id === "kingsshield" ? "Aegislash" : "Aegislash-Blade";
      if (attacker.species.name !== targetForme) attacker.formeChange(targetForme);
    }

// ability:compoundeyes.onSourceModifyAccuracy
onSourceModifyAccuracy(accuracy) {
      if (typeof accuracy !== "number") return;
      this.debug("compoundeyes - enhancing accuracy");
      return this.chainModify([5325, 4096]);
    }

// ability:trace.onStart
onStart(pokemon) {
      this.effectState.seek = true;
      if (pokemon.adjacentFoes().some((foeActive) => foeActive.ability === "noability")) {
        this.effectState.seek = false;
      }
      if (pokemon.hasItem("Ability Shield")) {
        this.add("-block", pokemon, "item: Ability Shield");
        this.effectState.seek = false;
      }
      if (this.effectState.seek) {
        this.singleEvent("Update", this.effect, this.effectState, pokemon);
      }
    }

// ability:trace.onUpdate
onUpdate(pokemon) {
      if (!this.effectState.seek) return;
      const possibleTargets = pokemon.adjacentFoes().filter(
        (target2) => !target2.getAbility().flags["notrace"] && target2.ability !== "noability"
      );
      if (!possibleTargets.length) return;
      const target = this.sample(possibleTargets);
      const ability = target.getAbility();
      pokemon.setAbility(ability, target);
    }

// ability:electricsurge.onStart
onStart(source) {
      this.field.setTerrain("electricterrain");
    }

// ability:clearbody.onTryBoost
onTryBoost(boost, target, source, effect) {
      if (source && target === source) return;
      let showMsg = false;
      let i;
      for (i in boost) {
        if (boost[i] < 0) {
          delete boost[i];
          showMsg = true;
        }
      }
      if (showMsg && !effect.secondaries && effect.id !== "octolock") {
        this.add("-fail", target, "unboost", "[from] ability: Clear Body", `[of] ${target}`);
      }
    }

// ability:unnerve.onStart
onStart(pokemon) {
      if (this.effectState.unnerved) return;
      this.add("-ability", pokemon, "Unnerve");
      this.effectState.unnerved = true;
    }

// ability:unnerve.onEnd
onEnd() {
      this.effectState.unnerved = false;
    }

// ability:unnerve.onFoeTryEatItem
onFoeTryEatItem() {
      return !this.effectState.unnerved;
    }

// ability:spicyspray.onDamagingHit
onDamagingHit(damage, target, source, move) {
      if (!source.trySetStatus("brn", target) && !source.status && source.hasType("Fire")) {
        this.add("-immune", source);
      }
    }

// ability:blaze.onModifyAtk
onModifyAtk(atk, attacker, defender, move) {
      if (move.type === "Fire" && attacker.hp <= attacker.maxhp / 3) {
        this.debug("Blaze boost");
        return this.chainModify(1.5);
      }
    }

// ability:blaze.onModifySpA
onModifySpA(atk, attacker, defender, move) {
      if (move.type === "Fire" && attacker.hp <= attacker.maxhp / 3) {
        this.debug("Blaze boost");
        return this.chainModify(1.5);
      }
    }

// ability:thickfat.onSourceModifyAtk
onSourceModifyAtk(atk, attacker, defender, move) {
      if (move.type === "Ice" || move.type === "Fire") {
        this.debug("Thick Fat weaken");
        return this.chainModify(0.5);
      }
    }

// ability:thickfat.onSourceModifySpA
onSourceModifySpA(atk, attacker, defender, move) {
      if (move.type === "Ice" || move.type === "Fire") {
        this.debug("Thick Fat weaken");
        return this.chainModify(0.5);
      }
    }

// ability:moldbreaker.onStart
onStart(pokemon) {
      this.add("-ability", pokemon, "Mold Breaker");
    }

// ability:moldbreaker.onModifyMove
onModifyMove(move) {
      move.ignoreAbility = true;
    }

// ability:sandforce.onBasePower
onBasePower(basePower, attacker, defender, move) {
      if (this.field.isWeather("sandstorm")) {
        if (move.type === "Rock" || move.type === "Ground" || move.type === "Steel") {
          this.debug("Sand Force boost");
          return this.chainModify([5325, 4096]);
        }
      }
    }

// ability:sandforce.onImmunity
onImmunity(type, pokemon) {
      if (type === "sandstorm") return false;
    }

// ability:unaware.onAnyModifyBoost
onAnyModifyBoost(boosts, pokemon) {
      const unawareUser = this.effectState.target;
      if (unawareUser === pokemon) return;
      if (unawareUser === this.activePokemon && pokemon === this.activeTarget) {
        boosts["def"] = 0;
        boosts["spd"] = 0;
        boosts["evasion"] = 0;
      }
      if (pokemon === this.activePokemon && unawareUser === this.activeTarget) {
        boosts["atk"] = 0;
        boosts["def"] = 0;
        boosts["spa"] = 0;
        boosts["accuracy"] = 0;
      }
    }

// ability:firemane.onModifyAtk
onModifyAtk(atk, attacker, defender, move) {
      if (move.type === "Fire") {
        this.debug("Fire Mane boost");
        return this.chainModify(1.5);
      }
    }

// ability:firemane.onModifySpA
onModifySpA(atk, attacker, defender, move) {
      if (move.type === "Fire") {
        this.debug("Fire Mane boost");
        return this.chainModify(1.5);
      }
    }

// ability:oblivious.onUpdate
onUpdate(pokemon) {
      if (pokemon.volatiles["attract"]) {
        this.add("-activate", pokemon, "ability: Oblivious");
        pokemon.removeVolatile("attract");
        this.add("-end", pokemon, "move: Attract", "[from] ability: Oblivious");
      }
      if (pokemon.volatiles["taunt"]) {
        this.add("-activate", pokemon, "ability: Oblivious");
        pokemon.removeVolatile("taunt");
      }
    }

// ability:oblivious.onImmunity
onImmunity(type, pokemon) {
      if (type === "attract") return false;
    }

// ability:oblivious.onTryHit
onTryHit(pokemon, target, move) {
      if (move.id === "attract" || move.id === "captivate" || move.id === "taunt") {
        this.add("-immune", pokemon, "[from] ability: Oblivious");
        return null;
      }
    }

// ability:oblivious.onTryBoost
onTryBoost(boost, target, source, effect) {
      if (effect.name === "Intimidate" && boost.atk) {
        delete boost.atk;
        this.add("-fail", target, "unboost", "Attack", "[from] ability: Oblivious", `[of] ${target}`);
      }
    }

// ability:queenlymajesty.onFoeTryMove
onFoeTryMove(target, source, move) {
      const targetAllExceptions = ["perishsong", "flowershield", "rototiller"];
      if (move.target === "foeSide" || move.target === "all" && !targetAllExceptions.includes(move.id)) {
        return;
      }
      const dazzlingHolder = this.effectState.target;
      if ((source.isAlly(dazzlingHolder) || move.target === "all") && move.priority > 0.1) {
        this.attrLastMove("[still]");
        this.add("cant", dazzlingHolder, "ability: Queenly Majesty", move, `[of] ${target}`);
        return false;
      }
    }

// ability:protean.onPrepareHit
onPrepareHit(source, target, move) {
      if (this.effectState.protean) return;
      if (move.hasBounced || move.flags["futuremove"] || move.sourceEffect === "snatch" || move.callsMove) return;
      const type = move.type;
      if (type && type !== "???" && source.getTypes().join() !== type) {
        if (!source.setType(type)) return;
        this.effectState.protean = true;
        this.add("-start", source, "typechange", type, "[from] ability: Protean");
      }
    }

// ability:lightningrod.onTryHit
onTryHit(target, source, move) {
      if (target !== source && move.type === "Electric") {
        if (!this.boost({ spa: 1 })) {
          this.add("-immune", target, "[from] ability: Lightning Rod");
        }
        return null;
      }
    }

// ability:lightningrod.onAnyRedirectTarget
onAnyRedirectTarget(target, source, source2, move) {
      if (move.type !== "Electric" || move.flags["pledgecombo"]) return;
      const redirectTarget = ["randomNormal", "adjacentFoe"].includes(move.target) ? "normal" : move.target;
      if (this.validTarget(this.effectState.target, source, redirectTarget)) {
        if (move.smartTarget) move.smartTarget = false;
        if (this.effectState.target !== target) {
          this.add("-activate", this.effectState.target, "ability: Lightning Rod");
        }
        return this.effectState.target;
      }
    }

// ability:megasol.onWeatherModifyDamage
onWeatherModifyDamage(damage, attacker, defender, move) {
      this.dex.conditions.getByID("sunnyday").onWeatherModifyDamage.call(this, damage, attacker, defender, move);
      return damage;
    }

// ability:weakarmor.onDamagingHit
onDamagingHit(damage, target, source, move) {
      if (move.category === "Physical") {
        this.boost({ def: -1, spe: 2 }, target, target);
      }
    }

// ability:illusion.onBeforeSwitchIn
onBeforeSwitchIn(pokemon) {
      pokemon.illusion = null;
      for (let i = pokemon.side.pokemon.length - 1; i > pokemon.position; i--) {
        const possibleTarget = pokemon.side.pokemon[i];
        if (!possibleTarget.fainted) {
          if (!pokemon.terastallized || !["Ogerpon", "Terapagos"].includes(possibleTarget.species.baseSpecies)) {
            pokemon.illusion = possibleTarget;
          }
          break;
        }
      }
    }

// ability:illusion.onDamagingHit
onDamagingHit(damage, target, source, move) {
      if (target.illusion) {
        this.singleEvent("End", this.dex.abilities.get("Illusion"), target.abilityState, target, source, move);
      }
    }

// ability:illusion.onEnd
onEnd(pokemon) {
      if (pokemon.illusion && !pokemon.beingCalledBack) {
        this.debug("illusion cleared");
        pokemon.illusion = null;
        const details = pokemon.getUpdatedDetails();
        this.add("replace", pokemon, details);
        this.add("-end", pokemon, "Illusion");
        if (this.ruleTable.has("illusionlevelmod")) {
          this.hint("Illusion Level Mod is active, so this Pok\xE9mon's true level was hidden.", true);
        }
      }
    }

// ability:illusion.onFaint
onFaint(pokemon) {
      pokemon.illusion = null;
    }

// ability:pressure.onStart
onStart(pokemon) {
      this.add("-ability", pokemon, "Pressure");
    }

// ability:pressure.onDeductPP
onDeductPP(target, source) {
      if (target.isAlly(source)) return;
      return 1;
    }

// ability:punkrock.onBasePower
onBasePower(basePower, attacker, defender, move) {
      if (move.flags["sound"]) {
        this.debug("Punk Rock boost");
        return this.chainModify([5325, 4096]);
      }
    }

// ability:punkrock.onSourceModifyDamage
onSourceModifyDamage(damage, source, target, move) {
      if (move.flags["sound"]) {
        this.debug("Punk Rock weaken");
        return this.chainModify(0.5);
      }
    }

// ability:zerotohero.onSwitchOut
onSwitchOut(pokemon) {
      if (pokemon.baseSpecies.baseSpecies !== "Palafin") return;
      if (pokemon.species.forme !== "Hero") {
        pokemon.formeChange("Palafin-Hero", this.effect, true);
        pokemon.heroMessageDisplayed = false;
      }
    }

// ability:zerotohero.onSwitchIn
onSwitchIn(pokemon) {
      if (pokemon.baseSpecies.baseSpecies !== "Palafin") return;
      if (!pokemon.heroMessageDisplayed && pokemon.species.forme === "Hero") {
        this.add("-activate", pokemon, "ability: Zero to Hero");
        pokemon.heroMessageDisplayed = true;
      }
    }

// ability:voltabsorb.onTryHit
onTryHit(target, source, move) {
      if (target !== source && move.type === "Electric") {
        if (!this.heal(target.baseMaxhp / 4)) {
          this.add("-immune", target, "[from] ability: Volt Absorb");
        }
        return null;
      }
    }

// ability:cloudnine.onSwitchIn
onSwitchIn(pokemon) {
      this.add("-ability", pokemon, "Cloud Nine");
      this.effect.onStart.call(this, pokemon);
    }

// ability:cloudnine.onStart
onStart(pokemon) {
      pokemon.abilityState.ending = false;
      this.eachEvent("WeatherChange", this.effect);
    }

// ability:cloudnine.onEnd
onEnd(pokemon) {
      pokemon.abilityState.ending = true;
      this.eachEvent("WeatherChange", this.effect);
    }

// ability:bulletproof.onTryHit
onTryHit(pokemon, target, move) {
      if (move.flags["bullet"]) {
        this.add("-immune", pokemon, "[from] ability: Bulletproof");
        return null;
      }
    }

// ability:parentalbond.onPrepareHit
onPrepareHit(source, target, move) {
      if (move.category === "Status" || move.multihit || move.flags["noparentalbond"] || move.flags["charge"] || move.flags["futuremove"] || move.spreadHit || move.isZ || move.isMax) return;
      move.multihit = 2;
      move.multihitType = "parentalbond";
    }

// ability:parentalbond.onSourceModifySecondaries
onSourceModifySecondaries(secondaries, target, source, move) {
      if (move.multihitType === "parentalbond" && move.id === "secretpower" && move.hit < 2) {
        return secondaries.filter((effect) => effect.volatileStatus === "flinch");
      }
    }

// ability:waterbubble.onSourceModifyAtk
onSourceModifyAtk(atk, attacker, defender, move) {
      if (move.type === "Fire") {
        return this.chainModify(0.5);
      }
    }

// ability:waterbubble.onSourceModifySpA
onSourceModifySpA(atk, attacker, defender, move) {
      if (move.type === "Fire") {
        return this.chainModify(0.5);
      }
    }

// ability:waterbubble.onModifyAtk
onModifyAtk(atk, attacker, defender, move) {
      if (move.type === "Water") {
        return this.chainModify(2);
      }
    }

// ability:waterbubble.onModifySpA
onModifySpA(atk, attacker, defender, move) {
      if (move.type === "Water") {
        return this.chainModify(2);
      }
    }

// ability:waterbubble.onUpdate
onUpdate(pokemon) {
      if (pokemon.status === "brn") {
        this.add("-activate", pokemon, "ability: Water Bubble");
        pokemon.cureStatus();
      }
    }

// ability:waterbubble.onSetStatus
onSetStatus(status, target, source, effect) {
      if (status.id !== "brn") return;
      if (effect?.status) {
        this.add("-immune", target, "[from] ability: Water Bubble");
      }
      return false;
    }

// ability:sniper.onModifyDamage
onModifyDamage(damage, source, target, move) {
      if (target.getMoveHitData(move).crit) {
        this.debug("Sniper boost");
        return this.chainModify(1.5);
      }
    }

// ability:torrent.onModifyAtk
onModifyAtk(atk, attacker, defender, move) {
      if (move.type === "Water" && attacker.hp <= attacker.maxhp / 3) {
        this.debug("Torrent boost");
        return this.chainModify(1.5);
      }
    }

// ability:torrent.onModifySpA
onModifySpA(atk, attacker, defender, move) {
      if (move.type === "Water" && attacker.hp <= attacker.maxhp / 3) {
        this.debug("Torrent boost");
        return this.chainModify(1.5);
      }
    }

// ability:overgrow.onModifyAtk
onModifyAtk(atk, attacker, defender, move) {
      if (move.type === "Grass" && attacker.hp <= attacker.maxhp / 3) {
        this.debug("Overgrow boost");
        return this.chainModify(1.5);
      }
    }

// ability:overgrow.onModifySpA
onModifySpA(atk, attacker, defender, move) {
      if (move.type === "Grass" && attacker.hp <= attacker.maxhp / 3) {
        this.debug("Overgrow boost");
        return this.chainModify(1.5);
      }
    }

// ability:disguise.onDamage
onDamage(damage, target, source, effect) {
      if (effect?.effectType === "Move" && ["mimikyu", "mimikyutotem"].includes(target.species.id)) {
        this.add("-activate", target, "ability: Disguise");
        this.effectState.busted = true;
        return 0;
      }
    }

// ability:disguise.onCriticalHit
onCriticalHit(target, source, move) {
      if (!target) return;
      if (!["mimikyu", "mimikyutotem"].includes(target.species.id)) {
        return;
      }
      const hitSub = target.volatiles["substitute"] && !move.flags["bypasssub"] && !(move.infiltrates && this.gen >= 6);
      if (hitSub) return;
      if (!target.runImmunity(move)) return;
      return false;
    }

// ability:disguise.onEffectiveness
onEffectiveness(typeMod, target, type, move) {
      if (!target || move.category === "Status") return;
      if (!["mimikyu", "mimikyutotem"].includes(target.species.id)) {
        return;
      }
      const hitSub = target.volatiles["substitute"] && !move.flags["bypasssub"] && !(move.infiltrates && this.gen >= 6);
      if (hitSub) return;
      if (!target.runImmunity(move)) return;
      return 0;
    }

// ability:disguise.onUpdate
onUpdate(pokemon) {
      if (["mimikyu", "mimikyutotem"].includes(pokemon.species.id) && this.effectState.busted) {
        const speciesid = pokemon.species.id === "mimikyutotem" ? "Mimikyu-Busted-Totem" : "Mimikyu-Busted";
        pokemon.formeChange(speciesid, this.effect, true);
        this.damage(pokemon.baseMaxhp / 8, pokemon, pokemon, this.dex.species.get(speciesid));
      }
    }

// ability:filter.onSourceModifyDamage
onSourceModifyDamage(damage, source, target, move) {
      if (target.getMoveHitData(move).typeMod > 0) {
        this.debug("Filter neutralize");
        return this.chainModify(0.75);
      }
    }

// ability:hypercutter.onTryBoost
onTryBoost(boost, target, source, effect) {
      if (source && target === source) return;
      if (boost.atk && boost.atk < 0) {
        delete boost.atk;
        if (!effect.secondaries) {
          this.add("-fail", target, "unboost", "Attack", "[from] ability: Hyper Cutter", `[of] ${target}`);
        }
      }
    }

// ability:stalwart.onModifyMove
onModifyMove(move) {
      move.tracksTarget = move.target !== "scripted";
    }

// ability:pickpocket.onAfterMoveSecondary
onAfterMoveSecondary(target, source, move) {
      if (source && source !== target && move?.flags["contact"]) {
        if (target.item || target.switchFlag || target.forceSwitchFlag || source.switchFlag === true) {
          return;
        }
        const yourItem = source.takeItem(target);
        if (!yourItem) {
          return;
        }
        if (!target.setItem(yourItem)) {
          source.item = yourItem.id;
          return;
        }
        this.add("-enditem", source, yourItem, "[silent]", "[from] ability: Pickpocket", `[of] ${source}`);
        this.add("-item", target, yourItem, "[from] ability: Pickpocket", `[of] ${source}`);
      }
    }

// ability:magicguard.onDamage
onDamage(damage, target, source, effect) {
      if (effect.effectType !== "Move") {
        if (effect.effectType === "Ability") this.add("-activate", source, "ability: " + effect.name);
        return false;
      }
    }

// ability:libero.onPrepareHit
onPrepareHit(source, target, move) {
      if (this.effectState.libero) return;
      if (move.hasBounced || move.flags["futuremove"] || move.sourceEffect === "snatch" || move.callsMove) return;
      const type = move.type;
      if (type && type !== "???" && source.getTypes().join() !== type) {
        if (!source.setType(type)) return;
        this.effectState.libero = true;
        this.add("-start", source, "typechange", type, "[from] ability: Libero");
      }
    }

// ability:solidrock.onSourceModifyDamage
onSourceModifyDamage(damage, source, target, move) {
      if (target.getMoveHitData(move).typeMod > 0) {
        this.debug("Solid Rock neutralize");
        return this.chainModify(0.75);
      }
    }

// ability:damp.onAnyTryMove
onAnyTryMove(target, source, effect) {
      if (["explosion", "mindblown", "mistyexplosion", "selfdestruct"].includes(effect.id)) {
        this.attrLastMove("[still]");
        this.add("cant", this.effectState.target, "ability: Damp", effect, `[of] ${target}`);
        return false;
      }
    }

// ability:damp.onAnyDamage
onAnyDamage(damage, target, source, effect) {
      if (effect && effect.name === "Aftermath") {
        return false;
      }
    }

// ability:emergencyexit.onEmergencyExit
onEmergencyExit(target) {
      if (!this.canSwitch(target.side) || target.forceSwitchFlag || target.switchFlag) return;
      target.switchFlag = true;
      this.add("-activate", target, "ability: Emergency Exit");
    }

// ability:flowerveil.onAllyTryBoost
onAllyTryBoost(boost, target, source, effect) {
      if (source && target === source || !target.hasType("Grass")) return;
      let showMsg = false;
      let i;
      for (i in boost) {
        if (boost[i] < 0) {
          delete boost[i];
          showMsg = true;
        }
      }
      if (showMsg && !effect.secondaries) {
        const effectHolder = this.effectState.target;
        this.add("-block", target, "ability: Flower Veil", `[of] ${effectHolder}`);
      }
    }

// ability:flowerveil.onAllySetStatus
onAllySetStatus(status, target, source, effect) {
      if (target.hasType("Grass") && source && target !== source && effect && effect.id !== "yawn") {
        this.debug("interrupting setStatus with Flower Veil");
        if (effect.name === "Synchronize" || effect.effectType === "Move" && !effect.secondaries) {
          const effectHolder = this.effectState.target;
          this.add("-block", target, "ability: Flower Veil", `[of] ${effectHolder}`);
        }
        return null;
      }
    }

// ability:flowerveil.onAllyTryAddVolatile
onAllyTryAddVolatile(status, target) {
      if (target.hasType("Grass") && status.id === "yawn") {
        this.debug("Flower Veil blocking yawn");
        const effectHolder = this.effectState.target;
        this.add("-block", target, "ability: Flower Veil", `[of] ${effectHolder}`);
        return null;
      }
    }

// ability:cursedbody.onDamagingHit
onDamagingHit(damage, target, source, move) {
      if (source.volatiles["disable"]) return;
      if (!move.isMax && !move.flags["futuremove"] && move.id !== "struggle") {
        if (this.randomChance(3, 10)) {
          source.addVolatile("disable", this.effectState.target);
        }
      }
    }

// ability:limber.onUpdate
onUpdate(pokemon) {
      if (pokemon.status === "par") {
        this.add("-activate", pokemon, "ability: Limber");
        pokemon.cureStatus();
      }
    }

// ability:limber.onSetStatus
onSetStatus(status, target, source, effect) {
      if (status.id !== "par") return;
      if (effect?.status) {
        this.add("-immune", target, "[from] ability: Limber");
      }
      return false;
    }

// ability:synchronize.onAfterSetStatus
onAfterSetStatus(status, target, source, effect) {
      if (!source || source === target) return;
      if (effect && effect.id === "toxicspikes") return;
      if (status.id === "slp" || status.id === "frz") return;
      this.add("-activate", target, "ability: Synchronize");
      source.trySetStatus(status, target, { status: status.id, id: "synchronize" });
    }

// ability:moody.onResidual
onResidual(pokemon) {
      let stats = [];
      const boost = {};
      let statPlus;
      for (statPlus in pokemon.boosts) {
        if (statPlus === "accuracy" || statPlus === "evasion") continue;
        if (pokemon.boosts[statPlus] < 6) {
          stats.push(statPlus);
        }
      }
      let randomStat = stats.length ? this.sample(stats) : void 0;
      if (randomStat) boost[randomStat] = 2;
      stats = [];
      let statMinus;
      for (statMinus in pokemon.boosts) {
        if (statMinus === "accuracy" || statMinus === "evasion") continue;
        if (pokemon.boosts[statMinus] > -6 && statMinus !== randomStat) {
          stats.push(statMinus);
        }
      }
      randomStat = stats.length ? this.sample(stats) : void 0;
      if (randomStat) boost[randomStat] = -1;
      this.boost(boost, pokemon, pokemon);
    }

// ability:raindish.onWeather
onWeather(target, source, effect) {
      if (target.effectiveWeather() !== effect.id) return;
      if (effect.id === "raindance" || effect.id === "primordialsea") {
        this.heal(target.baseMaxhp / 16);
      }
    }

// ability:solarpower.onModifySpA
onModifySpA(spa, pokemon) {
      if (["sunnyday", "desolateland"].includes(pokemon.effectiveWeather())) {
        return this.chainModify(1.5);
      }
    }

// ability:solarpower.onWeather
onWeather(target, source, effect) {
      if (target.effectiveWeather() !== effect.id) return;
      if (effect.id === "sunnyday" || effect.id === "desolateland") {
        this.damage(target.baseMaxhp / 8, target, target);
      }
    }

// ability:telepathy.onTryHit
onTryHit(target, source, move) {
      if (target !== source && target.isAlly(source) && move.category !== "Status") {
        this.add("-activate", target, "ability: Telepathy");
        return null;
      }
    }

// ability:keeneye.onTryBoost
onTryBoost(boost, target, source, effect) {
      if (source && target === source) return;
      if (boost.accuracy && boost.accuracy < 0) {
        delete boost.accuracy;
        if (!effect.secondaries) {
          this.add("-fail", target, "unboost", "accuracy", "[from] ability: Keen Eye", `[of] ${target}`);
        }
      }
    }

// ability:keeneye.onModifyMove
onModifyMove(move) {
      move.ignoreEvasion = true;
    }

// ability:bigpecks.onTryBoost
onTryBoost(boost, target, source, effect) {
      if (source && target === source) return;
      if (boost.def && boost.def < 0) {
        delete boost.def;
        if (!effect.secondaries && effect.id !== "octolock") {
          this.add("-fail", target, "unboost", "Defense", "[from] ability: Big Pecks", `[of] ${target}`);
        }
      }
    }

// ability:naturalcure.onSwitchOut
onSwitchOut(pokemon) {
      if (!pokemon.status || pokemon.status === "fnt") return;
      this.add("-curestatus", pokemon, pokemon.status, "[from] ability: Natural Cure", "[silent]");
      pokemon.clearStatus();
    }

// ability:symbiosis.onAllyAfterUseItem
onAllyAfterUseItem(item, pokemon) {
      if (pokemon.switchFlag) return;
      const source = this.effectState.target;
      const myItem = source.takeItem();
      if (!myItem) return;
      if (!this.singleEvent("TakeItem", myItem, source.itemState, pokemon, source, this.effect, myItem) || !pokemon.setItem(myItem)) {
        source.item = myItem.id;
        return;
      }
      this.add("-activate", source, "ability: Symbiosis", myItem, `[of] ${pokemon}`);
    }

// ability:sturdy.onTryHit
onTryHit(pokemon, target, move) {
      if (move.ohko) {
        this.add("-immune", pokemon, "[from] ability: Sturdy");
        return null;
      }
    }

// ability:sturdy.onDamage
onDamage(damage, target, source, effect) {
      if (target.hp === target.maxhp && damage >= target.hp && effect && effect.effectType === "Move") {
        this.add("-ability", target, "Sturdy");
        return target.hp - 1;
      }
    }

// ability:icebody.onWeather
onWeather(target, source, effect) {
      if (effect.id === "hail" || effect.id === "snowscape") {
        this.heal(target.baseMaxhp / 16);
      }
    }

// ability:icebody.onImmunity
onImmunity(type, pokemon) {
      if (type === "hail") return false;
    }

// ability:leafguard.onSetStatus
onSetStatus(status, target, source, effect) {
      if (["sunnyday", "desolateland"].includes(target.effectiveWeather())) {
        if (effect?.status) {
          this.add("-immune", target, "[from] ability: Leaf Guard");
        }
        return false;
      }
    }

// ability:leafguard.onTryAddVolatile
onTryAddVolatile(status, target) {
      if (status.id === "yawn" && ["sunnyday", "desolateland"].includes(target.effectiveWeather())) {
        this.add("-immune", target, "[from] ability: Leaf Guard");
        return null;
      }
    }

// ability:superluck.onModifyCritRatio
onModifyCritRatio(critRatio) {
      return critRatio + 1;
    }

// ability:wanderingspirit.onDamagingHit
onDamagingHit(damage, target, source, move) {
      if (this.checkMoveMakesContact(move, source, target)) this.skillSwap(source, target);
    }

// ability:sandveil.onImmunity
onImmunity(type, pokemon) {
      if (type === "sandstorm") return false;
    }

// ability:sandveil.onModifyAccuracy
onModifyAccuracy(accuracy) {
      if (typeof accuracy !== "number") return;
      if (this.field.isWeather("sandstorm")) {
        this.debug("Sand Veil - decreasing accuracy");
        return this.chainModify([3277, 4096]);
      }
    }

// ability:guts.onModifyAtk
onModifyAtk(atk, pokemon) {
      if (pokemon.status) {
        return this.chainModify(1.5);
      }
    }

// ability:imposter.onSwitchIn
onSwitchIn(pokemon) {
      const target = pokemon.side.foe.active[pokemon.side.foe.active.length - 1 - pokemon.position];
      if (target) {
        pokemon.transformInto(target, this.dex.abilities.get("imposter"));
      }
    }

// ability:supremeoverlord.onStart
onStart(pokemon) {
      if (pokemon.side.totalFainted) {
        this.add("-activate", pokemon, "ability: Supreme Overlord");
        const fallen = Math.min(pokemon.side.totalFainted, 5);
        this.add("-start", pokemon, `fallen${fallen}`, "[silent]");
        this.effectState.fallen = fallen;
      }
    }

// ability:supremeoverlord.onEnd
onEnd(pokemon) {
      this.add("-end", pokemon, `fallen${this.effectState.fallen}`, "[silent]");
    }

// ability:supremeoverlord.onBasePower
onBasePower(basePower, attacker, defender, move) {
      if (this.effectState.fallen) {
        const powMod = [4096, 4506, 4915, 5325, 5734, 6144];
        this.debug(`Supreme Overlord boost: ${powMod[this.effectState.fallen]}/4096`);
        return this.chainModify([powMod[this.effectState.fallen], 4096]);
      }
    }

// ability:justified.onDamagingHit
onDamagingHit(damage, target, source, move) {
      if (move.type === "Dark") {
        this.boost({ atk: 1 });
      }
    }

// ability:furcoat.onModifyDef
onModifyDef(def) {
      return this.chainModify(2);
    }

// ability:heatproof.onSourceModifyAtk
onSourceModifyAtk(atk, attacker, defender, move) {
      if (move.type === "Fire") {
        this.debug("Heatproof Atk weaken");
        return this.chainModify(0.5);
      }
    }

// ability:heatproof.onSourceModifySpA
onSourceModifySpA(atk, attacker, defender, move) {
      if (move.type === "Fire") {
        this.debug("Heatproof SpA weaken");
        return this.chainModify(0.5);
      }
    }

// ability:heatproof.onDamage
onDamage(damage, target, source, effect) {
      if (effect && effect.id === "brn") {
        return damage / 2;
      }
    }

// ability:magmaarmor.onUpdate
onUpdate(pokemon) {
      if (pokemon.status === "frz") {
        this.add("-activate", pokemon, "ability: Magma Armor");
        pokemon.cureStatus();
      }
    }

// ability:magmaarmor.onImmunity
onImmunity(type, pokemon) {
      if (type === "frz") return false;
    }

// ability:magician.onAfterMoveSecondarySelf
onAfterMoveSecondarySelf(source, target, move) {
      if (!move || source.switchFlag === true || !move.hitTargets || source.item || source.volatiles["gem"] || move.id === "fling" || move.category === "Status") return;
      const hitTargets = move.hitTargets;
      this.speedSort(hitTargets);
      for (const pokemon of hitTargets) {
        if (pokemon !== source) {
          const yourItem = pokemon.takeItem(source);
          if (!yourItem) continue;
          if (!source.setItem(yourItem)) {
            pokemon.item = yourItem.id;
            continue;
          }
          this.add("-item", source, yourItem, "[from] ability: Magician", `[of] ${pokemon}`);
          return;
        }
      }
    }

// ability:moxie.onSourceAfterFaint
onSourceAfterFaint(length, target, source, effect) {
      if (effect && effect.effectType === "Move") {
        this.boost({ atk: length }, source);
      }
    }

// ability:owntempo.onUpdate
onUpdate(pokemon) {
      if (pokemon.volatiles["confusion"]) {
        this.add("-activate", pokemon, "ability: Own Tempo");
        pokemon.removeVolatile("confusion");
      }
    }

// ability:owntempo.onTryAddVolatile
onTryAddVolatile(status, pokemon) {
      if (status.id === "confusion") return null;
    }

// ability:owntempo.onHit
onHit(target, source, move) {
      if (move?.volatileStatus === "confusion") {
        this.add("-immune", target, "confusion", "[from] ability: Own Tempo");
      }
    }

// ability:owntempo.onTryBoost
onTryBoost(boost, target, source, effect) {
      if (effect.name === "Intimidate" && boost.atk) {
        delete boost.atk;
        this.add("-fail", target, "unboost", "Attack", "[from] ability: Own Tempo", `[of] ${target}`);
      }
    }

// ability:static.onDamagingHit
onDamagingHit(damage, target, source, move) {
      if (this.checkMoveMakesContact(move, source, target)) {
        if (this.randomChance(3, 10)) {
          source.trySetStatus("par", target);
        }
      }
    }

// ability:cudchew.onEatItem
onEatItem(item, pokemon, source, effect) {
      if (item.isBerry && (!effect || !["bugbite", "pluck"].includes(effect.id))) {
        this.effectState.berry = item;
        this.effectState.counter = 2;
        if (!this.queue.peek()) this.effectState.counter--;
      }
    }

// ability:cudchew.onResidual
onResidual(pokemon) {
      if (!this.effectState.berry || !pokemon.hp) return;
      if (--this.effectState.counter <= 0) {
        const item = this.effectState.berry;
        this.add("-activate", pokemon, "ability: Cud Chew");
        this.add("-enditem", pokemon, item.name, "[eat]");
        if (this.singleEvent("Eat", item, null, pokemon, null, null)) {
          this.runEvent("EatItem", pokemon, null, null, item);
        }
        if (item.onEat) pokemon.ateBerry = true;
        delete this.effectState.berry;
        delete this.effectState.counter;
      }
    }

// ability:sapsipper.onTryHit
onTryHit(target, source, move) {
      if (target !== source && move.type === "Grass") {
        if (!this.boost({ atk: 1 })) {
          this.add("-immune", target, "[from] ability: Sap Sipper");
        }
        return null;
      }
    }

// ability:sapsipper.onAllyTryHitSide
onAllyTryHitSide(target, source, move) {
      if (source === this.effectState.target || !target.isAlly(source)) return;
      if (move.type === "Grass") {
        this.boost({ atk: 1 }, this.effectState.target);
      }
    }

// ability:marvelscale.onModifyDef
onModifyDef(def, pokemon) {
      if (pokemon.status) {
        return this.chainModify(1.5);
      }
    }

// ability:cutecharm.onDamagingHit
onDamagingHit(damage, target, source, move) {
      if (this.checkMoveMakesContact(move, source, target)) {
        if (this.randomChance(3, 10)) {
          source.addVolatile("attract", this.effectState.target);
        }
      }
    }

// ability:swarm.onModifyAtk
onModifyAtk(atk, attacker, defender, move) {
      if (move.type === "Bug" && attacker.hp <= attacker.maxhp / 3) {
        this.debug("Swarm boost");
        return this.chainModify(1.5);
      }
    }

// ability:swarm.onModifySpA
onModifySpA(atk, attacker, defender, move) {
      if (move.type === "Bug" && attacker.hp <= attacker.maxhp / 3) {
        this.debug("Swarm boost");
        return this.chainModify(1.5);
      }
    }

// ability:reckless.onBasePower
onBasePower(basePower, attacker, defender, move) {
      if (move.recoil || move.hasCrashDamage) {
        this.debug("Reckless boost");
        return this.chainModify([4915, 4096]);
      }
    }

// ability:piercingdrill.onHitProtect
onHitProtect(source, target, move) {
      if (move.flags["contact"]) {
        target.getMoveHitData(move).bypassProtect = this.effect;
        return false;
      }
    }

// ability:snowcloak.onImmunity
onImmunity(type, pokemon) {
      if (type === "hail") return false;
    }

// ability:snowcloak.onModifyAccuracy
onModifyAccuracy(accuracy) {
      if (typeof accuracy !== "number") return;
      if (this.field.isWeather(["hail", "snowscape"])) {
        this.debug("Snow Cloak - decreasing accuracy");
        return this.chainModify([3277, 4096]);
      }
    }

// ability:waterabsorb.onTryHit
onTryHit(target, source, move) {
      if (target !== source && move.type === "Water") {
        if (!this.heal(target.baseMaxhp / 4)) {
          this.add("-immune", target, "[from] ability: Water Absorb");
        }
        return null;
      }
    }

// ability:lightmetal.onModifyWeight
onModifyWeight(weighthg) {
      return this.trunc(weighthg / 2);
    }

// ability:frisk.onStart
onStart(pokemon) {
      for (const target of pokemon.foes()) {
        if (target.item) {
          this.add("-item", target, target.getItem().name, "[from] ability: Frisk", `[of] ${pokemon}`);
        }
      }
    }

// ability:steadfast.onFlinch
onFlinch(pokemon) {
      this.boost({ spe: 1 });
    }

// ability:whitesmoke.onTryBoost
onTryBoost(boost, target, source, effect) {
      if (source && target === source) return;
      let showMsg = false;
      let i;
      for (i in boost) {
        if (boost[i] < 0) {
          delete boost[i];
          showMsg = true;
        }
      }
      if (showMsg && !effect.secondaries && effect.id !== "octolock") {
        this.add("-fail", target, "unboost", "[from] ability: White Smoke", `[of] ${target}`);
      }
    }

// ability:overcoat.onImmunity
onImmunity(type, pokemon) {
      if (type === "sandstorm" || type === "hail" || type === "powder") return false;
    }

// ability:overcoat.onTryHit
onTryHit(target, source, move) {
      if (move.flags["powder"] && target !== source && this.dex.getImmunity("powder", target)) {
        this.add("-immune", target, "[from] ability: Overcoat");
        return null;
      }
    }

// ability:vitalspirit.onUpdate
onUpdate(pokemon) {
      if (pokemon.status === "slp") {
        this.add("-activate", pokemon, "ability: Vital Spirit");
        pokemon.cureStatus();
      }
    }

// ability:vitalspirit.onSetStatus
onSetStatus(status, target, source, effect) {
      if (status.id !== "slp") return;
      if (effect?.status) {
        this.add("-immune", target, "[from] ability: Vital Spirit");
      }
      return false;
    }

// ability:vitalspirit.onTryAddVolatile
onTryAddVolatile(status, target) {
      if (status.id === "yawn") {
        this.add("-immune", target, "[from] ability: Vital Spirit");
        return null;
      }
    }

// ability:healer.onResidual
onResidual(pokemon) {
      for (const allyActive of pokemon.adjacentAllies()) {
        if (allyActive.status && this.randomChance(1, 2)) {
          this.add("-activate", pokemon, "ability: Healer");
          allyActive.cureStatus();
        }
      }
    }

// ability:anticipation.onStart
onStart(pokemon) {
      for (const target of pokemon.foes()) {
        for (const moveSlot of target.moveSlots) {
          const move = this.dex.moves.get(moveSlot.move);
          if (move.category === "Status") continue;
          const moveType = move.id === "hiddenpower" ? target.hpType : move.type;
          if (this.dex.getImmunity(moveType, pokemon) && this.dex.getEffectiveness(moveType, pokemon) > 0 || move.ohko) {
            this.add("-ability", pokemon, "Anticipation");
            return;
          }
        }
      }
    }

// ability:cheekpouch.onEatItem
onEatItem(item, pokemon) {
      this.heal(pokemon.baseMaxhp / 3);
    }

// ability:angerpoint.onHit
onHit(target, source, move) {
      if (!target.hp) return;
      if (move?.effectType === "Move" && target.getMoveHitData(move).crit) {
        this.boost({ atk: 12 }, target, target);
      }
    }

// ability:shielddust.onModifySecondaries
onModifySecondaries(secondaries) {
      this.debug("Shield Dust prevent secondary");
      return secondaries.filter((effect) => !!effect.self);
    }

// ability:merciless.onModifyCritRatio
onModifyCritRatio(critRatio, source, target) {
      if (target && ["psn", "tox"].includes(target.status)) return 5;
    }

// ability:insomnia.onUpdate
onUpdate(pokemon) {
      if (pokemon.status === "slp") {
        this.add("-activate", pokemon, "ability: Insomnia");
        pokemon.cureStatus();
      }
    }

// ability:insomnia.onSetStatus
onSetStatus(status, target, source, effect) {
      if (status.id !== "slp") return;
      if (effect?.status) {
        this.add("-immune", target, "[from] ability: Insomnia");
      }
      return false;
    }

// ability:insomnia.onTryAddVolatile
onTryAddVolatile(status, target) {
      if (status.id === "yawn") {
        this.add("-immune", target, "[from] ability: Insomnia");
        return null;
      }
    }

// ability:opportunist.onFoeAfterBoost
onFoeAfterBoost(boost, target, source, effect) {
      if (effect?.name === "Opportunist" || effect?.name === "Mirror Herb") return;
      if (!this.effectState.boosts) this.effectState.boosts = {};
      const boostPlus = this.effectState.boosts;
      let i;
      for (i in boost) {
        if (boost[i] > 0) {
          boostPlus[i] = (boostPlus[i] || 0) + boost[i];
        }
      }
    }

// ability:opportunist.onAnySwitchIn
onAnySwitchIn() {
      if (!this.effectState.boosts) return;
      this.boost(this.effectState.boosts, this.effectState.target);
      delete this.effectState.boosts;
    }

// ability:opportunist.onAnyAfterMega
onAnyAfterMega() {
      if (!this.effectState.boosts) return;
      this.boost(this.effectState.boosts, this.effectState.target);
      delete this.effectState.boosts;
    }

// ability:opportunist.onAnyAfterTerastallization
onAnyAfterTerastallization() {
      if (!this.effectState.boosts) return;
      this.boost(this.effectState.boosts, this.effectState.target);
      delete this.effectState.boosts;
    }

// ability:opportunist.onAnyAfterMove
onAnyAfterMove() {
      if (!this.effectState.boosts) return;
      this.boost(this.effectState.boosts, this.effectState.target);
      delete this.effectState.boosts;
    }

// ability:opportunist.onResidual
onResidual(pokemon) {
      if (!this.effectState.boosts) return;
      this.boost(this.effectState.boosts, this.effectState.target);
      delete this.effectState.boosts;
    }

// ability:opportunist.onEnd
onEnd() {
      delete this.effectState.boosts;
    }

// ability:klutz.onStart
onStart(pokemon) {
      this.singleEvent("End", pokemon.getItem(), pokemon.itemState, pokemon);
    }

// ability:rivalry.onBasePower
onBasePower(basePower, attacker, defender, move) {
      if (attacker.gender && defender.gender) {
        if (attacker.gender === defender.gender) {
          this.debug("Rivalry boost");
          return this.chainModify(1.25);
        } else {
          this.debug("Rivalry weaken");
          return this.chainModify(0.75);
        }
      }
    }

// ability:shedskin.onResidual
onResidual(pokemon) {
      if (pokemon.hp && pokemon.status && this.randomChance(33, 100)) {
        this.debug("shed skin");
        this.add("-activate", pokemon, "ability: Shed Skin");
        pokemon.cureStatus();
      }
    }

// ability:sweetveil.onAllySetStatus
onAllySetStatus(status, target, source, effect) {
      if (status.id === "slp") {
        this.debug("Sweet Veil interrupts sleep");
        const effectHolder = this.effectState.target;
        this.add("-block", target, "ability: Sweet Veil", `[of] ${effectHolder}`);
        return null;
      }
    }

// ability:sweetveil.onAllyTryAddVolatile
onAllyTryAddVolatile(status, target) {
      if (status.id === "yawn") {
        this.debug("Sweet Veil blocking yawn");
        const effectHolder = this.effectState.target;
        this.add("-block", target, "ability: Sweet Veil", `[of] ${effectHolder}`);
        return null;
      }
    }

// ability:plus.onModifySpA
onModifySpA(spa, pokemon) {
      for (const allyActive of pokemon.allies()) {
        if (allyActive.hasAbility(["minus", "plus"])) {
          return this.chainModify(1.5);
        }
      }
    }

// ability:immunity.onUpdate
onUpdate(pokemon) {
      if (pokemon.status === "psn" || pokemon.status === "tox") {
        this.add("-activate", pokemon, "ability: Immunity");
        pokemon.cureStatus();
      }
    }

// ability:immunity.onSetStatus
onSetStatus(status, target, source, effect) {
      if (status.id !== "psn" && status.id !== "tox") return;
      if (effect?.status) {
        this.add("-immune", target, "[from] ability: Immunity");
      }
      return false;
    }

// ability:gluttony.onStart
onStart(pokemon) {
      pokemon.abilityState.gluttony = true;
    }

// ability:gluttony.onDamage
onDamage(item, pokemon) {
      pokemon.abilityState.gluttony = true;
    }

// ability:illuminate.onTryBoost
onTryBoost(boost, target, source, effect) {
      if (source && target === source) return;
      if (boost.accuracy && boost.accuracy < 0) {
        delete boost.accuracy;
        if (!effect.secondaries) {
          this.add("-fail", target, "unboost", "accuracy", "[from] ability: Illuminate", `[of] ${target}`);
        }
      }
    }

// ability:illuminate.onModifyMove
onModifyMove(move) {
      move.ignoreEvasion = true;
    }

// ability:analytic.onBasePower
onBasePower(basePower, pokemon) {
      let boosted = true;
      for (const target of this.getAllActive()) {
        if (target === pokemon) continue;
        if (this.queue.willMove(target)) {
          boosted = false;
          break;
        }
      }
      if (boosted) {
        this.debug("Analytic boost");
        return this.chainModify([5325, 4096]);
      }
    }

// ability:gooey.onDamagingHit
onDamagingHit(damage, target, source, move) {
      if (this.checkMoveMakesContact(move, source, target, true)) {
        this.add("-ability", target, "Gooey");
        this.boost({ spe: -1 }, source, target, null, true);
      }
    }

// ability:berserk.onDamage
onDamage(damage, target, source, effect) {
      this.effectState.checkedBerserk = !(effect.effectType === "Move" && !effect.multihit);
    }

// ability:berserk.onTryEatItem
onTryEatItem(item) {
      const healingItems = [
        "aguavberry",
        "enigmaberry",
        "figyberry",
        "iapapaberry",
        "magoberry",
        "sitrusberry",
        "wikiberry",
        "oranberry",
        "berryjuice"
      ];
      if (healingItems.includes(item.id)) {
        return this.effectState.checkedBerserk;
      }
      return true;
    }

// ability:berserk.onAfterMoveSecondary
onAfterMoveSecondary(target, source, move) {
      this.effectState.checkedBerserk = true;
      if (!source || source === target || !target.hp || !move.totalDamage) return;
      const lastAttackedBy = target.getLastAttackedBy();
      if (!lastAttackedBy) return;
      const damage = move.multihit && !move.smartTarget ? move.totalDamage : lastAttackedBy.damage;
      if (target.hp <= target.maxhp / 2 && target.hp + damage > target.maxhp / 2) {
        this.boost({ spa: 1 }, target, target);
      }
    }

// ability:battlebond.onSourceAfterFaint
onSourceAfterFaint(length, target, source, effect) {
      if (source.bondTriggered) return;
      if (effect?.effectType !== "Move") return;
      if (source.species.id === "greninjabond" && source.hp && !source.transformed && source.side.foePokemonLeft()) {
        this.boost({ atk: 1, spa: 1, spe: 1 }, source, source, this.effect);
        this.add("-activate", source, "ability: Battle Bond");
        source.bondTriggered = true;
      }
    }

// ability:battlebond.onModifyMove
onModifyMove(move, attacker) {
      if (move.id === "watershuriken" && attacker.species.name === "Greninja-Ash" && !attacker.transformed) {
        move.multihit = 3;
      }
    }

// ability:suctioncups.onDragOut
onDragOut(pokemon) {
      this.add("-activate", pokemon, "ability: Suction Cups");
      return null;
    }

// ability:poisonheal.onDamage
onDamage(damage, target, source, effect) {
      if (effect.id === "psn" || effect.id === "tox") {
        this.heal(target.baseMaxhp / 8);
        return false;
      }
    }

// ability:minus.onModifySpA
onModifySpA(spa, pokemon) {
      for (const allyActive of pokemon.allies()) {
        if (allyActive.hasAbility(["minus", "plus"])) {
          return this.chainModify(1.5);
        }
      }
    }

// ability:heavymetal.onModifyWeight
onModifyWeight(weighthg) {
      return weighthg * 2;
    }

// ability:poisonpoint.onDamagingHit
onDamagingHit(damage, target, source, move) {
      if (this.checkMoveMakesContact(move, source, target)) {
        if (this.randomChance(3, 10)) {
          source.trySetStatus("psn", target);
        }
      }
    }

// ability:effectspore.onDamagingHit
onDamagingHit(damage, target, source, move) {
      if (this.checkMoveMakesContact(move, source, target) && source.runStatusImmunity("powder")) {
        const r = this.random(100);
        if (r < 11) {
          source.trySetStatus("slp", target);
        } else if (r < 21) {
          source.trySetStatus("par", target);
        } else if (r < 30) {
          source.trySetStatus("psn", target);
        }
      }
    }

// ability:curiousmedicine.onStart
onStart(pokemon) {
      for (const ally of pokemon.adjacentAllies()) {
        ally.clearBoosts();
        this.add("-clearboost", ally, "[from] ability: Curious Medicine", `[of] ${pokemon}`);
      }
    }

// ability:dragonize.onModifyType
onModifyType(move, pokemon) {
      const noModifyType = [
        "judgment",
        "multiattack",
        "naturalgift",
        "revelationdance",
        "technoblast",
        "terrainpulse",
        "weatherball"
      ];
      if (move.type === "Normal" && (!noModifyType.includes(move.id) || this.activeMove?.isMax) && !(move.isZ && move.category !== "Status") && !(move.name === "Tera Blast" && pokemon.terastallized)) {
        move.type = "Dragon";
        move.typeChangerBoosted = this.effect;
      }
    }

// ability:dragonize.onBasePower
onBasePower(basePower, pokemon, target, move) {
      if (move.typeChangerBoosted === this.effect) return this.chainModify([4915, 4096]);
    }

// ability:unseenfist.onHitProtect
onHitProtect(source, target, move) {
      if (move.flags["contact"]) {
        target.getMoveHitData(move).bypassProtect = this.effect;
        return false;
      }
    }

// ability:steelyspirit.onAllyBasePower
onAllyBasePower(basePower, attacker, defender, move) {
      if (move.type === "Steel") {
        this.debug("Steely Spirit boost");
        return this.chainModify(1.5);
      }
    }

// ability:seedsower.onDamagingHit
onDamagingHit(damage, target, source, move) {
      this.field.setTerrain("grassyterrain");
    }

// ability:harvest.onResidual
onResidual(pokemon) {
      if (this.field.isWeather(["sunnyday", "desolateland"]) || this.randomChance(1, 2)) {
        if (pokemon.hp && !pokemon.item && this.dex.items.get(pokemon.lastItem).isBerry) {
          pokemon.setItem(pokemon.lastItem);
          pokemon.lastItem = "";
          this.add("-item", pokemon, pokemon.getItem(), "[from] ability: Harvest");
        }
      }
    }

// ability:tangledfeet.onModifyAccuracy
onModifyAccuracy(accuracy, target) {
      if (typeof accuracy !== "number") return;
      if (target?.volatiles["confusion"]) {
        this.debug("Tangled Feet - decreasing accuracy");
        return this.chainModify(0.5);
      }
    }

// ability:supersweetsyrup.onStart
onStart(pokemon) {
      if (pokemon.syrupTriggered) return;
      pokemon.syrupTriggered = true;
      this.add("-ability", pokemon, "Supersweet Syrup");
      for (const target of pokemon.adjacentFoes()) {
        if (target.volatiles["substitute"]) {
          this.add("-immune", target);
        } else {
          this.boost({ evasion: -1 }, target, pokemon, null, true);
        }
      }
    }

// ability:stickyhold.onTakeItem
onTakeItem(item, pokemon, source) {
      if (!this.activeMove) throw new Error("Battle.activeMove is null");
      if (!pokemon.hp || pokemon.item === "stickybarb") return;
      if (source && source !== pokemon || this.activeMove.id === "knockoff") {
        this.add("-activate", pokemon, "ability: Sticky Hold");
        return false;
      }
    }

// ability:skilllink.onModifyMove
onModifyMove(move) {
      if (move.multihit && Array.isArray(move.multihit) && move.multihit.length) {
        move.multihit = move.multihit[1];
      }
      if (move.multiaccuracy) {
        delete move.multiaccuracy;
      }
    }

// ability:rattled.onDamagingHit
onDamagingHit(damage, target, source, move) {
      if (["Dark", "Bug", "Ghost"].includes(move.type)) {
        this.boost({ spe: 1 });
      }
    }

// ability:rattled.onAfterBoost
onAfterBoost(boost, target, source, effect) {
      if (effect?.name === "Intimidate" && boost.atk) {
        this.boost({ spe: 1 });
      }
    }

// cond:par.onStart
onStart(target, source, sourceEffect) {
      if (sourceEffect && sourceEffect.effectType === "Ability") {
        this.add("-status", target, "par", "[from] ability: " + sourceEffect.name, `[of] ${source}`);
      } else {
        this.add("-status", target, "par");
      }
    }

// cond:par.onModifySpe
onModifySpe(spe, pokemon) {
      spe = this.finalModify(spe);
      if (!pokemon.hasAbility("quickfeet")) {
        spe = Math.floor(spe * 50 / 100);
      }
      return spe;
    }

// cond:par.onBeforeMove
onBeforeMove(pokemon) {
      if (this.randomChance(1, 8)) {
        this.add("cant", pokemon, "par");
        return false;
      }
    }

// cond:slp.onStart
onStart(target, source, sourceEffect) {
      if (sourceEffect && sourceEffect.effectType === "Ability") {
        this.add("-status", target, "slp", "[from] ability: " + sourceEffect.name, `[of] ${source}`);
      } else if (sourceEffect && sourceEffect.effectType === "Move") {
        this.add("-status", target, "slp", `[from] move: ${sourceEffect.name}`);
      } else {
        this.add("-status", target, "slp");
      }
      this.effectState.startTime = this.sample([2, 3, 3]);
      this.effectState.time = this.effectState.startTime;
      if (target.removeVolatile("nightmare")) {
        this.add("-end", target, "Nightmare", "[silent]");
      }
    }

// cond:slp.onBeforeMove
onBeforeMove(pokemon, target, move) {
      if (pokemon.hasAbility("earlybird")) {
        pokemon.statusState.time--;
      }
      pokemon.statusState.time--;
      if (pokemon.statusState.time <= 0) {
        pokemon.cureStatus();
        return;
      }
      this.add("cant", pokemon, "slp");
      if (move.sleepUsable) {
        return;
      }
      return false;
    }

// cond:frz.onStart
onStart(target, source, sourceEffect) {
      if (sourceEffect && sourceEffect.effectType === "Ability") {
        this.add("-status", target, "frz", "[from] ability: " + sourceEffect.name, `[of] ${source}`);
      } else {
        this.add("-status", target, "frz");
      }
      if (target.species.name === "Shaymin-Sky" && target.baseSpecies.baseSpecies === "Shaymin") {
        target.formeChange("Shaymin", this.effect, true);
      }
      this.effectState.startTime = 3;
      this.effectState.time = this.effectState.startTime;
    }

// cond:frz.onBeforeMove
onBeforeMove(pokemon, target, move) {
      if (move.flags["defrost"] && !(move.id === "burnup" && !pokemon.hasType("Fire"))) return;
      pokemon.statusState.time--;
      if (pokemon.statusState.time <= 0 || this.randomChance(1, 4)) {
        pokemon.cureStatus();
        return;
      }
      this.add("cant", pokemon, "frz");
      return false;
    }

// cond:frz.onModifyMove
onModifyMove(move, pokemon) {
      if (move.flags["defrost"]) {
        this.add("-curestatus", pokemon, "frz", `[from] move: ${move}`);
        pokemon.clearStatus();
      }
    }

// cond:frz.onAfterMoveSecondary
onAfterMoveSecondary(target, source, move) {
      if (move.thawsTarget) {
        target.cureStatus();
      }
    }

// cond:frz.onDamagingHit
onDamagingHit(damage, target, source, move) {
      if (move.type === "Fire" && move.category !== "Status" && move.id !== "polarflare") {
        target.cureStatus();
      }
    }

// cond:brn.onStart
onStart(target, source, sourceEffect) {
      if (sourceEffect && sourceEffect.id === "flameorb") {
        this.add("-status", target, "brn", "[from] item: Flame Orb");
      } else if (sourceEffect && sourceEffect.effectType === "Ability") {
        this.add("-status", target, "brn", "[from] ability: " + sourceEffect.name, `[of] ${source}`);
      } else {
        this.add("-status", target, "brn");
      }
    }

// cond:brn.onResidual
onResidual(pokemon) {
      this.damage(pokemon.baseMaxhp / 16);
    }

// cond:psn.onStart
onStart(target, source, sourceEffect) {
      if (sourceEffect && sourceEffect.effectType === "Ability") {
        this.add("-status", target, "psn", "[from] ability: " + sourceEffect.name, `[of] ${source}`);
      } else {
        this.add("-status", target, "psn");
      }
    }

// cond:psn.onResidual
onResidual(pokemon) {
      this.damage(pokemon.baseMaxhp / 8);
    }

// cond:tox.onStart
onStart(target, source, sourceEffect) {
      this.effectState.stage = 0;
      if (sourceEffect && sourceEffect.id === "toxicorb") {
        this.add("-status", target, "tox", "[from] item: Toxic Orb");
      } else if (sourceEffect && sourceEffect.effectType === "Ability") {
        this.add("-status", target, "tox", "[from] ability: " + sourceEffect.name, `[of] ${source}`);
      } else {
        this.add("-status", target, "tox");
      }
    }

// cond:tox.onSwitchIn
onSwitchIn() {
      this.effectState.stage = 0;
    }

// cond:tox.onResidual
onResidual(pokemon) {
      if (this.effectState.stage < 15) {
        this.effectState.stage++;
      }
      this.damage(this.clampIntRange(pokemon.baseMaxhp / 16, 1) * this.effectState.stage);
    }

// cond:confusion.onStart
onStart(target, source, sourceEffect) {
      if (sourceEffect?.id === "lockedmove") {
        this.add("-start", target, "confusion", "[fatigue]");
      } else if (sourceEffect?.effectType === "Ability") {
        this.add("-start", target, "confusion", "[from] ability: " + sourceEffect.name, `[of] ${source}`);
      } else {
        this.add("-start", target, "confusion");
      }
      const min = sourceEffect?.id === "axekick" ? 3 : 2;
      this.effectState.time = this.random(min, 6);
    }

// cond:confusion.onEnd
onEnd(target) {
      this.add("-end", target, "confusion");
    }

// cond:confusion.onBeforeMove
onBeforeMove(pokemon) {
      pokemon.volatiles["confusion"].time--;
      if (!pokemon.volatiles["confusion"].time) {
        pokemon.removeVolatile("confusion");
        return;
      }
      this.add("-activate", pokemon, "confusion");
      if (!this.randomChance(33, 100)) {
        return;
      }
      this.activeTarget = pokemon;
      const damage = this.actions.getConfusionDamage(pokemon, 40);
      if (typeof damage !== "number") throw new Error("Confusion damage not dealt");
      const activeMove = { id: this.toID("confused"), effectType: "Move", type: "???" };
      this.damage(damage, pokemon, pokemon, activeMove);
      return false;
    }

// cond:flinch.onBeforeMove
onBeforeMove(pokemon) {
      this.add("cant", pokemon, "flinch");
      this.runEvent("Flinch", pokemon);
      return false;
    }

// cond:trapped.onTrapPokemon
onTrapPokemon(pokemon) {
      pokemon.tryTrap();
    }

// cond:trapped.onStart
onStart(target) {
      this.add("-activate", target, "trapped");
    }

// cond:partiallytrapped.durationCallback
durationCallback(target, source) {
      if (source?.hasItem("gripclaw")) return 8;
      return this.random(5, 7);
    }

// cond:partiallytrapped.onStart
onStart(pokemon, source) {
      this.add("-activate", pokemon, "move: " + this.effectState.sourceEffect, `[of] ${source}`);
      this.effectState.boundDivisor = source.hasItem("bindingband") ? 6 : 8;
    }

// cond:partiallytrapped.onResidual
onResidual(pokemon) {
      const source = this.effectState.source;
      const gmaxEffect = ["gmaxcentiferno", "gmaxsandblast"].includes(this.effectState.sourceEffect.id);
      if (source && (!source.isActive || source.hp <= 0 || !source.activeTurns) && !gmaxEffect) {
        delete pokemon.volatiles["partiallytrapped"];
        this.add("-end", pokemon, this.effectState.sourceEffect, "[partiallytrapped]", "[silent]");
        return;
      }
      this.damage(pokemon.baseMaxhp / this.effectState.boundDivisor);
    }

// cond:partiallytrapped.onEnd
onEnd(pokemon) {
      this.add("-end", pokemon, this.effectState.sourceEffect, "[partiallytrapped]");
    }

// cond:partiallytrapped.onTrapPokemon
onTrapPokemon(pokemon) {
      const gmaxEffect = ["gmaxcentiferno", "gmaxsandblast"].includes(this.effectState.sourceEffect.id);
      if (this.effectState.source?.isActive || gmaxEffect) pokemon.tryTrap();
    }

// cond:lockedmove.onResidual
onResidual(target) {
      if (target.status === "slp") {
        delete target.volatiles["lockedmove"];
      }
      this.effectState.trueDuration--;
    }

// cond:lockedmove.onStart
onStart(target, source, effect) {
      this.effectState.trueDuration = this.random(2, 4);
      this.effectState.move = effect.id;
    }

// cond:lockedmove.onRestart
onRestart() {
      if (this.effectState.trueDuration >= 2) {
        this.effectState.duration = 2;
      }
    }

// cond:lockedmove.onAfterMove
onAfterMove(pokemon) {
      if (this.effectState.duration === 1) {
        pokemon.removeVolatile("lockedmove");
      }
    }

// cond:lockedmove.onEnd
onEnd(target) {
      if (this.effectState.trueDuration > 1) return;
      target.addVolatile("confusion");
    }

// cond:lockedmove.onLockMove
onLockMove(pokemon) {
      if (pokemon.volatiles["dynamax"]) return;
      return this.effectState.move;
    }

// cond:twoturnmove.onStart
onStart(attacker, defender, effect) {
      this.effectState.move = effect.id;
      attacker.addVolatile(effect.id);
      let moveTargetLoc = attacker.lastMoveTargetLoc;
      if (effect.sourceEffect && this.dex.moves.get(effect.id).target !== "self") {
        if (defender.fainted) {
          defender = this.sample(attacker.foes(true));
        }
        moveTargetLoc = attacker.getLocOf(defender);
      }
      attacker.volatiles[effect.id].targetLoc = moveTargetLoc;
      this.attrLastMove("[still]");
      this.runEvent("PrepareHit", attacker, defender, effect);
    }

// cond:twoturnmove.onEnd
onEnd(target) {
      target.removeVolatile(this.effectState.move);
    }

// cond:twoturnmove.onLockMove
onLockMove() {
      return this.effectState.move;
    }

// cond:twoturnmove.onMoveAborted
onMoveAborted(pokemon) {
      pokemon.removeVolatile("twoturnmove");
    }

// cond:choicelock.onStart
onStart(pokemon) {
      if (!this.activeMove) throw new Error("Battle.activeMove is null");
      if (!this.activeMove.id || this.activeMove.hasBounced || this.activeMove.sourceEffect === "snatch") return false;
      this.effectState.move = this.activeMove.id;
    }

// cond:choicelock.onBeforeMove
onBeforeMove(pokemon, target, move) {
      if (!pokemon.getItem().isChoice) {
        pokemon.removeVolatile("choicelock");
        return;
      }
      if (!pokemon.ignoringItem() && !pokemon.volatiles["dynamax"] && move.id !== this.effectState.move && move.id !== "struggle") {
        this.addMove("move", pokemon, move.name);
        this.attrLastMove("[still]");
        this.debug("Disabled by Choice item lock");
        this.add("-fail", pokemon);
        return false;
      }
    }

// cond:choicelock.onDisableMove
onDisableMove(pokemon) {
      if (!pokemon.getItem().isChoice || !pokemon.hasMove(this.effectState.move)) {
        pokemon.removeVolatile("choicelock");
        return;
      }
      if (pokemon.ignoringItem() || pokemon.volatiles["dynamax"]) {
        return;
      }
      for (const moveSlot of pokemon.moveSlots) {
        if (moveSlot.id !== this.effectState.move) {
          pokemon.disableMove(moveSlot.id, false, this.effectState.sourceEffect);
        }
      }
    }

// cond:mustrecharge.onBeforeMove
onBeforeMove(pokemon) {
      this.add("cant", pokemon, "recharge");
      pokemon.removeVolatile("mustrecharge");
      pokemon.removeVolatile("truant");
      return null;
    }

// cond:mustrecharge.onStart
onStart(pokemon) {
      this.add("-mustrecharge", pokemon);
    }

// cond:futuremove.onStart
onStart(target) {
      this.effectState.targetSlot = target.getSlot();
      this.effectState.endingTurn = this.turn - 1 + 2;
      if (this.effectState.endingTurn >= 254) {
        this.hint(`In Gen 8+, Future attacks will never resolve when used on the 255th turn or later.`);
      }
    }

// cond:futuremove.onResidual
onResidual(target) {
      if (this.getOverflowedTurnCount() < this.effectState.endingTurn) return;
      target.side.removeSlotCondition(this.getAtSlot(this.effectState.targetSlot), "futuremove");
    }

// cond:futuremove.onEnd
onEnd(target) {
      const data = this.effectState;
      const move = this.dex.moves.get(data.move);
      if (target.fainted || target === data.source) {
        this.hint(`${move.name} did not hit because the target is ${target.fainted ? "fainted" : "the user"}.`);
        return;
      }
      this.add("-end", target, "move: " + move.name);
      target.removeVolatile("Protect");
      target.removeVolatile("Endure");
      if (data.source.hasAbility("infiltrator") && this.gen >= 6) {
        data.moveData.infiltrates = true;
      }
      if (data.source.hasAbility("normalize") && this.gen >= 6) {
        data.moveData.type = "Normal";
      }
      const hitMove = new this.dex.Move(data.moveData);
      this.actions.trySpreadMoveHit([target], data.source, hitMove, true);
      if (data.source.isActive && data.source.hasItem("lifeorb") && this.gen >= 5) {
        this.singleEvent("AfterMoveSecondarySelf", data.source.getItem(), data.source.itemState, data.source, target, data.source.getItem());
      }
      this.activeMove = null;
      this.checkWin();
    }

// cond:healreplacement.onStart
onStart(target, source, sourceEffect) {
      this.effectState.sourceEffect = sourceEffect;
      this.add("-activate", source, "healreplacement");
    }

// cond:healreplacement.onSwitchIn
onSwitchIn(target) {
      if (!target.fainted) {
        target.heal(target.maxhp);
        this.add("-heal", target, target.getHealth, "[from] move: " + this.effectState.sourceEffect, "[zeffect]");
        target.side.removeSlotCondition(target, "healreplacement");
      }
    }

// cond:stall.onStart
onStart() {
      this.effectState.counter = 3;
    }

// cond:stall.onStallMove
onStallMove(pokemon) {
      const counter = this.effectState.counter || 1;
      this.debug(`Success chance: ${Math.round(100 / counter)}%`);
      const success = this.randomChance(1, counter);
      if (!success) delete pokemon.volatiles["stall"];
      return success;
    }

// cond:stall.onRestart
onRestart() {
      if (this.effectState.counter < this.effect.counterMax) {
        this.effectState.counter *= 3;
      }
      this.effectState.duration = 2;
    }

// cond:gem.onBasePower
onBasePower(basePower, user, target, move) {
      this.debug("Gem Boost");
      return this.chainModify([5325, 4096]);
    }

// cond:raindance.durationCallback
durationCallback(source, effect) {
      if (source?.hasItem("damprock")) {
        return 8;
      }
      return 5;
    }

// cond:raindance.onWeatherModifyDamage
onWeatherModifyDamage(damage, attacker, defender, move) {
      if (defender.effectiveWeather() !== "raindance") return;
      if (move.type === "Water") {
        this.debug("rain water boost");
        return this.chainModify(1.5);
      }
      if (move.type === "Fire") {
        this.debug("rain fire suppress");
        return this.chainModify(0.5);
      }
    }

// cond:raindance.onFieldStart
onFieldStart(field, source, effect) {
      if (effect?.effectType === "Ability") {
        if (this.gen <= 5) this.effectState.duration = 0;
        this.add("-weather", "RainDance", "[from] ability: " + effect.name, `[of] ${source}`);
      } else {
        this.add("-weather", "RainDance");
      }
    }

// cond:raindance.onFieldResidual
onFieldResidual() {
      this.add("-weather", "RainDance", "[upkeep]");
      this.eachEvent("Weather");
    }

// cond:raindance.onFieldEnd
onFieldEnd() {
      this.add("-weather", "none");
    }

// cond:primordialsea.onTryMove
onTryMove(attacker, defender, move) {
      if (move.type === "Fire" && move.category !== "Status") {
        this.debug("Primordial Sea fire suppress");
        this.add("-fail", attacker, move, "[from] Primordial Sea");
        this.attrLastMove("[still]");
        return null;
      }
    }

// cond:primordialsea.onWeatherModifyDamage
onWeatherModifyDamage(damage, attacker, defender, move) {
      if (defender.effectiveWeather() !== "primordialsea") return;
      if (move.type === "Water") {
        this.debug("Rain water boost");
        return this.chainModify(1.5);
      }
    }

// cond:primordialsea.onFieldStart
onFieldStart(field, source, effect) {
      this.add("-weather", "PrimordialSea", "[from] ability: " + effect.name, `[of] ${source}`);
    }

// cond:primordialsea.onFieldResidual
onFieldResidual() {
      this.add("-weather", "PrimordialSea", "[upkeep]");
      this.eachEvent("Weather");
    }

// cond:primordialsea.onFieldEnd
onFieldEnd() {
      this.add("-weather", "none");
    }

// cond:sunnyday.durationCallback
durationCallback(source, effect) {
      if (source?.hasItem("heatrock")) {
        return 8;
      }
      return 5;
    }

// cond:sunnyday.onWeatherModifyDamage
onWeatherModifyDamage(damage, attacker, defender, move) {
      if (move.id === "hydrosteam" && attacker.effectiveWeather() === "sunnyday") {
        this.debug("Sunny Day Hydro Steam boost");
        return this.chainModify(1.5);
      }
      if (defender.effectiveWeather() !== "sunnyday") return;
      if (move.type === "Fire") {
        this.debug("Sunny Day fire boost");
        return this.chainModify(1.5);
      }
      if (move.type === "Water") {
        this.debug("Sunny Day water suppress");
        return this.chainModify(0.5);
      }
    }

// cond:sunnyday.onFieldStart
onFieldStart(battle, source, effect) {
      if (effect?.effectType === "Ability") {
        if (this.gen <= 5) this.effectState.duration = 0;
        this.add("-weather", "SunnyDay", "[from] ability: " + effect.name, `[of] ${source}`);
      } else {
        this.add("-weather", "SunnyDay");
      }
    }

// cond:sunnyday.onImmunity
onImmunity(type, pokemon) {
      if (pokemon.effectiveWeather() !== "sunnyday") return;
      if (type === "frz") return false;
    }

// cond:sunnyday.onFieldResidual
onFieldResidual() {
      this.add("-weather", "SunnyDay", "[upkeep]");
      this.eachEvent("Weather");
    }

// cond:sunnyday.onFieldEnd
onFieldEnd() {
      this.add("-weather", "none");
    }

// cond:desolateland.onTryMove
onTryMove(attacker, defender, move) {
      if (move.type === "Water" && move.category !== "Status") {
        this.debug("Desolate Land water suppress");
        this.add("-fail", attacker, move, "[from] Desolate Land");
        this.attrLastMove("[still]");
        return null;
      }
    }

// cond:desolateland.onWeatherModifyDamage
onWeatherModifyDamage(damage, attacker, defender, move) {
      if (defender.effectiveWeather() !== "desolateland") return;
      if (move.type === "Fire") {
        this.debug("Desolate Land fire boost");
        return this.chainModify(1.5);
      }
    }

// cond:desolateland.onFieldStart
onFieldStart(field, source, effect) {
      this.add("-weather", "DesolateLand", "[from] ability: " + effect.name, `[of] ${source}`);
    }

// cond:desolateland.onImmunity
onImmunity(type, pokemon) {
      if (pokemon.effectiveWeather() !== "desolateland") return;
      if (type === "frz") return false;
    }

// cond:desolateland.onFieldResidual
onFieldResidual() {
      this.add("-weather", "DesolateLand", "[upkeep]");
      this.eachEvent("Weather");
    }

// cond:desolateland.onFieldEnd
onFieldEnd() {
      this.add("-weather", "none");
    }

// cond:sandstorm.durationCallback
durationCallback(source, effect) {
      if (source?.hasItem("smoothrock")) {
        return 8;
      }
      return 5;
    }

// cond:sandstorm.onModifySpD
onModifySpD(spd, pokemon) {
      if (pokemon.hasType("Rock") && pokemon.effectiveWeather() === "sandstorm") {
        return this.modify(spd, 1.5);
      }
    }

// cond:sandstorm.onFieldStart
onFieldStart(field, source, effect) {
      if (effect?.effectType === "Ability") {
        if (this.gen <= 5) this.effectState.duration = 0;
        this.add("-weather", "Sandstorm", "[from] ability: " + effect.name, `[of] ${source}`);
      } else {
        this.add("-weather", "Sandstorm");
      }
    }

// cond:sandstorm.onFieldResidual
onFieldResidual() {
      this.add("-weather", "Sandstorm", "[upkeep]");
      if (this.field.isWeather("sandstorm")) this.eachEvent("Weather");
    }

// cond:sandstorm.onWeather
onWeather(target) {
      this.damage(target.baseMaxhp / 16);
    }

// cond:sandstorm.onFieldEnd
onFieldEnd() {
      this.add("-weather", "none");
    }

// cond:hail.durationCallback
durationCallback(source, effect) {
      if (source?.hasItem("icyrock")) {
        return 8;
      }
      return 5;
    }

// cond:hail.onFieldStart
onFieldStart(field, source, effect) {
      if (effect?.effectType === "Ability") {
        if (this.gen <= 5) this.effectState.duration = 0;
        this.add("-weather", "Hail", "[from] ability: " + effect.name, `[of] ${source}`);
      } else {
        this.add("-weather", "Hail");
      }
    }

// cond:hail.onFieldResidual
onFieldResidual() {
      this.add("-weather", "Hail", "[upkeep]");
      if (this.field.isWeather("hail")) this.eachEvent("Weather");
    }

// cond:hail.onWeather
onWeather(target) {
      this.damage(target.baseMaxhp / 16);
    }

// cond:hail.onFieldEnd
onFieldEnd() {
      this.add("-weather", "none");
    }

// cond:snowscape.durationCallback
durationCallback(source, effect) {
      if (source?.hasItem("icyrock")) {
        return 8;
      }
      return 5;
    }

// cond:snowscape.onModifyDef
onModifyDef(def, pokemon) {
      if (pokemon.hasType("Ice") && pokemon.effectiveWeather() === "snowscape") {
        return this.modify(def, 1.5);
      }
    }

// cond:snowscape.onFieldStart
onFieldStart(field, source, effect) {
      if (effect?.effectType === "Ability") {
        if (this.gen <= 5) this.effectState.duration = 0;
        this.add("-weather", "Snowscape", "[from] ability: " + effect.name, `[of] ${source}`);
      } else {
        this.add("-weather", "Snowscape");
      }
    }

// cond:snowscape.onFieldResidual
onFieldResidual() {
      this.add("-weather", "Snowscape", "[upkeep]");
      if (this.field.isWeather("snowscape")) this.eachEvent("Weather");
    }

// cond:snowscape.onFieldEnd
onFieldEnd() {
      this.add("-weather", "none");
    }

// cond:deltastream.onEffectiveness
onEffectiveness(typeMod, target, type, move) {
      if (move && move.effectType === "Move" && move.category !== "Status" && type === "Flying" && typeMod > 0) {
        this.add("-fieldactivate", "Delta Stream");
        return 0;
      }
    }

// cond:deltastream.onFieldStart
onFieldStart(field, source, effect) {
      this.add("-weather", "DeltaStream", "[from] ability: " + effect.name, `[of] ${source}`);
    }

// cond:deltastream.onFieldResidual
onFieldResidual() {
      this.add("-weather", "DeltaStream", "[upkeep]");
      this.eachEvent("Weather");
    }

// cond:deltastream.onFieldEnd
onFieldEnd() {
      this.add("-weather", "none");
    }

// cond:dynamax.onStart
onStart(pokemon) {
      this.effectState.turns = 0;
      pokemon.removeVolatile("minimize");
      pokemon.removeVolatile("substitute");
      if (pokemon.volatiles["torment"]) {
        delete pokemon.volatiles["torment"];
        this.add("-end", pokemon, "Torment", "[silent]");
      }
      if (["cramorantgulping", "cramorantgorging"].includes(pokemon.species.id) && !pokemon.transformed) {
        pokemon.formeChange("cramorant");
      }
      this.add("-start", pokemon, "Dynamax", pokemon.gigantamax ? "Gmax" : "");
      if (pokemon.baseSpecies.name === "Shedinja") return;
      const ratio = 1.5 + pokemon.dynamaxLevel * 0.05;
      pokemon.maxhp = Math.floor(pokemon.maxhp * ratio);
      pokemon.hp = Math.floor(pokemon.hp * ratio);
      this.add("-heal", pokemon, pokemon.getHealth, "[silent]");
    }

// cond:dynamax.onTryAddVolatile
onTryAddVolatile(status, pokemon) {
      if (status.id === "flinch") return null;
    }

// cond:dynamax.onBeforeSwitchOut
onBeforeSwitchOut(pokemon) {
      pokemon.removeVolatile("dynamax");
    }

// cond:dynamax.onSourceModifyDamage
onSourceModifyDamage(damage, source, target, move) {
      if (move.id === "behemothbash" || move.id === "behemothblade" || move.id === "dynamaxcannon") {
        return this.chainModify(2);
      }
    }

// cond:dynamax.onDragOut
onDragOut(pokemon) {
      this.add("-block", pokemon, "Dynamax");
      return null;
    }

// cond:dynamax.onResidual
onResidual() {
      this.effectState.turns++;
    }

// cond:dynamax.onEnd
onEnd(pokemon) {
      this.add("-end", pokemon, "Dynamax");
      if (pokemon.baseSpecies.name === "Shedinja") return;
      pokemon.hp = pokemon.getUndynamaxedHP();
      pokemon.maxhp = pokemon.baseMaxhp;
      this.add("-heal", pokemon, pokemon.getHealth, "[silent]");
    }

// cond:commanded.onStart
onStart(pokemon) {
      this.boost({ atk: 2, spa: 2, spe: 2, def: 2, spd: 2 }, pokemon);
    }

// cond:commanded.onDragOut
onDragOut() {
      return false;
    }

// cond:commanded.onTrapPokemon
onTrapPokemon(pokemon) {
      pokemon.trapped = true;
    }

// cond:commanding.onDragOut
onDragOut() {
      return false;
    }

// cond:commanding.onTrapPokemon
onTrapPokemon(pokemon) {
      pokemon.trapped = true;
    }

// cond:commanding.onBeforeTurn
onBeforeTurn(pokemon) {
      this.queue.cancelAction(pokemon);
    }

// cond:arceus.onType
onType(types, pokemon) {
      if (pokemon.transformed || pokemon.ability !== "multitype" && this.gen >= 8) return types;
      let type = "Normal";
      if (pokemon.ability === "multitype") {
        type = pokemon.getItem().onPlate;
        if (!type) {
          type = "Normal";
        }
      }
      return [type];
    }

// cond:silvally.onType
onType(types, pokemon) {
      if (pokemon.transformed || pokemon.ability !== "rkssystem" && this.gen >= 8) return types;
      let type = "Normal";
      if (pokemon.ability === "rkssystem") {
        type = pokemon.getItem().onMemory;
        if (!type) {
          type = "Normal";
        }
      }
      return [type];
    }

// cond:zacian.onBattleStart
onBattleStart(pokemon) {
      if (pokemon.item !== "rustedsword") return;
      const rawSpecies = this.dex.species.get("Zacian-Crowned");
      const species = pokemon.setSpecies(rawSpecies);
      if (!species) return;
      pokemon.baseSpecies = rawSpecies;
      pokemon.details = pokemon.getUpdatedDetails();
      pokemon.setAbility(species.abilities["0"], null, null, true);
      pokemon.baseAbility = pokemon.ability;
      const ironHeadIndex = pokemon.baseMoves.indexOf("ironhead");
      if (ironHeadIndex >= 0) {
        const move = this.dex.moves.get("behemothblade");
        const pp = this.calculatePP(move, pokemon.ppUps[ironHeadIndex]);
        pokemon.baseMoveSlots[ironHeadIndex] = {
          move: move.name,
          id: move.id,
          pp,
          maxpp: pp,
          target: move.target,
          disabled: false,
          disabledSource: "",
          used: false
        };
        pokemon.moveSlots = pokemon.baseMoveSlots.slice();
      }
    }

// cond:zamazenta.onBattleStart
onBattleStart(pokemon) {
      if (pokemon.item !== "rustedshield") return;
      const rawSpecies = this.dex.species.get("Zamazenta-Crowned");
      const species = pokemon.setSpecies(rawSpecies);
      if (!species) return;
      pokemon.baseSpecies = rawSpecies;
      pokemon.details = pokemon.getUpdatedDetails();
      pokemon.setAbility(species.abilities["0"], null, null, true);
      pokemon.baseAbility = pokemon.ability;
      const ironHeadIndex = pokemon.baseMoves.indexOf("ironhead");
      if (ironHeadIndex >= 0) {
        const move = this.dex.moves.get("behemothbash");
        const pp = this.calculatePP(move, pokemon.ppUps[ironHeadIndex]);
        pokemon.baseMoveSlots[ironHeadIndex] = {
          move: move.name,
          id: move.id,
          pp,
          maxpp: pp,
          target: move.target,
          disabled: false,
          disabledSource: "",
          used: false
        };
        pokemon.moveSlots = pokemon.baseMoveSlots.slice();
      }
    }

// cond:rolloutstorage.onBasePower
onBasePower(relayVar, source, target, move) {
      let bp = Math.max(1, move.basePower);
      bp *= 2 ** source.volatiles["rolloutstorage"].contactHitCount;
      if (source.volatiles["defensecurl"]) {
        bp *= 2;
      }
      source.removeVolatile("rolloutstorage");
      return bp;
    }

// cond:protect.onStart
onStart(target) {
        this.add("-singleturn", target, "Protect");
      }

// cond:protect.onTryHit
onTryHit(target, source, move) {
        if (this.checkMoveBypassesProtect(move, source, target)) return;
        if (move.smartTarget) {
          move.smartTarget = false;
        } else {
          this.add("-activate", target, "move: Protect");
        }
        const lockedmove = source.getVolatile("lockedmove");
        if (lockedmove) {
          if (source.volatiles["lockedmove"].duration === 2) {
            delete source.volatiles["lockedmove"];
          }
        }
        return this.NOT_FAIL;
      }

// cond:tailwind.durationCallback
durationCallback(target, source, effect) {
        if (source?.hasAbility("persistent")) {
          this.add("-activate", source, "ability: Persistent", "[move] Tailwind");
          return 6;
        }
        return 4;
      }

// cond:tailwind.onSideStart
onSideStart(side, source) {
        if (source?.hasAbility("persistent")) {
          this.add("-sidestart", side, "move: Tailwind", "[persistent]");
        } else {
          this.add("-sidestart", side, "move: Tailwind");
        }
      }

// cond:tailwind.onModifySpe
onModifySpe(spe, pokemon) {
        return this.chainModify(2);
      }

// cond:tailwind.onSideEnd
onSideEnd(side) {
        this.add("-sideend", side, "move: Tailwind");
      }

// cond:trickroom.durationCallback
durationCallback(source, effect) {
        if (source?.hasAbility("persistent")) {
          this.add("-activate", source, "ability: Persistent", "[move] Trick Room");
          return 7;
        }
        return 5;
      }

// cond:trickroom.onFieldStart
onFieldStart(target, source) {
        if (source?.hasAbility("persistent")) {
          this.add("-fieldstart", "move: Trick Room", `[of] ${source}`, "[persistent]");
        } else {
          this.add("-fieldstart", "move: Trick Room", `[of] ${source}`);
        }
      }

// cond:trickroom.onFieldRestart
onFieldRestart(target, source) {
        this.field.removePseudoWeather("trickroom");
      }

// cond:trickroom.onFieldEnd
onFieldEnd() {
        this.add("-fieldend", "move: Trick Room");
      }

// cond:helpinghand.onStart
onStart(target, source) {
        this.effectState.multiplier = 1.5;
        this.add("-singleturn", target, "Helping Hand", `[of] ${source}`);
      }

// cond:helpinghand.onRestart
onRestart(target, source) {
        this.effectState.multiplier *= 1.5;
        this.add("-singleturn", target, "Helping Hand", `[of] ${source}`);
      }

// cond:helpinghand.onBasePower
onBasePower(basePower) {
        this.debug("Boosting from Helping Hand: " + this.effectState.multiplier);
        return this.chainModify(this.effectState.multiplier);
      }

// cond:followme.onStart
onStart(target, source, effect) {
        if (effect?.id === "zpower") {
          this.add("-singleturn", target, "move: Follow Me", "[zeffect]");
        } else {
          this.add("-singleturn", target, "move: Follow Me");
        }
      }

// cond:followme.onFoeRedirectTarget
onFoeRedirectTarget(target, source, source2, move) {
        if (!this.effectState.target.isSkyDropped() && this.validTarget(this.effectState.target, source, move.target)) {
          if (move.smartTarget) move.smartTarget = false;
          this.debug("Follow Me redirected target of move");
          return this.effectState.target;
        }
      }

// cond:throatchop.onStart
onStart(target) {
        this.add("-start", target, "Throat Chop", "[silent]");
      }

// cond:throatchop.onDisableMove
onDisableMove(pokemon) {
        for (const moveSlot of pokemon.moveSlots) {
          if (this.dex.moves.get(moveSlot.id).flags["sound"]) {
            pokemon.disableMove(moveSlot.id);
          }
        }
      }

// cond:throatchop.onBeforeMove
onBeforeMove(pokemon, target, move) {
        if (!move.isZOrMaxPowered && move.flags["sound"]) {
          this.add("cant", pokemon, "move: Throat Chop");
          return false;
        }
      }

// cond:throatchop.onModifyMove
onModifyMove(move, pokemon, target) {
        if (!move.isZOrMaxPowered && move.flags["sound"]) {
          this.add("cant", pokemon, "move: Throat Chop");
          return false;
        }
      }

// cond:throatchop.onEnd
onEnd(target) {
        this.add("-end", target, "Throat Chop", "[silent]");
      }

// cond:encore.onStart
onStart(target) {
        let move = target.lastMove;
        if (!move || target.volatiles["dynamax"]) return false;
        if (move.isMax && move.baseMove) move = this.dex.moves.get(move.baseMove);
        const moveSlot = target.getMoveData(move.id);
        if (move.isZ || move.isMax || move.flags["failencore"] || !moveSlot || moveSlot.pp <= 0) {
          return false;
        }
        this.effectState.move = move.id;
        this.add("-start", target, "Encore");
        const action = this.queue.willMove(target);
        if (!action) {
          this.effectState.duration++;
        } else if (action.moveid !== move.id && !target.hasItem("mentalherb")) {
          const priority = action.priority - this.dex.moves.get(action.moveid).priority + this.dex.moves.get(move.id).priority;
          this.queue.changeAction(target, {
            choice: "move",
            // target: undefined,
            // targetLoc: undefined,
            moveid: move.id,
            order: action.order
          });
          this.queue.willMove(target).priority = priority;
        }
      }

// cond:encore.onOverrideAction
onOverrideAction(pokemon, target, move) {
        if (move.id !== this.effectState.move) return this.effectState.move;
      }

// cond:encore.onResidual
onResidual(target) {
        const moveSlot = target.getMoveData(this.effectState.move);
        if (!moveSlot || moveSlot.pp <= 0) {
          target.removeVolatile("encore");
        }
      }

// cond:encore.onEnd
onEnd(target) {
        this.add("-end", target, "Encore");
      }

// cond:encore.onDisableMove
onDisableMove(pokemon) {
        if (!this.effectState.move || !pokemon.hasMove(this.effectState.move)) {
          return;
        }
        for (const moveSlot of pokemon.moveSlots) {
          if (moveSlot.id !== this.effectState.move) {
            pokemon.disableMove(moveSlot.id);
          }
        }
      }

// cond:ragepowder.onStart
onStart(pokemon) {
        this.add("-singleturn", pokemon, "move: Rage Powder");
      }

// cond:ragepowder.onFoeRedirectTarget
onFoeRedirectTarget(target, source, source2, move) {
        const ragePowderUser = this.effectState.target;
        if (ragePowderUser.isSkyDropped()) return;
        if (source.runStatusImmunity("powder") && this.validTarget(ragePowderUser, source, move.target)) {
          if (move.smartTarget) move.smartTarget = false;
          this.debug("Rage Powder redirected target of move");
          return ragePowderUser;
        }
      }

// cond:wideguard.onSideStart
onSideStart(target, source) {
        this.add("-singleturn", source, "Wide Guard");
      }

// cond:wideguard.onTryHit
onTryHit(target, source, move) {
        if (move?.target !== "allAdjacent" && move.target !== "allAdjacentFoes") {
          return;
        }
        if (this.checkMoveBypassesProtect(move, source, target)) return;
        this.add("-activate", target, "move: Wide Guard");
        const lockedmove = source.getVolatile("lockedmove");
        if (lockedmove) {
          if (source.volatiles["lockedmove"].duration === 2) {
            delete source.volatiles["lockedmove"];
          }
        }
        return this.NOT_FAIL;
      }

// cond:perishsong.onEnd
onEnd(target) {
        this.add("-start", target, "perish0");
        target.faint();
      }

// cond:perishsong.onResidual
onResidual(pokemon) {
        const duration = pokemon.volatiles["perishsong"].duration;
        this.add("-start", pokemon, `perish${duration}`);
      }

// cond:auroraveil.durationCallback
durationCallback(target, source, effect) {
        if (source?.hasItem("lightclay")) {
          return 8;
        }
        return 5;
      }

// cond:auroraveil.onAnyModifyDamage
onAnyModifyDamage(damage, source, target, move) {
        if (target !== source && this.effectState.target.hasAlly(target)) {
          if (target.side.getSideCondition("reflect") && this.getCategory(move) === "Physical" || target.side.getSideCondition("lightscreen") && this.getCategory(move) === "Special") {
            return;
          }
          if (!target.getMoveHitData(move).crit && !move.infiltrates) {
            this.debug("Aurora Veil weaken");
            if (this.activePerHalf > 1) return this.chainModify([2732, 4096]);
            return this.chainModify(0.5);
          }
        }
      }

// cond:auroraveil.onSideStart
onSideStart(side) {
        this.add("-sidestart", side, "move: Aurora Veil");
      }

// cond:auroraveil.onSideEnd
onSideEnd(side) {
        this.add("-sideend", side, "move: Aurora Veil");
      }

// cond:lightscreen.durationCallback
durationCallback(target, source, effect) {
        if (source?.hasItem("lightclay")) {
          return 8;
        }
        return 5;
      }

// cond:lightscreen.onAnyModifyDamage
onAnyModifyDamage(damage, source, target, move) {
        if (target !== source && this.effectState.target.hasAlly(target) && this.getCategory(move) === "Special") {
          if (!target.getMoveHitData(move).crit && !move.infiltrates) {
            this.debug("Light Screen weaken");
            if (this.activePerHalf > 1) return this.chainModify([2732, 4096]);
            return this.chainModify(0.5);
          }
        }
      }

// cond:lightscreen.onSideStart
onSideStart(side) {
        this.add("-sidestart", side, "move: Light Screen");
      }

// cond:lightscreen.onSideEnd
onSideEnd(side) {
        this.add("-sideend", side, "move: Light Screen");
      }

// cond:reflect.durationCallback
durationCallback(target, source, effect) {
        if (source?.hasItem("lightclay")) {
          return 8;
        }
        return 5;
      }

// cond:reflect.onAnyModifyDamage
onAnyModifyDamage(damage, source, target, move) {
        if (target !== source && this.effectState.target.hasAlly(target) && this.getCategory(move) === "Physical") {
          if (!target.getMoveHitData(move).crit && !move.infiltrates) {
            this.debug("Reflect weaken");
            if (this.activePerHalf > 1) return this.chainModify([2732, 4096]);
            return this.chainModify(0.5);
          }
        }
      }

// cond:reflect.onSideStart
onSideStart(side) {
        this.add("-sidestart", side, "Reflect");
      }

// cond:reflect.onSideEnd
onSideEnd(side) {
        this.add("-sideend", side, "Reflect");
      }

// cond:roost.onStart
onStart(target) {
        if (target.terastallized) {
          if (target.hasType("Flying")) {
            this.add("-hint", "If a Terastallized Pokemon uses Roost, it remains Flying-type.");
          }
          return false;
        }
        this.add("-singleturn", target, "move: Roost");
      }

// cond:roost.onType
onType(types, pokemon) {
        this.effectState.typeWas = types;
        return types.filter((type) => type !== "Flying");
      }

// cond:imprison.onStart
onStart(target) {
        this.add("-start", target, "move: Imprison");
      }

// cond:imprison.onFoeDisableMove
onFoeDisableMove(pokemon) {
        for (const moveSlot of this.effectState.source.moveSlots) {
          if (moveSlot.id === "struggle") continue;
          pokemon.disableMove(moveSlot.id, true);
        }
        pokemon.maybeDisabled = true;
      }

// cond:imprison.onFoeBeforeMove
onFoeBeforeMove(attacker, defender, move) {
        if (move.id !== "struggle" && this.effectState.source.hasMove(move.id) && !move.isZOrMaxPowered) {
          this.add("cant", attacker, "move: Imprison", move);
          return false;
        }
      }

// cond:spikyshield.onStart
onStart(target) {
        this.add("-singleturn", target, "move: Protect");
      }

// cond:spikyshield.onTryHit
onTryHit(target, source, move) {
        if (this.checkMoveBypassesProtect(move, source, target)) return;
        if (move.smartTarget) {
          move.smartTarget = false;
        } else {
          this.add("-activate", target, "move: Protect");
        }
        const lockedmove = source.getVolatile("lockedmove");
        if (lockedmove) {
          if (source.volatiles["lockedmove"].duration === 2) {
            delete source.volatiles["lockedmove"];
          }
        }
        if (this.checkMoveMakesContact(move, source, target)) {
          this.damage(source.baseMaxhp / 8, source, target);
        }
        return this.NOT_FAIL;
      }

// cond:spikyshield.onHit
onHit(target, source, move) {
        if (move.isZOrMaxPowered && this.checkMoveMakesContact(move, source, target)) {
          this.damage(source.baseMaxhp / 8, source, target);
        }
      }

// cond:glaiverush.onStart
onStart(pokemon) {
        this.add("-singlemove", pokemon, "Glaive Rush", "[silent]");
      }

// cond:glaiverush.onAccuracy
onAccuracy() {
        return true;
      }

// cond:glaiverush.onSourceModifyDamage
onSourceModifyDamage() {
        return this.chainModify(2);
      }

// cond:glaiverush.onBeforeMove
onBeforeMove(pokemon) {
        this.debug("removing Glaive Rush drawback before attack");
        pokemon.removeVolatile("glaiverush");
      }

// cond:yawn.onStart
onStart(target, source) {
        this.add("-start", target, "move: Yawn", `[of] ${source}`);
      }

// cond:yawn.onEnd
onEnd(target) {
        this.add("-end", target, "move: Yawn", "[silent]");
        target.trySetStatus("slp", this.effectState.source);
      }

// cond:taunt.onStart
onStart(target) {
        if (target.activeTurns && !this.queue.willMove(target)) {
          this.effectState.duration++;
        }
        this.add("-start", target, "move: Taunt");
      }

// cond:taunt.onEnd
onEnd(target) {
        this.add("-end", target, "move: Taunt");
      }

// cond:taunt.onDisableMove
onDisableMove(pokemon) {
        for (const moveSlot of pokemon.moveSlots) {
          const move = this.dex.moves.get(moveSlot.id);
          if (move.category === "Status" && move.id !== "mefirst") {
            pokemon.disableMove(moveSlot.id);
          }
        }
      }

// cond:taunt.onBeforeMove
onBeforeMove(attacker, defender, move) {
        if (!(move.isZ && move.isZOrMaxPowered) && move.category === "Status" && move.id !== "mefirst") {
          this.add("cant", attacker, "move: Taunt", move);
          return false;
        }
      }

// cond:banefulbunker.onStart
onStart(target) {
        this.add("-singleturn", target, "move: Protect");
      }

// cond:banefulbunker.onTryHit
onTryHit(target, source, move) {
        if (this.checkMoveBypassesProtect(move, source, target)) return;
        if (move.smartTarget) {
          move.smartTarget = false;
        } else {
          this.add("-activate", target, "move: Protect");
        }
        const lockedmove = source.getVolatile("lockedmove");
        if (lockedmove) {
          if (source.volatiles["lockedmove"].duration === 2) {
            delete source.volatiles["lockedmove"];
          }
        }
        if (this.checkMoveMakesContact(move, source, target)) {
          source.trySetStatus("psn", target);
        }
        return this.NOT_FAIL;
      }

// cond:banefulbunker.onHit
onHit(target, source, move) {
        if (move.isZOrMaxPowered && this.checkMoveMakesContact(move, source, target)) {
          source.trySetStatus("psn", target);
        }
      }

// cond:kingsshield.onStart
onStart(target) {
        this.add("-singleturn", target, "Protect");
      }

// cond:kingsshield.onTryHit
onTryHit(target, source, move) {
        if (this.checkMoveBypassesProtect(move, source, target, false)) return;
        if (move.smartTarget) {
          move.smartTarget = false;
        } else {
          this.add("-activate", target, "move: Protect");
        }
        const lockedmove = source.getVolatile("lockedmove");
        if (lockedmove) {
          if (source.volatiles["lockedmove"].duration === 2) {
            delete source.volatiles["lockedmove"];
          }
        }
        if (this.checkMoveMakesContact(move, source, target)) {
          this.boost({ atk: -1 }, source, target, this.dex.getActiveMove("King's Shield"));
        }
        return this.NOT_FAIL;
      }

// cond:kingsshield.onHit
onHit(target, source, move) {
        if (move.isZOrMaxPowered && this.checkMoveMakesContact(move, source, target)) {
          this.boost({ atk: -1 }, source, target, this.dex.getActiveMove("King's Shield"));
        }
      }

// cond:disable.onStart
onStart(pokemon, source, effect) {
        if (this.queue.willMove(pokemon) || pokemon === this.activePokemon && this.activeMove && !this.activeMove.isExternal) {
          this.effectState.duration--;
        }
        if (!pokemon.lastMove) {
          this.debug(`Pokemon hasn't moved yet`);
          return false;
        }
        for (const moveSlot of pokemon.moveSlots) {
          if (moveSlot.id === pokemon.lastMove.id) {
            if (!moveSlot.pp) {
              this.debug("Move out of PP");
              return false;
            }
          }
        }
        if (effect.effectType === "Ability") {
          this.add("-start", pokemon, "Disable", pokemon.lastMove.name, "[from] ability: " + effect.name, `[of] ${source}`);
        } else {
          this.add("-start", pokemon, "Disable", pokemon.lastMove.name);
        }
        this.effectState.move = pokemon.lastMove.id;
      }

// cond:disable.onEnd
onEnd(pokemon) {
        this.add("-end", pokemon, "Disable");
      }

// cond:disable.onBeforeMove
onBeforeMove(attacker, defender, move) {
        if (!(move.isZ && move.isZOrMaxPowered) && move.id === this.effectState.move && !move.flags["cantusetwice"]) {
          this.add("cant", attacker, "Disable", move);
          return false;
        }
      }

// cond:disable.onDisableMove
onDisableMove(pokemon) {
        for (const moveSlot of pokemon.moveSlots) {
          if (moveSlot.id === this.effectState.move) {
            pokemon.disableMove(moveSlot.id);
          }
        }
      }

// cond:substitute.onStart
onStart(target, source, effect) {
        if (effect?.id === "shedtail") {
          this.add("-start", target, "Substitute", "[from] move: Shed Tail");
        } else {
          this.add("-start", target, "Substitute");
        }
        this.effectState.hp = Math.floor(target.maxhp / 4);
        if (target.volatiles["partiallytrapped"]) {
          this.add("-end", target, target.volatiles["partiallytrapped"].sourceEffect, "[partiallytrapped]", "[silent]");
          delete target.volatiles["partiallytrapped"];
        }
      }

// cond:substitute.onTryPrimaryHit
onTryPrimaryHit(target, source, move) {
        if (target === source || move.flags["bypasssub"] || move.infiltrates) {
          return;
        }
        let damage = this.actions.getDamage(source, target, move);
        if (!damage && damage !== 0) {
          this.add("-fail", source);
          this.attrLastMove("[still]");
          return null;
        }
        if (damage > target.volatiles["substitute"].hp) {
          damage = target.volatiles["substitute"].hp;
        }
        target.volatiles["substitute"].hp -= damage;
        source.lastDamage = damage;
        if (target.volatiles["substitute"].hp <= 0) {
          if (move.ohko) this.add("-ohko");
          target.removeVolatile("substitute");
        } else {
          this.add("-activate", target, "move: Substitute", "[damage]");
        }
        if (damage) {
          this.actions.applyRecoilDamage(damage, move, source);
        }
        if (move.drain) {
          this.heal(Math.ceil(damage * move.drain[0] / move.drain[1]), source, target, "drain");
        }
        this.singleEvent("AfterSubDamage", move, null, target, source, move, damage);
        this.runEvent("AfterSubDamage", target, source, move, damage);
        return this.HIT_SUBSTITUTE;
      }

// cond:substitute.onEnd
onEnd(target) {
        this.add("-end", target, "Substitute");
      }

// cond:leechseed.onStart
onStart(target) {
        this.add("-start", target, "move: Leech Seed");
      }

// cond:leechseed.onResidual
onResidual(pokemon) {
        const target = this.getAtSlot(pokemon.volatiles["leechseed"].sourceSlot);
        if (!target || target.fainted || target.hp <= 0) {
          this.debug("Nothing to leech into");
          return;
        }
        const damage = this.damage(pokemon.baseMaxhp / 8, pokemon, target);
        if (damage) {
          this.heal(damage, target, pokemon);
        }
      }

// cond:quickguard.onSideStart
onSideStart(target, source) {
        this.add("-singleturn", source, "Quick Guard");
      }

// cond:quickguard.onTryHit
onTryHit(target, source, move) {
        if (move.priority <= 0.1) return;
        if (this.checkMoveBypassesProtect(move, source, target)) return;
        this.add("-activate", target, "move: Quick Guard");
        const lockedmove = source.getVolatile("lockedmove");
        if (lockedmove) {
          if (source.volatiles["lockedmove"].duration === 2) {
            delete source.volatiles["lockedmove"];
          }
        }
        return this.NOT_FAIL;
      }

// cond:healingwish.onSwitchIn
onSwitchIn(target) {
        this.singleEvent("Swap", this.effect, this.effectState, target);
      }

// cond:healingwish.onSwap
onSwap(target) {
        if (!target.fainted && (target.hp < target.maxhp || target.status)) {
          target.heal(target.maxhp);
          target.clearStatus();
          this.add("-heal", target, target.getHealth, "[from] move: Healing Wish");
          target.side.removeSlotCondition(target, "healingwish");
        }
      }

// cond:allyswitch.onStart
onStart() {
        this.effectState.counter = 3;
      }

// cond:allyswitch.onRestart
onRestart(pokemon) {
        const counter = this.effectState.counter || 1;
        this.debug(`Ally Switch success chance: ${Math.round(100 / counter)}%`);
        const success = this.randomChance(1, counter);
        if (!success) {
          delete pokemon.volatiles["allyswitch"];
          return false;
        }
        if (this.effectState.counter < this.effect.counterMax) {
          this.effectState.counter *= 3;
        }
        this.effectState.duration = 2;
      }

// cond:curse.onStart
onStart(pokemon, source) {
        this.add("-start", pokemon, "Curse", `[of] ${source}`);
      }

// cond:curse.onResidual
onResidual(pokemon) {
        this.damage(pokemon.baseMaxhp / 4);
      }

// cond:mistyterrain.durationCallback
durationCallback(source, effect) {
        if (source?.hasItem("terrainextender")) {
          return 8;
        }
        return 5;
      }

// cond:mistyterrain.onSetStatus
onSetStatus(status, target, source, effect) {
        if (!target.isGrounded() || target.isSemiInvulnerable()) return;
        if (effect && (effect.status || effect.id === "yawn")) {
          this.add("-activate", target, "move: Misty Terrain");
        }
        return false;
      }

// cond:mistyterrain.onTryAddVolatile
onTryAddVolatile(status, target, source, effect) {
        if (!target.isGrounded() || target.isSemiInvulnerable()) return;
        if (status.id === "confusion") {
          if (effect.effectType === "Move" && !effect.secondaries) this.add("-activate", target, "move: Misty Terrain");
          return null;
        }
      }

// cond:mistyterrain.onBasePower
onBasePower(basePower, attacker, defender, move) {
        if (move.type === "Dragon" && defender.isGrounded() && !defender.isSemiInvulnerable()) {
          this.debug("misty terrain weaken");
          return this.chainModify(0.5);
        }
      }

// cond:mistyterrain.onFieldStart
onFieldStart(field, source, effect) {
        if (effect?.effectType === "Ability") {
          this.add("-fieldstart", "move: Misty Terrain", "[from] ability: " + effect.name, `[of] ${source}`);
        } else {
          this.add("-fieldstart", "move: Misty Terrain");
        }
      }

// cond:mistyterrain.onFieldEnd
onFieldEnd() {
        this.add("-fieldend", "Misty Terrain");
      }

// cond:psychicterrain.durationCallback
durationCallback(source, effect) {
        if (source?.hasItem("terrainextender")) {
          return 8;
        }
        return 5;
      }

// cond:psychicterrain.onTryHit
onTryHit(target, source, effect) {
        if (effect && (effect.priority <= 0.1 || effect.target === "self")) {
          return;
        }
        if (target.isSemiInvulnerable() || target.isAlly(source)) return;
        if (!target.isGrounded()) {
          const baseMove = this.dex.moves.get(effect.id);
          if (baseMove.priority > 0) {
            this.hint("Psychic Terrain doesn't affect airborne Pok\xE9mon.");
          }
          return;
        }
        this.add("-activate", target, "move: Psychic Terrain");
        return null;
      }

// cond:psychicterrain.onBasePower
onBasePower(basePower, attacker, defender, move) {
        if (move.type === "Psychic" && attacker.isGrounded() && !attacker.isSemiInvulnerable()) {
          this.debug("psychic terrain boost");
          return this.chainModify([5325, 4096]);
        }
      }

// cond:psychicterrain.onFieldStart
onFieldStart(field, source, effect) {
        if (effect?.effectType === "Ability") {
          this.add("-fieldstart", "move: Psychic Terrain", "[from] ability: " + effect.name, `[of] ${source}`);
        } else {
          this.add("-fieldstart", "move: Psychic Terrain");
        }
      }

// cond:psychicterrain.onFieldEnd
onFieldEnd() {
        this.add("-fieldend", "move: Psychic Terrain");
      }

// cond:destinybond.onStart
onStart(pokemon) {
        this.add("-singlemove", pokemon, "Destiny Bond");
      }

// cond:destinybond.onFaint
onFaint(target, source, effect) {
        if (!source || !effect || target.isAlly(source)) return;
        if (effect.effectType === "Move" && !effect.flags["futuremove"]) {
          if (source.volatiles["dynamax"]) {
            this.add("-hint", "Dynamaxed Pok\xE9mon are immune to Destiny Bond.");
            return;
          }
          this.add("-activate", target, "move: Destiny Bond");
          source.faint();
        }
      }

// cond:destinybond.onBeforeMove
onBeforeMove(pokemon, target, move) {
        if (move.id === "destinybond") return;
        this.debug("removing Destiny Bond before attack");
        pokemon.removeVolatile("destinybond");
      }

// cond:destinybond.onMoveAborted
onMoveAborted(pokemon, target, move) {
        pokemon.removeVolatile("destinybond");
      }

// cond:grassyterrain.durationCallback
durationCallback(source, effect) {
        if (source?.hasItem("terrainextender")) {
          return 8;
        }
        return 5;
      }

// cond:grassyterrain.onBasePower
onBasePower(basePower, attacker, defender, move) {
        const weakenedMoves = ["earthquake", "bulldoze", "magnitude"];
        if (weakenedMoves.includes(move.id) && defender.isGrounded() && !defender.isSemiInvulnerable()) {
          this.debug("move weakened by grassy terrain");
          return this.chainModify(0.5);
        }
        if (move.type === "Grass" && attacker.isGrounded()) {
          this.debug("grassy terrain boost");
          return this.chainModify([5325, 4096]);
        }
      }

// cond:grassyterrain.onFieldStart
onFieldStart(field, source, effect) {
        if (effect?.effectType === "Ability") {
          this.add("-fieldstart", "move: Grassy Terrain", "[from] ability: " + effect.name, `[of] ${source}`);
        } else {
          this.add("-fieldstart", "move: Grassy Terrain");
        }
      }

// cond:grassyterrain.onResidual
onResidual(pokemon) {
        if (pokemon.isGrounded() && !pokemon.isSemiInvulnerable()) {
          this.heal(pokemon.baseMaxhp / 16, pokemon, pokemon);
        } else {
          this.debug(`Pokemon semi-invuln or not grounded; Grassy Terrain skipped`);
        }
      }

// cond:grassyterrain.onFieldEnd
onFieldEnd() {
        this.add("-fieldend", "move: Grassy Terrain");
      }

// cond:gravity.durationCallback
durationCallback(source, effect) {
        if (source?.hasAbility("persistent")) {
          this.add("-activate", source, "ability: Persistent", "[move] Gravity");
          return 7;
        }
        return 5;
      }

// cond:gravity.onFieldStart
onFieldStart(target, source) {
        if (source?.hasAbility("persistent")) {
          this.add("-fieldstart", "move: Gravity", "[persistent]");
        } else {
          this.add("-fieldstart", "move: Gravity");
        }
        for (const pokemon of this.getAllActive()) {
          let applies = false;
          if (pokemon.removeVolatile("bounce") || pokemon.removeVolatile("fly")) {
            applies = true;
            this.queue.cancelMove(pokemon);
            pokemon.removeVolatile("twoturnmove");
          }
          if (pokemon.volatiles["skydrop"]) {
            applies = true;
            this.queue.cancelMove(pokemon);
            if (pokemon.volatiles["skydrop"].source) {
              this.add("-end", pokemon.volatiles["twoturnmove"].source, "Sky Drop", "[interrupt]");
            }
            pokemon.removeVolatile("skydrop");
            pokemon.removeVolatile("twoturnmove");
          }
          if (pokemon.volatiles["magnetrise"]) {
            applies = true;
            delete pokemon.volatiles["magnetrise"];
          }
          if (pokemon.volatiles["telekinesis"]) {
            applies = true;
            delete pokemon.volatiles["telekinesis"];
          }
          if (applies) this.add("-activate", pokemon, "move: Gravity");
        }
      }

// cond:gravity.onModifyAccuracy
onModifyAccuracy(accuracy) {
        if (typeof accuracy !== "number") return;
        return this.chainModify([6840, 4096]);
      }

// cond:gravity.onDisableMove
onDisableMove(pokemon) {
        for (const moveSlot of pokemon.moveSlots) {
          if (this.dex.moves.get(moveSlot.id).flags["gravity"]) {
            pokemon.disableMove(moveSlot.id);
          }
        }
      }

// cond:gravity.onBeforeMove
onBeforeMove(pokemon, target, move) {
        if (move.flags["gravity"] && !move.isZ) {
          this.add("cant", pokemon, "move: Gravity", move);
          return false;
        }
      }

// cond:gravity.onModifyMove
onModifyMove(move, pokemon, target) {
        if (move.flags["gravity"] && !move.isZ) {
          this.add("cant", pokemon, "move: Gravity", move);
          return false;
        }
      }

// cond:gravity.onFieldEnd
onFieldEnd() {
        this.add("-fieldend", "move: Gravity");
      }

// cond:safeguard.durationCallback
durationCallback(target, source, effect) {
        if (source?.hasAbility("persistent")) {
          this.add("-activate", source, "ability: Persistent", "[move] Safeguard");
          return 7;
        }
        return 5;
      }

// cond:safeguard.onSetStatus
onSetStatus(status, target, source, effect) {
        if (!effect || !source) return;
        if (effect.id === "yawn") return;
        if (effect.effectType === "Move" && effect.infiltrates && !target.isAlly(source)) return;
        if (target !== source) {
          this.debug("interrupting setStatus");
          if (effect.id === "synchronize" || effect.effectType === "Move" && !effect.secondaries) {
            this.add("-activate", target, "move: Safeguard");
          }
          return null;
        }
      }

// cond:safeguard.onTryAddVolatile
onTryAddVolatile(status, target, source, effect) {
        if (!effect || !source) return;
        if (effect.effectType === "Move" && effect.infiltrates && !target.isAlly(source)) return;
        if ((status.id === "confusion" || status.id === "yawn") && target !== source) {
          if (effect.effectType === "Move" && !effect.secondaries) this.add("-activate", target, "move: Safeguard");
          return null;
        }
      }

// cond:safeguard.onSideStart
onSideStart(side, source) {
        if (source?.hasAbility("persistent")) {
          this.add("-sidestart", side, "Safeguard", "[persistent]");
        } else {
          this.add("-sidestart", side, "Safeguard");
        }
      }

// cond:safeguard.onSideEnd
onSideEnd(side) {
        this.add("-sideend", side, "Safeguard");
      }

// cond:unburden.onModifySpe
onModifySpe(spe, pokemon) {
        if (!pokemon.item && !pokemon.ignoringAbility()) {
          return this.chainModify(2);
        }
      }

// cond:flashfire.onStart
onStart(target) {
        this.add("-start", target, "ability: Flash Fire");
      }

// cond:flashfire.onModifyAtk
onModifyAtk(atk, attacker, defender, move) {
        if (move.type === "Fire" && attacker.hasAbility("flashfire")) {
          this.debug("Flash Fire boost");
          return this.chainModify(1.5);
        }
      }

// cond:flashfire.onModifySpA
onModifySpA(atk, attacker, defender, move) {
        if (move.type === "Fire" && attacker.hasAbility("flashfire")) {
          this.debug("Flash Fire boost");
          return this.chainModify(1.5);
        }
      }

// cond:flashfire.onEnd
onEnd(target) {
        this.add("-end", target, "ability: Flash Fire", "[silent]");
      }

// cond:healblock.durationCallback
durationCallback(target, source, effect) {
        if (effect?.name === "Psychic Noise") {
          return 2;
        }
        if (source?.hasAbility("persistent")) {
          this.add("-activate", source, "ability: Persistent", "[move] Heal Block");
          return 7;
        }
        return 5;
      }

// cond:healblock.onStart
onStart(pokemon, source) {
        this.add("-start", pokemon, "move: Heal Block");
        source.moveThisTurnResult = true;
      }

// cond:healblock.onDisableMove
onDisableMove(pokemon) {
        for (const moveSlot of pokemon.moveSlots) {
          if (this.dex.moves.get(moveSlot.id).flags["heal"]) {
            pokemon.disableMove(moveSlot.id);
          }
        }
      }

// cond:healblock.onBeforeMove
onBeforeMove(pokemon, target, move) {
        if (move.flags["heal"] && !move.isZ && !move.isMax) {
          this.add("cant", pokemon, "move: Heal Block", move);
          return false;
        }
      }

// cond:healblock.onModifyMove
onModifyMove(move, pokemon) {
        if (move.flags["heal"] && !move.isZ && !move.isMax) {
          this.add("cant", pokemon, "move: Heal Block", move);
          return false;
        }
      }

// cond:healblock.onEnd
onEnd(pokemon) {
        this.add("-end", pokemon, "move: Heal Block");
      }

// cond:healblock.onTryHeal
onTryHeal(damage, target, source, effect) {
        if (effect && (effect.id === "zpower" || effect.isZ)) return damage;
        if (source && target !== source && target.hp !== target.maxhp && effect.name === "Pollen Puff") {
          this.attrLastMove("[still]");
          this.add("cant", source, "move: Heal Block", effect);
          return null;
        }
        return false;
      }

// cond:healblock.onRestart
onRestart(target, source, effect) {
        if (effect?.name === "Psychic Noise") return;
        this.add("-fail", target, "move: Heal Block");
        if (!source.moveThisTurnResult) {
          source.moveThisTurnResult = false;
        }
      }

// cond:toxicspikes.onSideStart
onSideStart(side) {
        this.add("-sidestart", side, "move: Toxic Spikes");
        this.effectState.layers = 1;
      }

// cond:toxicspikes.onSideRestart
onSideRestart(side) {
        if (this.effectState.layers >= 2) return false;
        this.add("-sidestart", side, "move: Toxic Spikes");
        this.effectState.layers++;
      }

// cond:toxicspikes.onSwitchIn
onSwitchIn(pokemon) {
        if (!pokemon.isGrounded()) return;
        if (pokemon.hasType("Poison")) {
          this.add("-sideend", pokemon.side, "move: Toxic Spikes", `[of] ${pokemon}`);
          pokemon.side.removeSideCondition("toxicspikes");
        } else if (pokemon.hasType("Steel") || pokemon.hasItem("heavydutyboots")) {
        } else if (this.effectState.layers >= 2) {
          pokemon.trySetStatus("tox", pokemon.side.foe.active[0]);
        } else {
          pokemon.trySetStatus("psn", pokemon.side.foe.active[0]);
        }
      }

// cond:stealthrock.onSideStart
onSideStart(side) {
        this.add("-sidestart", side, "move: Stealth Rock");
      }

// cond:stealthrock.onSwitchIn
onSwitchIn(pokemon) {
        if (pokemon.hasItem("heavydutyboots")) return;
        const typeMod = this.clampIntRange(pokemon.runEffectiveness(this.dex.getActiveMove("stealthrock")), -6, 6);
        this.damage(pokemon.maxhp * 2 ** typeMod / 8);
      }

// cond:spikes.onSideStart
onSideStart(side) {
        this.add("-sidestart", side, "Spikes");
        this.effectState.layers = 1;
      }

// cond:spikes.onSideRestart
onSideRestart(side) {
        if (this.effectState.layers >= 3) return false;
        this.add("-sidestart", side, "Spikes");
        this.effectState.layers++;
      }

// cond:spikes.onSwitchIn
onSwitchIn(pokemon) {
        if (!pokemon.isGrounded() || pokemon.hasItem("heavydutyboots")) return;
        const damageAmounts = [0, 3, 4, 6];
        this.damage(damageAmounts[this.effectState.layers] * pokemon.maxhp / 24);
      }

// cond:attract.onStart
onStart(pokemon, source, effect) {
        if (!(pokemon.gender === "M" && source.gender === "F") && !(pokemon.gender === "F" && source.gender === "M")) {
          this.debug("incompatible gender");
          return false;
        }
        if (!this.runEvent("Attract", pokemon, source)) {
          this.debug("Attract event failed");
          return false;
        }
        if (effect.name === "Cute Charm") {
          this.add("-start", pokemon, "Attract", "[from] ability: Cute Charm", `[of] ${source}`);
        } else if (effect.name === "Destiny Knot") {
          this.add("-start", pokemon, "Attract", "[from] item: Destiny Knot", `[of] ${source}`);
        } else {
          this.add("-start", pokemon, "Attract");
        }
      }

// cond:attract.onUpdate
onUpdate(pokemon) {
        if (this.effectState.source && !this.effectState.source.isActive && pokemon.volatiles["attract"]) {
          this.debug(`Removing Attract volatile on ${pokemon}`);
          pokemon.removeVolatile("attract");
        }
      }

// cond:attract.onBeforeMove
onBeforeMove(pokemon, target, move) {
        this.add("-activate", pokemon, "move: Attract", "[of] " + this.effectState.source);
        if (this.randomChance(1, 2)) {
          this.add("cant", pokemon, "Attract");
          return false;
        }
      }

// cond:attract.onEnd
onEnd(pokemon) {
        this.add("-end", pokemon, "Attract", "[silent]");
      }

// cond:torment.onStart
onStart(pokemon, source, effect) {
        if (pokemon.volatiles["dynamax"]) {
          delete pokemon.volatiles["torment"];
          return false;
        }
        if (effect?.id === "gmaxmeltdown") this.effectState.duration = 3;
        this.add("-start", pokemon, "Torment");
      }

// cond:torment.onEnd
onEnd(pokemon) {
        this.add("-end", pokemon, "Torment");
      }

// cond:torment.onDisableMove
onDisableMove(pokemon) {
        if (pokemon.lastMove && pokemon.lastMove.id !== "struggle") pokemon.disableMove(pokemon.lastMove.id);
      }

// cond:embargo.onStart
onStart(pokemon) {
        this.add("-start", pokemon, "Embargo");
        this.singleEvent("End", pokemon.getItem(), pokemon.itemState, pokemon);
      }

// cond:embargo.onEnd
onEnd(pokemon) {
        this.add("-end", pokemon, "Embargo");
      }

// cond:magnetrise.onStart
onStart(target) {
        this.add("-start", target, "Magnet Rise");
      }

// cond:magnetrise.onImmunity
onImmunity(type) {
        if (type === "Ground") return false;
      }

// cond:magnetrise.onEnd
onEnd(target) {
        this.add("-end", target, "Magnet Rise");
      }

// cond:ingrain.onStart
onStart(pokemon) {
        this.add("-start", pokemon, "move: Ingrain");
      }

// cond:ingrain.onResidual
onResidual(pokemon) {
        this.heal(pokemon.baseMaxhp / 16);
      }

// cond:ingrain.onTrapPokemon
onTrapPokemon(pokemon) {
        pokemon.tryTrap();
      }

// cond:ingrain.onDragOut
onDragOut(pokemon) {
        this.add("-activate", pokemon, "move: Ingrain");
        return null;
      }

// cond:smackdown.onStart
onStart(pokemon) {
        let applies = false;
        if (pokemon.hasType("Flying") || pokemon.hasAbility(["levitate", "eelevate"])) applies = true;
        if (pokemon.hasItem("ironball") || pokemon.volatiles["ingrain"] || this.field.getPseudoWeather("gravity")) applies = false;
        if (pokemon.removeVolatile("fly") || pokemon.removeVolatile("bounce")) {
          applies = true;
          this.queue.cancelMove(pokemon);
          pokemon.removeVolatile("twoturnmove");
        }
        if (pokemon.volatiles["magnetrise"]) {
          applies = true;
          delete pokemon.volatiles["magnetrise"];
        }
        if (pokemon.volatiles["telekinesis"]) {
          applies = true;
          delete pokemon.volatiles["telekinesis"];
        }
        if (!applies) return false;
        this.add("-start", pokemon, "Smack Down");
      }

// cond:smackdown.onRestart
onRestart(pokemon) {
        if (pokemon.removeVolatile("fly") || pokemon.removeVolatile("bounce")) {
          this.queue.cancelMove(pokemon);
          pokemon.removeVolatile("twoturnmove");
          this.add("-start", pokemon, "Smack Down");
        }
      }

// cond:focusenergy.onStart
onStart(target, source, effect) {
        if (target.volatiles["dragoncheer"]) return false;
        if (effect?.id === "zpower") {
          this.add("-start", target, "move: Focus Energy", "[zeffect]");
        } else if (effect && ["costar", "imposter", "psychup", "transform"].includes(effect.id)) {
          this.add("-start", target, "move: Focus Energy", "[silent]");
        } else {
          this.add("-start", target, "move: Focus Energy");
        }
      }

// cond:focusenergy.onModifyCritRatio
onModifyCritRatio(critRatio) {
        return critRatio + 2;
      }

// cond:charge.onStart
onStart(pokemon, source, effect) {
        if (effect && ["Electromorphosis", "Wind Power"].includes(effect.name)) {
          this.add("-start", pokemon, "Charge", this.activeMove.name, "[from] ability: " + effect.name);
        } else {
          this.add("-start", pokemon, "Charge");
        }
      }

// cond:charge.onRestart
onRestart(pokemon, source, effect) {
        if (effect && ["Electromorphosis", "Wind Power"].includes(effect.name)) {
          this.add("-start", pokemon, "Charge", this.activeMove.name, "[from] ability: " + effect.name);
        } else {
          this.add("-start", pokemon, "Charge");
        }
      }

// cond:charge.onBasePower
onBasePower(basePower, attacker, defender, move) {
        if (move.type === "Electric") {
          this.debug("charge boost");
          return this.chainModify(2);
        }
      }

// cond:charge.onMoveAborted
onMoveAborted(pokemon, target, move) {
        if (move.type === "Electric" && move.id !== "charge") {
          pokemon.removeVolatile("charge");
        }
      }

// cond:charge.onAfterMove
onAfterMove(pokemon, target, move) {
        if (move.type === "Electric" && move.id !== "charge") {
          pokemon.removeVolatile("charge");
        }
      }

// cond:charge.onEnd
onEnd(pokemon) {
        this.add("-end", pokemon, "Charge", "[silent]");
      }

// cond:nightmare.onStart
onStart(pokemon) {
        if (pokemon.status !== "slp" && !pokemon.hasAbility("comatose")) {
          return false;
        }
        this.add("-start", pokemon, "Nightmare");
      }

// cond:nightmare.onResidual
onResidual(pokemon) {
        this.damage(pokemon.baseMaxhp / 4);
      }

// cond:electricterrain.durationCallback
durationCallback(source, effect) {
        if (source?.hasItem("terrainextender")) {
          return 8;
        }
        return 5;
      }

// cond:electricterrain.onSetStatus
onSetStatus(status, target, source, effect) {
        if (status.id === "slp" && target.isGrounded() && !target.isSemiInvulnerable()) {
          if (effect.id === "yawn" || effect.effectType === "Move" && !effect.secondaries) {
            this.add("-activate", target, "move: Electric Terrain");
          }
          return false;
        }
      }

// cond:electricterrain.onTryAddVolatile
onTryAddVolatile(status, target) {
        if (!target.isGrounded() || target.isSemiInvulnerable()) return;
        if (status.id === "yawn") {
          this.add("-activate", target, "move: Electric Terrain");
          return null;
        }
      }

// cond:electricterrain.onBasePower
onBasePower(basePower, attacker, defender, move) {
        if (move.type === "Electric" && attacker.isGrounded() && !attacker.isSemiInvulnerable()) {
          this.debug("electric terrain boost");
          return this.chainModify([5325, 4096]);
        }
      }

// cond:electricterrain.onFieldStart
onFieldStart(field, source, effect) {
        if (effect?.effectType === "Ability") {
          this.add("-fieldstart", "move: Electric Terrain", "[from] ability: " + effect.name, `[of] ${source}`);
        } else {
          this.add("-fieldstart", "move: Electric Terrain");
        }
      }

// cond:electricterrain.onFieldEnd
onFieldEnd() {
        this.add("-fieldend", "move: Electric Terrain");
      }
