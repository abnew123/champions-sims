// ability aerilate.onModifyType (prio -1 / )
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

// ability aerilate.onBasePower (prio 23 / )
onBasePower(basePower, pokemon, target, move) {
      if (move.typeChangerBoosted === this.effect) return this.chainModify([4915, 4096]);
    }

// ability toughclaws.onBasePower (prio 21 / )
onBasePower(basePower, attacker, defender, move) {
      if (move.flags["contact"]) {
        return this.chainModify([5325, 4096]);
      }
    }

// ability adaptability.onModifySTAB (prio  / )
onModifySTAB(stab, source, target, move) {
      if (move.forceSTAB || source.hasType(move.type)) {
        if (stab === 2) {
          return 2.25;
        }
        return 2;
      }
    }

// ability pixilate.onModifyType (prio -1 / )
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

// ability pixilate.onBasePower (prio 23 / )
onBasePower(basePower, pokemon, target, move) {
      if (move.typeChangerBoosted === this.effect) return this.chainModify([4915, 4096]);
    }

// ability fairyaura.onAnyBasePower (prio 20 / )
onAnyBasePower(basePower, source, target, move) {
      if (target === source || move.category === "Status" || move.type !== "Fairy") return;
      if (!move.auraBooster?.hasAbility("Fairy Aura")) move.auraBooster = this.effectState.target;
      if (move.auraBooster !== this.effectState.target) return;
      return this.chainModify([move.hasAuraBreak ? 3072 : 5448, 4096]);
    }

// ability sandrush.onImmunity (prio  / )
onImmunity(type, pokemon) {
      if (type === "sandstorm") return false;
    }

// ability multiscale.onSourceModifyDamage (prio  / )
onSourceModifyDamage(damage, source, target, move) {
      if (target.hp >= target.maxhp) {
        this.debug("Multiscale weaken");
        return this.chainModify(0.5);
      }
    }

// ability liquidvoice.onModifyType (prio -1 / )
onModifyType(move, pokemon) {
      if (move.flags["sound"] && !pokemon.volatiles["dynamax"]) {
        move.type = "Water";
      }
    }

// ability sharpness.onBasePower (prio 19 / )
onBasePower(basePower, attacker, defender, move) {
      if (move.flags["slicing"]) {
        this.debug("Sharpness boost");
        return this.chainModify(1.5);
      }
    }

// ability ironfist.onBasePower (prio 23 / )
onBasePower(basePower, attacker, defender, move) {
      if (move.flags["punch"]) {
        this.debug("Iron Fist boost");
        return this.chainModify([4915, 4096]);
      }
    }

// ability sheerforce.onModifyMove (prio  / )
onModifyMove(move, pokemon) {
      if (move.secondaries && !move.hasSheerForceBoost) {
        delete move.secondaries;
        delete move.self;
        if (move.id === "clangoroussoulblaze") delete move.selfBoost;
        move.hasSheerForce = true;
      }
    }

// ability sheerforce.onBasePower (prio 21 / )
onBasePower(basePower, pokemon, target, move) {
      if (move.hasSheerForce || move.hasSheerForceBoost) return this.chainModify([5325, 4096]);
    }

// ability megalauncher.onBasePower (prio 19 / )
onBasePower(basePower, attacker, defender, move) {
      if (move.flags["pulse"]) {
        return this.chainModify(1.5);
      }
    }

// ability friendguard.onAnyModifyDamage (prio  / )
onAnyModifyDamage(damage, source, target, move) {
      if (target !== this.effectState.target && target.isAlly(this.effectState.target)) {
        this.debug("Friend Guard weaken");
        return this.chainModify(0.75);
      }
    }

// ability scrappy.onModifyMove (prio -5 / )
onModifyMove(move) {
      if (!move.ignoreImmunity) move.ignoreImmunity = {};
      if (move.ignoreImmunity !== true) {
        move.ignoreImmunity["Fighting"] = true;
        move.ignoreImmunity["Normal"] = true;
      }
    }

// ability hugepower.onModifyAtk (prio 5 / )
onModifyAtk(atk) {
      return this.chainModify(2);
    }

// ability infiltrator.onModifyMove (prio  / )
onModifyMove(move) {
      move.infiltrates = true;
    }

// ability technician.onBasePower (prio 30 / )
onBasePower(basePower, attacker, defender, move) {
      const basePowerAfterMultiplier = this.modify(basePower, this.event.modifier);
      this.debug(`Base Power: ${basePowerAfterMultiplier}`);
      if (basePowerAfterMultiplier <= 60) {
        this.debug("Technician boost");
        return this.chainModify(1.5);
      }
    }

// ability stancechange.onModifyMove (prio 1 / )
onModifyMove(move, attacker, defender) {
      if (attacker.species.baseSpecies !== "Aegislash" || attacker.transformed) return;
      if (move.category === "Status" && move.id !== "kingsshield") return;
      const targetForme = move.id === "kingsshield" ? "Aegislash" : "Aegislash-Blade";
      if (attacker.species.name !== targetForme) attacker.formeChange(targetForme);
    }

// ability compoundeyes.onSourceModifyAccuracy (prio -1 / )
onSourceModifyAccuracy(accuracy) {
      if (typeof accuracy !== "number") return;
      this.debug("compoundeyes - enhancing accuracy");
      return this.chainModify([5325, 4096]);
    }

// ability blaze.onModifyAtk (prio 5 / )
onModifyAtk(atk, attacker, defender, move) {
      if (move.type === "Fire" && attacker.hp <= attacker.maxhp / 3) {
        this.debug("Blaze boost");
        return this.chainModify(1.5);
      }
    }

// ability blaze.onModifySpA (prio 5 / )
onModifySpA(atk, attacker, defender, move) {
      if (move.type === "Fire" && attacker.hp <= attacker.maxhp / 3) {
        this.debug("Blaze boost");
        return this.chainModify(1.5);
      }
    }

// ability thickfat.onSourceModifyAtk (prio 6 / )
onSourceModifyAtk(atk, attacker, defender, move) {
      if (move.type === "Ice" || move.type === "Fire") {
        this.debug("Thick Fat weaken");
        return this.chainModify(0.5);
      }
    }

// ability thickfat.onSourceModifySpA (prio 5 / )
onSourceModifySpA(atk, attacker, defender, move) {
      if (move.type === "Ice" || move.type === "Fire") {
        this.debug("Thick Fat weaken");
        return this.chainModify(0.5);
      }
    }

// ability moldbreaker.onModifyMove (prio  / )
onModifyMove(move) {
      move.ignoreAbility = true;
    }

// ability sandforce.onBasePower (prio 21 / )
onBasePower(basePower, attacker, defender, move) {
      if (this.field.isWeather("sandstorm")) {
        if (move.type === "Rock" || move.type === "Ground" || move.type === "Steel") {
          this.debug("Sand Force boost");
          return this.chainModify([5325, 4096]);
        }
      }
    }

// ability sandforce.onImmunity (prio  / )
onImmunity(type, pokemon) {
      if (type === "sandstorm") return false;
    }

// ability firemane.onModifyAtk (prio 5 / )
onModifyAtk(atk, attacker, defender, move) {
      if (move.type === "Fire") {
        this.debug("Fire Mane boost");
        return this.chainModify(1.5);
      }
    }

// ability firemane.onModifySpA (prio 5 / )
onModifySpA(atk, attacker, defender, move) {
      if (move.type === "Fire") {
        this.debug("Fire Mane boost");
        return this.chainModify(1.5);
      }
    }

// ability oblivious.onImmunity (prio  / )
onImmunity(type, pokemon) {
      if (type === "attract") return false;
    }

// ability megasol.onWeatherModifyDamage (prio 1 / )
onWeatherModifyDamage(damage, attacker, defender, move) {
      this.dex.conditions.getByID("sunnyday").onWeatherModifyDamage.call(this, damage, attacker, defender, move);
      return damage;
    }

// ability punkrock.onBasePower (prio 7 / )
onBasePower(basePower, attacker, defender, move) {
      if (move.flags["sound"]) {
        this.debug("Punk Rock boost");
        return this.chainModify([5325, 4096]);
      }
    }

// ability punkrock.onSourceModifyDamage (prio  / )
onSourceModifyDamage(damage, source, target, move) {
      if (move.flags["sound"]) {
        this.debug("Punk Rock weaken");
        return this.chainModify(0.5);
      }
    }

// ability waterbubble.onSourceModifyAtk (prio 5 / )
onSourceModifyAtk(atk, attacker, defender, move) {
      if (move.type === "Fire") {
        return this.chainModify(0.5);
      }
    }

// ability waterbubble.onSourceModifySpA (prio 5 / )
onSourceModifySpA(atk, attacker, defender, move) {
      if (move.type === "Fire") {
        return this.chainModify(0.5);
      }
    }

// ability waterbubble.onModifyAtk (prio  / )
onModifyAtk(atk, attacker, defender, move) {
      if (move.type === "Water") {
        return this.chainModify(2);
      }
    }

// ability waterbubble.onModifySpA (prio  / )
onModifySpA(atk, attacker, defender, move) {
      if (move.type === "Water") {
        return this.chainModify(2);
      }
    }

// ability sniper.onModifyDamage (prio  / )
onModifyDamage(damage, source, target, move) {
      if (target.getMoveHitData(move).crit) {
        this.debug("Sniper boost");
        return this.chainModify(1.5);
      }
    }

// ability torrent.onModifyAtk (prio 5 / )
onModifyAtk(atk, attacker, defender, move) {
      if (move.type === "Water" && attacker.hp <= attacker.maxhp / 3) {
        this.debug("Torrent boost");
        return this.chainModify(1.5);
      }
    }

// ability torrent.onModifySpA (prio 5 / )
onModifySpA(atk, attacker, defender, move) {
      if (move.type === "Water" && attacker.hp <= attacker.maxhp / 3) {
        this.debug("Torrent boost");
        return this.chainModify(1.5);
      }
    }

// ability overgrow.onModifyAtk (prio 5 / )
onModifyAtk(atk, attacker, defender, move) {
      if (move.type === "Grass" && attacker.hp <= attacker.maxhp / 3) {
        this.debug("Overgrow boost");
        return this.chainModify(1.5);
      }
    }

// ability overgrow.onModifySpA (prio 5 / )
onModifySpA(atk, attacker, defender, move) {
      if (move.type === "Grass" && attacker.hp <= attacker.maxhp / 3) {
        this.debug("Overgrow boost");
        return this.chainModify(1.5);
      }
    }

// ability disguise.onCriticalHit (prio  / )
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

// ability disguise.onEffectiveness (prio  / )
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

// ability filter.onSourceModifyDamage (prio  / )
onSourceModifyDamage(damage, source, target, move) {
      if (target.getMoveHitData(move).typeMod > 0) {
        this.debug("Filter neutralize");
        return this.chainModify(0.75);
      }
    }

// ability stalwart.onModifyMove (prio 1 / )
onModifyMove(move) {
      move.tracksTarget = move.target !== "scripted";
    }

// ability solidrock.onSourceModifyDamage (prio  / )
onSourceModifyDamage(damage, source, target, move) {
      if (target.getMoveHitData(move).typeMod > 0) {
        this.debug("Solid Rock neutralize");
        return this.chainModify(0.75);
      }
    }

// ability solarpower.onModifySpA (prio 5 / )
onModifySpA(spa, pokemon) {
      if (["sunnyday", "desolateland"].includes(pokemon.effectiveWeather())) {
        return this.chainModify(1.5);
      }
    }

// ability keeneye.onModifyMove (prio  / )
onModifyMove(move) {
      move.ignoreEvasion = true;
    }

// ability icebody.onImmunity (prio  / )
onImmunity(type, pokemon) {
      if (type === "hail") return false;
    }

// ability superluck.onModifyCritRatio (prio  / )
onModifyCritRatio(critRatio) {
      return critRatio + 1;
    }

// ability sandveil.onImmunity (prio  / )
onImmunity(type, pokemon) {
      if (type === "sandstorm") return false;
    }

// ability guts.onModifyAtk (prio 5 / )
onModifyAtk(atk, pokemon) {
      if (pokemon.status) {
        return this.chainModify(1.5);
      }
    }

// ability supremeoverlord.onBasePower (prio 21 / )
onBasePower(basePower, attacker, defender, move) {
      if (this.effectState.fallen) {
        const powMod = [4096, 4506, 4915, 5325, 5734, 6144];
        this.debug(`Supreme Overlord boost: ${powMod[this.effectState.fallen]}/4096`);
        return this.chainModify([powMod[this.effectState.fallen], 4096]);
      }
    }

// ability furcoat.onModifyDef (prio 6 / )
onModifyDef(def) {
      return this.chainModify(2);
    }

// ability heatproof.onSourceModifyAtk (prio 6 / )
onSourceModifyAtk(atk, attacker, defender, move) {
      if (move.type === "Fire") {
        this.debug("Heatproof Atk weaken");
        return this.chainModify(0.5);
      }
    }

// ability heatproof.onSourceModifySpA (prio 5 / )
onSourceModifySpA(atk, attacker, defender, move) {
      if (move.type === "Fire") {
        this.debug("Heatproof SpA weaken");
        return this.chainModify(0.5);
      }
    }

// ability magmaarmor.onImmunity (prio  / )
onImmunity(type, pokemon) {
      if (type === "frz") return false;
    }

// ability marvelscale.onModifyDef (prio 6 / )
onModifyDef(def, pokemon) {
      if (pokemon.status) {
        return this.chainModify(1.5);
      }
    }

// ability swarm.onModifyAtk (prio 5 / )
onModifyAtk(atk, attacker, defender, move) {
      if (move.type === "Bug" && attacker.hp <= attacker.maxhp / 3) {
        this.debug("Swarm boost");
        return this.chainModify(1.5);
      }
    }

// ability swarm.onModifySpA (prio 5 / )
onModifySpA(atk, attacker, defender, move) {
      if (move.type === "Bug" && attacker.hp <= attacker.maxhp / 3) {
        this.debug("Swarm boost");
        return this.chainModify(1.5);
      }
    }

// ability reckless.onBasePower (prio 23 / )
onBasePower(basePower, attacker, defender, move) {
      if (move.recoil || move.hasCrashDamage) {
        this.debug("Reckless boost");
        return this.chainModify([4915, 4096]);
      }
    }

// ability snowcloak.onImmunity (prio  / )
onImmunity(type, pokemon) {
      if (type === "hail") return false;
    }

// ability overcoat.onImmunity (prio  / )
onImmunity(type, pokemon) {
      if (type === "sandstorm" || type === "hail" || type === "powder") return false;
    }

// ability merciless.onModifyCritRatio (prio  / )
onModifyCritRatio(critRatio, source, target) {
      if (target && ["psn", "tox"].includes(target.status)) return 5;
    }

// ability rivalry.onBasePower (prio 24 / )
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

// ability plus.onModifySpA (prio 5 / )
onModifySpA(spa, pokemon) {
      for (const allyActive of pokemon.allies()) {
        if (allyActive.hasAbility(["minus", "plus"])) {
          return this.chainModify(1.5);
        }
      }
    }

// ability illuminate.onModifyMove (prio  / )
onModifyMove(move) {
      move.ignoreEvasion = true;
    }

// ability analytic.onBasePower (prio 21 / )
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

// ability battlebond.onModifyMove (prio -1 / )
onModifyMove(move, attacker) {
      if (move.id === "watershuriken" && attacker.species.name === "Greninja-Ash" && !attacker.transformed) {
        move.multihit = 3;
      }
    }

// ability minus.onModifySpA (prio 5 / )
onModifySpA(spa, pokemon) {
      for (const allyActive of pokemon.allies()) {
        if (allyActive.hasAbility(["minus", "plus"])) {
          return this.chainModify(1.5);
        }
      }
    }

// ability dragonize.onModifyType (prio -1 / )
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

// ability dragonize.onBasePower (prio 23 / )
onBasePower(basePower, pokemon, target, move) {
      if (move.typeChangerBoosted === this.effect) return this.chainModify([4915, 4096]);
    }

// ability steelyspirit.onAllyBasePower (prio 22 / )
onAllyBasePower(basePower, attacker, defender, move) {
      if (move.type === "Steel") {
        this.debug("Steely Spirit boost");
        return this.chainModify(1.5);
      }
    }

// ability skilllink.onModifyMove (prio  / )
onModifyMove(move) {
      if (move.multihit && Array.isArray(move.multihit) && move.multihit.length) {
        move.multihit = move.multihit[1];
      }
      if (move.multiaccuracy) {
        delete move.multiaccuracy;
      }
    }

// item lifeorb.onModifyDamage (prio  / )
onModifyDamage(damage, source, target, move) {
      return this.chainModify([5324, 4096]);
    }

// item miracleseed.onBasePower (prio 15 / )
onBasePower(basePower, user, target, move) {
      if (move.type === "Grass") {
        return this.chainModify([4915, 4096]);
      }
    }

// item choicescarf.onModifyMove (prio  / )
onModifyMove(move, pokemon) {
      pokemon.addVolatile("choicelock");
    }

// item chopleberry.onSourceModifyDamage (prio  / )
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

// item fairyfeather.onBasePower (prio 15 / )
onBasePower(basePower, user, target, move) {
      if (move && move.type === "Fairy") {
        return this.chainModify([4915, 4096]);
      }
    }

// item colburberry.onSourceModifyDamage (prio  / )
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

// item mysticwater.onBasePower (prio 15 / )
onBasePower(basePower, user, target, move) {
      if (move.type === "Water") {
        return this.chainModify([4915, 4096]);
      }
    }

// item blackglasses.onBasePower (prio 15 / )
onBasePower(basePower, user, target, move) {
      if (move && move.type === "Dark") {
        return this.chainModify([4915, 4096]);
      }
    }

// item occaberry.onSourceModifyDamage (prio  / )
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

// item charcoal.onBasePower (prio 15 / )
onBasePower(basePower, user, target, move) {
      if (move && move.type === "Fire") {
        return this.chainModify([4915, 4096]);
      }
    }

// item passhoberry.onSourceModifyDamage (prio  / )
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

// item widelens.onSourceModifyAccuracy (prio -2 / )
onSourceModifyAccuracy(accuracy) {
      if (typeof accuracy === "number") {
        return this.chainModify([4505, 4096]);
      }
    }

// item cobaberry.onSourceModifyDamage (prio  / )
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

// item kasibberry.onSourceModifyDamage (prio  / )
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

// item sharpbeak.onBasePower (prio 15 / )
onBasePower(basePower, user, target, move) {
      if (move && move.type === "Flying") {
        return this.chainModify([4915, 4096]);
      }
    }

// item twistedspoon.onBasePower (prio 15 / )
onBasePower(basePower, user, target, move) {
      if (move.type === "Psychic") {
        return this.chainModify([4915, 4096]);
      }
    }

// item expertbelt.onModifyDamage (prio  / )
onModifyDamage(damage, source, target, move) {
      if (move && target.getMoveHitData(move).typeMod > 0) {
        return this.chainModify([4915, 4096]);
      }
    }

// item nevermeltice.onBasePower (prio 15 / )
onBasePower(basePower, user, target, move) {
      if (move.type === "Ice") {
        return this.chainModify([4915, 4096]);
      }
    }

// item roseliberry.onSourceModifyDamage (prio  / )
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

// item habanberry.onSourceModifyDamage (prio  / )
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

// item leek.onModifyCritRatio (prio  / )
onModifyCritRatio(critRatio, user) {
      if (["farfetchd", "sirfetchd"].includes(this.toID(user.baseSpecies.baseSpecies))) {
        return critRatio + 2;
      }
    }

// item scopelens.onModifyCritRatio (prio  / )
onModifyCritRatio(critRatio) {
      return critRatio + 1;
    }

// item magnet.onBasePower (prio 15 / )
onBasePower(basePower, user, target, move) {
      if (move.type === "Electric") {
        return this.chainModify([4915, 4096]);
      }
    }

// item blackbelt.onBasePower (prio 15 / )
onBasePower(basePower, user, target, move) {
      if (move && move.type === "Fighting") {
        return this.chainModify([4915, 4096]);
      }
    }

// item kebiaberry.onSourceModifyDamage (prio  / )
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

// item dragonfang.onBasePower (prio 15 / )
onBasePower(basePower, user, target, move) {
      if (move && move.type === "Dragon") {
        return this.chainModify([4915, 4096]);
      }
    }

// item spelltag.onBasePower (prio 15 / )
onBasePower(basePower, user, target, move) {
      if (move.type === "Ghost") {
        return this.chainModify([4915, 4096]);
      }
    }

// item silkscarf.onBasePower (prio 15 / )
onBasePower(basePower, user, target, move) {
      if (move.type === "Normal") {
        return this.chainModify([4915, 4096]);
      }
    }

// item tangaberry.onSourceModifyDamage (prio  / )
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

// item kingsrock.onModifyMove (prio -1 / )
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

// item babiriberry.onSourceModifyDamage (prio  / )
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

// item chartiberry.onSourceModifyDamage (prio  / )
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

// item softsand.onBasePower (prio 15 / )
onBasePower(basePower, user, target, move) {
      if (move.type === "Ground") {
        return this.chainModify([4915, 4096]);
      }
    }

// move weatherball.onModifyType (prio  / )
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

// move weatherball.onModifyMove (prio  / )
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

// movecond helpinghand.onBasePower (prio 10 / )
onBasePower(basePower) {
        this.debug("Boosting from Helping Hand: " + this.effectState.multiplier);
        return this.chainModify(this.effectState.multiplier);
      }

// move expandingforce.onBasePower (prio  / )
onBasePower(basePower, source) {
      if (this.field.isTerrain("psychicterrain") && source.isGrounded()) {
        this.debug("terrain buff");
        return this.chainModify(1.5);
      }
    }

// move expandingforce.onModifyMove (prio  / )
onModifyMove(move, source, target) {
      if (this.field.isTerrain("psychicterrain") && source.isGrounded()) {
        move.target = "allAdjacentFoes";
      }
    }

// movecond throatchop.onModifyMove (prio  / )
onModifyMove(move, pokemon, target) {
        if (!move.isZOrMaxPowered && move.flags["sound"]) {
          this.add("cant", pokemon, "move: Throat Chop");
          return false;
        }
      }

// move lowkick.basePowerCallback (prio  / )
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

// move lastrespects.basePowerCallback (prio  / )
basePowerCallback(pokemon, target, move) {
      return 50 + 50 * pokemon.side.totalFainted;
    }

// move hurricane.onModifyMove (prio  / )
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

// move knockoff.onBasePower (prio  / )
onBasePower(basePower, source, target, move) {
      const item = target.getItem();
      if (!this.singleEvent("TakeItem", item, target.itemState, target, target, move, item)) return;
      if (item.id) {
        return this.chainModify(1.5);
      }
    }

// move stompingtantrum.basePowerCallback (prio  / )
basePowerCallback(pokemon, target, move) {
      if (pokemon.moveLastTurnResult === false) {
        this.debug("doubling Stomping Tantrum BP due to previous move failure");
        return move.basePower * 2;
      }
      return move.basePower;
    }

// move blizzard.onModifyMove (prio  / )
onModifyMove(move) {
      if (this.field.isWeather(["hail", "snowscape"])) move.accuracy = true;
    }

// movecond auroraveil.onAnyModifyDamage (prio  / )
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

// movecond lightscreen.onAnyModifyDamage (prio  / )
onAnyModifyDamage(damage, source, target, move) {
        if (target !== source && this.effectState.target.hasAlly(target) && this.getCategory(move) === "Special") {
          if (!target.getMoveHitData(move).crit && !move.infiltrates) {
            this.debug("Light Screen weaken");
            if (this.activePerHalf > 1) return this.chainModify([2732, 4096]);
            return this.chainModify(0.5);
          }
        }
      }

// move solarbeam.onBasePower (prio  / )
onBasePower(basePower, pokemon, target) {
      const weakWeathers = ["raindance", "primordialsea", "sandstorm", "hail", "snowscape"];
      if (weakWeathers.includes(pokemon.effectiveWeather())) {
        this.debug("weakened by weather");
        return this.chainModify(0.5);
      }
    }

// movecond reflect.onAnyModifyDamage (prio  / )
onAnyModifyDamage(damage, source, target, move) {
        if (target !== source && this.effectState.target.hasAlly(target) && this.getCategory(move) === "Physical") {
          if (!target.getMoveHitData(move).crit && !move.infiltrates) {
            this.debug("Reflect weaken");
            if (this.activePerHalf > 1) return this.chainModify([2732, 4096]);
            return this.chainModify(0.5);
          }
        }
      }

// move eruption.basePowerCallback (prio  / )
basePowerCallback(pokemon, target, move) {
      const bp = move.basePower * pokemon.hp / pokemon.maxhp;
      this.debug(`BP: ${bp}`);
      return bp;
    }

// movecond glaiverush.onSourceModifyDamage (prio  / )
onSourceModifyDamage() {
        return this.chainModify(2);
      }

// move terrainpulse.onModifyType (prio  / )
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

// move terrainpulse.onModifyMove (prio  / )
onModifyMove(move, pokemon) {
      if (this.field.terrain && pokemon.isGrounded()) {
        move.basePower *= 2;
        this.debug("BP doubled in Terrain");
      }
    }

// move waterspout.basePowerCallback (prio  / )
basePowerCallback(pokemon, target, move) {
      const bp = move.basePower * pokemon.hp / pokemon.maxhp;
      this.debug(`BP: ${bp}`);
      return bp;
    }

// move freezedry.onEffectiveness (prio  / )
onEffectiveness(typeMod, target, type) {
      if (type === "Water") return 1;
    }

// move powertrip.basePowerCallback (prio  / )
basePowerCallback(pokemon, target, move) {
      const bp = move.basePower + 20 * pokemon.positiveBoosts();
      this.debug(`BP: ${bp}`);
      return bp;
    }

// move tripleaxel.basePowerCallback (prio  / )
basePowerCallback(pokemon, target, move) {
      return 20 * move.hit;
    }

// move ragefist.basePowerCallback (prio  / )
basePowerCallback(pokemon) {
      return Math.min(350, 50 + 50 * pokemon.timesAttacked);
    }

// move grassknot.basePowerCallback (prio  / )
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

// move risingvoltage.basePowerCallback (prio  / )
basePowerCallback(source, target, move) {
      if (this.field.isTerrain("electricterrain") && target.isGrounded()) {
        if (!source.isAlly(target)) this.hint(`${move.name}'s BP doubled on grounded target.`);
        return move.basePower * 2;
      }
      return move.basePower;
    }

// move heavyslam.basePowerCallback (prio  / )
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

// move acrobatics.basePowerCallback (prio  / )
basePowerCallback(pokemon, target, move) {
      if (!pokemon.item) {
        this.debug("BP doubled for no item");
        return move.basePower * 2;
      }
      return move.basePower;
    }

// move thunder.onModifyMove (prio  / )
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

// move assurance.basePowerCallback (prio  / )
basePowerCallback(pokemon, target, move) {
      if (target.hurtThisTurn) {
        this.debug("BP doubled on damaged target");
        return move.basePower * 2;
      }
      return move.basePower;
    }

// move curse.onModifyMove (prio  / )
onModifyMove(move, source, target) {
      if (!source.hasType("Ghost")) {
        move.target = "self";
      } else if (source !== target && source.isAlly(target)) {
        move.target = "randomNormal";
      }
    }

// move beatup.basePowerCallback (prio  / )
basePowerCallback(pokemon, target, move) {
      const setSpecies = this.dex.species.get(move.allies.shift().set.species);
      const bp = 5 + Math.floor(setSpecies.baseStats.atk / 10);
      this.debug(`BP for ${setSpecies.name} hit: ${bp}`);
      return bp;
    }

// move beatup.onModifyMove (prio  / )
onModifyMove(move, pokemon) {
      move.allies = pokemon.side.pokemon.filter((ally) => ally === pokemon || !ally.fainted && !ally.status);
      move.multihit = move.allies.length;
    }

// move barbbarrage.onBasePower (prio  / )
onBasePower(basePower, pokemon, target) {
      if (target.status === "psn" || target.status === "tox") {
        return this.chainModify(2);
      }
    }

// movecond mistyterrain.onBasePower (prio 6 / )
onBasePower(basePower, attacker, defender, move) {
        if (move.type === "Dragon" && defender.isGrounded() && !defender.isSemiInvulnerable()) {
          this.debug("misty terrain weaken");
          return this.chainModify(0.5);
        }
      }

// move round.basePowerCallback (prio  / )
basePowerCallback(target, source, move) {
      if (move.sourceEffect === "round") {
        this.debug("BP doubled");
        return move.basePower * 2;
      }
      return move.basePower;
    }

// move ficklebeam.onBasePower (prio  / )
onBasePower(basePower, pokemon) {
      if (this.randomChance(3, 10)) {
        this.attrLastMove("[anim] Fickle Beam All Out");
        this.add("-activate", pokemon, "move: Fickle Beam");
        return this.chainModify(2);
      }
    }

// movecond psychicterrain.onBasePower (prio 6 / )
onBasePower(basePower, attacker, defender, move) {
        if (move.type === "Psychic" && attacker.isGrounded() && !attacker.isSemiInvulnerable()) {
          this.debug("psychic terrain boost");
          return this.chainModify([5325, 4096]);
        }
      }

// movecond grassyterrain.onBasePower (prio 6 / )
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

// move ragingbull.onModifyType (prio  / )
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

// move facade.onBasePower (prio  / )
onBasePower(basePower, pokemon) {
      if (pokemon.status && pokemon.status !== "slp") {
        return this.chainModify(2);
      }
    }

// move payback.basePowerCallback (prio  / )
basePowerCallback(pokemon, target, move) {
      if (target.newlySwitched || this.queue.willMove(target)) {
        this.debug("Payback NOT boosted");
        return move.basePower;
      }
      this.debug("Payback damage boost");
      return move.basePower * 2;
    }

// movecond gravity.onModifyMove (prio  / )
onModifyMove(move, pokemon, target) {
        if (move.flags["gravity"] && !move.isZ) {
          this.add("cant", pokemon, "move: Gravity", move);
          return false;
        }
      }

// move hardpress.basePowerCallback (prio  / )
basePowerCallback(pokemon, target) {
      const hp = target.hp;
      const maxHP = target.maxhp;
      const bp = Math.floor(Math.floor((100 * (100 * Math.floor(hp * 4096 / maxHP)) + 2048 - 1) / 4096) / 100) || 1;
      this.debug(`BP for ${hp}/${maxHP} HP: ${bp}`);
      return bp;
    }

// cond sunnyday.onWeatherModifyDamage (prio  / )
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

// cond sunnyday.onImmunity (prio  / )
onImmunity(type, pokemon) {
      if (pokemon.effectiveWeather() !== "sunnyday") return;
      if (type === "frz") return false;
    }

// cond raindance.onWeatherModifyDamage (prio  / )
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

// cond sandstorm.onModifySpD (prio 10 / )
onModifySpD(spd, pokemon) {
      if (pokemon.hasType("Rock") && pokemon.effectiveWeather() === "sandstorm") {
        return this.modify(spd, 1.5);
      }
    }

// cond snowscape.onModifyDef (prio 10 / )
onModifyDef(def, pokemon) {
      if (pokemon.hasType("Ice") && pokemon.effectiveWeather() === "snowscape") {
        return this.modify(def, 1.5);
      }
    }

// cond psychicterrain.onBasePower (prio 6 / )
onBasePower(basePower, attacker, defender, move) {
        if (move.type === "Psychic" && attacker.isGrounded() && !attacker.isSemiInvulnerable()) {
          this.debug("psychic terrain boost");
          return this.chainModify([5325, 4096]);
        }
      }

// cond grassyterrain.onBasePower (prio 6 / )
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

// cond electricterrain.onBasePower (prio 6 / )
onBasePower(basePower, attacker, defender, move) {
        if (move.type === "Electric" && attacker.isGrounded() && !attacker.isSemiInvulnerable()) {
          this.debug("electric terrain boost");
          return this.chainModify([5325, 4096]);
        }
      }

// cond mistyterrain.onBasePower (prio 6 / )
onBasePower(basePower, attacker, defender, move) {
        if (move.type === "Dragon" && defender.isGrounded() && !defender.isSemiInvulnerable()) {
          this.debug("misty terrain weaken");
          return this.chainModify(0.5);
        }
      }

// cond reflect.onAnyModifyDamage (prio  / )
onAnyModifyDamage(damage, source, target, move) {
        if (target !== source && this.effectState.target.hasAlly(target) && this.getCategory(move) === "Physical") {
          if (!target.getMoveHitData(move).crit && !move.infiltrates) {
            this.debug("Reflect weaken");
            if (this.activePerHalf > 1) return this.chainModify([2732, 4096]);
            return this.chainModify(0.5);
          }
        }
      }

// cond lightscreen.onAnyModifyDamage (prio  / )
onAnyModifyDamage(damage, source, target, move) {
        if (target !== source && this.effectState.target.hasAlly(target) && this.getCategory(move) === "Special") {
          if (!target.getMoveHitData(move).crit && !move.infiltrates) {
            this.debug("Light Screen weaken");
            if (this.activePerHalf > 1) return this.chainModify([2732, 4096]);
            return this.chainModify(0.5);
          }
        }
      }

// cond auroraveil.onAnyModifyDamage (prio  / )
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

// cond helpinghand.onBasePower (prio 10 / )
onBasePower(basePower) {
        this.debug("Boosting from Helping Hand: " + this.effectState.multiplier);
        return this.chainModify(this.effectState.multiplier);
      }

// cond frz.onModifyMove (prio  / )
onModifyMove(move, pokemon) {
      if (move.flags["defrost"]) {
        this.add("-curestatus", pokemon, "frz", `[from] move: ${move}`);
        pokemon.clearStatus();
      }
    }

