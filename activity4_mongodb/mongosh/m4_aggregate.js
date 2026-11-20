// Activity 4 - aggregation pipeline: active products, average price and stock per category
const c = db.getSiblingDB("ecommerce").products;
print("category".padEnd(17) + "products".padStart(9) + "avg_price".padStart(12) + "units".padStart(11));
c.aggregate([{$match: {status: "active"}},
             {$group: {_id: "$category", n: {$sum: 1}, avg: {$avg: "$price"}, units: {$sum: "$inventory.stock"}}},
             {$sort: {n: -1}}]).forEach(r =>
  print(r._id.padEnd(17) + String(r.n).padStart(9) + r.avg.toFixed(0).padStart(12) + String(r.units).padStart(11)));
