/*
 * KATSU Replay — uitvoering per M1-candle (spiegel van katsu/execution.py; docs/replay_spec.md).
 * Prijzen in de data = BID; ASK = BID + spread. Werkt in de browser (window.KatsuSim) en in node (module.exports).
 */
(function (root) {
  "use strict";

  var SPECS = {
    EURUSD: { point: 0.00001, tick: 0.00001, minSpread: 0.00001, slip: 0.00003, comm: 0.00008, rolloverMin: 0.00005, pip: 0.0001 },
    XAUUSD: { point: 0.01, tick: 0.01, minSpread: 0.10, slip: 0.25, comm: 0.08, rolloverMin: 0.50, pip: 0.1 },
  };
  var ROLL_START = 23 * 60 + 55, ROLL_END = 90;

  function spread(bar, spec) {
    var sp = Math.max(bar.s * spec.point, spec.minSpread);
    var m = ((bar.t % 1440) + 1440) % 1440;          // bar.t = servertijd in minuten
    if (spec.rolloverMin > 0 && (m >= ROLL_START || m < ROLL_END)) sp = Math.max(2 * sp, spec.rolloverMin);
    return sp;
  }

  function roundTick(x, tick) { return Math.round(Math.round(x / tick) * tick * 1e10) / 1e10; }

  /* order: {dir: 1|-1, type: "market"|"limit"|"stop", entry, sl, tp, status: "pending"} — wordt ter plaatse bijgewerkt.
     Geeft een lijst gebeurtenissen terug ("gevuld", "gesloten"). */
  function step(order, bar, spec) {
    var ev = [];
    var long = order.dir > 0, sp = spread(bar, spec), slip = spec.slip;
    var fillBar = false, tpAllowed = true;
    if (order.status === "pending") {
      var askO = bar.o + sp, askL = bar.l + sp, askH = bar.h + sp, fill = null;
      if (order.cancelAt != null && ((long && bar.h >= order.cancelAt) || (!long && askL <= order.cancelAt))) {
        order.status = "cancelled"; order.exitT = bar.t; ev.push("geannuleerd"); return ev;
      }
      if (order.type === "market") {
        fill = long ? askO + slip : bar.o - slip;
      } else if (order.type === "limit") {
        if (long && askL <= order.entry) fill = Math.min(order.entry, askO);
        if (!long && bar.h >= order.entry) fill = Math.max(order.entry, bar.o);
        tpAllowed = false;
      } else if (order.type === "stop") {
        if (long && askH >= order.entry) fill = Math.max(order.entry, askO) + slip;
        if (!long && bar.l <= order.entry) fill = Math.min(order.entry, bar.o) - slip;
        tpAllowed = false;
      }
      if (fill === null) return ev;
      order.status = "open"; order.fill = fill; order.fillT = bar.t;
      order.risk = Math.abs(fill - order.sl);
      fillBar = true; ev.push("gevuld");
      if (order.type === "market") tpAllowed = true;
    }
    if (order.status !== "open") return ev;
    if (order.closeNext && !fillBar) {                 // manueel sluiten: op de open van deze candle
      var px = long ? bar.o - slip : bar.o + sp + slip;
      return finish(order, px, bar.t, "MANUEEL", spec, ev);
    }
    var advO, adv, fav;
    if (long) { advO = bar.o; adv = bar.l; fav = bar.h; } else { advO = bar.o + sp; adv = bar.h + sp; fav = bar.l + sp; }
    var s = long ? 1 : -1;
    var slHit = s * (adv - order.sl) <= 0;
    var tpHit = order.tp != null && s * (fav - order.tp) >= 0 && (!fillBar || tpAllowed);
    if (slHit) {
      var gap = !fillBar && s * (advO - order.sl) <= 0;
      return finish(order, (gap ? advO : order.sl) - s * slip, bar.t, "SL", spec, ev);
    }
    if (tpHit) return finish(order, order.tp, bar.t, "TP", spec, ev);
    return ev;
  }

  function finish(order, px, t, reason, spec, ev) {
    order.status = "closed"; order.exitPx = px; order.exitT = t; order.reason = reason;
    var risk = Math.abs(order.fill - order.slAtFill);
    if (!(risk > 0)) risk = order.risk;
    order.rGross = order.dir * (px - order.fill) / risk;
    order.rNet = order.rGross - spec.comm / risk;
    ev.push("gesloten");
    return ev;
  }

  /* Bij het vullen wordt de SL van dat moment vastgelegd: R blijft gemeten t.o.v. het oorspronkelijke risico,
     ook als de SL later verschoven wordt (bv. naar break-even). */
  function stepWithRisk(order, bar, spec) {
    var wasPending = order.status === "pending";
    if (wasPending) order.slAtFill = order.sl;
    return step(order, bar, spec);
  }

  var api = { SPECS: SPECS, spread: spread, step: stepWithRisk, roundTick: roundTick };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.KatsuSim = api;
})(typeof window !== "undefined" ? window : this);
