// Activity 4 - explain() of the category + price-range query, with and without the compound index (hint)
const c = db.getSiblingDB("ecommerce").products;
const q = {category: "Laptops", price: {$gte: 50000, $lte: 80000}};
function summary(label, ex) {
  const s = ex.executionStats; let p = ex.queryPlanner.winningPlan; p = p.queryPlan || p; const st = [];
  while (p) { st.push(p.stage + (p.indexName ? "[" + p.indexName + "]" : "")); p = p.inputStage; }
  print(label.padEnd(34) + "plan=" + st.join(" > ").padEnd(42) + " nReturned=" + s.nReturned +
        " keysExamined=" + s.totalKeysExamined + " docsExamined=" + s.totalDocsExamined + " timeMs=" + s.executionTimeMillis);
}
print("query: " + JSON.stringify(q) + "  sort: {price: 1}\n");
summary("forced collection scan ($natural)", c.find(q).sort({price: 1}).hint({$natural: 1}).explain("executionStats"));
summary("planner choice (compound index)", c.find(q).sort({price: 1}).explain("executionStats"));
