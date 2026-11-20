// Activity 4 - collection overview from the MongoDB shell
const c = db.getSiblingDB("ecommerce").products;
print("MongoDB server " + db.version() + "   collection ecommerce.products   documents: " + c.countDocuments({}));
print("\n--- one Laptop document (nested specs) ---");
print(JSON.stringify(c.findOne({category: "Laptops"}, {_id: 0, sku: 1, name: 1, brand: 1, price: 1, specs: 1, ratings: 1, inventory: 1})));
print("\n--- one Book document (completely different specs) ---");
print(JSON.stringify(c.findOne({category: "Books"}, {_id: 0, sku: 1, name: 1, price: 1, specs: 1})));
print("\n--- one Apparel document (embedded variants array, first 3 shown) ---");
print(JSON.stringify(c.findOne({category: "Apparel"}, {_id: 0, sku: 1, name: 1, price: 1, variants: {$slice: 3}, "inventory.stock": 1})));
print("\n--- indexes ---");
c.getIndexes().forEach(i => print(i.name.padEnd(22) + JSON.stringify(i.key) + (i.unique ? "  unique" : "") +
  (i.partialFilterExpression ? "  partial " + JSON.stringify(i.partialFilterExpression) : "")));
