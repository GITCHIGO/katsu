// Test-hulp: leest {sym, bars:[{t,o,h,l,c,s}], order:{...}} van stdin, speelt de order af, schrijft het resultaat.
const sim = require("./sim.js");
let buf = "";
process.stdin.on("data", (d) => (buf += d));
process.stdin.on("end", () => {
  const inp = JSON.parse(buf);
  const spec = Object.assign({}, sim.SPECS[inp.sym], inp.spec || {});
  const out = inp.orders.map((o) => {
    const order = Object.assign({ status: "pending" }, o);
    for (const b of inp.bars) {
      if (o.closeAt != null && b.t >= o.closeAt) order.closeNext = true;
      sim.step(order, b, spec);
      if (order.status === "closed" || order.status === "cancelled") break;
    }
    return order;
  });
  process.stdout.write(JSON.stringify(out));
});
